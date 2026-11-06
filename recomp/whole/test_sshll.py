"""NDK SSHLL/SSHLL2: signed widening against real Bionic, QEMU and an integer oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile

from sshll_cases import generate

HERE = Path(__file__).resolve().parent
MASK = (1 << 64) - 1
EDGES = [0, MASK, 1, 0x8000000080000000, 0x7fffffff7fffffff,
         0xaaaaaaaaaaaaaaaa, 0x5555555555555555, 0x0001000100010001,
         0xff00ff00ff00ff00, 0x00ff00ff00ff00ff, 0xffff0000ffff0000,
         0x0000ffff0000ffff, 0x8080808080808080, 0x7f7f7f7f7f7f7f,
         0x8000000000000000, 0x0000000080000000]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def oracle(name, seed):
    data = bytearray()
    random = 0x9e3779b97f4a7c15 ^ seed
    for lane in range(16):
        random ^= (random << 13) & MASK
        random ^= random >> 7
        random ^= (random << 17) & MASK
        data += struct.pack('<Q', EDGES[(seed + lane) % 16] if seed < 16 else random)
    nzcv = (seed & 15) << 28
    fpsr = (seed & 31) | ((seed & 32) << 2) | ((seed & 64) << 21)
    fpcr = ((seed & 3) << 22) | ((seed & 4) << 22) | ((seed & 8) << 22)
    struct.pack_into('<QQQ', data, 64, nzcv, fpsr, fpcr)
    vectors = {reg: bytes(data[offset:offset + 16])
               for reg, offset in [(0, 0), (1, 16), (2, 32), (3, 48), (17, 96), (31, 112)]}
    if name.startswith('actual_unity_'):
        bits, high, shift, dst, src = 32, False, 0, 0, 0
    else:
        match = re.fullmatch(r'(sshll2?|sxtl2?)_(8|16|32)(?:_(\d+))?_(separate|overlap|high_regs|high_overlap)', name)
        assert match, name
        op, width, immediate, variant = match.groups()
        bits, high, shift = int(width), op.endswith('2'), int(immediate or 0)
        dst, src = {'separate': (2, 0), 'overlap': (0, 0),
                    'high_regs': (31, 17), 'high_overlap': (31, 31)}[variant]
    source = vectors[src][8 if high else 0:16 if high else 8]
    wide = bytearray()
    for offset in range(0, 8, bits // 8):
        value = int.from_bytes(source[offset:offset + bits // 8], 'little', signed=True)
        wide += ((value << shift) & ((1 << (bits * 2)) - 1)).to_bytes(bits // 4, 'little')
    vectors[dst] = bytes(wide)
    return b''.join(vectors[reg] for reg in (0, 1, 2, 3, 17, 31)) + struct.pack('<QQQ', nzcv, fpsr, fpcr) + b'\xab' * 8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--semantics-dir', type=Path)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent/'work/remill-src')
    parser.add_argument('--cc', default='clang-18')
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--reference-only', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)  # Never overwrite an earlier failure or accepted cohort.
    out, cases = args.out, generate()
    own=['sshll_cases.py','sshll_records.h','sshll_ref.c','sshll_native_wrapper.S','sshll_test.cpp','test_sshll.py','test_sshll_decode.py']
    support=['runtime.cpp','runtime.h','cooperative_poll.cpp','cooperative_poll.h','guest_memory.h','compile.py','jump_tables.py','callback_roots.py','nonlocal_roots.py']
    fixture=out/'source/whole';fixture.mkdir(parents=True)
    held={}
    for name in own+support:
        p=HERE/name;shutil.copyfile(p,fixture/name);held[str(p)]=sha(p)
    frozen_aes=out/'source/fastaes';frozen_aes.mkdir()
    for name in ['elfload.c','elfload.h','elf64.h']:
        p=HERE.parent/'fastaes'/name;shutil.copyfile(p,frozen_aes/name);held[str(p)]=sha(p)
    remill_include=out/'remill-include';shutil.copytree(args.remill/'include',remill_include)
    for p in (args.remill/'include').rglob('*'):
        if p.is_file():held[str(p)]=sha(p)
    lines = ['.text']
    for name, instructions in cases.items():
        lines += [f'.global {name}', f'.type {name}, %function', f'{name}:', '.cfi_startproc']
        lines += ['    ' + instruction for instruction in instructions]
        lines += ['.cfi_endproc', f'.size {name}, .-{name}']
    source = out/'sshll.S'
    source.write_text('\n'.join(lines) + '\n')
    (out/'generated_cases.h').write_text(''.join(f'CASE({name})\n' for name in cases))
    ndk_cc = args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    obj, library = out/'ndk-sshll.o', out/'sshll.so'
    subprocess.run([str(ndk_cc), '-c', str(source), '-o', str(obj)], check=True)
    with obj.open('rb') as stream:
        elf=ELFFile(stream)
        actual=elf.get_section_by_name('.symtab').get_symbol_by_name('actual_unity_708d13d8_0f20a400')[0]
        body=elf.get_section(actual['st_shndx']).data()
        assert struct.unpack_from('<I',body,actual['st_value']+24)[0]==0x0f20a400
    subprocess.run([str(ndk_cc), '-shared', '-nostdlib', str(obj), '-o', str(library)], check=True)
    # The actual NDK core also executes natively with Bionic before lifting.
    reference = out/'reference'
    wrapper=out/'ndk-native-wrapper.o'
    subprocess.run([str(ndk_cc),'-c',str(fixture/'sshll_native_wrapper.S'),'-o',str(wrapper)],check=True)
    reference_command=[str(ndk_cc),'-static','-O2','-fno-emulated-tls',str(fixture/'sshll_ref.c'),str(obj),str(wrapper),'-I'+str(fixture),'-I'+str(out),'-o',str(reference)]
    subprocess.run(reference_command,check=True)
    with (out/'expected.txt').open('w') as log:
        subprocess.run([str(args.reference_root/'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    reference_records=0
    with(out/'expected.txt').open()as stream:
        for row in stream:
            name,seed,record=row.split();assert bytes.fromhex(record)==oracle(name,int(seed)),(name,seed);reference_records+=1
    assert reference_records==473*256
    if args.reference_only:
        for p,digest in held.items():assert sha(Path(p))==digest,p
        (out/'acceptance.json').write_text(json.dumps(dict(passed=True,reference_only=True,records=reference_records,variants=len(cases),actual_Bionic=True,NDK_object_sha256=sha(obj),reference_sha256=sha(reference),records_sha256=sha(out/'expected.txt'),held_sources=held,limits='Native original AArch64 instructions and mathematical signed oracle only; no lifted/native Windows execution.'),indent=2)+'\n')
        print('SSHLL Bionic reference PASS',reference_records,flush=True);return
    compile_command = [sys.executable, str(fixture/'compile.py'), str(library), '--out', str(out), '--base', '0x30000000',
                       '--lift', str(args.lift), '--cxx', args.cxx, '--target',
                       'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu']
    if args.semantics_dir:
        compile_command += ['--semantics-dir', str(args.semantics_dir)]
    subprocess.run(compile_command, check=True)
    manifest = json.loads((out/'manifest.json').read_text())
    assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']

    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)

    cc, cxx = (args.mingw/'gcc.exe', args.mingw/'g++.exe') if args.windows else (args.cc, args.cxx)
    loader, binary = out/'elfload.o', out/('sshll.exe' if args.windows else 'sshll')
    subprocess.run([str(cc), '-O2', '-c', host(frozen_aes/'elfload.c'), '-o', host(loader)], check=True)
    command = [str(cxx), '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64', f'-DSEMANTIC_LIB="{host(library)}"',
               f'-I{host(remill_include)}', f'-I{host(fixture)}', f'-I{host(frozen_aes)}', f'-I{host(out)}',
               host(fixture/'sshll_test.cpp'), host(fixture/'runtime.cpp'),host(fixture/'cooperative_poll.cpp'),host(loader),
               *[host(p) for p in manifest['objects']], '-latomic', '-o', host(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    with (out/'actual.txt').open('w') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    count = 0
    with (out/'expected.txt').open() as expected, (out/'actual.txt').open() as actual:
        for want, got in zip(expected, actual, strict=True):
            assert want == got, (want, got)
            name, seed, record = want.split()
            assert bytes.fromhex(record) == oracle(name, int(seed)), (name, seed)
            count += 1
    assert count == 473 * 256
    for p,digest in held.items():assert sha(Path(p))==digest,p
    proof = dict(passed=True, records=count, variants=len(cases), ndk_object_sha256=sha(obj),
                 ndk_compiler_sha256=sha(ndk_cc.resolve()),ndk_version=subprocess.check_output([str(ndk_cc),'--version'],text=True).splitlines()[0],
                 literal_reached_word='0f20a400',literal_reached_guest_pc='0x708d13d8',
                 reference_sha256=sha(reference), actual_sha256=sha(out/'actual.txt'), expected_sha256=sha(out/'expected.txt'),
                 executable_sha256=sha(binary), target=manifest['target'], toolchain=manifest['toolchain'],
                 oracle='signed source lane; mathematical left shift modulo widened lane width; source snapshots, NZCV/FPSR/FPCR and output guards',
                 real_Bionic_reference=True,reference_command=reference_command,
                 State1200=True,Memory64=True,all_unrelated_State_bytes_checked=True,
                 held_sources=held,compiled_source_directory=str(fixture),
                 native_wrapper_sha256=sha(wrapper),
                 source_sha256={name: sha(fixture/name) for name in own})
    (out/'acceptance.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(f'SSHLL PASS: {count:,} full source/result/flags records ({len(cases)} variants), ARM64 QEMU and independent oracle')


if __name__ == '__main__':
    main()
