"""Isolated LLVM18 -O2 State materialization; no signal/GC implementation."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--windows', action='store_true')
    args = p.parse_args()
    out = HERE.parent / ('work/safepoint-windows' if args.windows else 'work/safepoint-linux')
    out.mkdir(parents=True, exist_ok=True)
    flags = shlex.split(subprocess.check_output(['llvm-config-18', '--cxxflags', '--ldflags', '--system-libs',
                                                '--libs', 'core', 'irreader', 'analysis', 'transformutils'], text=True))
    instrument = out / 'instrument'
    subprocess.run([args.cxx, str(HERE / 'safepoint_instrument.cpp'), *flags, '-std=c++17', '-O2', '-o', str(instrument)], check=True)
    library = out / 'safepoint.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-nostdlib', '-shared',
                    str(HERE / 'safepoint_fixture.S'), '-o', str(library)], check=True)
    target = 'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out / 'guest'), '--lift', str(args.lift),
                    '--cxx', args.cxx, '--base', '0x56000000', '--target', target], check=True)
    manifest = json.loads((out / 'guest/manifest.json').read_text())
    assert not manifest['imports'] and not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    objects = []
    for original in map(Path, manifest['objects']):
        source = original.with_suffix('.ll')
        modified = original.with_suffix('.poll.ll')
        optimized = original.with_suffix('.poll.O2.ll')
        obj = original.with_suffix('.poll.o')
        subprocess.run([str(instrument), str(source), str(modified)], check=True)
        subprocess.run([args.cxx, '-target', target, '-O2', '-Wno-override-module', '-S', '-emit-llvm', str(modified), '-o', str(optimized)], check=True)
        text = optimized.read_text()
        fast_calls = re.findall(r'\bcall\b[^\n]*@__bunker_poll_requested\(', text)
        slow_calls = re.findall(r'\bcall\b[^\n]*@__bunker_poll_slow\(ptr[^\n]*', text)
        assert len(fast_calls) >= 2 and len(slow_calls) >= 2, 'Entry/backedge checks or explicit State-pointer barriers were eliminated'
        assert not re.search(r'\bcall\b[^\n]*@__remill_(?:flag_computation|compare_)', text), 'Opaque identity helpers still provide accidental loop barriers'
        declarations = [line for line in text.splitlines() if line.startswith('declare') and '__bunker_poll_' in line]
        assert len(declarations) == 2 and all('memory(none)' not in line and 'speculatable' not in line for line in declarations)
        subprocess.run([args.cxx, '-target', target, '-O2', '-Wno-override-module', '-c', str(optimized), '-o', str(obj)], check=True)
        disassembly = subprocess.check_output(['llvm-objdump-18', '-dr', str(obj)], text=True)
        obj.with_suffix('.disassembly.txt').write_text(disassembly)
        assert disassembly.count('__bunker_poll_requested') >= 2 and disassembly.count('__bunker_poll_slow') >= 2, 'Native object lost poll calls'
        objects.append(obj)

    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    cc = '/mnt/c/mingw64/bin/gcc.exe' if args.windows else args.cc
    cxx = '/mnt/c/mingw64/bin/g++.exe' if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)], check=True)
    binary = out / ('safepoint.exe' if args.windows else 'safepoint')
    command = [cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-I{hp(args.remill / "include")}',
               f'-I{hp(out / "guest")}', f'-DSAFEPOINT_LIBRARY="{hp(library)}"',
               hp(HERE / 'safepoint_test.cpp'), hp(HERE / 'safepoint_control.cpp'), hp(HERE / 'runtime.cpp'),
               hp(loader), *map(hp, objects), '-pthread', '-latomic', '-o', hp(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    subprocess.run([str(binary)], check=True, timeout=45)
    print('LLVM18 -O2 IR/native poll retention verified; this is a cooperative materialization experiment, not signal delivery or GC correctness.')


if __name__ == '__main__':
    main()
