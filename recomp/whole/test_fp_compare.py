"""Check floating compare values and cumulative FPSR against ARM64 QEMU."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

from fp_compare_cases import generate
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
    parser.add_argument('--family', choices=['compare', 'minmax', 'arith', 'recip'], default='compare')
    args = parser.parse_args()
    case_generator = generate
    if args.family == 'minmax':
        from fp_minmax_cases import generate as case_generator
    elif args.family == 'arith':
        from fp_arith_extra_cases import generate as case_generator
    elif args.family == 'recip':
        from fp_recip_steps_cases import generate as case_generator
    edges, modes = (38, 16) if args.family in ('arith', 'recip') else (20, 4)
    edge_records_per_case = modes * 2 * edges * edges
    random_cases = 512 if args.family == 'recip' else 0
    records_per_case = edge_records_per_case + modes * 2 * random_cases
    driver_define = ['FP_CASE_DRIVER="fp_arith_extra_driver.h"'] if args.family in ('arith', 'recip') else []
    if random_cases:
        driver_define += [f'FP_RECIP_RANDOM_CASES={random_cases}']
    out = HERE.parent / f'work/fp-{args.family}-{"windows" if args.windows else "linux"}'
    out.mkdir(parents=True, exist_ok=True)
    cases = case_generator()
    source = out / 'fp-compare.S'
    lines = ['.text']
    for name, (instructions, _) in cases.items():
        lines += [f'.global {name}', f'.type {name}, %function', f'{name}:', '.cfi_startproc']
        lines += ['    ' + line for line in instructions]
        lines += ['.cfi_endproc', f'.size {name}, .-{name}']
    source.write_text('\n'.join(lines) + '\n')
    (out / 'fp_generated_cases.h').write_text(''.join(f'CASE({name}, {width})\n' for name, (_, width) in cases.items()))
    reference = out / 'reference'
    build_reference(args.cc, args.reference_root, [HERE / 'fp_compare_ref.c', source], reference, [HERE, out], driver_define)
    with (out / 'ref.bin').open('wb') as log:
        subprocess.run([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    expected = (out / 'ref.bin').read_bytes()
    if len(expected) != len(cases) * records_per_case * 24:
        raise RuntimeError('Reference produced an incorrect number of records')
    if args.reference_only:
        print(f'ARM64 reference ready: {len(cases) * records_per_case:,} cases in {out / "ref.bin"}')
        # A short probe report: scalar first lane qNaN/sNaN and subnormal flags.
        names = list(cases)
        probe_names = ('fcmeq_s_reg_normal', 'fcmgt_s_reg_normal', 'fcmge_s_reg_normal') if args.family == 'compare' else ('fmin_s_normal', 'fmax_s_normal', 'fmin_d_normal', 'fmax_d_normal')
        probes = ((0, 14, 2), (0, 17, 2), (1, 4, 0), (1, 4, 14)) if args.family == 'compare' else (
            (0, 0, 1), (0, 1, 0), (0, 16, 14), (0, 14, 16),
            (0, 14, 17), (0, 17, 16), (0, 17, 18),
            (1, 4, 0), (1, 5, 0), (1, 4, 16), (1, 4, 17),
            (2, 16, 2), (3, 4, 17))
        if args.family == 'arith':
            probe_names = ('fnmul_s_normal', 'fabd_s_normal', 'fsqrt_s_normal')
            probes = ((0, 16, 2), (0, 17, 2), (0, 14, 17), (0, 17, 18),
                      (2, 16, 2), (0, 0, 12), (0, 1, 2), (4, 20, 20), (8, 20, 20),
                      (0, 8, 22), (1, 8, 22), (0, 8, 26), (1, 8, 26),
                      (4, 3, 34), (4, 2, 35), (0, 24, 8), (1, 24, 8), (1, 5, 0), (4, 30, 0))
        elif args.family == 'recip':
            probe_names = ('frecps_s_normal', 'frsqrts_s_normal')
            probes = ((0, 16, 2), (0, 17, 2), (0, 14, 17), (0, 17, 18),
                      (0, 15, 2), (0, 2, 15), (2, 16, 2),
                      (0, 0, 12), (0, 1, 13), (1, 4, 12),
                      (0, 10, 28), (4, 10, 28), (8, 10, 28),
                      (0, 4, 4), (4, 4, 4), (8, 4, 4), (12, 4, 4),
                      (0, 2, 28), (8, 2, 28), (0, 2, 30), (8, 2, 30))
        for name in probe_names:
            case = names.index(name)
            for mode, a, b in probes:
                record = case * records_per_case + mode * 2 * edges * edges + a * edges + b
                result, flags = expected[record * 24:record * 24 + 16], struct.unpack_from('<Q', expected, record * 24 + 16)[0]
                print(name, 'mode', mode, 'a,b', a, b, 'result', result.hex(), 'FPSR', hex(flags))
        return
    if args.lift is None:
        parser.error('--lift is required unless --reference-only is given')
    library = out / 'fp-compare.so'
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
    binary = out / ('fp-compare.exe' if args.windows else 'fp-compare')
    command = [str(cxx), '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64',
               *[f'-D{define}' for define in driver_define],
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
            case, sub = divmod(record, records_per_case)
            if sub >= edge_records_per_case:
                mode, sub = divmod(sub - edge_records_per_case, 2 * random_cases)
                flags, sample = divmod(sub, random_cases)
                print(names[case], 'mode', mode, 'initial', flags, 'random sample', sample,
                      'ARM64', expected[record * 24:(record + 1) * 24].hex(),
                      'x86', actual[record * 24:(record + 1) * 24].hex())
                continue
            mode, sub = divmod(sub, 2 * edges * edges)
            flags, sub = divmod(sub, edges * edges)
            a, b = divmod(sub, edges)
            print(names[case], 'mode', mode, 'initial', flags, 'edge a,b', a, b,
                  'ARM64', expected[record * 24:(record + 1) * 24].hex(),
                  'x86', actual[record * 24:(record + 1) * 24].hex())
        raise SystemExit(f'{len(failures):,} FP {args.family} cases differ')
    print(f'Floating {args.family}: {len(expected) // 24:,} cases match ARM64 QEMU ({len(cases)} register variants, FPCR/FPSR modes).')


if __name__ == '__main__':
    main()
