"""Immutable positive scalar FADDP S/D ARM64 reference and optional dual-host gate."""
import argparse,hashlib,importlib.util,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--reference-root',type=Path,required=True);p.add_argument('--toolchain',type=Path);p.add_argument('--support-commit',default='HEAD');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));a=p.parse_args()
 out=a.out.resolve();out.mkdir(exist_ok=False)
 commit=subprocess.check_output(['git.exe','-C',wp(ROOT),'rev-parse',a.support_commit],text=True).strip()
 archive=subprocess.check_output(['git.exe','-C',wp(ROOT),'archive',commit,'recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';owned={}
 for name in ('faddp_cases.py','faddp_native_wrapper.S','faddp_ref.c','faddp_test.cpp','test_faddp.py','test_faddp_decode.py'):
  f=HERE/name;owned[f.name]=sha(f);shutil.copy2(f,source/'whole'/f.name)
 spec=importlib.util.spec_from_file_location('frozen_cases',source/'whole/faddp_cases.py');casesmodule=importlib.util.module_from_spec(spec);spec.loader.exec_module(casesmodule)
 generated=out/'generated';generated.mkdir();cases=casesmodule.generate(generated)
 def run(cmd,name,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n'+(out/name).read_text(errors='replace')[-3000:])
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=a.reference_root/'usr/bin/qemu-aarch64-static'
 external={str(x.resolve()):sha(x.resolve())for x in(ndk,qemu,Path('/usr/bin/clang-18'))};pins={str(x):sha(x)for x in source.rglob('*')if x.is_file()}
 initial=dict(support_commit=commit,owned=owned,support_archive_sha256=sha(out/'support.tar'),sources=pins,external=external,scope='reference-only'if a.toolchain is None else'ARM64 plus dual-host scalar FADDP S/D')
 (out/'source-pin.json').write_text(json.dumps(initial,indent=2)+'\n')
 obj=out/'ndk-faddp.o';run([ndk,'-c','-Wall','-Wextra','-Werror',generated/'faddp.S','-o',obj],'ndk-build.log')
 # Literal original instructions are copied verbatim, not assembled substitutes.
 unity=ROOT/'recomp/work/windows-first-frame-ushll-mask1/native/libunity.so';assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 original_sites={0xae33bc:0x7e30d800}
 with unity.open('rb')as f:
  elf=ELFFile(f)
  for rva,word in original_sites.items():
   seg=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+4<=s['p_vaddr']+s['p_filesz']);assert seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+4]==word.to_bytes(4,'little')
 external[str(unity)]=sha(unity)
 wrapper=out/'wrapper.o';run([ndk,'-c',source/'whole/faddp_native_wrapper.S','-o',wrapper],'wrapper-build.log')
 spec=importlib.util.spec_from_file_location('frozen_reference',source/'whole/test_fastaes.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 reference=out/'reference';helper.build_reference('clang-18',a.reference_root,[source/'whole/faddp_ref.c',obj,wrapper],reference,[generated]);run([qemu,reference],'arm64-records.log')
 text=(out/'arm64-records.log').read_text();expected=[x for x in text.splitlines()if x.startswith('RECORD ')];assert len(expected)==len(cases)*2048 and f'FADDP-RECORDS-SUCCESS {len(expected)}'in text and'FADDP-REFERENCE-SUCCESS'in text
 hosts={}
 if a.toolchain:
  tools={str(x):sha(x)for x in a.toolchain.rglob('*')if x.is_file()};initial['tool_inputs']=tools
  run([sys.executable,source/'whole/test_faddp_decode.py','--toolchain',a.toolchain,'--out',out/'decode'],'decode-controller.log')
  library=out/'faddp.so';run(['clang-18','--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',obj,'-o',library],'guest-link.log')
  for windows in(False,True):
   label='windows'if windows else'linux';build=out/label;path=wp if windows else str
   run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x38000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18','--jobs','4'],label+'-compile.log',900)
   m=json.loads((build/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
   cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
   for compiler in(cc,cxx):
    compiler_path=Path(shutil.which(compiler)or compiler).resolve();external[str(compiler_path)]=sha(compiler_path)
   flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(source/'whole'),'-I'+path(source/'fastaes'),'-I'+path(generated),'-I'+path(build),f'-DFADDP_LIB="{path(library)}"']
   loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');objects=[]
   for n,new in(('runtime.cpp',False),('faddp_test.cpp',True)):
    target=build/(Path(n).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if new else[]),'-c',path(source/'whole'/n),'-o',path(target)],label+'-'+Path(n).stem+'-build.log');objects.append(target)
   binary=build/('faddp.exe'if windows else'faddp');run([cxx,*map(path,objects),path(loader),*map(path,m['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(binary)],label+'-link.log');run([binary],label+'-records.log')
   text=(out/(label+'-records.log')).read_text();assert[x for x in text.splitlines()if x.startswith('RECORD ')]==expected and'FADDP-HOST-SUCCESS'in text;hosts[label]=dict(records=len(expected),binary_sha256=sha(binary),heads=len(m['traces']),objects=len(m['objects']))
  assert all(sha(n)==h for n,h in tools.items())
 for n,h in pins.items():assert sha(n)==h,n
 for n,h in external.items():assert sha(n)==h,n
 for n,h in owned.items():assert sha(HERE/n)==h,n
 initial.update(passed=True,records_each=len(expected),cases=len(cases),ndk_core_sha256=sha(obj),reference_sha256=sha(reference),original_words={hex(k):hex(v)for k,v in original_sites.items()},external=external,hosts=hosts,limits='Reference-only if hosts empty. Scalar S/D pair-add, all16 rounding/FZ/DN modes with sticky flags; no traps/AFP merge/half/new vector semantics. Full800 ARM state streams;8 independent full1200 raw host checks. No game execution.')
 initial['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(initial,indent=2)+'\n');print('FADDP-FUNCTIONAL-SUCCESS',len(expected),'hosts',list(hosts),flush=True)
if __name__=='__main__':main()
