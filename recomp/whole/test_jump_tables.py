"""Compile real Clang switches; prove baseline failure and recovered execution."""
import argparse
import importlib.util
import inspect as python_inspect
import io
import json
from pathlib import Path
import subprocess
import sys

from elftools.elf.elffile import ELFFile
from jump_tables import recover
from test_fastaes import build_reference

HERE=Path(__file__).resolve().parent


def compile_with_recovery(library,out,lift,cxx,windows,recovery):
    spec=importlib.util.spec_from_file_location('whole_compiler',HERE/'compile.py')
    compiler=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    original=compiler.inspect
    def inspect(path,base):
        options={'recover_jumps':False} if 'recover_jumps' in python_inspect.signature(original).parameters else {}
        image,start,entries,manifest=original(path,base,**options)
        if recovery:
            with path.open('rb') as stream: report=recover(ELFFile(stream))
            entries=sorted(set(entries)|{base+address for address in report['entries']})
            manifest['jump_tables']=report
        return image,start,entries,manifest
    compiler.inspect=inspect
    previous=sys.argv
    try:
        sys.argv=[str(HERE/'compile.py'),str(library),'--out',str(out),'--lift',str(lift),
                  '--base','0x50000000','--cxx',cxx,'--target',
                  'x86_64-w64-windows-gnu' if windows else 'x86_64-linux-gnu']
        compiler.main()
    finally:sys.argv=previous


def safety_checks(library,report):
    raw=bytearray(library.read_bytes())
    elf=ELFFile(io.BytesIO(raw))
    table=report['tables'][0]
    def file_offset(address):
        for section in elf.iter_sections():
            if section['sh_addr']<=address<section['sh_addr']+section['sh_size']:
                return section['sh_offset']+address-section['sh_addr']
        raise AssertionError('address outside section')
    # A different branch condition does not prove the unsigned index range.
    damaged=raw.copy();offset=file_offset(table['guard'])
    instruction=int.from_bytes(damaged[offset:offset+4],'little')
    damaged[offset:offset+4]=(instruction&~15).to_bytes(4,'little') # B.EQ
    rejected=recover(ELFFile(io.BytesIO(damaged)))
    assert not rejected['entries'] and rejected['unresolved'],rejected
    # Let the out-of-range/default path jump back into dispatch after the
    # guard. The guard still precedes the load textually, but no longer proves
    # a bound along every control-flow path.
    damaged=raw.copy()
    displacement=(instruction>>5)&0x7ffff
    if displacement&(1<<18):displacement-=1<<19
    default=table['guard']+displacement*4
    back=(table['guard']+4-default)//4
    offset_default=file_offset(default)
    damaged[offset_default:offset_default+4]=(0x14000000|(back&0x3ffffff)).to_bytes(4,'little')
    rejected=recover(ELFFile(io.BytesIO(damaged)))
    assert not rejected['entries'] and rejected['unresolved'],rejected
    # B.HS with CMP #20 has the same proven 20-element range as B.HI #19.
    damaged=raw.copy()
    damaged[offset:offset+4]=((instruction&~15)|2).to_bytes(4,'little')
    cmp_offset=offset-4
    cmp_instruction=int.from_bytes(damaged[cmp_offset:cmp_offset+4],'little')
    damaged[cmp_offset:cmp_offset+4]=((cmp_instruction&~(0xfff<<10))|(20<<10)).to_bytes(4,'little')
    alternate=recover(ELFFile(io.BytesIO(damaged)))
    assert alternate['entries']==report['entries'] and alternate['tables'][0]['count']==20,alternate
    # A conditional branch to its own fallthrough proves no range at all.
    damaged=raw.copy()
    damaged[offset:offset+4]=((instruction&~(0x7ffff<<5))|(1<<5)).to_bytes(4,'little')
    rejected=recover(ELFFile(io.BytesIO(damaged)))
    assert not rejected['entries'] and rejected['unresolved'],rejected
    # Reaching definitions matter: replace the selector-copy MOV with MOV W8,WZR.
    damaged=raw.copy()
    for offset in range(file_offset(table['function']),file_offset(table['site']),4):
        if damaged[offset:offset+4]==bytes.fromhex('e803002a'):
            damaged[offset:offset+4]=bytes.fromhex('e8031f2a')
            rejected=recover(ELFFile(io.BytesIO(damaged)))
            assert not rejected['entries'] and rejected['unresolved'],rejected
            break
    else:raise AssertionError('fixture selector MOV changed')
    # An out-of-function case invalidates the whole table, not only that entry.
    damaged=raw.copy();offset=file_offset(table['table'])
    damaged[offset:offset+table['entry_size']]=(255 if table['entry_size']==1 else 0x7fff if table['entry_size']==2 else 0x7fffffff).to_bytes(table['entry_size'],'little')
    rejected=recover(ELFFile(io.BytesIO(damaged)))
    assert not rejected['entries'] and rejected['unresolved'],rejected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--cc',default='clang-18');parser.add_argument('--cxx',default='clang++-18')
    parser.add_argument('--windows',action='store_true')
    parser.add_argument('--mingw',type=Path,default=Path('/mnt/c/mingw64/bin'))
    args=parser.parse_args()
    root=HERE.parent/f'work/jump-tables-{"windows" if args.windows else "linux"}'
    root.mkdir(parents=True,exist_ok=True)
    def host(path):
        return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip() if args.windows else str(path)
    cc=args.mingw/'gcc.exe' if args.windows else args.cc
    cxx=args.mingw/'g++.exe' if args.windows else args.cxx
    for layout,size,flags in [('byte',1,[]),('half',2,['-DSWITCH_WIDE_CASES','-Wl,--no-relax']),('word',4,['-mllvm','-aarch64-enable-compress-jump-tables=false'])]:
        directory=root/layout;directory.mkdir(exist_ok=True)
        library=directory/'switch.so'
        subprocess.run([args.cc,'--target=aarch64-linux-gnu','-O2','-ffreestanding','-fPIC','-fuse-ld=lld','-shared','-nostdlib',*flags,str(HERE/'switch_fixture.c'),'-o',str(library)],check=True)
        with library.open('rb') as stream:report=recover(ELFFile(stream))
        assert len(report['tables'])==1 and len(report['entries'])==20 and not report['unresolved'],report
        assert report['tables'][0]['entry_size']==size,report
        safety_checks(library,report)
        reference=directory/'reference'
        build_reference(args.cc,args.reference_root,[HERE/'switch_ref.c',HERE/'switch_fixture.c'],reference,[HERE],['SWITCH_WIDE_CASES'] if layout=='half' else [])
        expected=subprocess.check_output([str(args.reference_root/'usr/bin/qemu-aarch64-static'),str(reference)])
        loader=directory/'elfload.o'
        subprocess.run([str(cc),'-O2','-c',host(HERE.parent/'fastaes/elfload.c'),'-o',host(loader)],check=True)
        for recovery in (False,True):
            out=directory/('recovered' if recovery else 'baseline')
            compile_with_recovery(library,out,args.lift,args.cxx,args.windows,recovery)
            manifest=json.loads((out/'manifest.json').read_text())
            binary=out/('switch.exe' if args.windows else 'switch')
            command=[str(cxx),'-O2','-std=c++17','-DADDRESS_SIZE_BITS=64',f'-DSWITCH_LIBRARY="{host(library)}"',
                     f'-I{host(args.remill/"include")}',f'-I{host(HERE)}',f'-I{host(HERE.parent/"fastaes")}',f'-I{host(out)}',
                     host(HERE/'switch_test.cpp'),host(HERE/'runtime.cpp'),host(loader),*[host(obj) for obj in manifest['objects']],'-latomic','-o',host(binary)]
            if args.windows:command.insert(1,'-static')
            subprocess.run(command,check=True)
            result=subprocess.run([str(binary)],capture_output=True)
            if not recovery:
                assert result.returncode and b'unresolved indirect target' in result.stderr,(result.returncode,result.stderr)
                print(layout,'baseline fails on unrecovered case entry:',result.stderr.decode().strip(),flush=True)
            else:
                assert result.returncode==0,(result.returncode,result.stderr)
                assert result.stdout==expected,'Recovered switch result differs from ARM64'
                print(layout,f'recovered: {len(expected)//8:,} cases match ARM64 QEMU; 20 bounded targets',flush=True)


if __name__=='__main__':main()
