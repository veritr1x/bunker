"""Build, lift and execute a multi-function ARM64 ELF as native x86_64 code."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    args = parser.parse_args()
    out = HERE.parent / 'work/whole-fixture'
    out.mkdir(parents=True, exist_ok=True)
    library = out / 'fixture.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-ffreestanding',
                    '-fPIC', '-shared', '-nostdlib', '-O1', '-fno-optimize-sibling-calls',
                    '-funwind-tables', '-Wl,--hash-style=both', '-Wl,--no-rosegment',
                    str(HERE / 'fixture.c'), '-o', str(library)], check=True)
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out),
                    '--lift', str(args.lift), '--base', '0x20000000', '--shard-size', '2', '--cxx', args.cxx], check=True)
    manifest = json.loads((out / 'manifest.json').read_text())
    loader = out / 'elfload.o'
    subprocess.run([args.cc, '-O2', '-c', str(HERE.parent / 'fastaes/elfload.c'), '-o', str(loader)], check=True)
    binary = out / 'test-fixture'
    subprocess.run([args.cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
                    f'-DFIXTURE_LIB="{library}"', f'-I{args.remill / "include"}',
                    f'-I{HERE}', f'-I{HERE.parent / "fastaes"}', f'-I{out}',
                    str(HERE / 'fixture_test.cpp'), str(HERE / 'runtime.cpp'),
                    str(loader), *manifest['objects'], '-latomic', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    negative = subprocess.run([str(binary), 'unknown-target'], capture_output=True, text=True)
    if negative.returncode == 0 or 'unresolved indirect target at 0xdeadbeef' not in negative.stderr:
        raise RuntimeError(f'Unknown-target failure was not reported: {negative}')
    print('Unknown-target negative test passed.')


if __name__ == '__main__':
    main()
