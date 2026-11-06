"""Focused owned fixed-anonymous replacement, actual NDK/Bionic and Windows (WSL)."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('fixed_anon_guest.c','fixed_anon_ref.c','fixed_anon_test.cpp','test_fixed_anon.py')
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source-manifest',type=Path,required=True);ap.add_argument('--source-sha',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,allow_failure=False,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout);(out/(label+'.stdout.log')).write_bytes(r.stdout);(out/(label+'.stderr.log')).write_bytes(r.stderr);text=r.stdout.decode(errors='replace')+r.stderr.decode(errors='replace');(out/(label+'.log')).write_text(text)
  if not allow_failure and r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-5000:])
  return r.returncode,text
 try:
  assert sha(a.source_manifest)==a.source_sha;pin(a.source_manifest);packet=json.loads(a.source_manifest.read_text());production=packet.get('production_sources')or{n.removeprefix('recomp/'):h for n,h in packet['PINS'].items()};assert production and all(re.fullmatch('[a-f0-9]{64}',h)for h in production.values())
  root=HERE.parent;compile_names=['windows/filesystem.cpp','windows/growdown_memory.cpp','whole/format.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/fixed_anon_test.cpp'];pending=compile_names+['fastaes/elfload.c',*('windows/'+n for n in OWN),*('whole/'+n for n in ('compile.py','jump_tables.py','callback_roots.py','nonlocal_roots.py'))];seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    child=(p.parent/inc).resolve()
    if child.is_file()and child.is_relative_to(root):pending.append(str(child.relative_to(root)))
  for name,h in production.items():assert sha(source/name)==h==sha(root/name)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');tool=W/'integer-popcount8b-preparation1/toolchains/f967bf3b57f889d7-469903ec4d84cbd3';cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe')
  for p in(ndk,qemu,tool/'remill-lift',tool/'aarch64.bc',cxx,cc):pin(p)
  ref=out/'original-Bionic';run([ndk,'-static','-O1','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'windows/fixed_anon_guest.c',source/'windows/fixed_anon_ref.c','-o',ref],'compile-Bionic');_,text=run([qemu,ref],'actual-Bionic',timeout=30);reference=[x for x in text.splitlines()if x.startswith('FIXED-REF ')];assert len(reference)==4 and 'FIXED-ANON-ARM-PASS records=4 TLS=17'in text
  guest=out/'fixed-anon.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'windows/fixed_anon_guest.c','-o',guest],'compile-NDK');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x6d000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK');m=json.loads((translated/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(translated),'-DFIXED_IMAGE="'+wp(guest)+'"','-DFIXED_ROOT="'+wp(out)+'"'];objects=[]
  for name in compile_names:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('fixed_anon_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'fixed-anon.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,m['objects']),'-Wl,--wrap='+WRAP,'-Wl,--wrap=__imp_VirtualAlloc','-Wl,--wrap=__imp_VirtualFree','-static','-pthread','-latomic','-ladvapi32','-o',wp(exe)],'link');_,text=run([exe],'actual-Windows',timeout=60);match=re.search(r'FIXED-ANON-PASS checks=(\d+) NDK_calls=(\d+) installed=(\d+) successes=4 rejected=(\d+) native_pre_error=(\d+) State=1200 Memory64=8',text);assert match,text[-2000:];assert [x for x in text.splitlines()if x.startswith('FIXED-REF ')]==reference
  negatives={}
  for mode,needle in [('--post-failure','destructive MAP_FIXED recommit failed'),('--guest-pinned','active mapping use')]:
   status,text=run([exe,mode],'reject-'+mode[2:],True,30);assert status and needle in text and 'fixed-anon fixture:'not in text and 'negative boundary returned'not in text
   if mode=='--post-failure':assert 'POST-DESTRUCTIVE-OS-FAIL'in text and 'target_state=8192'in text
   negatives[mode]=dict(exit_code=status,stdout=desc(out/('reject-'+mode[2:]+'.log')),named_boundary=needle)
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,production_source_manifest=desc(a.source_manifest),source_snapshot={str(p.relative_to(source)):sha(p)for p in source.rglob('*')if p.is_file()},owned_sources={n:sha(source/'windows'/n)for n in OWN},scope='Owned single-reservation private-anonymous fixed PROT_NONE replacement, NDK direct/volatile pointer ABI and real Windows decommit/recommit/protection/zeroing; no arbitrary MAP_FIXED replacement capability.',focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),installed_callbacks=int(match[3]),successful_fixed_calls=4,rejected_requests=int(match[4]),actual_native_predecommit_error=int(match[5]),State1200=True,Memory64=True,traces=len(m['traces']),objects=len(m['objects']),whole_owner_generation_refresh=True,exclusive_success_invalidation=True,pinned_and_validation_failure_preservation=True,foreign_file_growdown_crossowner_unchanged=True),native_fault_policy='TEST-local transparent IAT wrappers forward normal calls unchanged. Predecommit fault calls actual VirtualFree with invalid flags and observes its real failure with no mutation. Separate postdecommit child calls actual VirtualAlloc with invalid allocation type; reserved target and actual native error precede named destructive fatal. No invented API errors or untouched/atomic claim after decommit.',Bionic_reference=dict(executable=desc(ref),stdout=desc(out/'actual-Bionic.log'),records=reference),guest=desc(guest),guest_manifest=desc(translated/'manifest.json'),executable=desc(exe),stdout=desc(out/'actual-Windows.log'),negative_processes=negatives,held_inputs=held,commands=commands,limits='Synthetic owned memory and canary contents; no original GC helper/heap reclamation/game execution. Only flags0x32/prot0/fd-1/offset0 inside one owned anonymous nongrowdown mapping and no whole-owner pins. No file/unowned/growdown/crossowner overwrite, MEM_RESET or MEM_RELEASE during replacement. Postdestructive recommit failure is fatal, not an atomic failure return.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FIXED-ANON-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
