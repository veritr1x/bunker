"""Check ARM64 variadic call sites against a QEMU libc reference on both hosts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from test_fastaes import build_reference
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lift', required=True, type=Path)
    p.add_argument('--reference-root', required=True, type=Path)
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--windows', action='store_true')
    p.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    a = p.parse_args()
    out = HERE.parent / ('work/format-windows' if a.windows else 'work/format-linux')
    out.mkdir(parents=True, exist_ok=True)

    def run(command):
        subprocess.run([str(x) for x in command], check=True)

    def hp(path):
        if a.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    reference = out / 'reference'
    build_reference(a.cc, a.reference_root, [HERE / 'format_guest_ref.c'], reference, [HERE], ['_GNU_SOURCE'])
    with (out / 'reference.bin').open('wb') as log:
        subprocess.run([str(a.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    library = out / 'format-guest.so'
    run([a.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-ffreestanding', '-fno-builtin', '-fPIC',
         '-shared', '-nostdlib', '-O1', '-fno-jump-tables', '-fno-optimize-sibling-calls', '-funwind-tables', HERE / 'format_guest.c', '-o', library])
    run([sys.executable, HERE / 'compile.py', library, '--out', out, '--lift', a.lift, '--cxx', a.cxx,
         '--base', '0x40000000', '--target', 'x86_64-w64-windows-gnu' if a.windows else 'x86_64-linux-gnu'])
    manifest = json.loads((out / 'manifest.json').read_text())
    cc = a.mingw / 'gcc.exe' if a.windows else a.cc
    cxx = a.mingw / 'g++.exe' if a.windows else a.cxx
    common = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-I{hp(a.remill / "include")}', f'-I{hp(HERE)}']
    if a.windows:
        common += ['-static']
    unit = out / ('unit.exe' if a.windows else 'unit')
    run([cxx, *common, hp(HERE / 'format_test.cpp'), hp(HERE / 'format.cpp'),
         hp(HERE / 'runtime.cpp'), '-latomic', '-o', hp(unit)])
    run([unit])
    logging_unit = out / ('logging-unit.exe' if a.windows else 'logging-unit')
    run([cxx, *common, hp(HERE.parent / 'windows/logging_test.cpp'), hp(HERE.parent / 'windows/logging.cpp'),
         hp(HERE / 'format.cpp'), hp(HERE / 'runtime.cpp'), '-latomic', '-o', hp(logging_unit)])
    run([logging_unit])
    memory_unit = out / ('provider-memory.exe' if a.windows else 'provider-memory')
    run([cxx, *common, hp(HERE.parent / 'windows/provider_memory_test.cpp'),
         hp(HERE.parent / 'windows/jni_host.cpp'), hp(HERE.parent / 'windows/logging.cpp'),
         hp(HERE / 'format.cpp'), hp(HERE / 'runtime.cpp'), '-latomic', '-o', hp(memory_unit)])
    run([memory_unit])
    fatal = subprocess.run([str(logging_unit), '--assert'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if fatal.returncode == 0 or b'fatal 42' not in fatal.stderr:
        raise RuntimeError('guest assertion did not report and terminate')
    print('Logging fatal assertion reports and terminates.')
    loader = out / 'elfload.o'
    run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)])
    binary = out / ('format.exe' if a.windows else 'format')
    run([cxx, *common, f'-I{hp(out)}', f'-I{hp(HERE.parent / "fastaes")}',
         f'-DFORMAT_LIBRARY="{hp(library)}"', hp(HERE / 'format_guest_test.cpp'), hp(HERE / 'runtime.cpp'),
         hp(HERE / 'format.cpp'), hp(HERE.parent / 'windows/logging.cpp'), hp(loader),
         *[hp(obj) for obj in manifest['objects']], '-latomic', '-o', hp(binary)])
    with (out / 'actual.bin').open('wb') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    expected = (out / 'reference.bin').read_bytes()
    actual = (out / 'actual.bin').read_bytes()
    if len(expected) != 16 * 1028 or len(actual) != len(expected):
        raise RuntimeError(f'incorrect record lengths: {len(expected)}, {len(actual)}')
    for n in range(16):
        left, right = expected[n*1028:(n+1)*1028], actual[n*1028:(n+1)*1028]
        if left != right:
            print('case', n, 'reference', repr(left[:160]), 'actual', repr(right[:160]), file=sys.stderr)
            raise RuntimeError(f'format case {n} differs')
    print('ARM64 variadic formatter: 16 exact QEMU records passed (direct + va_list, mixed spills, logs/output).')


if __name__ == '__main__':
    main()
