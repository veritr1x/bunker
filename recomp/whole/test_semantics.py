"""Check lane/replicate/structure loads and table lookups against ARM64 QEMU."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import integer_cases
import release_cases
from test_fastaes import build_reference

HERE = Path(__file__).resolve().parent


def generate(out):
    functions = {}

    def load_case(instruction, sp=False):
        prefix = ['ldp q31, q0, [x1, #80]', 'ldp q1, q2, [x1, #96]']
        if sp:
            prefix += ['mov x5, sp', 'sub sp, sp, #128']
            for offset in range(0, 128, 32):
                prefix += [f'ldp q6, q7, [x1, #{offset}]', f'stp q6, q7, [sp, #{offset}]']
            prefix += ['mov x3, sp', instruction, 'mov x4, sp', 'sub x3, x4, x3', 'mov sp, x5']
        else:
            prefix += ['mov x3, x1', instruction, 'sub x3, x1, x3']
        return prefix + ['stp q31, q0, [x0]', 'stp q1, q2, [x0, #32]', 'str x3, [x0, #64]', 'ret']

    for element, lanes, amount in [('b', 16, 1), ('h', 8, 2), ('s', 4, 4), ('d', 2, 8)]:
        for lane in range(lanes):
            for mode, suffix in [('plain', ''), ('imm', f', #{amount}'), ('reg', ', x2')]:
                for sp in (False, True):
                    name = f'ld1_{element}_{lane}_{mode}_{"sp" if sp else "x"}'
                    functions[name] = load_case(f'ld1 {{ v31.{element} }}[{lane}], [{"sp" if sp else "x1"}]{suffix}', sp)
    for arr, amount in [('8b', 1), ('16b', 1), ('4h', 2), ('8h', 2),
                        ('2s', 4), ('4s', 4), ('1d', 8), ('2d', 8)]:
        for mode, suffix in [('plain', ''), ('imm', f', #{amount}'), ('reg', ', x2')]:
            for sp in (False, True):
                name = f'ld1r_{arr}_{mode}_{"sp" if sp else "x"}'
                functions[name] = load_case(f'ld1r {{ v31.{arr} }}, [{"sp" if sp else "x1"}]{suffix}', sp)

    arrangements = [('8b', 32), ('16b', 64), ('4h', 32), ('8h', 64),
                    ('2s', 32), ('4s', 64), ('2d', 64)]
    for arr, amount in arrangements:
        registers = ', '.join(f'v{r}.{arr}' for r in [31, 0, 1, 2])
        for op in ('ld4', 'st4'):
            for mode, suffix in [('plain', ''), ('imm', f', #{amount}'), ('reg', ', x2')]:
                name = f'{op}_{arr}_{mode}'
                if op == 'ld4':
                    instructions = ['ldp q31, q0, [x1, #80]', 'ldp q1, q2, [x1, #96]', 'mov x3, x1',
                        f'ld4 {{ {registers} }}, [x1]{suffix}', 'stp q31, q0, [x0]',
                        'stp q1, q2, [x0, #32]', 'sub x3, x1, x3', 'str x3, [x0, #64]', 'ret']
                else:
                    instructions = ['ldp q31, q0, [x1]', 'ldp q1, q2, [x1, #32]',
                        'add x3, x0, #16', 'mov x4, x3', f'st4 {{ {registers} }}, [x3]{suffix}',
                        'sub x3, x3, x4', 'str x3, [x0, #96]', 'ret']
                functions[name] = instructions
    for op in ('tbl', 'tbx'):
        for lanes in (8, 16):
            for count in range(1, 5):
                registers = ', '.join(f'v{r}.16b' for r in [31, 0, 1, 2][:count])
                for mode, dst in [('normal', 5), ('table_overlap', 31), ('index_overlap', 4)]:
                    name = f'{op}_{lanes}_{count}_{mode}'
                    functions[name] = ['ldp q31, q0, [x1]', 'ldp q1, q2, [x1, #32]',
                        'ldr q4, [x1, #64]', 'ldr q5, [x1, #80]',
                        f'{op} v{dst}.{lanes}b, {{ {registers} }}, v4.{lanes}b',
                        f'str q{dst}, [x0]', 'stp q31, q0, [x0, #16]',
                        'stp q1, q2, [x0, #48]', 'str q4, [x0, #80]', 'ret']
    additional = integer_cases.generate()
    if functions.keys() & additional.keys():
        raise RuntimeError('Duplicate generated instruction case names')
    functions.update(additional)
    functions.update(release_cases.generate())
    lines = ['.text']
    for name, instructions in functions.items():
        lines += [f'.global {name}', f'.type {name}, %function', f'{name}:', '.cfi_startproc']
        lines += ['    ' + instruction for instruction in instructions]
        lines += ['.cfi_endproc', f'.size {name}, .-{name}']
    source = out / 'semantics.S'
    source.write_text('\n'.join(lines) + '\n')
    (out / 'generated_cases.h').write_text(''.join(f'CASE({name})\n' for name in functions))
    return source, len(functions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--windows', action='store_true', help='Run the lifted code as a native Windows executable')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    out = HERE.parent / ('work/windows-semantics' if args.windows else 'work/whole-semantics')
    out.mkdir(parents=True, exist_ok=True)
    source, count = generate(out)
    library = out / 'semantics.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib',
                    str(source), '-o', str(library)], check=True)
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out),
                    '--base', '0x30000000', '--lift', str(args.lift), '--cxx', args.cxx,
                    '--target', 'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'], check=True)
    manifest = json.loads((out / 'manifest.json').read_text())

    def host_path(path):
        if args.windows:
            return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
        return str(path)

    host_cc = str(args.mingw / 'gcc.exe') if args.windows else args.cc
    host_cxx = str(args.mingw / 'g++.exe') if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([host_cc, '-O2', '-c', host_path(HERE.parent / 'fastaes/elfload.c'), '-o', host_path(loader)], check=True)
    binary = out / ('recomp.exe' if args.windows else 'recomp')
    command = [host_cxx, '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64',
               f'-DSEMANTIC_LIB="{host_path(library)}"', f'-I{host_path(args.remill / "include")}', f'-I{host_path(HERE)}',
               f'-I{host_path(HERE.parent / "fastaes")}', f'-I{host_path(out)}', host_path(HERE / 'semantic_test.cpp'),
               host_path(HERE / 'runtime.cpp'), host_path(loader), *[host_path(p) for p in manifest['objects']],
               '-latomic', '-o', host_path(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    reference = out / 'reference'
    build_reference(args.cc, args.reference_root, [HERE / 'semantic_ref.c', source], reference, [HERE, out])
    with (out / 'recomp.txt').open('w') as log:
        subprocess.run([str(binary)], stdout=log, check=True)
    with (out / 'ref.txt').open('w') as log:
        subprocess.run([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)], stdout=log, check=True)
    native, lifted = (out / 'ref.txt').read_text().splitlines(), (out / 'recomp.txt').read_text().splitlines()
    if len(native) != count * 256 or len(native) != len(lifted):
        raise RuntimeError('Reference or recompiled output has an incorrect case count')
    failures = [(a, b) for a, b in zip(native, lifted) if a != b]
    if failures:
        for a, b in failures[:5]:
            print('ARM64:', a, '\nx86:  ', b)
        raise SystemExit(f'{len(failures)} semantic cases differ')
    print(f'{len(native):,} instruction cases match ARM64 QEMU ({count} instruction/register variants).')


if __name__ == '__main__':
    main()
