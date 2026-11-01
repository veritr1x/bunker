"""Validate explicit Android z_stream ABI with NDK callers and ARM64-QEMU traces."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib
import zipfile
from prepare_zlib import prepare, SOURCES
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'whole'))
from test_fastaes import build_reference
from elftools.elf.elffile import ELFFile
HERE = Path(__file__).resolve().parent


def generate(out, apk=None):
    data = bytes(range(256)) * 3 + b'Bunker static Windows zlib\0' * 13
    cases = []
    arrays = {}

    def add(name, content, bits, inchunk=7, outchunk=13, options=0, capacity=4096, flush=0):
        arrays[name] = content
        cases.append((name, bits, inchunk, outchunk, options, capacity, flush))

    for bits in (-15, 15, 31):
        compressor = zlib.compressobj(wbits=bits)
        compressed = compressor.compress(data) + compressor.flush()
        for inchunk, outchunk in ((1, 1), (7, 13), (4096, 4096)):
            for options in (0, 1, 8, 32, 33):
                add(f'valid_{bits}_{inchunk}_{options}', compressed, bits, inchunk, outchunk, options)
        add(f'truncated_{bits}', compressed[:-5], bits)
        corrupt = bytearray(compressed);corrupt[0] ^= 0xff
        add(f'corrupt_{bits}', bytes(corrupt), bits)
        add(f'small_output_{bits}', compressed, bits, capacity=23)
        add(f'finish_{bits}', compressed, bits, flush=4)
        if bits == 15:
            add('init_default', compressed, bits, options=16)
            add('fail_allocate', compressed, bits, options=2)
            add('wrong_wrapper', compressed, 31)
            add('bad_window', compressed, 100)
    dictionary = b'Bunker dictionary'
    compressor = zlib.compressobj(zdict=dictionary)
    add('dictionary_required', compressor.compress(dictionary * 20) + compressor.flush(), 15)
    actual_assets = {}
    if apk is not None:
        with zipfile.ZipFile(apk) as package:
            candidates = [e for e in package.infolist() if e.compress_type == zipfile.ZIP_DEFLATED and
                          e.filename.startswith('assets/bin/Data/') and 0 < e.file_size <= 4096 and not e.flag_bits & 1]
            if not candidates:
                raise RuntimeError('No small deflated Unity asset exists in the supplied real APK')
            selected = next((e for e in candidates if e.filename == 'assets/bin/Data/boot.config'), candidates[0])
            expected = package.read(selected)
        with apk.open('rb') as source:
            source.seek(selected.header_offset)
            local = source.read(30)
            if local[:4] != b'PK\x03\x04':
                raise RuntimeError('Invalid actual APK local member header')
            name_size, extra_size = struct.unpack_from('<HH', local, 26)
            offset = selected.header_offset + 30 + name_size + extra_size
            source.seek(offset)
            compressed = source.read(selected.compress_size)
        if zlib.decompress(compressed, -15) != expected or binascii.crc32(expected) != selected.CRC:
            raise RuntimeError('Actual member raw DEFLATE bytes do not match APK size/CRC')
        with apk.open('rb') as source:
            apk_sha = hashlib.file_digest(source, 'sha256').hexdigest()
        evidence = {'apk': str(apk), 'apk_sha256': apk_sha, 'member': selected.filename, 'offset': offset,
                    'compressed_size': len(compressed), 'size': len(expected), 'crc32': selected.CRC}
        (out / 'real-apk-member.json').write_text(json.dumps(evidence, indent=2) + '\n')
        for label, inc, ouc, options in [('real_apk_default',1,1,0),('real_apk_callbacks',7,13,1)]:
            add(label, compressed, -15, inc, ouc, options)
            actual_assets[label] = expected
    lines = []
    identifiers = {}
    for i, (name, content) in enumerate(arrays.items()):
        ident = f'compressed_{i}';identifiers[name] = ident
        lines += [f'static const unsigned char {ident}[] = {{' + ','.join(map(str, content)) + '};']
    lines += ['struct ZlibCase {const unsigned char *data;uint32_t length;int32_t window_bits;uint32_t input_chunk,output_chunk,options,capacity;int32_t flush;};',
              'static const struct ZlibCase zlib_cases[] = {']
    lines += [f'{{{identifiers[n]},sizeof({identifiers[n]}),{bits},{ic},{oc},{options},{cap},{flush}}},'
              for n, bits, ic, oc, options, cap, flush in cases]
    (out / 'zlib_generated_cases.h').write_text('\n'.join(lines) + '\n};\n')
    return cases, actual_assets


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--windows', action='store_true')
    p.add_argument('--apk', type=Path, help='Also verify an actual deflated Unity asset and its ZIP CRC/size')
    p.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    a = p.parse_args()
    out = HERE.parent / ('work/zlib-windows' if a.windows else 'work/zlib-linux')
    out.mkdir(parents=True, exist_ok=True)

    def hp(path):
        if a.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    def run(command, **kwargs):
        subprocess.run([str(v) for v in command], check=True, **kwargs)

    cc = a.mingw / 'gcc.exe' if a.windows else a.cc
    cxx = a.mingw / 'g++.exe' if a.windows else a.cxx
    source, archive = prepare(out / 'backend', cc, a.mingw / 'ar.exe' if a.windows else 'llvm-ar-18', hp)
    compiler = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    fields = ['next_in','avail_in','total_in','next_out','avail_out','total_out','msg','state','zalloc','zfree','opaque','data_type','adler','reserved']
    probe = out / 'ndk-layout.c'
    probe.write_text('#include <stdint.h>\n#include <stddef.h>\n#include <zlib.h>\nconst uint64_t layout[]={sizeof(z_stream),sizeof(uLong),' +
                     ','.join(f'offsetof(z_stream,{field})' for field in fields) + '};\n')
    obj = out / 'ndk-layout.o';run([compiler, '-c', probe, '-o', obj])
    with obj.open('rb') as binary:
        elf = ELFFile(binary);symbol = elf.get_section_by_name('.symtab').get_symbol_by_name('layout')[0]
        raw = elf.get_section(symbol['st_shndx']).data()[symbol['st_value']:symbol['st_value'] + symbol['st_size']]
        layout = struct.unpack('<' + 'Q' * (2 + len(fields)), raw)
    if layout != (112,8,0,8,16,24,32,40,48,56,64,72,80,88,96,104):
        raise RuntimeError(f'NDK layout differs: {layout}')
    (out / 'ndk-layout.json').write_text(json.dumps(dict(zip(['size','uLong_size',*fields],layout)),indent=2))
    cases, actual_assets = generate(out, a.apk)
    reference = out / 'reference'
    build_reference(a.cc, a.reference_root, [HERE / 'zlib_ref.c', HERE / 'zlib_guest_fixture.c', *[source / name for name in SOURCES]], reference, [HERE,out,source])
    with (out / 'reference.bin').open('wb') as log:
        run([a.reference_root / 'usr/bin/qemu-aarch64-static', reference], stdout=log)
    common = ['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill / "include")}',f'-I{hp(source)}']
    if a.windows:
        common += ['-static']
    unit = out / ('unit.exe' if a.windows else 'unit')
    run([cxx,*common,hp(HERE/'zlib_test.cpp'),hp(HERE/'zlib_host.cpp'),hp(HERE.parent/'whole/runtime.cpp'),hp(archive),'-latomic','-o',hp(unit)])
    run([unit])
    library = out / 'zlib-guest.so'
    run([compiler,'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-vectorize','-fno-slp-vectorize','-funwind-tables',HERE/'zlib_guest_fixture.c','-o',library])
    run([sys.executable,HERE.parent/'whole/compile.py',library,'--out',out,'--lift',a.lift,'--cxx',a.cxx,'--base','0x63000000','--target','x86_64-w64-windows-gnu' if a.windows else 'x86_64-linux-gnu'])
    manifest = json.loads((out/'manifest.json').read_text())
    loader = out/'elfload.o';run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)])
    binary = out/('zlib-test.exe' if a.windows else 'zlib-test')
    run([cxx,*common,f'-I{hp(out)}',f'-DZLIB_LIBRARY="{hp(library)}"',hp(HERE/'zlib_guest_test.cpp'),hp(HERE/'zlib_host.cpp'),hp(HERE/'libc.cpp'),
         hp(HERE.parent/'whole/runtime.cpp'),hp(loader),*[hp(obj) for obj in manifest['objects']],hp(archive),'-latomic','-o',hp(binary)])
    with (out/'actual.bin').open('wb') as log:
        run([binary],stdout=log)
    expected=(out/'reference.bin').read_bytes();actual=(out/'actual.bin').read_bytes()
    offset=0;records=0
    for i,case in enumerate(cases):
        count=struct.unpack_from('<I',expected,offset+4)[0];length=16+count*72+4096
        if expected[offset:offset+length]!=actual[offset:offset+length]:
            left,right=expected[offset:offset+length],actual[offset:offset+length]
            pos=next((j for j,(a,b) in enumerate(zip(left,right)) if a!=b),min(len(left),len(right)))
            raise RuntimeError(f'zlib case {case[0]} differs at byte {pos}: ref={left[max(0,pos-16):pos+24].hex()} host={right[max(0,pos-16):pos+24].hex()}')
        if case[0] in actual_assets:
            payload=actual_assets[case[0]]
            output=actual[offset+16+count*72:offset+length]
            if struct.unpack_from('<i',actual,offset)[0]!=1 or output[:len(payload)]!=payload:
                raise RuntimeError('Translated actual APK resource did not reach stream end with original bytes')
            print(f'{case[0]}: {len(payload)} actual Unity asset bytes, CRC32 {binascii.crc32(output[:len(payload)]):08x}')
        offset+=length;records+=count
    if offset!=len(expected) or len(actual)!=len(expected):
        raise RuntimeError(f'incorrect output lengths {len(expected)}, {len(actual)}, {offset}')
    print(f'NDK zlib: {len(cases)} scenarios, {records:,} streaming records and all output bytes match ARM64 QEMU; Android112-byte layout verified.')


if __name__=='__main__':
    main()
