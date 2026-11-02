"""Explicit SI_TKILL sender: same NDK core on Bionic ARM64 and translated hosts."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('signal_host.h','signal_host.cpp','signal_sender_fixture.h','signal_sender_guest.c','signal_sender_test.cpp','signal_sender_ref.c','test_signal_sender.py','signal_sender.md')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('out','toolchain'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--support-commit',default='a7a0463');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));p.add_argument('--qemu',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static'));a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 def wp(q):return subprocess.check_output(['wslpath','-m',str(Path(q).resolve())],text=True).strip()
 git=['git.exe','-C',wp(HERE.parent.parent)];commit=subprocess.check_output([*git,'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output([*git,'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';overlay={}
 for n in OWN:overlay[n]=sha(HERE/n);shutil.copy2(HERE/n,source/'windows'/n)
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()}
 result={'passed':False,'support_commit':commit,'overlays':overlay,'source_pins':pins,'tool_pins':tools,'support_archive_sha256':sha(out/'support.tar'),'limits':'Explicit virtual test UID on translated hosts; native ARM64 reference uses actual Bionic getpid/getuid. No game UID profile, signal30 game activation or GC qualification.'}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 def run(cmd,name,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text(errors="replace")[-6000:]}')
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';external={str(x.resolve()):sha(x.resolve())for x in(ndk,a.qemu,Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))}
 core=out/'sender-core.o';run([ndk,'-c','-O1','-fPIC','-fno-builtin','-fno-vectorize','-fno-slp-vectorize','-fno-stack-protector','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror',source/'windows/signal_sender_guest.c','-o',core],'ndk-core-build.log')
 library=out/'sender.so';run([ndk,'-shared','-nostdlib',core,'-o',library],'guest-link.log')
 reference=out/'arm64-bionic-reference';run([ndk,'-static','-fno-emulated-tls','-O1','-Wall','-Wextra','-Werror',source/'windows/signal_sender_ref.c',core,'-o',reference],'reference-build.log');run([a.qemu,reference],'arm64-reference.log',60)
 def records(text,prefix):
  data=[]
  for line in text.splitlines():
   if not line.startswith(prefix+' '):continue
   m=re.fullmatch(prefix+r' mode=(\d+) count=(\d+) pid=(\d+) uid=(\d+) code=-6 raw=([0-9a-f]{256})',line);assert m,line
   mode,count,pid,uid=map(int,m.group(1,2,3,4));raw=bytearray.fromhex(m[5]);assert pid>0 and raw[:12]==bytes.fromhex('1e00000000000000faffffff')
   assert int.from_bytes(raw[16:20],'little')==pid and int.from_bytes(raw[20:24],'little')==uid
   raw[16:24]=b'\0'*8;assert raw==bytes.fromhex('1e00000000000000faffffff')+b'\0'*116
   data.append((mode,count,raw.hex()))
  assert len(data)==2 and [x[:2] for x in data]==[(0,1),(1,2)];return data
 native=(out/'arm64-reference.log').read_text();expected=records(native,'REFERENCE');assert 'SIGNAL-SENDER-ARM64-SUCCESS' in native
 platforms={};old_inputs={}
 for windows in (False,True):
  label='windows'if windows else'linux';build=out/label
  run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x5e000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-compile.log',900)
  manifest=json.loads((build/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  hp=wp if windows else str;cc=Path('/mnt/c/mingw64/bin/gcc.exe')if windows else'clang-18';cxx=Path('/mnt/c/mingw64/bin/g++.exe')if windows else'clang++-18'
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.toolchain/'include')];loader=build/'loader.o';run([cc,'-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],label+'-loader.log');objects={}
  for rel in ('whole/runtime.cpp','whole/signal_frame.cpp','whole/cooperative_poll.cpp','windows/libc.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/semaphore_host.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',hp(source/rel),'-o',hp(obj)],label+'-'+Path(rel).stem+'-build.log');objects[Path(rel).stem]=obj
  binary=build/('sender.exe'if windows else'sender');run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+hp(build),f'-DSENDER_LIBRARY="{hp(library)}"',hp(source/'windows/signal_sender_test.cpp'),*map(hp,[objects[n]for n in ('runtime','signal_frame','libc','signal_host','signal_delivery')]),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',hp(binary)],label+'-test-build.log')
  run([binary],label+'-focused.log',60);text=(out/(label+'-focused.log')).read_text();assert records(text,'HOST')==expected and 'SIGNAL-SENDER-HOST-SUCCESS' in text
  negatives={}
  for mode,needle in [('throw-standard','TEST sender snapshot exception'),('throw-unknown','TEST sender unknown snapshot exception'),('invalid-pid','sender PID is not a positive')]:
   if windows:
    capture=out/'capture.ps1'
    if not capture.exists():capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo
$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start()
$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296}
@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
    raw=subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',wp(capture),'-Exe',wp(binary),'-Mode',mode],text=True,timeout=30);value=json.loads(raw);assert value['exit_code']==0xc0000409 and needle in value['stderr'],value
   else:
    r=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=30);value={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr};assert r.returncode==-6 and needle in r.stderr,value
   (out/(label+'-'+mode+'.json')).write_text(json.dumps(value,indent=2)+'\n');negatives[mode]=value
  regressions={}
  for kind,macro,lib in [('signal-host','SIGNAL_HOST_LIBRARY','policy.so'),('signal-delivery','SIGNAL_DELIVERY_LIBRARY','delivery.so')]:
   old=HERE.parent/'work'/(kind+'-'+label);mm=json.loads((old/'guest/manifest.json').read_text());assert not mm['unsupported_traces']and not mm['unresolved_direct_targets']
   for q in [old/lib,old/'guest/manifest.json',old/'guest/traces.h',*map(Path,mm['objects'])]:old_inputs[str(q)]=sha(q)
   if kind=='signal-host':old_inputs[str(old/'reference.bin')]=sha(old/'reference.bin')
   extra=[f'-DSIGNAL_HOST_REFERENCE="{hp(old/"reference.bin")}"']if kind=='signal-host'else[]
   exe=build/(kind+('-regression.exe'if windows else'-regression'));names=('runtime','signal_host','semaphore_host')if kind=='signal-host'else('runtime','signal_host','signal_frame','signal_delivery','semaphore_host','cooperative_poll')
   run([cxx,*flags,'-I'+hp(old/'guest'),f'-D{macro}="{hp(old/lib)}"',*extra,hp(source/'windows'/(kind.replace('-','_')+'_test.cpp')),*map(hp,[objects[n]for n in names]),hp(loader),*map(hp,mm['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',hp(exe)],label+'-'+kind+'-regression-build.log');run([exe],label+'-'+kind+'-regression.log',90);regressions[kind]={'stdout':(out/(label+'-'+kind+'-regression.log')).read_text(),'binary_sha256':sha(exe)}
  platforms[label]={'focused_stdout':text,'binary_sha256':sha(binary),'traces':len(manifest['traces']),'objects':len(manifest['objects']),'negatives':negatives,'regressions':regressions};(out/'progress.json').write_text(json.dumps(platforms,indent=2)+'\n');print(label,'passed',flush=True)
 for n,h in overlay.items():assert sha(HERE/n)==h and sha(source/'windows'/n)==h,n
 for n,h in {**pins,**tools,**external,**old_inputs}.items():assert sha(n)==h,n
 result.update(passed=True,platforms=platforms,external_tools=external,reused_inputs=old_inputs,reference_stdout=native,fixture_sha256=sha(library),core_object_sha256=sha(core),reference_executable_sha256=sha(reference),normalization='Only process-dependent pid/uid bytes16..23 are normalized after each raw value is checked against that process/profile identity; all128 Info bytes are otherwise compared.')
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('SIGNAL-SENDER-ALL-SUCCESS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
