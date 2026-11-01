"""Compile the complete real libFastAES image and compare x86, ARM64 and OpenSSL."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def build_reference(cc, root, sources, output, includes=(), defines=()):
    sysroot = root / 'usr/aarch64-linux-gnu'
    gcc = root / 'usr/lib/gcc-cross/aarch64-linux-gnu/13'
    subprocess.run([cc, '--target=aarch64-linux-gnu', f'--sysroot={sysroot}',
                    f'-B{gcc}', f'-L{gcc}', '-fuse-ld=lld', '-static', '-O2',
                    *[f'-I{p}' for p in includes], *[f'-D{v}' for v in defines],
                    *map(str, sources), '-o', str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    args = parser.parse_args()
    out = HERE.parent / 'work/whole-fastaes'
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(args.library), '--out', str(out),
                    '--lift', str(args.lift), '--cxx', args.cxx], check=True)
    manifest = json.loads((out / 'manifest.json').read_text())
    loader = out / 'elfload.o'
    subprocess.run([args.cc, '-O2', '-c', str(HERE.parent / 'fastaes/elfload.c'), '-o', str(loader)], check=True)
    binary = out / 'recomp'
    define = f'LIB="{args.library.resolve()}"'
    subprocess.run([args.cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-D{define}',
                    f'-I{args.remill / "include"}', f'-I{HERE}', f'-I{HERE.parent / "fastaes"}', f'-I{out}',
                    str(HERE / 'fastaes_test.cpp'), str(HERE / 'runtime.cpp'), str(loader),
                    *manifest['objects'], '-latomic', '-o', str(binary)], check=True)
    with (out / 'recomp.txt').open('w') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    reference = out / 'reference'
    build_reference(args.cc, args.reference_root,
                    [HERE.parent / 'fastaes/ref_arm64.c', HERE.parent / 'fastaes/elfload.c'],
                    reference, [HERE.parent / 'fastaes'], [define])
    with (out / 'ref.txt').open('w') as log:
        subprocess.run([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    spec = importlib.util.spec_from_file_location('aes_check', HERE.parent / 'fastaes/check.py')
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    check.WORK = out
    # The checker compares all calls with the original and encryption with OpenSSL.
    # Its exit status is propagated to this process.
    check.main()


if __name__ == '__main__':
    main()
