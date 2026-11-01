"""Compare complete integer SIMD multiply-family state snapshots with ARM64."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from multiply_cases import generate
from test_fastaes import build_reference

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--cc',default='clang-18');parser.add_argument('--cxx',default='clang++-18')
    parser.add_argument('--windows',action='store_true')
    parser.add_argument('--mingw',type=Path,default=Path('/mnt/c/mingw64/bin'))
    args=parser.parse_args()
    out=HERE.parent/f'work/integer-multiply-{"windows" if args.windows else "linux"}'
    out.mkdir(parents=True,exist_ok=True)
    cases=generate()
    lines=['.text']
    for name,instructions in cases.items():
        lines += [f'.global {name}',f'.type {name}, %function',f'{name}:','.cfi_startproc']
        lines += ['    '+instruction for instruction in instructions]
        lines += ['.cfi_endproc',f'.size {name}, .-{name}']
    source=out/'multiply.S';source.write_text('\n'.join(lines)+'\n')
    (out/'generated_cases.h').write_text(''.join(f'CASE({name})\n'for name in cases))
    library=out/'multiply.so'
    subprocess.run([args.cc,'--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',str(source),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(library),'--out',str(out),'--base','0x30000000',
                    '--lift',str(args.lift),'--cxx',args.cxx,'--target',
                    'x86_64-w64-windows-gnu'if args.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'manifest.json').read_text())
    def host(path):
        return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if args.windows else str(path)
    cc=args.mingw/'gcc.exe'if args.windows else args.cc
    cxx=args.mingw/'g++.exe'if args.windows else args.cxx
    loader=out/'elfload.o'
    subprocess.run([str(cc),'-O2','-c',host(HERE.parent/'fastaes/elfload.c'),'-o',host(loader)],check=True)
    binary=out/('multiply.exe'if args.windows else'multiply')
    command=[str(cxx),'-O2','-std=c++17','-DADDRESS_SIZE_BITS=64',f'-DSEMANTIC_LIB="{host(library)}"',
             f'-I{host(args.remill/"include")}',f'-I{host(HERE)}',f'-I{host(HERE.parent/"fastaes")}',f'-I{host(out)}',
             host(HERE/'semantic_test.cpp'),host(HERE/'runtime.cpp'),host(loader),
             *[host(p)for p in manifest['objects']],'-latomic','-o',host(binary)]
    if args.windows:command.insert(1,'-static')
    subprocess.run(command,check=True)
    reference=out/'reference'
    build_reference(args.cc,args.reference_root,[HERE/'semantic_ref.c',source],reference,[HERE,out])
    with(out/'actual.txt').open('w')as log:subprocess.run([str(binary)],stdout=log,check=True)
    with(out/'expected.txt').open('w')as log:
        subprocess.run([str(args.reference_root/'usr/bin/qemu-aarch64-static'),str(reference)],stdout=log,check=True)
    with(out/'expected.txt').open()as expected,(out/'actual.txt').open()as actual:
        count=0
        for want,got in zip(expected,actual,strict=True):
            if want!=got:raise AssertionError(f'ARM64:{want}\nx86:{got}')
            count+=1
    assert count==len(cases)*256,count
    print(f'Integer multiply: {count:,} cases match ARM64 QEMU ({len(cases)} variants).')


if __name__=='__main__':main()
