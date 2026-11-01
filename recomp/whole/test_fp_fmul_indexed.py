"""Raw indexed FMUL32/64 oracle, including original Unity opcode0x4f809214."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from fp_fmul_indexed_cases import generate
from test_fp_fmla import digest
from test_fastaes import build_reference
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--lift',type=Path)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--windows',action='store_true')
    parser.add_argument('--reference-only',action='store_true')
    parser.add_argument('--reference-file',type=Path)
    parser.add_argument('--record-directory',type=Path,required=True)
    args=parser.parse_args();platform='windows'if args.windows else'linux';out=HERE.parent/f'work/fp-fmul-indexed-{platform}';out.mkdir(exist_ok=True,parents=True);args.record_directory.mkdir(exist_ok=True,parents=True)
    cases=generate();lines=['.text'];declarations=[];records=0;source=out/'fixture.S'
    for name,(body,width,full,*_)in cases.items():
        lines += [f'.global {name}',f'.type {name}, %function',name+':','.cfi_startproc',*('    '+op for op in body),'.cfi_endproc',f'.size {name}, .-{name}']
        declarations += [f'CASE({name},{width},{int(full)})'];records+=32*(38*38+1024+((254 if width==32 else 2046)*8 if full else 64))
    source.write_text('\n'.join(lines)+'\n');(out/'fp_fmul_indexed_generated.h').write_text('\n'.join(declarations)+'\n')
    key={p.name:digest(p)for p in [source,out/'fp_fmul_indexed_generated.h',HERE/'fp_fmul_indexed_driver.h',HERE/'fp_fmul_indexed_ref.c']};key['qemu_sha256']=digest(args.reference_root/'usr/bin/qemu-aarch64-static')
    if args.reference_file:
        expected=args.reference_file;meta=json.loads(expected.with_suffix('.provenance.json').read_text())
        if meta['key']!=key or meta['sha256']!=digest(expected):raise RuntimeError('Indexed FMUL oracle source/hash mismatch')
    else:
        reference=out/'reference';build_reference('clang-18',args.reference_root,[HERE/'fp_fmul_indexed_ref.c',source],reference,[HERE,out]);expected=args.record_directory/'reference.bin'
        with expected.open('wb')as stream:subprocess.run([str(args.reference_root/'usr/bin/qemu-aarch64-static'),str(reference)],stdout=stream,check=True)
        expected.with_suffix('.provenance.json').write_text(json.dumps({'key':key,'sha256':digest(expected)},indent=2)+'\n')
    if expected.stat().st_size!=records*64:raise RuntimeError('Indexed FMUL oracle record count mismatch')
    print(f'Indexed FMUL ARM64 oracle: {len(cases)} variants, {records:,} records',flush=True)
    if args.reference_only:return
    if not args.lift:parser.error('--lift required unless --reference-only')
    image=out/'fixture.so';subprocess.run(['clang-18','--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',str(source),'-o',str(image)],check=True)
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(image),'--out',str(out/'lifted'),'--lift',str(args.lift),'--cxx','clang++-18','--base','0x5f000000','--target','x86_64-w64-windows-gnu'if args.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'lifted/manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if args.windows else str(Path(path).resolve())
    cc='/mnt/c/mingw64/bin/gcc.exe'if args.windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if args.windows else'clang++-18';loader=out/'elfload.o'
    subprocess.run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True);binary=out/('test.exe'if args.windows else'test')
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-I'+hp(args.remill/'include'),'-I'+hp(HERE),'-I'+hp(out),'-I'+hp(out/'lifted'),f'-DFMUL_INDEXED_IMAGE="{hp(image)}"',hp(HERE/'fp_fmul_indexed_test.cpp'),hp(HERE/'runtime.cpp'),hp(loader),*map(hp,manifest['objects']),'-latomic','-o',hp(binary)]
    if args.windows:command[1:1]=['-static','-pthread']
    subprocess.run(command,check=True);actual=args.record_directory/f'actual-{platform}.bin'
    with actual.open('wb')as stream:subprocess.run([str(binary)],stdout=stream,check=True)
    with expected.open('rb')as ref,actual.open('rb')as got:
        offset=0
        while True:
            a=ref.read(1048576);b=got.read(1048576)
            if a!=b:
                for i in range(0,max(len(a),len(b)),64):
                    if a[i:i+64]!=b[i:i+64]:raise RuntimeError(f'Indexed FMUL mismatch record{offset//64+i//64}: expected{a[i:i+64].hex()} actual{b[i:i+64].hex()}')
            if not a:break
            offset+=len(a)
    (out/'acceptance.json').write_text(json.dumps({'passed':True,'variants':len(cases),'records':records,'record_bytes':64,'toolchain':manifest['toolchain'],'reference_sha256':digest(expected),'actual_sha256':digest(actual),'sources':{str(HERE/n):digest(HERE/n)for n in ['fp_fmul_indexed_cases.py','fp_fmul_indexed_driver.h','fp_fmul_indexed_ref.c','fp_fmul_indexed_test.cpp','test_fp_fmul_indexed.py','fp_fmla_cases.py']}},indent=2)+'\n')
    print(f'Indexed FMUL PASS: {records:,} exact result/source/FPSR/NZCV records',flush=True)


if __name__=='__main__':main()
