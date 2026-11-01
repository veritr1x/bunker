"""Check FP32/FP64 precision conversion and cumulative exception flags against ARM64 QEMU."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from fp_precision_cases import EDGE_COUNT, EDGES32, EDGES64, generate
from test_fastaes import build_reference

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--reference-only', action='store_true')
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    out = HERE.parent / ('work/fp-precision-windows' if args.windows else 'work/fp-precision-linux')
    out.mkdir(parents=True, exist_ok=True)
    cases = generate()
    samples = EDGE_COUNT + 256
    per_case = samples * 16 * 2
    source = out / 'fp-precision.S'
    lines = ['.text']
    for name, (instructions, _) in cases.items():
        lines += [f'.global {name}', f'.type {name}, %function', f'{name}:', '.cfi_startproc']
        lines += ['    ' + line for line in instructions]
        lines += ['.cfi_endproc', f'.size {name}, .-{name}']
    source.write_text('\n'.join(lines) + '\n')
    (out / 'fp_generated_cases.h').write_text(''.join(f'CASE({name}, {width})\n' for name, (_, width) in cases.items()))
    (out / 'fp_precision_edges.h').write_text(
        f'#define FP_PRECISION_EDGE_COUNT {EDGE_COUNT}\nstatic const uint32_t precision_edges32[] = {{\n' +
        ''.join(f'UINT32_C({v:#x}),\n' for v in EDGES32) + '};\nstatic const uint64_t precision_edges64[] = {\n' +
        ''.join(f'UINT64_C({v:#x}),\n' for v in EDGES64) + '};\n')
    define = 'FP_CASE_DRIVER="fp_precision_driver.h"'
    reference = out / 'reference'
    build_reference(args.cc, args.reference_root, [HERE / 'fp_compare_ref.c', source], reference, [HERE, out], [define])
    with (out / 'ref.bin').open('wb') as log:
        subprocess.run([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    expected = (out / 'ref.bin').read_bytes()
    if len(expected) != len(cases) * per_case * 24:
        raise RuntimeError('Reference produced an incorrect number of records')
    if args.reference_only:
        print(f'ARM64 precision-conversion reference: {len(cases) * per_case:,} cases')
        return
    if args.lift is None:
        parser.error('--lift is required unless --reference-only is given')
    library = out / 'fp-precision.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib',
                    str(source), '-o', str(library)], check=True)
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out), '--base', '0x50000000',
                    '--lift', str(args.lift), '--cxx', args.cxx, '--target',
                    'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'], check=True)
    manifest = json.loads((out / 'manifest.json').read_text())

    def host_path(path):
        if args.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    cc = args.mingw / 'gcc.exe' if args.windows else args.cc
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([str(cc), '-O2', '-c', host_path(HERE.parent / 'fastaes/elfload.c'), '-o', host_path(loader)], check=True)
    binary = out / ('fp-precision.exe' if args.windows else 'fp-precision')
    command = [str(cxx), '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64', f'-D{define}',
               f'-DFP_COMPARE_LIBRARY="{host_path(library)}"', f'-I{host_path(args.remill / "include")}',
               f'-I{host_path(HERE)}', f'-I{host_path(HERE.parent / "fastaes")}', f'-I{host_path(out)}',
               host_path(HERE / 'fp_compare_test.cpp'), host_path(HERE / 'runtime.cpp'), host_path(loader),
               *[host_path(obj) for obj in manifest['objects']], '-latomic', '-o', host_path(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    with (out / 'recomp.bin').open('wb') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    actual = (out / 'recomp.bin').read_bytes()
    if len(actual) != len(expected):
        raise RuntimeError(f'Output length differs: {len(actual)} vs {len(expected)}')
    failures = [i for i in range(len(expected) // 24) if actual[i * 24:(i + 1) * 24] != expected[i * 24:(i + 1) * 24]]
    if failures:
        names = list(cases)
        for record in failures[:10]:
            case, sub = divmod(record, per_case)
            mode, sub = divmod(sub, samples * 2)
            flags, sample = divmod(sub, samples)
            print(names[case], 'mode', mode, 'initial', flags, 'sample', sample,
                  'ARM64', expected[record * 24:(record + 1) * 24].hex(),
                  'x86', actual[record * 24:(record + 1) * 24].hex())
        raise SystemExit(f'{len(failures):,} precision-conversion cases differ')
    print(f'FP precision conversions: {len(expected) // 24:,} cases match ARM64 QEMU ({len(cases)} register variants, rounding/NaN/underflow/FZ/DN/FPSR modes).')


if __name__ == '__main__':
    main()
