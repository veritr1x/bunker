"""Test typed AAPCS64 bridges, including compiler-generated guest call sites.

Run from WSL with --windows to compile and execute native Windows PE binaries
using the installed MinGW compiler. Clang in WSL builds the ARM64 input and
cross-compiles the lifted LLVM IR into Windows objects.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    out = HERE.parent / ('work/bridge-windows' if args.windows else 'work/bridge-linux')
    out.mkdir(parents=True, exist_ok=True)

    def host_path(path):
        if args.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    def host_run(arguments):
        subprocess.run([str(value) for value in arguments], check=True)

    host_cc = args.mingw / 'gcc.exe' if args.windows else args.cc
    host_cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    includes = [f'-I{host_path(args.remill / "include")}', f'-I{host_path(HERE)}']
    unit = out / ('bridge-test.exe' if args.windows else 'bridge-test')
    common = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', *includes]
    if args.windows:
        common += ['-static']
    host_run([host_cxx, *common, host_path(HERE / 'bridge_test.cpp'),
              host_path(HERE / 'runtime.cpp'), '-latomic', '-o', host_path(unit)])
    host_run([unit])

    library = out / 'bridge-guest.so'
    host_run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-ffreestanding',
              '-fPIC', '-shared', '-nostdlib', '-O1', '-fno-optimize-sibling-calls',
              '-funwind-tables', str(HERE / 'bridge_guest.c'), '-o', str(library)])
    host_run([sys.executable, HERE / 'compile.py', library, '--out', out, '--lift', args.lift,
              '--cxx', args.cxx, '--base', '0x40000000', '--shard-size', '3',
              '--target', 'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'])
    manifest = json.loads((out / 'manifest.json').read_text())
    loader = out / 'elfload.o'
    host_run([host_cc, '-O2', '-c', host_path(HERE.parent / 'fastaes/elfload.c'), '-o', host_path(loader)])
    binary = out / ('bridge-guest-test.exe' if args.windows else 'bridge-guest-test')
    host_run([host_cxx, *common, f'-I{host_path(out)}', f'-I{host_path(HERE.parent / "fastaes")}',
              f'-DBRIDGE_LIBRARY="{host_path(library)}"', host_path(HERE / 'bridge_guest_test.cpp'),
              host_path(HERE / 'runtime.cpp'), host_path(loader),
              *[host_path(obj) for obj in manifest['objects']], '-latomic', '-o', host_path(binary)])
    host_run([binary])


if __name__ == '__main__':
    main()
