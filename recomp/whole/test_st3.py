"""Actual same-NDK ST3 reference and matched Linux/Windows translated gate."""
from pathlib import Path
import argparse,hashlib,importlib.util,io,json,shutil,subprocess,sys,tarfile
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OWNED=['st3_cases.py','st3_records.h','st3_ref.c','st3_native_wrapper.S','st3_test.cpp','test_st3.py','test_st3_decode.py']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--toolchain',type=Path);p.add_argument('--reference',type=Path);p.add_argument('--support-commit',required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 commit=subprocess.check_output(['git.exe','-C',wp(ROOT),'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output(['git.exe','-C',wp(ROOT),'archive',commit,'recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as f:f.extractall(O/'source',filter='data')
 S=O/'source/recomp';owned={}
 for n in OWNED:owned[n]=sha(HERE/n);shutil.copy2(HERE/n,S/'whole'/n)
 def run(cmd,name,timeout=300):
  print('STAGE',name,flush=True)
  with(O/name).open('w')as f:q=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if q.returncode:raise RuntimeError(name+' exit'+str(q.returncode)+'\n'+(O/name).read_text(errors='replace')[-5000:])
 spec=importlib.util.spec_from_file_location('frozen_st3',S/'whole/st3_cases.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);G=O/'generated';G.mkdir();cases=m.generate(G)
 CC=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');Q=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
 external={str(x.resolve()):sha(x.resolve())for x in[CC,Q,Path(shutil.which('clang-18')).resolve()]};sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()};obj=O/'ndk-st3.o'
 unity=ROOT/'recomp/work/windows-first-frame-label2/native/libunity.so';assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 with unity.open('rb')as f:e=ELFFile(f);rva=0x4fdb38;s=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+4<=s['p_vaddr']+s['p_filesz']);assert s.data()[rva-s['p_vaddr']:rva-s['p_vaddr']+4]==bytes.fromhex('5441004c')
 external[str(unity)]=sha(unity)
 if a.reference:
  R=a.reference;prior=json.loads((R/'acceptance.json').read_text());assert prior['passed']and prior['records_each']==1152
  for n in ['st3_cases.py','st3_records.h','st3_ref.c','st3_native_wrapper.S']:assert sha(R/'source/recomp/whole'/n)==owned[n]
  for name in ['ndk-st3.o','reference','arm64-records.log']:shutil.copy2(R/name,O/name);assert sha(O/name)==prior['reference_files'][name]
 else:
  run([CC,'-c','-Wall','-Wextra','-Werror',G/'st3.S','-o',obj],'ndk-build.log');run([CC,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(G),S/'whole/st3_ref.c',obj,S/'whole/st3_native_wrapper.S','-o',O/'reference'],'reference-build.log')
  with(O/'reference').open('rb')as f:e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());assert any(s['p_type']=='PT_TLS'and s['p_align']>=64 for s in e.iter_segments())
  run([Q,O/'reference'],'arm64-records.log')
 text=(O/'arm64-records.log').read_text();records=[x for x in text.splitlines()if x.startswith('RECORD ')];assert len(records)==1152 and 'ST3-REFERENCE-SUCCESS'in text
 hosts={};tools={}
 if a.toolchain:
  tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};run([sys.executable,S/'whole/test_st3_decode.py','--toolchain',a.toolchain,'--out',O/'decode'],'decode.log')
  lib=O/'st3.so';run(['clang-18','--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',obj,'-o',lib],'guest-link.log')
  for windows in(False,True):
   label='windows'if windows else'linux';B=O/label;conv=wp if windows else str
   run([sys.executable,S/'whole/compile.py',lib,'--out',B,'--base','0x38000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18','--jobs','4'],label+'-translate.log',900)
   manifest=json.loads((B/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
   cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
   for exe in(cc,cxx):path=Path(shutil.which(exe)or exe).resolve();external[str(path)]=sha(path)
   flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(a.toolchain/'include'),'-I'+conv(S/'whole'),'-I'+conv(S/'fastaes'),'-I'+conv(G),'-I'+conv(B),f'-DST3_LIB="{conv(lib)}"'];objects=[]
   loader=B/'elfload.o';run([cc,'-O2','-c',conv(S/'fastaes/elfload.c'),'-o',conv(loader)],label+'-loader.log')
   for n in['runtime.cpp','st3_test.cpp']:
    o=B/(Path(n).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n=='st3_test.cpp'else[]),'-c',conv(S/'whole'/n),'-o',conv(o)],label+'-'+n+'.log');objects.append(o)
   binary=B/('st3.exe'if windows else'st3');run([cxx,*map(conv,objects),conv(loader),*map(conv,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',conv(binary)],label+'-link.log');run([binary],label+'-records.log')
   observed=(O/(label+'-records.log')).read_text();assert [x for x in observed.splitlines()if x.startswith('RECORD ')]==records and 'ST3-HOST-SUCCESS raw_full1200=72'in observed;hosts[label]=dict(records=len(records),heads=len(manifest['traces']),objects=len(manifest['objects']),executable_sha256=sha(binary))
 for group in[sources,external,tools]:
  for n,h in group.items():assert sha(n)==h,n
 for n,h in owned.items():assert sha(HERE/n)==h,n
 result=dict(passed=True,cases=len(cases),records_each=len(records),owned_sources=owned,support_commit=commit,support_archive_sha256=sha(O/'support.tar'),sources=sources,external=external,tool_inputs=tools,reference_files={n:sha(O/n)for n in['ndk-st3.o','reference','arm64-records.log']},hosts=hosts,record_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),scope='ST3 multiple baseline AdvSIMD-enabled normal-memory profile, representative7arrangements/3modes/three-register-wrap/SP/alias/unaligned, exact4c004154; stores24/48B; SP initialalignment valid, no FP trap/disabledAdvSIMD/device memory profile; no game or cohort selection',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ST3-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
