"""Check Bionic locale ownership and actual NDK ARM64 locale callers."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--remill', type=Path, required=True)
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--windows', action='store_true')
    p.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    a = p.parse_args()
    out = HERE.parent / ('work/locale-windows' if a.windows else 'work/locale-linux')
    out.mkdir(parents=True, exist_ok=True)

    def run(command):
        subprocess.run([str(v) for v in command], check=True)

    def hp(path):
        if a.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    compiler = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library = out / 'locale.so'
    run([compiler, '-shared', '-nostdlib', '-fPIC', '-O1', '-fno-stack-protector', '-D_FORTIFY_SOURCE=0',
         '-fno-builtin', '-fno-vectorize', '-fno-slp-vectorize', '-fno-jump-tables', '-funwind-tables',
         HERE / 'locale_guest.c', '-o', library])
    run([sys.executable, HERE.parent / 'whole/compile.py', library, '--out', out, '--lift', a.lift,
         '--cxx', a.cxx, '--base', '0x6d000000', '--target', 'x86_64-w64-windows-gnu' if a.windows else 'x86_64-linux-gnu'])
    manifest = json.loads((out / 'manifest.json').read_text())
    cc = a.mingw / 'gcc.exe' if a.windows else a.cc
    cxx = a.mingw / 'g++.exe' if a.windows else a.cxx
    loader = out / 'elfload.o'
    run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)])
    binary = out / ('locale.exe' if a.windows else 'locale')
    command = [cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-I{hp(a.remill / "include")}',
               f'-I{hp(out)}', f'-DLOCALE_LIBRARY="{hp(library)}"', hp(HERE / 'locale_test.cpp'),
               hp(HERE / 'libc.cpp'), hp(HERE.parent / 'whole/runtime.cpp'), hp(loader),
               *[hp(obj) for obj in manifest['objects']], '-latomic', '-pthread', '-o', hp(binary)]
    if a.windows:
        command.insert(1, '-static')
    run(command)
    run([binary])
    (out / 'result.json').write_text(json.dumps({'status': 'passed', 'translated_callers': 29,
        'platform': 'windows' if a.windows else 'linux', 'toolchain': manifest['toolchain'],
        'traces': len(manifest['traces']), 'unsupported': len(manifest['unsupported_traces']),
        'unresolved_direct': len(manifest['unresolved_direct_targets'])}, indent=2) + '\n')


if __name__ == '__main__':
    main()
