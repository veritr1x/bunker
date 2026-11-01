"""Validate native libc imports with actual NDK ARM64 startup callers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--windows', action='store_true')
    p.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    a = p.parse_args()
    out = HERE.parent / ('work/libc-windows' if a.windows else 'work/libc-linux')
    out.mkdir(parents=True, exist_ok=True)

    def run(command, **kwargs):
        subprocess.run([str(v) for v in command], check=True, **kwargs)

    def hp(path):
        if a.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    cc = a.mingw / 'gcc.exe' if a.windows else a.cc
    cxx = a.mingw / 'g++.exe' if a.windows else a.cxx
    common = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-I{hp(a.remill / "include")}']
    if a.windows:
        common += ['-static']
    unit = out / ('libc-unit.exe' if a.windows else 'libc-unit')
    run([cxx, *common, hp(HERE / 'libc_test.cpp'), hp(HERE / 'libc.cpp'),
         hp(HERE.parent / 'whole/runtime.cpp'), '-latomic', '-o', hp(unit)])
    run([unit])
    for name in ('__stack_chk_fail', 'abort'):
        fatal = subprocess.run([str(unit), name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if fatal.returncode == 0 or b'guest libc fatal' not in fatal.stderr:
            raise RuntimeError(f'{name} failed to report and terminate')
    print('Guest stack-check and abort imports terminate truthfully.')
    compiler = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library = out / 'libc-guest.so'
    run([compiler, '-shared', '-nostdlib', '-fPIC', '-O1', '-fno-stack-protector', '-D_FORTIFY_SOURCE=0',
         '-fno-builtin', '-fno-vectorize', '-fno-slp-vectorize', '-fno-jump-tables', '-funwind-tables',
         HERE / 'libc_guest_fixture.c', '-o', library])
    run([sys.executable, HERE.parent / 'whole/compile.py', library, '--out', out, '--lift', a.lift,
         '--cxx', a.cxx, '--base', '0x62000000', '--target', 'x86_64-w64-windows-gnu' if a.windows else 'x86_64-linux-gnu'])
    manifest = json.loads((out / 'manifest.json').read_text())
    loader = out / 'elfload.o'
    run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)])
    binary = out / ('libc-guest.exe' if a.windows else 'libc-guest')
    run([cxx, *common, f'-I{hp(out)}', f'-DLIBC_LIBRARY="{hp(library)}"',
         hp(HERE / 'libc_guest_test.cpp'), hp(HERE / 'libc.cpp'), hp(HERE.parent / 'whole/runtime.cpp'),
         hp(loader), *[hp(obj) for obj in manifest['objects']], '-latomic', '-o', hp(binary)])
    run([binary], env={**os.environ, 'BUNKER_HOST_ONLY_TEST': 'must never reach the virtual environment'})


if __name__ == '__main__':
    main()
