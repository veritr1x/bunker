"""Immutable timed-private-futex gate with unchanged untimed regression; no game."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,re
HERE=Path(__file__).resolve().parent
OWN=('futex_timed_ref.c','futex_timed_test.cpp','test_futex_timed.py')
CORE=('windows/signal_futex.h','windows/signal_futex.cpp')
OLD=('futex_fixture.h','futex_guest.c','futex_guest.S','futex_ref.c','futex_test.cpp','test_futex.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('preparation','source-preview','source-peer','primary-audit','out','ndk','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--reuse-reference',type=Path)
 a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);prep=a.preparation.resolve();W=prep.parent;source=out/'source';shutil.copytree(prep/'source',source);S=source/'recomp';old=W/'futex-fixture1/qualification3'
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 prior=read(old/'acceptance.json');assert prior['passed']and sha(old/'acceptance.json')=='3d1bd842e61a88dd162b3a59e454ea3a7e8e921b99bcd0f94bc9b900a90f87ac'
 baseline={}
 for n in OLD:
  f=old/'source/recomp/windows'/n;assert sha(f)==prior['fixture_sources'][n];baseline[n]=sha(f);shutil.copy2(f,S/'windows'/n)
 fixtures={}
 for n in OWN:fixtures[n]=sha(HERE/n);shutil.copy2(HERE/n,S/'windows'/n)
 core={n:sha(S/n)for n in CORE};preview=read(a.source_preview);declared=preview.get('source_files',preview.get('core_sources',preview));assert all(declared.get(n)==h for n,h in core.items()),declared
 base=read(prep/'preparation.json');assert base['base_commit'].startswith('4f7db3')and sha(prep/'base-recomp.tar')==base['base_archive_sha256']
 def local_path(s):
  if re.match(r'^[A-Za-z]:[\\/]',s):return Path(subprocess.check_output(['wslpath','-u',s],text=True).strip())
  return Path(s)
 proof=local_path(preview['untimed_body_proof_path']);assert sha(proof)==preview['untimed_body_proof_sha256']
 prerequisites={str(f.resolve()):sha(f)for f in(a.source_preview,a.source_peer,a.primary_audit,prep/'preparation.json',prep/'base-recomp.tar',prep/'protected-base-files.json',proof,old/'acceptance.json',old/'source-pin.json')}
 def add_pin(n,h):
  f=local_path(n);assert sha(f)==h,n;prerequisites[str(f)]=h
 def expand(j):
  if isinstance(j,list):
   for v in j:expand(v)
  elif isinstance(j,dict):
   if isinstance(j.get('path'),str)and re.fullmatch('[0-9a-f]{64}',str(j.get('sha256',''))):add_pin(j['path'],j['sha256'])
   for n,v in j.items():
    if isinstance(v,str)and re.fullmatch('[0-9a-f]{64}',v)and(n.startswith('/')or re.match(r'^[A-Za-z]:[\\/]',n)):add_pin(n,v)
    elif isinstance(v,(dict,list)):expand(v)
 for f in(a.source_preview,a.source_peer,a.primary_audit,prep/'protected-base-files.json',proof):expand(read(f))
 # Reused actual NDK objects/library and lifted callers are byte-pinned. No
 # new ISA/lift is needed: the existing seven-GP ABI already forwards timeout.
 reused={str(old/n):sha(old/n)for n in('guest-c.o','guest-S.o','futex.so','native-status.ps1')}
 for label in ('linux','windows'):
  D=old/label/'guest';m=read(D/'manifest.json');assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  for f in [D/'manifest.json',D/'traces.h',*map(Path,m['objects'])]:reused[str(f)]=sha(f)
 for n,h in prior['evidence'].items():
  # All original reusable caller artifacts are required to remain exact.
  if n in reused:assert reused[n]==h,n
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};commands=[]
 def run(cmd,name,timeout=120):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(out/name).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(out/name).read_text(errors='replace')[-6000:])
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');external={str(f.resolve()):sha(f.resolve())for f in(cc,qemu,Path('/usr/bin/clang-18'),Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))}
 reference_reuse={}
 if a.reuse_reference:
  previous=a.reuse_reference.resolve();rp=read(previous/'source-pin.json');assert rp['core_sources']==core and rp['fixture_sources']['futex_timed_ref.c']==fixtures['futex_timed_ref.c']and rp['untimed_fixture_sources']==baseline and rp['tools']==tools and rp['external']==external
  expand(rp)
  for name in('source-pin.json','reference','arm64-reference.log','reference-build.log'):
   f=previous/name;prerequisites[str(f)]=sha(f);reference_reuse[str(f)]=sha(f)
 initial=dict(core_sources=core,fixture_sources=fixtures,untimed_fixture_sources=baseline,sources=pins,tools=tools,external=external,prerequisites=prerequisites,reused_caller_artifacts=reused,reference_reuse=reference_reuse,source_preview_path=str(a.source_preview.resolve()),source_preview_sha256=sha(a.source_preview),base_commit=base['base_commit'],base_archive_path=str(prep/'base-recomp.tar'),base_archive_sha256=sha(prep/'base-recomp.tar'))
 (out/'source-pin.json').write_text(json.dumps(initial,indent=2)+'\n')
 flags=['-O1','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-I'+str(S/'windows')]
 run([cc,*flags,'-fsyntax-only',S/'windows/futex_timed_ref.c'],'reference-new-source-precheck.log')
 # Warning prechecks on both relevant host compilers precede runtime runs.
 for windows in(False,True):
  label='windows'if windows else'linux';path=wp if windows else str;build=old/label/'guest';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
  opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(S/'windows'),'-I'+path(build),f'-DFUTEX_LIBRARY="{path(old/"futex.so")}"']
  run([cxx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',path(S/'windows/futex_timed_test.cpp')],label+'-new-source-precheck.log')
 reference=out/'reference'
 if a.reuse_reference:
  shutil.copy2(a.reuse_reference/'reference',reference);shutil.copy2(a.reuse_reference/'arm64-reference.log',out/'arm64-reference.log');(out/'reference-reuse.json').write_text(json.dumps(dict(executed_here=False,prior_files=reference_reuse,reason='Host-only actual C++ protocol PC materialization correction; reference C/baseline/core/NDK caller/tools unchanged.'),indent=2)+'\n')
 else:
  run([cc,*flags,'-static',S/'windows/futex_timed_ref.c',old/'guest-c.o',old/'guest-S.o','-pthread','-o',reference],'reference-build.log');run([qemu,reference],'arm64-reference.log',85)
 def observed(text):
  oldrows=[s for s in text.splitlines()if s.startswith(('PROBE ','GROUP ','RACES ','SIGNAL '))];assert oldrows==prior['canonical_records']and len(oldrows)==23
  rows=[s for s in text.splitlines()if s.startswith(('TIMED ','TIMED-DEADLINE ','TIMED-WAKE ','TIMED-LONGWAKE ','TIMED-SIGNAL ','TIMED-OVERRUN '))];assert len(rows)==38,len(rows)
  races=[re.fullmatch(r'TIMED-RACE (\d+) result=(-?\d+) errno=(\d+) wake=(\d+)',s)for s in text.splitlines()if s.startswith('TIMED-RACE ')];assert len(races)==16 and all(races)
  for i,m in enumerate(races):assert int(m[1])==i and(int(m[2]),int(m[3]),int(m[4]))in[(0,731,1),(-1,110,0)]
  return rows,[dict(index=int(m[1]),result=int(m[2]),errno=int(m[3]),wake=int(m[4]))for m in races]
 native=(out/'arm64-reference.log').read_text();expected,nativeraces=observed(native);assert'FUTEX-TIMED-ARM64-SUCCESS records=38'in native;platforms={}
 for windows in(False,True):
  label='windows'if windows else'linux';D=out/label;D.mkdir();build=old/label/'guest';m=read(build/'manifest.json');path=wp if windows else str;cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';c='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
  opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(S/'windows'),'-I'+path(build),f'-DFUTEX_LIBRARY="{path(old/"futex.so")}"'];compiled=[];loader=D/'loader.o';run([c,'-O2','-c',path(S/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log')
  for rel in('whole/runtime.cpp','whole/signal_frame.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_futex.cpp'):
   f=D/(Path(rel).stem+'.o');run([cxx,*opts,'-c',path(S/rel),'-o',path(f)],label+'-'+f.stem+'.log');compiled.append(f)
  binary=D/('futex-timed.exe'if windows else'futex-timed');run([cxx,*opts,'-Wall','-Wextra','-Werror',path(S/'windows/futex_timed_test.cpp'),*map(path,compiled),path(loader),*map(path,m['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(binary)],label+'-focused-build.log');run([binary],label+'-focused.log',85);text=(out/(label+'-focused.log')).read_text();rows,races=observed(text);assert rows==expected and'FUTEX-TIMED-HOST-SUCCESS records=38'in text
  # The old two production import-fence cases execute unchanged with new core.
  negatives={};capture=old/'native-status.ps1'
  for mode in('unsupported','excluded'):
   if windows:n=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(binary),'-Mode',mode],text=True,timeout=40));assert n['exit_code']==3,n
   else:
    r=subprocess.run([str(binary),mode],text=True,capture_output=True,timeout=40);n=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);assert r.returncode==-6,n
   assert'private futex syscall:'in n['stderr'];(out/(label+'-'+mode+'.json')).write_text(json.dumps(n,indent=2)+'\n');negatives[mode]=n
  platforms[label]=dict(timed_records=rows,timed_races=races,untimed_checks=int(re.search(r'FUTEX-HOST-SUCCESS records=23 checks=(\d+)',text)[1]),total_checks=int(re.search(r'FUTEX-TIMED-HOST-SUCCESS records=38 checks=(\d+)',text)[1]),negative_cases=negatives,binary_sha256=sha(binary),heads=len(m['traces']),objects=len(m['objects']))
 for group in(pins,tools,external,prerequisites,reused):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in fixtures.items():assert sha(HERE/n)==h,n
 for n,h in core.items():assert sha(prep/'source/recomp'/n)==h,n
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,scope='Relative timed WAIT_PRIVATE extension plus unchanged untimed23 regression, no game/root admission change.',core_sources=core,fixture_sources=fixtures,untimed_fixture_sources=baseline,canonical_records=expected,arm64_records=38,arm64_races=nativeraces,platforms=platforms,source_pin_path=str(out/'source-pin.json'),source_pin_sha256=sha(out/'source-pin.json'),source_preview_path=str(a.source_preview.resolve()),source_preview_sha256=sha(a.source_preview),primary_audit_path=str(a.primary_audit.resolve()),primary_audit_sha256=sha(a.primary_audit),evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and'source'not in f.relative_to(out).parts},limits='Same original actual NDK caller7GP object reused; no new lift/ISA semantics. Per-host timing bounds establish real delay, not equal scheduling/latency or suspend/resume equivalence. ARM64 overrun uses actual native caught wrapper; host overrun is labelled C++ Runtime protocol with real SignalDelivery/NDK handler. Free deadline/wake distribution is observed, not guaranteed. Actual admitted test handlers are component-only; production admission remains0. No actual Game28 duration/thread-role inference.')
 (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FUTEX-TIMED-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
