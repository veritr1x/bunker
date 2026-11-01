"""Compare lifted exclusive instructions with ARM64, including trace splits."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from exclusive_cases import generate, generate_pairs
from test_fastaes import build_reference

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--cc', default='clang-18')
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--baseline-only', action='store_true', help='Prove old trace-local LDXR/STLXR loses its reservation')
    parser.add_argument('--pairs', action='store_true', help='Test W/X pair-exclusive forms, including the actual Unity ctor71 retry pattern')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    if args.pairs and args.baseline_only:
        parser.error('--pairs cannot be combined with --baseline-only')
    out = HERE.parent / f'work/exclusive-{"pairs-" if args.pairs else ""}{"baseline-" if args.baseline_only else ""}{"windows" if args.windows else "linux"}'
    out.mkdir(parents=True, exist_ok=True)
    functions, cases = generate_pairs() if args.pairs else generate(args.baseline_only)
    lines = ['.text']
    for name, instructions in functions.items():
        lines += [f'.global {name}', f'.type {name}, %function', f'{name}:', '.cfi_startproc']
        lines += ['    ' + instruction for instruction in instructions]
        lines += ['.cfi_endproc', f'.size {name}, .-{name}']
    source = out / 'exclusive.S'
    source.write_text('\n'.join(lines) + '\n')
    (out / 'generated_cases.h').write_text(''.join(f'CASE({name})\n' for name in cases))
    library = out / 'exclusive.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib', str(source), '-o', str(library)], check=True)
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out), '--base', '0x30000000',
                    '--lift', str(args.lift), '--cxx', args.cxx, '--target',
                    'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'], check=True)
    manifest = json.loads((out / 'manifest.json').read_text())
    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    cc = args.mingw / 'gcc.exe' if args.windows else args.cc
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([str(cc), '-O2', '-c', host(HERE.parent / 'fastaes/elfload.c'), '-o', host(loader)], check=True)
    binary = out / ('exclusive.exe' if args.windows else 'exclusive')
    command = [str(cxx), '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64', f'-DSEMANTIC_LIB="{host(library)}"',
               f'-I{host(args.remill / "include")}', f'-I{host(HERE)}', f'-I{host(HERE.parent / "fastaes")}', f'-I{host(out)}',
               host(HERE / 'semantic_test.cpp'), host(HERE / 'runtime.cpp'), host(loader),
               *[host(p) for p in manifest['objects']], '-latomic', '-o', host(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    reference = out / 'reference'
    build_reference(args.cc, args.reference_root, [HERE / 'semantic_ref.c', source], reference, [HERE, out])
    with (out / 'actual.txt').open('w') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    with (out / 'expected.txt').open('w') as log:
        subprocess.run([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    expected = (out / 'expected.txt').read_text().splitlines()
    actual = (out / 'actual.txt').read_text().splitlines()
    assert len(expected) == len(actual) == len(cases) * 256
    failures = [(want, got) for want, got in zip(expected, actual) if want != got]
    if args.baseline_only:
        assert len(failures) == 256, 'Baseline no longer reproduces the trace-local reservation failure'
        print('Baseline reproduced: all 256 LDXR→separate-trace STLXR calls lose their reservation.')
    else:
        if failures:
            raise AssertionError(f'{len(failures)} mismatches; ARM64:{failures[0][0]}\nx86:{failures[0][1]}')
        print(f'Exclusive instructions: {len(actual):,} cases match ARM64 QEMU ({len(cases)} variants, {len(functions)} trace heads).')


if __name__ == '__main__':
    main()
