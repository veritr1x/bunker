"""Prepare Windows objects for real libmain + a clearly synthetic Unity fixture."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from inventory import elf_inventory

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libmain', type=Path, required=True)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=HERE.parent / 'work/windows-loader')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    synthetic = out / 'synthetic-unity.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-ffreestanding',
                    '-fPIC', '-shared', '-nostdlib', '-O1', '-funwind-tables',
                    str(HERE / 'synthetic_unity.c'), '-o', str(synthetic)], check=True)
    for name, library, base in [('main', args.libmain, 0x40000000), ('unity', synthetic, 0x50000000)]:
        target = out / name
        subprocess.run([sys.executable, str(HERE.parent / 'whole/compile.py'), str(library),
                        '--out', str(target), '--lift', str(args.lift), '--base', hex(base),
                        '--target', 'x86_64-w64-windows-gnu', '--cxx', args.cxx], check=True)
        shutil.copyfile(target / 'traces.h', out / f'{name}_traces.h')
    shutil.copyfile(args.libmain, out / 'libmain.so')
    info = elf_inventory(synthetic)
    (out / 'synthetic_inventory.json').write_text(json.dumps(info, indent=2) + '\n')
    (out / 'synthetic_finalizers.h').write_text('static const addr_t kUnityFinalizers[] = {\n' +
        ''.join(f'  {0x50000000 + entry:#x},\n' for entry in info['finalizers'] if entry) + '};\n')
    print(f'Prepared real libmain + synthetic Unity loader fixture at {out}')


if __name__ == '__main__':
    main()
