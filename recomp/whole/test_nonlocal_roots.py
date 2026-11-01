"""NDK static import-ownership proofs and continuation-only native dispatch."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
from elftools.dwarf.callframe import FDE
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from nonlocal_roots import recover
HERE=Path(__file__).resolve().parent


def load(path):
    with path.open('rb') as stream:
        return recover(ELFFile(stream))


def mutate(source,destination,mode):
    raw=bytearray(source.read_bytes());elf=ELFFile(io.BytesIO(raw))
    custom=elf.get_section_by_name('.plt.nonlocal')
    assert custom is not None
    if mode in ('TRUNCATED_PLT','NUMERIC_GOT'):
        offset=custom['sh_offset']+(12 if mode=='TRUNCATED_PLT'else 8)
        word=int.from_bytes(raw[offset:offset+4],'little')
        if mode=='TRUNCATED_PLT':word&=~(1<<30)
        else:
            # A numeric MOV of the correct GOT page still lacks Base+RVA
            # provenance in an ET_DYN image.
            got=next(r['r_offset']for s in elf.iter_sections()if isinstance(s,RelocationSection)
                     for r in s.iter_relocations()
                     if elf.get_section(s['sh_link']).get_symbol(r['r_info_sym']).name=='setjmp')
            page=got&~0xfff;assert page<65536
            word=0xd2800000|(page<<5)|16
        raw[offset:offset+4]=word.to_bytes(4,'little')
    else:
        relocations=[(s,i,r)for s in elf.iter_sections()if isinstance(s,RelocationSection)
                     for i,r in enumerate(s.iter_relocations())]
        section,index,record=next((s,i,r)for s,i,r in relocations
            if elf.get_section(s['sh_link']).get_symbol(r['r_info_sym']).name=='setjmp')
        offset=section['sh_offset']+index*section['sh_entsize']
        if mode=='ADDEND':
            assert section.is_RELA();struct.pack_into('<q',raw,offset+16,4)
        elif mode=='MISALIGNED_GOT':struct.pack_into('<Q',raw,offset,record['r_offset']+4)
        elif mode=='WRONG_RELOCATION':
            struct.pack_into('<Q',raw,offset+8,(record['r_info_sym']<<32)|257) # ABS64 is not GLOB_DAT/JUMP_SLOT.
        elif mode=='OBJECT_SYMBOL':
            symbols=elf.get_section(section['sh_link']);where=symbols['sh_offset']+record['r_info_sym']*symbols['sh_entsize']+4
            raw[where]=(raw[where]&0xf0)|1 # STT_OBJECT, never an imported function entry.
        elif mode=='DUPLICATE_GOT':
            other,at,_=next((s,i,r)for s,i,r in relocations if r['r_offset']!=record['r_offset'])
            struct.pack_into('<Q',raw,other['sh_offset']+at*other['sh_entsize'],record['r_offset'])
        else:raise AssertionError(mode)
    destination.write_bytes(raw)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path)
    p.add_argument('--remill',type=Path,required=True)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--analysis-only',action='store_true')
    p.add_argument('--audit',type=Path,action='append',default=[])
    a=p.parse_args();out=HERE.parent/('work/nonlocal-roots-windows'if a.windows else'work/nonlocal-roots-linux');out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    variants=['NORMAL','PADDED_PLT','TAIL','INDIRECT','WRONG_IMPORT','LOCAL_SHADOW','DEFINED_INTERPOSABLE','NONEXEC_POST']
    valid=[];reports={}
    for variant in variants:
        library=out/(variant.lower()+'.so')
        subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-Wl,--no-relax,--strip-all',
                        *([]if variant=='NORMAL'else['-DNONLOCAL_'+variant]),
                        str(HERE/'nonlocal_roots_fixture.S'),'-o',str(library)],check=True)
        report=load(library);reports[variant]=report
        with library.open('rb')as stream:
            elf=ELFFile(stream);assert elf.get_section_by_name('.symtab')is None
            symbols={s['st_value']for s in elf.get_section_by_name('.dynsym').iter_symbols()}
            bounds=([(r['initial_location'],r['initial_location']+r['address_range'])
                     for r in elf.get_dwarf_info().EH_CFI_entries()if isinstance(r,FDE)]
                    if elf.get_section_by_name('.eh_frame')is not None else [])
            assert all(e not in symbols and not any(lo<=e<hi for lo,hi in bounds)for e in report['entries'])
        if variant in ('NORMAL','PADDED_PLT'):
            assert len(report['entries'])==3 and len(report['continuations'])==3 and not report['unresolved'],report
            assert {c['api']for c in report['continuations']}=={'setjmp','_setjmp','sigsetjmp'}
            assert all(c['entry']==c['site']+4 and c['proof']['got']and c['proof']['stub_instructions']for c in report['continuations'])
            valid.append((variant,library,report))
        elif variant in ('WRONG_IMPORT','LOCAL_SHADOW','DEFINED_INTERPOSABLE'):assert not report['entries']and not report['unresolved'],report
        else:
            assert not report['entries']and len(report['unresolved'])==1,report
            expected={'TAIL':'tail B','INDIRECT':'indirect BLR','NONEXEC_POST':'not a complete executable'}[variant]
            assert expected in report['unresolved'][0]['reason'],report
        print(variant,len(report['entries']),'roots',len(report['unresolved']),'unresolved',flush=True)
    for variant in ('TRUNCATED_PLT','NUMERIC_GOT','ADDEND','MISALIGNED_GOT','WRONG_RELOCATION','OBJECT_SYMBOL','DUPLICATE_GOT'):
        library=out/(variant.lower()+'.so');mutate(out/'padded_plt.so',library,variant)
        report=load(library);reports[variant]=report
        assert len(report['entries'])==(1 if variant=='DUPLICATE_GOT'else 2),report
        assert len(report['unresolved'])==(2 if variant=='DUPLICATE_GOT'else 1),report
        assert all(c['api']!='setjmp'for c in report['continuations'])
        print(variant,len(report['entries']),'roots',len(report['unresolved']),'unresolved',flush=True)
    (out/'static-reports.json').write_text(json.dumps(reports,indent=2)+'\n')
    for library in a.audit:
        report=load(library);report['source_sha256']=hashlib.sha256(library.read_bytes()).hexdigest()
        (out/(library.name+'.audit.json')).write_text(json.dumps(report,indent=2)+'\n')
        print('AUDIT',library,len(report['entries']),'roots',len(report['unresolved']),'unresolved',report['summary'],flush=True)
        if library.name=='libunity.so':
            observed=[c for c in report['continuations']if c['site']==0x43a048]
            assert len(observed)==1 and observed[0]['entry']==0x43a04c and observed[0]['api']=='setjmp',observed
            print('Actual Unity continuation proved: ELF0x43a04c -> guest0x7043a04c',flush=True)
    if a.analysis_only:return
    if a.lift is None:p.error('--lift required for native continuation dispatch gate')
    spec=importlib.util.spec_from_file_location('nonlocal_fixture_compiler',HERE/'compile.py')
    compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler);original=compiler.inspect
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if a.windows else str(path)
    hostcc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else'clang-18';hostcxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else'clang++-18'
    loader=out/'elfload.o';subprocess.run([hostcc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    native=[]
    for name,library,report in valid:
        for recovered in (False,True):
            destination=out/name.lower()/('recovered'if recovered else'baseline')
            def inspect(path,base,**options):
                # Isolated injection only: compile.py stays unchanged.
                image,start,entries,manifest=original(path,base,**options)
                requested={base+e for e in report['entries']}
                entries=sorted((set(entries)|requested)if recovered else(set(entries)-requested))
                manifest['isolated_nonlocal_roots']=dict(enabled=recovered,**report)
                return image,start,entries,manifest
            compiler.inspect=inspect;previous=sys.argv
            try:
                sys.argv=[str(HERE/'compile.py'),str(library),'--out',str(destination),'--lift',str(a.lift),
                          '--cxx','clang++-18','--base','0x5c000000','--target','x86_64-w64-windows-gnu'if a.windows else'x86_64-linux-gnu']
                compiler.main()
            finally:sys.argv=previous
            manifest=json.loads((destination/'manifest.json').read_text());assert not manifest['unsupported_traces']
            roots={0x5c000000+e for e in report['entries']};actual=set(manifest['traces'])
            assert roots<=actual if recovered else roots.isdisjoint(actual),'Fixture return PCs already baseline roots'
            (destination/'nonlocal_entries.h').write_text('static constexpr addr_t kNonlocalEntries[]={'+','.join(hex(e)for e in sorted(roots))+'};\n')
            binary=destination/('dispatch.exe'if a.windows else'dispatch')
            command=[hostcxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(destination)}',
              f'-DNONLOCAL_LIBRARY="{hp(library)}"',hp(HERE/'nonlocal_roots_test.cpp'),hp(HERE/'runtime.cpp'),
              hp(loader),*[hp(obj)for obj in manifest['objects']],'-pthread','-latomic','-o',hp(binary)]
            if a.windows:command.insert(1,'-static')
            subprocess.run(command,check=True);run=subprocess.run([str(binary)],capture_output=True,timeout=20)
            if recovered:assert run.returncode==0,run.stderr;print(name,run.stdout.decode().strip(),flush=True)
            else:
                assert run.returncode and b'unresolved indirect target'in run.stderr,run.stderr
                print(name,'baseline reproduces unavailable post-call dispatch entry',flush=True)
            native.append(dict(variant=name,recovered=recovered,exit_code=run.returncode,stdout=run.stdout.decode(),
                               stderr=run.stderr.decode(),executable_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
    (out/'native-results.json').write_text(json.dumps(native,indent=2)+'\n')


if __name__=='__main__':main()
