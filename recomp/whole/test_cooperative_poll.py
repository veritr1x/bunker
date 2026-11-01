"""Opt-in compiler/runtime polls, optimized State escape and cycle-cut checks."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def check_cycle_cuts(instrument, out):
    output=out/'cfg.poll.ll'
    subprocess.run([str(instrument),str(HERE/'poll_cfg_fixture.ll'),str(output)],check=True)
    text=output.read_text()
    assert all(word not in text for word in ('nounwind','nosync','willreturn','memory(none)','readnone','nocapture'))
    for body in re.findall(r'^define[^\n]*@sub_[0-9a-f]+\([^\n]*\).*?^}',text,re.M|re.S):
        blocks={}
        for match in re.finditer(r'^([a-zA-Z0-9_.]+):[^\n]*\n(.*?)(?=^[a-zA-Z0-9_.]+:|^})',body,re.M|re.S):
            blocks[match[1]]=match[2]
        assert blocks
        # Independently remove all blocks containing a fast poll and prove the
        # remaining CFG acyclic. This includes the multi-entry and dead SCCs.
        graph={name:re.findall(r'label %([a-zA-Z0-9_.]+)',code) for name,code in blocks.items()
               if '@__bunker_guest_poll_requested' not in code}
        color={}
        def visit(node):
            if node not in graph:return
            assert color.get(node)!=1, 'An unpolled CFG cycle remains'
            if color.get(node)==2:return
            color[node]=1
            for successor in graph[node]:visit(successor)
            color[node]=2
        for node in graph:visit(node)
    rejected=subprocess.run([str(instrument),str(output),str(out/'double.ll')],capture_output=True,text=True)
    assert rejected.returncode and 'already contains' in rejected.stderr
    print('Irreducible/disconnected CFG cycles are cut; stale effects removed; double instrumentation rejected.',flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cc', default='clang-18')
    p.add_argument('--cxx', default='clang++-18')
    p.add_argument('--windows', action='store_true')
    args = p.parse_args()
    out = HERE.parent / ('work/cooperative-poll-windows' if args.windows else 'work/cooperative-poll-linux')
    out.mkdir(parents=True, exist_ok=True)
    instrument = out / 'instrument'
    subprocess.run([sys.executable,str(HERE/'build_poll_instrument.py'),'--cxx',args.cxx,'--out',str(instrument)],check=True)
    check_cycle_cuts(instrument,out)
    library = out / 'safepoint.so'
    subprocess.run([args.cc, '--target=aarch64-linux-gnu', '-fuse-ld=lld', '-nostdlib', '-shared',
                    str(HERE / 'safepoint_fixture.S'), '-o', str(library)], check=True)
    target = 'x86_64-w64-windows-gnu' if args.windows else 'x86_64-linux-gnu'
    subprocess.run([sys.executable, str(HERE / 'compile.py'), str(library), '--out', str(out / 'guest'), '--lift', str(args.lift),
                    '--cxx', args.cxx, '--base', '0x56000000', '--target', target,'--poll-instrument',str(instrument)], check=True)
    manifest = json.loads((out / 'guest/manifest.json').read_text())
    assert not manifest['imports'] and not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    assert manifest['cooperative_polls'] and len(manifest['toolchain']['poll_instrument'])==64
    objects = []
    for original in map(Path, manifest['objects']):
        source = original.with_suffix('.ll')
        optimized = original.with_suffix('.poll.O2.ll')
        subprocess.run([args.cxx, '-target', target, '-O2', '-Wno-override-module', '-S', '-emit-llvm', str(source), '-o', str(optimized)], check=True)
        text = optimized.read_text()
        fast_calls = re.findall(r'\bcall\b[^\n]*@__bunker_guest_poll_requested\(', text)
        slow_calls = re.findall(r'\bcall\b[^\n]*@__bunker_guest_poll_slow\(ptr[^\n]*', text)
        assert len(fast_calls) >= 2 and len(slow_calls) >= 2, 'Entry/backedge checks or explicit State-pointer barriers were eliminated'
        assert not re.search(r'\bcall\b[^\n]*@__remill_(?:flag_computation|compare_)', text), 'Opaque identity helpers still provide accidental loop barriers'
        declarations = [line for line in text.splitlines() if line.startswith('declare') and '__bunker_guest_poll_' in line]
        assert len(declarations) == 2 and all('memory(none)' not in line and 'speculatable' not in line for line in declarations)
        disassembly = subprocess.check_output(['llvm-objdump-18', '-dr', str(original)], text=True)
        original.with_suffix('.disassembly.txt').write_text(disassembly)
        assert disassembly.count('__bunker_guest_poll_requested') >= 2 and disassembly.count('__bunker_guest_poll_slow') >= 2, 'Native object lost poll calls'
        objects.append(original)

    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    cc = '/mnt/c/mingw64/bin/gcc.exe' if args.windows else args.cc
    cxx = '/mnt/c/mingw64/bin/g++.exe' if args.windows else args.cxx
    loader = out / 'elfload.o'
    subprocess.run([cc, '-O2', '-c', hp(HERE.parent / 'fastaes/elfload.c'), '-o', hp(loader)], check=True)
    binary = out / ('safepoint.exe' if args.windows else 'safepoint')
    command = [cxx, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-I{hp(args.remill / "include")}',
               f'-I{hp(out / "guest")}', f'-DSAFEPOINT_LIBRARY="{hp(library)}"',
               hp(HERE / 'cooperative_poll_test.cpp'), hp(HERE / 'cooperative_poll.cpp'), hp(HERE / 'runtime.cpp'),
               hp(loader), *map(hp, objects), '-pthread', '-latomic', '-o', hp(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    subprocess.run([str(binary)], check=True, timeout=45)
    print('Opt-in compiler/runtime LLVM18 -O2 IR/native poll retention verified; no signal delivery or GC integration.')


if __name__ == '__main__':
    main()
