"""Regress switch dispatch joins whose incoming paths have separate guards."""
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
    root = HERE.parent / f'work/joined-jump-tables-{"windows" if args.windows else "linux"}'
    root.mkdir(parents=True, exist_ok=True)
    source = HERE / 'joined_switch_fixture.S'
    variants = ['', 'MULTI_NARROWER_PATH', 'MULTI_UNGUARDED_PATH', 'MULTI_DIFFERENT_BOUND',
                'MULTI_INDEX_CLOBBER', 'MULTI_SOURCE_MISMATCH']
    libraries = []
    for define in variants:
        destination = root / f'{define or "normal"}.so'
        subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib', '-Wl,--no-relax',
                        *([f'-D{define}'] if define else []), str(source), '-o', str(destination)], check=True)
        with destination.open('rb') as stream:
            report = recover(ELFFile(stream))
        if define and define != 'MULTI_NARROWER_PATH':
            assert not report['entries'] and report['unresolved'], (define, report)
            print(define, 'rejected', flush=True)
        else:
            assert len(report['tables']) == 1 and len(report['entries']) == 21 and not report['unresolved'], report
            assert report['tables'][0]['count'] == 21 and len(report['tables'][0]['guards']) == 3, report
            libraries.append((define, destination))
    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    cc = args.mingw / 'gcc.exe' if args.windows else args.cc
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    loader = root / 'elfload.o'
    subprocess.run([str(cc), '-O2', '-c', host(HERE.parent / 'fastaes/elfload.c'), '-o', host(loader)], check=True)
    for define, library in libraries:
        directory = root / (define or 'normal')
        directory.mkdir(exist_ok=True)
        reference = directory / 'reference'
        build_reference(args.cc, args.reference_root, [HERE / 'masked_switch_ref.c', source], reference, [HERE],
                        ['SWITCH_MULTI_GUARD'] + ([define] if define else []))
        expected = subprocess.check_output([str(args.reference_root / 'usr/bin/qemu-aarch64-static'), str(reference)])
        for recovery in (False, True):
            out = directory / ('recovered' if recovery else 'baseline')
            compile_with_recovery(library, out, args.lift, args.cxx, args.windows, recovery)
            manifest = json.loads((out / 'manifest.json').read_text())
            binary = out / ('joined.exe' if args.windows else 'joined')
            command = [str(cxx), '-O2', '-std=c++17', '-DSWITCH_MULTI_GUARD', '-DADDRESS_SIZE_BITS=64',
                       f'-DSWITCH_LIBRARY="{host(library)}"', f'-I{host(HERE.parent / "work/remill-src/include")}',
                       f'-I{host(HERE)}', f'-I{host(HERE.parent / "fastaes")}', f'-I{host(out)}',
                       host(HERE / 'masked_switch_test.cpp'), host(HERE / 'runtime.cpp'), host(loader),
                       *[host(path) for path in manifest['objects']], '-latomic', '-o', host(binary)]
            if args.windows:
                command.insert(1, '-static')
            subprocess.run(command, check=True)
            result = subprocess.run([str(binary)], capture_output=True)
            if recovery:
                assert result.returncode == 0, result.stderr
                assert result.stdout == expected, 'Recovered joined switch differs from ARM64'
                print(f'{define or "normal"}: {len(expected)//8:,} cases match ARM64 QEMU; all three incoming ranges verified.', flush=True)
            else:
                assert result.returncode and b'unresolved indirect target' in result.stderr, result.stderr
                print(define or 'normal', 'baseline reproduces unresolved case', flush=True)


if __name__ == '__main__':
    main()
