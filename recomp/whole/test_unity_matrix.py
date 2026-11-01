"""Execute the original unchanged104-byte Unity function on ARM64 and lifted hosts."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile
from test_fastaes import build_reference
from unity_matrix_fixture import prepare,CODE_SHA

HERE=Path(__file__).resolve().parent


def digest(path):
    result=hashlib.sha256()
    with path.open('rb')as stream:
        for part in iter(lambda:stream.read(1048576),b''):result.update(part)
    return result.hexdigest()


def compare(reference,actual):
    mismatches=[];records=0;mismatch_records=0
    with reference.open('rb')as ref,actual.open('rb')as got:
        while True:
            a=ref.read(16);b=got.read(16)
            if not a and not b:break
            if len(a)!=16 or a!=b:raise RuntimeError(f'Matrix record header/length mismatch at{records}')
            index,profile,control,size=struct.unpack('<4I',a);x=ref.read(792+size);y=got.read(792+size)
            if x!=y:
                mismatch_records+=1
                at=next(i for i in range(min(len(x),len(y)))if x[i]!=y[i])if len(x)==len(y)else min(len(x),len(y))
                if len(mismatches)<8:mismatches.append({'record':index,'profile':profile,'mode':control//2,'initial_flags':control%2,'first_byte':at,'expected':x[max(0,at//8*8):at//8*8+8].hex(),'actual':y[max(0,at//8*8):at//8*8+8].hex()})
            records+=1
    return records,mismatches,mismatch_records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unity',type=Path,required=True)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--windows',action='store_true')
    parser.add_argument('--record-directory',type=Path,required=True,help='Native Linux directory for large output streams')
    args=parser.parse_args();platform='windows'if args.windows else'linux';out=HERE.parent/f'work/unity-matrix-{platform}';out.mkdir(parents=True,exist_ok=True)
    args.record_directory.mkdir(exist_ok=True,parents=True)
    source,extraction=prepare(args.unity,out);image=out/'fixture.so'
    subprocess.run(['clang-18','--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib','-fPIC',str(source),'-o',str(image)],check=True)
    with image.open('rb')as stream:
        elf=ELFFile(stream);symbol=elf.get_section_by_name('.symtab').get_symbol_by_name('unity_original_matrix')[0];section=elf.get_section(symbol['st_shndx'])
        code=section.data()[symbol['st_value']-section['sh_addr']:symbol['st_value']-section['sh_addr']+symbol['st_size']]
        if len(code)!=104 or hashlib.sha256(code).hexdigest()!=CODE_SHA:raise RuntimeError('Relocated fixture changed original machine code')
        extraction['fixture_guest_entry']=hex(0x5e000000+symbol['st_value'])
    reference=out/'reference';build_reference('clang-18',args.reference_root,[HERE/'unity_matrix_ref.c',source],reference,[HERE])
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(image),'--out',str(out/'lifted'),'--lift',str(args.lift),'--cxx','clang++-18','--base','0x5e000000','--target','x86_64-w64-windows-gnu'if args.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'lifted/manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(path.resolve())],text=True).strip()if args.windows else str(path.resolve())
    cc='/mnt/c/mingw64/bin/gcc.exe'if args.windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if args.windows else'clang++-18'
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/('test.exe'if args.windows else'test')
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-I'+hp(args.remill/'include'),'-I'+hp(HERE),'-I'+hp(out/'lifted'),f'-DMATRIX_IMAGE="{hp(image)}"',hp(HERE/'unity_matrix_test.cpp'),hp(HERE/'runtime.cpp'),hp(loader),*map(hp,map(Path,manifest['objects'])),'-latomic','-o',hp(binary)]
    if args.windows:command[1:1]=['-static','-pthread']
    subprocess.run(command,check=True)
    report={'toolchain':manifest['toolchain'],'extraction':extraction,'profiles':{}}
    for profile in ['finite','diagnostic']:
        arguments=[]if profile=='finite'else['diagnostic'];ref_file=args.record_directory/f'reference-{platform}-{profile}.bin';actual=args.record_directory/f'actual-{platform}-{profile}.bin'
        with ref_file.open('wb')as stream:r=subprocess.run([str(args.reference_root/'usr/bin/qemu-aarch64-static'),str(reference),*arguments],stdout=stream,stderr=subprocess.PIPE,text=True,check=True)
        print(r.stderr,end='',flush=True)
        with actual.open('wb')as stream:r=subprocess.run([str(binary),*arguments],stdout=stream,stderr=subprocess.PIPE,text=True,check=True)
        print(r.stderr,end='',flush=True)
        records,mismatches,mismatch_records=compare(ref_file,actual);passed=mismatch_records==0
        report['profiles'][profile]={'passed':passed,'records':records,'mismatch_records':mismatch_records,'mismatches':mismatches,'reference_sha256':digest(ref_file),'actual_sha256':digest(actual)}
        print(f'Exact Unity matrix {platform} {profile}: {records:,} records, {mismatch_records:,} different, {"PASS"if passed else"DIFFERENT"}',flush=True)
        if profile=='finite'and not passed:
            (out/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError('Finite exact-code matrix acceptance failed')
    report['sources']={str(HERE/name):digest(HERE/name)for name in ['unity_matrix_fixture.py','unity_matrix_driver.h','unity_matrix_ref.c','unity_matrix_test.cpp','test_unity_matrix.py']}
    (out/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
