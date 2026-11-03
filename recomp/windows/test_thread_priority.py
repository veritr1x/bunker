"""Isolated Windows owned-thread priority and true platform-native JNI gate."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('priority_fixture.h','priority_guest.c','priority_guest.S','priority_ref.c','priority_test.cpp','test_thread_priority.py','thread_priority_fixture.md')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in('preparation','out','ndk','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();prep=a.preparation.resolve();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';shutil.copytree(prep/'source',source);S=source/'recomp';W=prep.parent
 preview=prep/'core-preview4.json';assert sha(preview)=='106b4defa68e40f30330c41b94af29b3b1d26fa8d386ca6a5136008dc3819d56';base=read(preview);core=base['source_files'];assert len(core)==8 and base['base_commit']=='263907fd85fc727cd895da73a23c08c2c7f67694'
 archive=prep/'base-recomp.tar';assert sha(archive)==base['base_archive_sha256']=='ec9c189465e4779cfa5b20f54a3f1f11f81df63a9d76227d3121af147ed667e0'
 for n,h in core.items():assert sha(S/n)==h
 own={n:sha(HERE/n)for n in OWN}
 for n in OWN:shutil.copy2(HERE/n,S/'windows'/n)
 peer=W/'priority-source-peer3/peer.json';assert sha(peer)=='0191336d24dd436573335a9d45fba278b4c4945df9893044d5da9a61eb31dd47'
 prereq={str(x):sha(x)for x in(preview,archive,peer)}
 primary=W/'game26-priority-plan/evidence.json';prereq[str(primary)]=sha(primary)
 for directory in('game26-priority-plan','game26-priority-audit'):
  for f in(W/directory).rglob('*'):
   if f.is_file():prereq[str(f)]=sha(f)
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};commands=[]
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(command,name,timeout=180):
  command=list(map(str,command));commands.append(command);print('STAGE',name,flush=True)
  with(out/name).open('w')as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(out/name).read_text(errors='replace')[-6000:])
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');wc=Path('/mnt/c/mingw64/bin/gcc.exe');wx=Path('/mnt/c/mingw64/bin/g++.exe')
 external={str(f.resolve()):sha(f.resolve())for f in(cc,qemu,wc,wx,Path('/usr/bin/clang++-18'),Path('/usr/bin/clang-18'))};header=W/'java-init-candidate4/jni.h';external[str(header)]=sha(header);gen=out/'generated';gen.mkdir();shutil.copy2(header,gen/'jni.h')
 flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-I'+str(S/'windows')];ndk_objects=[]
 for ext in('c','S'):
  obj=out/('guest-'+ext+'.o');run([cc,*flags,'-c',S/('windows/priority_guest.'+ext),'-o',obj],'ndk-'+ext+'.log');ndk_objects.append(obj)
 library=out/'priority.so';run([cc,'-shared','-nostdlib',*ndk_objects,'-o',library],'ndk-library.log');reference=out/'reference';run([cc,*flags,'-static',S/'windows/priority_ref.c',*ndk_objects,'-pthread','-o',reference],'reference-build.log');run([qemu,reference],'arm64-reference.log',45);reftext=(out/'arm64-reference.log').read_text();assert 'PRIORITY-ARM64-SUCCESS'in reftext
 probes=re.findall(r'ANDROID-PROBE (\d+) form=(\d+) value=(-?\d+) errno=(\d+)',reftext);assert len(probes)==10
 poison=re.findall(r'ANDROID-POISON (\d+) value=(-?\d+) errno=(\d+)',reftext);assert len(poison)==3
 (out/'source-pin.json').write_text(json.dumps(dict(base_commit=base['base_commit'],base_archive_path=str(archive),base_archive_sha256=sha(archive),core_sources=core,fixture_sources=own,source_pins=pins,tool_pins=tools,external_pins=external,prerequisites=prereq),indent=2)+'\n')
 def lift(lib,D,baseaddr):
  run([sys.executable,S/'whole/compile.py',lib,'--out',D,'--base',baseaddr,'--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],D.name+'-lift.log',240);m=read(D/'manifest.json');assert not m['unsupported_traces']and not m['unresolved_direct_targets'];return m
 build=out/'focused-guest';m=lift(library,build,'0x5d000000');opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.toolchain/'include'),'-I'+wp(S/'windows'),'-I'+wp(gen),'-I'+wp(build),f'-DPRIORITY_LIBRARY="{wp(library)}"']
 run([wx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/priority_test.cpp')],'windows-new-precheck.log')
 loader=out/'elfload.o';run([wc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader.log');compiled={}
 def object_file(rel,windows=True):
  key=(rel,windows)
  if key not in compiled:
   f=out/(Path(rel).stem+('-win.o'if windows else'-linux.o'));compiler=wx if windows else'clang++-18';path=wp if windows else str;extra=['-Wall','-Wextra','-Werror']if Path(rel).name in('thread_priority.cpp','android_process.cpp')else[]
   nativeopts=opts if windows else['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',str(a.toolchain/'include'),'-I'+str(gen)]
   run([compiler,*nativeopts,*extra,'-c',path(S/rel),'-o',path(f)],f.name+'.log');compiled[key]=f
  return compiled[key]
 objects=[object_file(rel)for rel in('whole/runtime.cpp','windows/pthread_host.cpp','windows/thread_priority.cpp','windows/android_process.cpp','windows/jni_host.cpp')]
 binary=out/'priority.exe';run([wx,*opts,'-Wall','-Wextra','-Werror',wp(S/'windows/priority_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-o',wp(binary)],'windows-focused-build.log');run([binary],'windows-focused.log',60);wintext=(out/'windows-focused.log').read_text();assert 'PRIORITY-WINDOWS-SUCCESS'in wintext and len(re.findall(r'WINDOWS-SET form=',wintext))==12
 capture=out/'native-status.ps1';capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo;$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296};@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
 def negative(exe,mode,needle,code,name):
  record=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(exe),'-Mode',mode],text=True,timeout=45));(out/name).write_text(json.dumps(record,indent=2)+'\n');assert record['exit_code']==code and needle in record['stderr'],record;return record
 negatives={mode:negative(binary,mode,needle,0xc0000409,'negative-'+mode+'.json')for mode,needle in [('group','group/user namespace'),('unowned','owned thread catalog'),('expired','Android Process adapter owner expired')]}
 legacy={}
 # Existing source bytes are frozen verbatim; no live runner or old output directories used.
 for windows in(True,False):
  label='windows'if windows else'linux';path=wp if windows else str;cxx=wx if windows else'clang++-18';exe=out/('legacy-jni.exe'if windows else'legacy-jni');run([cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(gen),path(S/'windows/jni_host_test.cpp'),path(object_file('windows/jni_host.cpp',windows)),path(object_file('whole/runtime.cpp',windows)),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(exe)],label+'-legacy-jni-build.log');run([exe],label+'-legacy-jni.log',45);legacy[label+'-jni']=dict(binary_sha256=sha(exe),log_sha256=sha(out/(label+'-legacy-jni.log')),stdout=(out/(label+'-legacy-jni.log')).read_text())
 for name,baseaddr,test,guest,macro in [('pthreads','0x70000000','pthread_test.cpp','pthread_guest_fixture.c','PTHREAD_GUEST_IMAGE'),('lifecycle','0x5a000000','worker_signal_lifecycle_test.cpp','worker_signal_lifecycle_guest.c','WORKER_SIGNAL_LIBRARY')]:
  lib=out/(name+'.so');run([cc,'-shared','-nostdlib',*flags,S/('windows/'+guest),'-o',lib],name+'-ndk.log');D=out/(name+'-guest');lm=lift(lib,D,baseaddr)
  if name=='pthreads':shutil.copy2(D/'traces.h',D/'pthread_traces.h')
  localopts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.toolchain/'include'),'-I'+wp(D),f'-D{macro}="{wp(lib)}"'];extra=[]
  if name=='lifecycle':extra=[object_file('windows/signal_host.cpp'),object_file('windows/worker_signal_lifecycle.cpp')]
  exe=out/(name+'.exe');run([wx,*localopts,wp(S/('windows/'+test)),wp(object_file('whole/runtime.cpp')),wp(object_file('windows/pthread_host.cpp')),*map(wp,extra),wp(loader),*map(wp,lm['objects']),'-static','-latomic','-pthread','-o',wp(exe)],name+'-build.log');run([exe],name+'.log',90);legacy[name]=dict(binary_sha256=sha(exe),heads=len(lm['traces']),objects=len(lm['objects']),stdout=(out/(name+'.log')).read_text())
  if name=='lifecycle':legacy[name]['negatives']={mode:negative(exe,mode,needle,0xc0000409,'legacy-'+mode[2:]+'.json')for mode,needle in [('--enter-fail','ENTER-FAILURE-CANCELLED-ESRCH'),('--active-exit','active context use'),('--foreign-use','wrong native worker')]}
 for group in(pins,tools,external,prereq):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in core.items():assert sha(prep/'source/recomp'/n)==h
 for n,h in own.items():assert sha(HERE/n)==h
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');result=dict(passed=True,scope='Actual Windows owned-thread translation + true platform-native static JNI. ARM64 real Bionic CFS contract separately observed; no Linux Pthreads provider qualification.',core_sources=core,fixture_sources=own,arm64_stdout=reftext,windows_stdout=wintext,windows_checks=int(re.search(r'PRIORITY-CHECKS (\d+)',wintext)[1]),native_negatives=negatives,legacy=legacy,heads=len(m['traces']),objects=len(m['objects']),source_pin_sha256=sha(out/'source-pin.json'),executable_sha256=sha(binary),reference_sha256=sha(reference),same_ndk_object_sha256=[sha(f)for f in ndk_objects],limits='No game execution, foreign OpenThread, processclass/boost/service changes. Tests mutate only actual owned disposable worker levels and restore before exit. Translation is not Android CFS/permission/inheritance equivalence. TID reuse/native failure injection and unsupported process-class branches are source-qualified, not manufactured live outcomes.',evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and'source'not in f.relative_to(out).parts});(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('THREAD-PRIORITY-FOCUSED-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
