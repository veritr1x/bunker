"""Freeze genuine NDK PRFM/PRFUM cases; run same object on ARM64 and both lifted hosts."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
from elftools.elf.elffile import ELFFile
from test_fastaes import build_reference

HERE = Path(__file__).resolve().parent
OWN = ('test_prefetch.py', 'test_prefetch_decode.py', 'prefetch_test.cpp',
       'prefetch_ref.c', 'prefetch_native_wrapper.S', 'prefetch.md')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


RECORDS = r'''
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct {const char*name;uint32_t word;unsigned rn,misalign;} PrefetchCase;
static const PrefetchCase cases[]={
#define CASE(name,word,rn,misalign) {#name,word,rn,misalign},
#include "prefetch_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static int run_prefetch_records(void(*call)(unsigned,uint8_t*,const uint8_t*),uintptr_t guard){
 static uint8_t target[65536] __attribute__((aligned(16)));
 for(unsigned n=0;n<sizeof(target);++n)target[n]=(uint8_t)(n*37+11);
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<16;++seed){
  unsigned modes=((cases[test].word&31)==1)?5:1;
  for(unsigned mode=0;mode<modes;++mode){
   uint8_t input[768] __attribute__((aligned(16))), output_space[1664] __attribute__((aligned(16)));
   uint8_t original[768],target_before[65536];uint8_t*out=output_space+32;
   memset(input,0x73,sizeof(input));memset(output_space,0xab,sizeof(output_space));
   uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
   for(unsigned n=0;n<92;++n){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}
   uintptr_t address=mode==0?(uintptr_t)(target+256):mode==1?(uintptr_t)(target+257):mode==2?0:mode==3?guard:UINTPTR_MAX-15;
   unsigned rn=cases[test].rn;
   if(rn>=2&&rn<30&&rn!=18)put64(input+(rn-2)*8,address);
   put64(input+736,(uint64_t)seed<<28);put64(input+744,(seed&1)?UINT64_C(0x0800001f):0);put64(input+752,(uint64_t)(seed&3)<<22);
   memcpy(original,input,sizeof(input));memcpy(target_before,target,sizeof(target));call(test,out,input);
   if(memcmp(original,input,sizeof(input))||memcmp(target_before,target,sizeof(target)))return 20;
   for(unsigned n=0;n<sizeof(output_space);++n)if((n<32||n>=1632)&&output_space[n]!=0xab)return 21;
   if(memcmp(out,out+800,800))return 22;
   if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16!=cases[test].misalign)return 23;
   for(unsigned reg=2;reg<30;++reg)if(reg!=18&&get64(out+reg*8)!=get64(input+(reg-2)*8))return 24;
   if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 25;
   /* Locally validated real pointers, reserved x18 and link/SP vary by host. */
   for(unsigned n=0;n<2;++n)put64(out+n*8,0);
   put64(out+18*8,0);put64(out+30*8,0);put64(out+31*8,0);
   if(rn>=2&&rn<30)put64(out+rn*8,0);
   printf("RECORD %s %u %u ",cases[test].name,seed,mode);
   for(unsigned n=0;n<800;++n)printf("%02x",out[n]);
   putchar('\n');++count;
  }
 }
 printf("PREFETCH-RECORDS-SUCCESS %u\n",count);return 0;
}
'''


def generate(out):
    cases = []

    def add(name, word, rn, misalign=0):
        cases.append((name, word, rn, misalign))

    for form in (0, 1):
        for rt in range(32):
            for rn in (20, 31):
                word = (0xf9800000 if form else 0xf8800000) | rn << 5 | rt
                add(f'{"prfm" if form else "prfum"}_hint{rt}_rn{rn}', word, rn)
    for form, offsets in ((0, [-256, -255, -112, -1, 0, 1, 7, 8, 15, 255]),
                          (1, [0, 8, 16, 248, 256, 4096, 32760])):
        for rn in (20, 31):
            for offset in offsets:
                word = ((0xf9800000 | (offset // 8) << 10) if form else
                        (0xf8800000 | (offset & 511) << 12)) | rn << 5 | 1
                add(f'edge_{form}_{rn}_{"m" if offset < 0 else "p"}{abs(offset)}', word, rn)
    originals = [(0x825adedc, 0xf9800301, 24), (0x825ae0c8, 0xf8990281, 20),
                 (0x825ae110, 0xf9800301, 24), (0x825ae11c, 0xf9800301, 24),
                 (0x825ae134, 0xf9800101, 8), (0x825ae14c, 0xf9800321, 25)]
    for pc, word, rn in originals:
        add(f'original_{pc:x}', word, rn)
    for form in (0, 1):
        add(f'misaligned_sp_{form}', (0xf9800000 if form else 0xf8800000) | 31 << 5 | 1, 31, 8)
    add('unchanged_nop', 0xd503201f, 20)
    lines = ['.text']

    def function(name, body):
        lines.extend([f'.global {name}', f'.type {name},%function', f'{name}:',
                      '.cfi_startproc', *['  ' + x for x in body], '.cfi_endproc',
                      f'.size {name},.-{name}'])

    def snapshot(offset):
        body = [f'str x{reg},[x0,#{offset+reg*8}]' for reg in range(31)]
        body += [f'str q{reg},[x0,#{offset+256+reg*16}]' for reg in range(32)]
        body += ['mov x2,sp', f'str x2,[x0,#{offset+248}]']
        # Baseline lacks the NZCV system-register selector. Observe actual
        # flags through supported flag-preserving conditional aliases instead.
        body += ['cset x2,mi', 'lsl x2,x2,#31', 'cset x3,eq',
                 'orr x2,x2,x3,lsl#30', 'cset x3,cs', 'orr x2,x2,x3,lsl#29',
                 'cset x3,vs', 'orr x2,x2,x3,lsl#28', f'str x2,[x0,#{offset+768}]']
        for register, pos in (('fpsr', 776), ('fpcr', 784)):
            body += [f'mrs x2,{register}', f'str x2,[x0,#{offset+pos}]']
        body += [f'ldr x2,[x0,#{offset+16}]', f'ldr x3,[x0,#{offset+24}]']
        return body

    for name, word, rn, misalign in cases:
        body = ['sub sp,sp,#240']
        body += [f'stp x{reg},x{reg+1},[sp,#{(reg-18)*8}]' for reg in range(18, 30, 2)]
        body += ['str x30,[sp,#96]']
        body += [f'str q{reg},[sp,#{112+(reg-8)*16}]' for reg in range(8, 16)]
        for register, pos in (('fpsr', 744), ('fpcr', 752)):
            body += [f'ldr x2,[x1,#{pos}]', f'msr {register},x2']
        body += [f'ldr q{reg},[x1,#{224+reg*16}]' for reg in range(32)]
        body += [f'ldr x{reg},[x1,#{(reg-2)*8}]' for reg in range(2, 30) if reg != 18]
        if misalign:
            body += ['sub sp,sp,#8']
        body += snapshot(0) + [f'.inst 0x{word:08x}'] + snapshot(800)
        if misalign:
            body += ['add sp,sp,#8']
        body += [f'ldr q{reg},[sp,#{112+(reg-8)*16}]' for reg in range(8, 16)]
        body += [f'ldp x{reg},x{reg+1},[sp,#{(reg-18)*8}]' for reg in range(18, 30, 2)]
        body += ['ldr x30,[sp,#96]', 'add sp,sp,#240', 'ret']
        function(name, body)
        function('raw_' + name, [f'.inst 0x{word:08x}', 'ret'])
        function('exclusive_' + name, ['ldxr x2,[x0]', f'.inst 0x{word:08x}',
                                     'stxr w3,x2,[x0]', 'mov w0,w3', 'ret'])
    function('prefetch_control_load', ['ldr x0,[x0]', 'ret'])
    function('prefetch_control_store', ['str x1,[x0]', 'ret'])
    (out / 'prefetch.S').write_text('\n'.join(lines) + '\n')
    (out / 'prefetch_cases.h').write_text(''.join(f'CASE({n},0x{w:08x},{r},{m})\n' for n, w, r, m in cases))
    (out / 'prefetch_records.h').write_text(RECORDS)
    (out / 'case-oracle.json').write_text(json.dumps(cases, indent=2) + '\n')
    return cases, originals


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--ndk', type=Path, default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
    p.add_argument('--support-commit', default='0a5bdf2')
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = HERE.parent.parent
    commit = subprocess.check_output(['git', 'rev-parse', a.support_commit], cwd=root, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', commit, 'recomp/whole', 'recomp/fastaes'], cwd=root)
    (out / 'support.tar').write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out / 'host', filter='data')
    source = out / 'host/recomp'
    overlay = {}
    for name in OWN:
        overlay[name] = sha(HERE / name)
        shutil.copy2(HERE / name, source / 'whole' / name)
    source_pins = {str(f.relative_to(source)): sha(f) for f in source.rglob('*') if f.is_file()}
    # build_reference was imported by this controller; prove that exact helper
    # is byte-identical to the accepted frozen source before invoking it.
    assert sha(HERE / 'test_fastaes.py') == source_pins['whole/test_fastaes.py']
    tool_pins = {str(f): sha(f) for f in a.toolchain.rglob('*') if f.is_file()}
    external = [a.reference_root / 'usr/bin/qemu-aarch64-static']
    ndk = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    external += [ndk.resolve(), Path('/usr/bin/clang-18').resolve(), Path('/usr/bin/clang++-18').resolve(),
                 Path('/mnt/c/mingw64/bin/g++.exe'), Path('/mnt/c/mingw64/bin/gcc.exe')]
    external_pins = {str(f): sha(f) for f in external}
    result = {'passed': False, 'support_commit': commit, 'overlays': overlay,
              'support_archive_sha256': sha(out / 'support.tar'), 'support_sources': source_pins,
              'toolchain_inputs': tool_pins, 'external_tools': external_pins}
    (out / 'source-pin.json').write_text(json.dumps(result, indent=2) + '\n')

    def run(command, name, timeout=300, negative=False):
        log = out / name
        with log.open('w') as stream:
            completed = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        if (completed.returncode == 0) == negative:
            raise RuntimeError(f'{name}: unexpected exit {completed.returncode}\n{log.read_text(errors="replace")[-5000:]}')
        return completed.returncode

    def wp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()

    for tool in external:
        run([tool, '--version'], tool.name + '-version.log')
    run([sys.executable, source / 'whole/test_prefetch_decode.py', '--toolchain', a.toolchain,
         '--out', out / 'decode'], 'decode-controller.log')
    generated = out / 'generated'
    generated.mkdir()
    cases, originals = generate(generated)
    obj = out / 'ndk-prefetch.o'
    run([ndk, '-c', '-Wall', '-Wextra', '-Werror', generated / 'prefetch.S', '-o', obj], 'ndk-build.log')
    with obj.open('rb') as stream:
        elf = ELFFile(stream)
        for pc, word, _ in originals:
            symbol = elf.get_section_by_name('.symtab').get_symbol_by_name(f'raw_original_{pc:x}')[0]
            data = elf.get_section(symbol['st_shndx']).data()
            assert struct.unpack_from('<I', data, symbol['st_value'])[0] == word
    # Source-level invalid operands are not the same as valid unnamed imm5 hints.
    assembler_negatives = {}
    for index, instruction in enumerate(('prfum pldl1strm,[x20,#-257]', 'prfum pldl1strm,[x20,#256]',
                                          'prfm pldl1strm,[x20,#1]', 'prfm pldl1strm,[x20,#32768]',
                                          'prfm #32,[x20]')):
        bad = generated / f'invalid-{index}.S'
        bad.write_text('.text\n' + instruction + '\n')
        assembler_negatives[instruction] = run([ndk, '-c', bad, '-o', generated / f'invalid-{index}.o'], f'invalid-{index}.log', negative=True)
    library = out / 'prefetch.so'
    run(['clang-18', '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib', obj, '-o', library], 'guest-link.log')
    wrapper = out / 'ndk-wrapper.o'
    run([ndk, '-c', '-Wall', '-Wextra', '-Werror', source / 'whole/prefetch_native_wrapper.S', '-o', wrapper], 'wrapper-build.log')
    reference = out / 'arm64-reference'
    with (out / 'reference-build.log').open('w') as log:
        # This uses the exact NDK core object, not an independently assembled substitute.
        saved = sys.stdout
        build_reference('clang-18', a.reference_root, [source / 'whole/prefetch_ref.c', obj, wrapper], reference, [generated])
    qemu = a.reference_root / 'usr/bin/qemu-aarch64-static'
    run([qemu, reference], 'arm64-records.log')
    fault_results = {'arm64': run([qemu, reference, '--fault-load'], 'arm64-fault.log', 30, True)}
    assert fault_results['arm64'] == -11, fault_results
    expected = [x for x in (out / 'arm64-records.log').read_text().splitlines() if x.startswith('RECORD ')]
    expected_count = sum(16 * (5 if word & 31 == 1 else 1) for _, word, _, _ in cases)
    assert len(expected) == expected_count
    assert f'PREFETCH-RECORDS-SUCCESS {expected_count}' in (out / 'arm64-records.log').read_text()
    assert f'PREFETCH-REFERENCE-SUCCESS exclusive={len(cases)} ' in (out / 'arm64-records.log').read_text()
    manifests = {}
    for windows in (False, True):
        host = 'windows' if windows else 'linux'
        build = out / host
        run([sys.executable, source / 'whole/compile.py', library, '--out', build,
             '--base', '0x36000000', '--lift', a.toolchain / 'remill-lift',
             '--semantics-dir', a.toolchain, '--target', 'x86_64-w64-windows-gnu' if windows else 'x86_64-linux-gnu',
             '--cxx', 'clang++-18', '--jobs', '4'], host + '-compile.log', 900)
        manifest = json.loads((build / 'manifest.json').read_text())
        assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        path = wp if windows else lambda p: str(p)
        cc = '/mnt/c/mingw64/bin/gcc.exe' if windows else 'clang-18'
        cxx = '/mnt/c/mingw64/bin/g++.exe' if windows else 'clang++-18'
        loader = build / 'elfload.o'
        run([cc, '-O2', '-c', path(source / 'fastaes/elfload.c'), '-o', path(loader)], host + '-loader.log')
        binary = build / ('prefetch.exe' if windows else 'prefetch')
        flags = ['-O2', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-DADDRESS_SIZE_BITS=64',
                 '-isystem', path(a.toolchain / 'include'), '-I' + path(source / 'whole'),
                 '-I' + path(source / 'fastaes'), '-I' + path(generated), '-I' + path(build),
                 f'-DPREFETCH_LIB="{path(library)}"']
        # Werror applies only to new sources, never broadens accepted runtime warnings.
        test_obj = build / 'prefetch-test.o'
        run([cxx, *flags, '-c', path(source / 'whole/prefetch_test.cpp'), '-o', path(test_obj)], host + '-test-build.log')
        runtime_obj = build / 'runtime.o'
        run([cxx, *[v for v in flags if v not in ('-Wall', '-Wextra', '-Werror')], '-c', path(source / 'whole/runtime.cpp'), '-o', path(runtime_obj)], host + '-runtime-build.log')
        run([cxx, path(test_obj), path(runtime_obj), path(loader), *[path(p) for p in manifest['objects']],
             '-latomic', *(['-static', '-pthread'] if windows else ['-pthread']), '-o', path(binary)], host + '-link.log')
        run([binary], host + '-records.log')
        actual_text = (out / (host + '-records.log')).read_text()
        actual = [x for x in actual_text.splitlines() if x.startswith('RECORD ')]
        assert actual == expected, host + ' normalized actual native state mismatch'
        assert f'PREFETCH-RECORDS-SUCCESS {expected_count}' in actual_text
        assert f'PREFETCH-HOST-SUCCESS raw={len(cases)} exclusive={len(cases)} ordinary=2' in actual_text
        if windows:
            native_exit = out / 'native-exit.ps1'
            native_exit.write_text('''param([string]$Binary,[string]$Stdout,[string]$Stderr,[string]$Result)
$ErrorActionPreference='Stop'
$child=Start-Process -FilePath $Binary -ArgumentList @('--fault-load') -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
$child.Refresh()
@{exit_code=$child.ExitCode} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $Result
''')
            status = out / 'windows-fault-status.json'
            run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', wp(native_exit),
                 '-Binary', wp(binary), '-Stdout', wp(out / 'windows-fault.stdout.log'),
                 '-Stderr', wp(out / 'windows-fault.log'), '-Result', wp(status)], 'windows-fault-controller.log', 30)
            fault_results[host] = json.loads(status.read_text(encoding='utf-8-sig'))['exit_code']
            assert (fault_results[host] & 0xffffffff) == 0xc0000005, fault_results
        else:
            fault_results[host] = run([binary, '--fault-load'], host + '-fault.log', 30, True)
            assert fault_results[host] == -11, fault_results
        manifests[host] = {'binary_sha256': sha(binary), 'manifest_sha256': sha(build / 'manifest.json'),
                           'traces': len(manifest['traces']), 'objects': len(manifest['objects']), 'toolchain': manifest['toolchain']}
        print(f'{host}: {expected_count} native-matching records, {len(cases)} raw/exclusive probes', flush=True)
    for name, pin in overlay.items():
        assert sha(HERE / name) == pin and sha(source / 'whole' / name) == pin
    for name, pin in source_pins.items():
        assert sha(source / name) == pin
    for name, pin in {**tool_pins, **external_pins}.items():
        assert sha(name) == pin
    assert sha(HERE / 'test_fastaes.py') == source_pins['whole/test_fastaes.py']
    result.update({'passed': True, 'cases': len(cases), 'records_each': expected_count,
                   'same_ndk_core_sha256': sha(obj), 'fixture_sha256': sha(library),
                   'assembler_negatives': assembler_negatives, 'actual_noaccess_load_failures': fault_results,
                   'hosts': manifests, 'reference_sha256': sha(reference),
                   'limits': 'Effect-free implementation; no cache timing/hardware performance/MTE or game initialization claim'})
    result['evidence'] = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file() and 'host' not in f.relative_to(out).parts and f.name != 'acceptance.json'}
    (out / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PREFETCH-ALL-HOSTS-SUCCESS ' + str(out / 'acceptance.json'), flush=True)


if __name__ == '__main__':
    main()
