"""Check constant callback proofs and actual translated, stripped teardown."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import FDE
from callback_roots import recover

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path)
    parser.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    parser.add_argument('--analysis-only', action='store_true')
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--cc', default='clang-18')
    parser.add_argument('--cxx', default='clang++-18')
    args = parser.parse_args()
    out = HERE.parent / ('work/callback-windows' if args.windows else 'work/callback-linux')
    out.mkdir(parents=True, exist_ok=True)
    variants = ['', 'PADDED_PLT', 'UNKNOWN', 'MIXED', 'CLOBBER', 'NONEXEC', 'MISALIGNED', 'WRONG_IMPORT', 'W_CLOBBER', 'TRUNCATED', 'NUMERIC']
    valid = []
    for variant in variants:
        library = out / f'{variant or "normal"}.so'
        subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-shared', '-nostdlib',
                        '-Wl,--no-relax,--strip-all', *([f'-DCALLBACK_{variant}'] if variant else []),
                        str(HERE / 'callback_fixture.S'), '-o', str(library)], check=True)
        if variant == 'NUMERIC':
            raw = bytearray(library.read_bytes())
            with library.open('rb') as stream:
                elf = ELFFile(stream)
                text = elf.get_section_by_name('.text')
                entry = next(s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name == 'callback_register')
                # The tiny destructor follows exactly the three registration
                # instructions. Confirm the candidate is genuinely executable.
                address = entry + 12
                assert text['sh_addr'] <= address < text['sh_addr'] + text['sh_size']
                position = text['sh_offset'] + entry - text['sh_addr']
                for index, value in enumerate((address & 0xffff, address >> 16)):
                    offset = position + index * 4
                    word = int.from_bytes(raw[offset:offset + 4], 'little')
                    raw[offset:offset + 4] = ((word & ~(0xffff << 5)) | (value << 5)).to_bytes(4, 'little')
            library.write_bytes(raw)
        with library.open('rb') as stream:
            elf = ELFFile(stream)
            assert elf.get_section_by_name('.symtab') is None, 'Fixture retained local symbols'
            report = recover(elf)
            if variant in ('', 'PADDED_PLT'):
                symbols = {symbol['st_value'] for symbol in elf.get_section_by_name('.dynsym').iter_symbols()}
                bounds = [(record['initial_location'], record['initial_location'] + record['address_range'])
                          for record in elf.get_dwarf_info().EH_CFI_entries() if isinstance(record, FDE)]
                assert all(address not in symbols and not any(lo <= address < hi for lo, hi in bounds)
                           for address in report['entries']), 'Destructor retained a symbol or containing FDE'
                if variant == 'PADDED_PLT':
                    # Loading only W17 truncates the relocated function pointer;
                    # a real GOT relocation alone cannot prove this is a valid
                    # LP64 import stub. Its callback must not become a root.
                    broken = bytearray(library.read_bytes())
                    position = elf.get_section_by_name('.plt.custom')['sh_offset'] + 4
                    word = int.from_bytes(broken[position:position + 4], 'little')
                    broken[position:position + 4] = (word & ~(1 << 30)).to_bytes(4, 'little')
                    rejected = recover(ELFFile(io.BytesIO(broken)))
                    assert len(rejected['entries']) == 2 and len(rejected['registrations']) == 2, rejected
        if variant in ('', 'PADDED_PLT'):
            assert len(report['entries']) == 3 and len(report['registrations']) == 3 and not report['unresolved'], report
            assert {r['api'] for r in report['registrations']} == {'atexit', '__cxa_atexit'}
            assert all(r['proof']['definitions'] and r['proof']['got'] for r in report['registrations'])
            valid.append((variant or 'normal', library, report))
        elif variant == 'WRONG_IMPORT':
            assert not report['entries'] and not report['registrations'] and not report['unresolved'], report
        else:
            assert not report['entries'] and not report['registrations'] and len(report['unresolved']) == 1, (variant, report)
            if variant == 'NUMERIC':
                assert 'not proven load-base-relative' in report['unresolved'][0]['reason'], report
        print(f'{variant or "normal"}: {len(report["entries"])} roots, {len(report["unresolved"])} unresolved', flush=True)
    if args.analysis_only:
        return
    if args.lift is None:
        parser.error('--lift required for native tests')

    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)

    # The parent owns compile.py integration. Override only inspect for the
    # baseline so it cannot silently regain callbacks through default recovery.
    spec = importlib.util.spec_from_file_location('callback_compiler', HERE / 'compile.py')
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    original = compiler.inspect
    cc = '/mnt/c/mingw64/bin/gcc.exe' if args.windows else args.cc
    cxx = '/mnt/c/mingw64/bin/g++.exe' if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)], check=True)
    for name, library, report in valid:
        for recovered in (False, True):
            destination = out / name / ('recovered' if recovered else 'baseline')

            def inspect(path, base, **options):
                options['recover_callbacks'] = False
                image, start, entries, manifest = original(path, base, **options)
                if recovered:
                    entries = sorted(set(entries) | {base + address for address in report['entries']})
                    manifest['callback_roots'] = report
                return image, start, entries, manifest

            compiler.inspect = inspect
            previous = sys.argv
            try:
                sys.argv = [str(HERE / 'compile.py'), str(library), '--out', str(destination), '--lift', str(args.lift),
                            '--cxx', args.cxx, '--base', '0x54000000', '--target',
                            'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu']
                compiler.main()
            finally:
                sys.argv = previous
            manifest = json.loads((destination / 'manifest.json').read_text())
            seeds = set(manifest['traces'])
            roots = {0x54000000 + address for address in report['entries']}
            assert roots <= seeds if recovered else roots.isdisjoint(seeds), 'Fixture callbacks were already baseline trace roots'
            binary = destination / ('teardown.exe' if args.windows else 'teardown')
            command = [cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
                       f'-DCALLBACK_LIBRARY="{hp(library)}"',
                       f'-DCALLBACK_DSO={0x54000000 + next(r["dso"] for r in report["registrations"] if r["dso"] is not None):#x}',
                       f'-I{hp(args.remill / "include")}', f'-I{hp(destination)}',
                       hp(HERE / 'callback_test.cpp'), hp(HERE.parent / 'windows/libc.cpp'), hp(HERE / 'runtime.cpp'),
                       hp(loader), *[hp(obj) for obj in manifest['objects']], '-latomic', '-o', hp(binary)]
            if args.windows:
                command.insert(1, '-static')
            subprocess.run(command, check=True)
            result = subprocess.run([str(binary)], capture_output=True)
            if recovered:
                assert result.returncode == 0, result.stderr
                print(name, result.stdout.decode().strip(), flush=True)
            else:
                assert result.returncode and b'not a registered translated entry' in result.stderr and b'__cxa_finalize callback=' in result.stderr, result.stderr
                print(name, 'baseline reproduces missing destructor entry at teardown', flush=True)


if __name__ == '__main__':
    main()
