"""Regress Unity's masked W/X index and constant table base across loop cases."""
import argparse
import json
from pathlib import Path
import subprocess

from elftools.elf.elffile import ELFFile
from jump_tables import recover
from test_fastaes import build_reference
from test_jump_tables import compile_with_recovery

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--cc', default='clang-18')
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    root = HERE.parent / f'work/masked-jump-tables-{"windows" if args.windows else "linux"}'
    root.mkdir(parents=True, exist_ok=True)
    source = HERE / 'masked_switch_fixture.S'
    library = root / 'switch.so'
    for define in ('', 'MASK_SOURCE_CLOBBER', 'MASK_DIFFERENT_WIDTH', 'MASK_CASE_BASE_CLOBBER', 'MASK_GUARD_BYPASS'):
        destination = library if not define else root / f'{define}.so'
        subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib', '-Wl,--no-relax',
                        *([f'-D{define}'] if define else []), str(source), '-o', str(destination)], check=True)
        with destination.open('rb') as stream:
            report = recover(ELFFile(stream))
        if define:
            assert not report['entries'] and report['unresolved'], (define, report)
            print(define, 'rejected', flush=True)
        else:
            assert len(report['tables']) == 1 and len(report['entries']) == 3 and not report['unresolved'], report
            assert report['tables'][0]['count'] == 5 and report['tables'][0]['closed_cfg'], report
            assert all(address < report['tables'][0]['table'] for address in report['entries']), report
    reference = root / 'reference'
    build_reference(args.cc, args.reference_root, [HERE / 'masked_switch_ref.c', source], reference, [HERE])
    expected = subprocess.check_output([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)])
    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    cc = args.mingw / 'gcc.exe' if args.windows else args.cc
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    loader = root / 'elfload.o'
    subprocess.run([str(cc), '-O2', '-c', host(HERE.parent / 'fastaes/elfload.c'), '-o', host(loader)], check=True)
    for recovery in (False, True):
        out = root / ('recovered' if recovery else 'baseline')
        compile_with_recovery(library, out, args.lift, args.cxx, args.windows, recovery)
        manifest = json.loads((out / 'manifest.json').read_text())
        binary = out / ('masked.exe' if args.windows else 'masked')
        command = [str(cxx), '-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64', f'-DSWITCH_LIBRARY="{host(library)}"',
                   f'-I{host(HERE.parent / "work/remill-src/include")}', f'-I{host(HERE)}', f'-I{host(HERE.parent / "fastaes")}',
                   f'-I{host(out)}', host(HERE / 'masked_switch_test.cpp'), host(HERE / 'runtime.cpp'), host(loader),
                   *[host(path) for path in manifest['objects']], '-latomic', '-o', host(binary)]
        if args.windows:
            command.insert(1, '-static')
        subprocess.run(command, check=True)
        result = subprocess.run([str(binary)], capture_output=True)
        if recovery:
            assert result.returncode == 0, result.stderr
            assert result.stdout == expected, 'Recovered masked switch differs from ARM64'
            print(f'Masked switch: {len(expected)//8:,} cases match ARM64 QEMU; closed CFG verified.', flush=True)
        else:
            assert result.returncode and b'unresolved indirect target' in result.stderr, result.stderr
            print('Baseline reproduces unresolved masked switch case:', result.stderr.decode().strip(), flush=True)


if __name__ == '__main__':
    main()
