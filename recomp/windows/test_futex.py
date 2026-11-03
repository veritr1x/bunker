"""Immutable private-futex component gate; no game/cohort or unrelated regressions."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,re,tarfile,difflib
HERE=Path(__file__).resolve().parent
OWN=('futex_fixture.h','futex_guest.c','futex_guest.S','futex_ref.c','futex_test.cpp','test_futex.py')
CORE=('whole/runtime.h','whole/runtime.cpp','windows/signal_futex.h','windows/signal_futex.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('preparation','out','ndk','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();prep=a.preparation.resolve();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';shutil.copytree(prep/'source',source);S=source/'recomp';W=prep.parent
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 fixtures={}
 for n in OWN:fixtures[n]=sha(HERE/n);shutil.copy2(HERE/n,S/'windows'/n)
 core={n:sha(S/n)for n in CORE};assert core==read(prep/'core-preview2.json');base=read(prep/'preparation.json');assert base['base_commit']=='7b0c45e1b12269b5af3cceb510a7e023c1c60109'and sha(prep/'support.tar')==base['base_archive_sha256']
 prereq={};held=W/'signal-sleep-held5.json';assert sha(held)=='53c4eb66e9440bda4fb20f5eaca5fa3da10a7eb64aeeef144b2bc54a7a1f067e';prereq[str(held)]=sha(held)
 for n,h in read(held)['core_sources'].items():assert sha(S/'windows'/n)==h;prereq[str(S/'windows'/n)]=h
 peer=W/'futex-core-source-peer2/peer.json';assert sha(peer)=='d0678964fa0b49efc765e0f429e0cf8a5a9664fb7696d83fca47d6efe2579c9d';prereq[str(peer)]=sha(peer)
 patch=[]
 with tarfile.open(prep/'support.tar')as t:
  for n in CORE:
   try:old=t.extractfile('recomp/'+n).read().decode()
   except KeyError:old=''
   patch+=difflib.unified_diff(old.splitlines(True),(S/n).read_text().splitlines(True),fromfile='a/recomp/'+n if old else'/dev/null',tofile='b/recomp/'+n)
 (out/'futex.patch').write_text(''.join(patch));pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};commands=[]
 def run(cmd,name,timeout=120):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(out/name).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(out/name).read_text(errors='replace')[-5000:])
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');external={str(f.resolve()):sha(f.resolve())for f in(cc,qemu,Path('/usr/bin/clang-18'),Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))}
 primary=W/'game25-syscall-audit/evidence.json';assert sha(primary)=='375f60824dc2596f07e5bf1b7918fcbad4093d7598c75af03302343cd12cbbd8';external[str(primary)]=sha(primary)
 for n,h in read(primary)['artifact_sha256'].items():assert sha(n)==h;external[n]=h
 for n in ('syscall-number-primary.json','qemu-futex-primary.json'):
  f=W/'game25-futex-primary'/n;j=read(f);external[str(f)]=sha(f);assert sha(j['path'])==j['sha256'];external[j['path']]=j['sha256']
 objects=[];flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-I'+str(S/'windows')]
 for ext in ('c','S'):
  f=out/('guest-'+ext+'.o');run([cc,*flags,'-c',S/('windows/futex_guest.'+ext),'-o',f],'ndk-'+ext+'.log');objects.append(f)
 library=out/'futex.so';run([cc,'-shared','-nostdlib',*objects,'-o',library],'ndk-library.log');reference=out/'reference';run([cc,*flags,'-static',S/'windows/futex_ref.c',*objects,'-pthread','-o',reference],'reference-build.log');run([qemu,reference],'arm64-reference.log',45)
 def observed(text):
  rows=[s for s in text.splitlines()if s.startswith(('PROBE ','GROUP ','RACES ','SIGNAL '))];assert len(rows)==23
  races=[re.fullmatch(r'RACE (\d+) result=(-?\d+) errno=(\d+) wake=(\d+)',s)for s in text.splitlines()if s.startswith('RACE ')];assert len(races)==64 and all(races)
  for i,m in enumerate(races):assert int(m[1])==i and (int(m[2]),int(m[3]),int(m[4]))in[(0,731,1),(-1,11,0)]
  return rows,[dict(index=int(m[1]),result=int(m[2]),errno=int(m[3]),wake=int(m[4]))for m in races]
 native=(out/'arm64-reference.log').read_text();expected,nativeraces=observed(native);assert'FUTEX-ARM64-SUCCESS records=23'in native
 initial=dict(core=core,fixtures=fixtures,sources=pins,tools=tools,external=external,prerequisites=prereq,base_preparation_sha256=sha(prep/'preparation.json'),base_archive_sha256=sha(prep/'support.tar'),base_commit=base['base_commit']);(out/'source-pin.json').write_text(json.dumps(initial,indent=2)+'\n');platforms={}
 for windows in (False,True):
  label='windows'if windows else'linux';D=out/label;D.mkdir();build=D/'guest';path=wp if windows else str
  run([sys.executable,S/'whole/compile.py',library,'--out',build,'--base','0x5c000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-lift.log',180);m=read(build/'manifest.json');assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';c='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(S/'windows'),'-I'+path(build),f'-DFUTEX_LIBRARY="{path(library)}"'];compiled=[]
  run([cxx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',path(S/'windows/futex_test.cpp'),path(S/'windows/signal_futex.cpp')],label+'-new-source-precheck.log');loader=D/'loader.o';run([c,'-O2','-c',path(S/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log')
  for rel in ('whole/runtime.cpp','whole/signal_frame.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_futex.cpp'):
   f=D/(Path(rel).stem+'.o');run([cxx,*opts,'-c',path(S/rel),'-o',path(f)],label+'-'+f.stem+'.log');compiled.append(f)
  binary=D/('futex.exe'if windows else'futex');run([cxx,*opts,'-Wall','-Wextra','-Werror',path(S/'windows/futex_test.cpp'),*map(path,compiled),path(loader),*map(path,m['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(binary)],label+'-focused-build.log');run([binary],label+'-focused.log',45);text=(out/(label+'-focused.log')).read_text();rows,races=observed(text);assert rows==expected and'FUTEX-HOST-SUCCESS records=23'in text
  capture=out/'native-status.ps1'
  if windows:capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo;$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296};@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
  negatives={}
  for mode in ('unsupported','excluded'):
   if windows:n=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(binary),'-Mode',mode],text=True,timeout=45));assert n['exit_code']==3,n
   else:
    r=subprocess.run([str(binary),mode],text=True,capture_output=True,timeout=45);n=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);assert r.returncode==-6,n
   assert'private futex syscall:'in n['stderr']and('outside98'in n['stderr']if mode=='unsupported'else'outside admitted'in n['stderr']);(out/(label+'-'+mode+'.json')).write_text(json.dumps(n,indent=2)+'\n');negatives[mode]=n
  platforms[label]=dict(stdout=text,canonical_records=rows,races=races,checks=int(re.search(r'FUTEX-HOST-SUCCESS records=23 checks=(\d+)',text)[1]),negative_cases=negatives,binary_sha256=sha(binary),heads=len(m['traces']),objects=len(m['objects']))
 for group in (pins,tools,external,prereq):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in core.items():assert sha(prep/'source/recomp'/n)==h,n
 for n,h in fixtures.items():assert sha(HERE/n)==h,n
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');result=dict(passed=True,scope='Focused private futex component only; no game/cohort or new production signal admission.',core_sources=core,fixture_sources=fixtures,canonical_records=expected,arm64_records=23,arm64_races=nativeraces,platforms=platforms,source_pin_sha256=sha(out/'source-pin.json'),evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and'source'not in f.relative_to(out).parts},limits='ActualARM64 reference observes publickernel results; native readyflags are not kernel-enrollment proof. HostAdmission witnesses actualtickets.64race outcomes satisfy permittedrelations, not fixed scheduling. ExistingRuntimeimports clearreservations; readonlyhelper doesnot. No unrelatedregression reruns/originalGame25 call/workerrole/GCsuccess claim.')
 (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FUTEX-FOCUSED-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()