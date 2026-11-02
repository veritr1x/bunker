"""Freeze actual Windows pthread/signal ownership, without enabling delivery."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('worker_signal_lifecycle.h','worker_signal_lifecycle.cpp','worker_signal_lifecycle_fixture.h','worker_signal_lifecycle_guest.c','worker_signal_lifecycle_test.cpp','test_worker_signal_lifecycle.py','worker_signal_lifecycle.md')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('out','toolchain'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--support-commit',default='d6fc7a7');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 root=HERE.parent.parent
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 git=['git.exe','-C',wp(root)];commit=subprocess.check_output([*git,'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output([*git,'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';overlays={}
 for name in OWN:overlays[name]=sha(HERE/name);shutil.copy2(HERE/name,source/'windows'/name)
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};result={'passed':False,'support_commit':commit,'overlays':overlays,'source_pins':pins,'tool_pins':tools,'support_archive_sha256':sha(out/'support.tar')};(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 def run(cmd,name,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text(errors="replace")[-5000:]}')
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe');external={str(x.resolve()):sha(x.resolve())for x in(ndk,cxx,cc,Path('/usr/bin/clang++-18'))}
 library=out/'fixture.so';run([ndk,'-shared','-fPIC','-nostdlib','-O1','-fno-stack-protector','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror',source/'windows/worker_signal_lifecycle_guest.c','-o',library],'ndk-build.log')
 build=out/'guest';run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x5a000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'guest-compile.log',900);manifest=json.loads((build/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.toolchain/'include'),'-I'+wp(source/'windows'),'-I'+wp(source/'whole'),'-I'+wp(source/'fastaes'),'-I'+wp(build),f'-DWORKER_SIGNAL_LIBRARY="{wp(library)}"'];loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'loader-build.log');objects=[]
 for filename,new in [('whole/runtime.cpp',False),('windows/pthread_host.cpp',False),('windows/signal_host.cpp',False),('windows/worker_signal_lifecycle.cpp',True),('windows/worker_signal_lifecycle_test.cpp',True)]:
  obj=out/(Path(filename).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if new else[]),'-c',wp(source/filename),'-o',wp(obj)],Path(filename).stem+'-build.log');objects.append(obj)
 binary=out/'worker-signal.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(binary)],'link.log');run([binary],'focused.log',60);text=(out/'focused.log').read_text();assert'WORKER-SIGNAL-LIFECYCLE-SUCCESS 'in text and'no-delivery-no-GC'in text
 capture=out/'capture.ps1';capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo
$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start()
$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296}
@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
 negatives={}
 for mode,needle in [('--enter-fail','ENTER-FAILURE-CANCELLED-ESRCH'),('--active-exit','worker signal retirement has active context use'),('--foreign-use','worker signal use released on wrong native worker')]:
  raw=subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',wp(capture),'-Exe',wp(binary),'-Mode',mode],text=True,timeout=30);(out/(mode[2:]+'.json')).write_text(raw);value=json.loads(raw);assert value['exit_code']==0xc0000409 and needle in value['stderr'],value;negatives[mode]=value
 for name,s in overlays.items():assert sha(HERE/name)==s and sha(source/'windows'/name)==s
 for name,s in{**pins,**tools,**external}.items():assert sha(name)==s
 result.update({'passed':True,'focused_stdout':text.strip(),'negatives':negatives,'executable_sha256':sha(binary),'fixture_sha256':sha(library),'traces':len(manifest['traces']),'objects':len(manifest['objects']),'external_tools':external,'scope':'actual Windows Pthreads workers/TLS plus virtual signal ownership only; no delivery or collector registration'})
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(text.strip());print('WORKER-SIGNAL-ALL-SUCCESS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
