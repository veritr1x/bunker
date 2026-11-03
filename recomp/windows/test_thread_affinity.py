"""Freeze and qualify only the new four-byte private owned-thread affinity profile."""
import argparse,hashlib,json,platform,re,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('affinity_fixture.h','affinity_guest.c','affinity_guest.S','affinity_ref.c','affinity_test.cpp','test_thread_affinity.py','thread_affinity_fixture.md','affinity_native_linux.c','affinity_native_linux.S')
BASE='bc438ce66f5d371ef3f3975785242d2c9b0ef811'
ARCHIVE='9452d02dec3e173aad556c7532be2f9e97f7032df561281368f7ed53e3259fd4'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in('preparation','out','ndk','toolchain','source-preview','source-peer'):p.add_argument('--'+n,type=Path,required=True)
 for n in('source-preview','source-peer'):p.add_argument('--'+n+'-sha256',required=True)
 a=p.parse_args();prep=a.preparation.resolve();out=a.out.resolve();out.mkdir(exist_ok=False);W=prep.parent
 preview=a.source_preview.resolve();peer=a.source_peer.resolve();assert sha(preview)==a.source_preview_sha256 and sha(peer)==a.source_peer_sha256
 base=read(preview);review=read(peer);assert review['passed']and base['base_commit']==BASE and base['base_archive_sha256']==ARCHIVE
 core=base['source_files'];assert set(core)=={'windows/thread_affinity.h','windows/thread_affinity.cpp'}
 assert review['source_files']==core and review['protected_base_sources']==base['protected_source_files']
 archive=prep/'base-recomp.tar';assert sha(archive)==ARCHIVE
 source=out/'source';shutil.copytree(prep/'source',source);S=source/'recomp'
 for name,digest in core.items():assert sha(S/name)==digest,name
 protected=base['protected_source_files']
 with tarfile.open(archive)as t:
  for name,digest in protected.items():assert sha(S/name)==digest==hashlib.sha256(t.extractfile('recomp/'+name).read()).hexdigest(),name
 own={name:sha(HERE/name)for name in OWN}
 for name in OWN:shutil.copy2(HERE/name,S/'windows'/name)
 prereq={str(f):sha(f)for f in(preview,peer,archive,prep/'base.json')}
 for directory in('game27-affinity-audit',):
  for f in(W/directory).rglob('*'):
   if f.is_file():prereq[str(f)]=sha(f)
 for f in prep.iterdir():
  if f.is_file():prereq[str(f)]=sha(f)
 qemu_source=W/'game25-futex-primary/qemu-8.2.2-syscall.c';prereq[str(qemu_source)]=sha(qemu_source)
 assert platform.machine()=='x86_64','native oracle assembly is explicitly x86_64, not a generic syscall forwarder'
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};commands=[]
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def run(command,name,timeout=180):
  command=list(map(str,command));commands.append(command);print('STAGE',name,flush=True)
  with(out/name).open('w')as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(out/name).read_text(errors='replace')[-5000:])
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');wc=Path('/mnt/c/mingw64/bin/gcc.exe');wx=Path('/mnt/c/mingw64/bin/g++.exe')
 external={str(f.resolve()):sha(f.resolve())for f in(cc,qemu,wc,wx,Path('/usr/bin/clang++-18'))}
 pin=dict(base_commit=BASE,base_archive_path=str(archive),base_archive_sha256=ARCHIVE,core_sources=core,fixture_sources=own,protected_source_files=protected,source_pins=pins,tool_pins=tools,external_pins=external,prerequisites=prereq)
 (out/'source-pin.json').write_text(json.dumps(pin,indent=2)+'\n')
 flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-I'+str(S/'windows')];ndk_objects=[]
 for ext in('c','S'):
  obj=out/('guest-'+ext+'.o');run([cc,*flags,'-c',S/('windows/affinity_guest.'+ext),'-o',obj],'ndk-'+ext+'.log');ndk_objects.append(obj)
 library=out/'affinity.so';run([cc,'-shared','-nostdlib',*ndk_objects,'-o',library],'ndk-library.log')
 reference=out/'reference';run([cc,*flags,'-DAFFINITY_QEMU_DIVERGENCE=1','-static',S/'windows/affinity_ref.c',*ndk_objects,'-pthread','-o',reference],'reference-build.log');run([qemu,reference],'arm64-reference.log',45)
 arm=(out/'arm64-reference.log').read_text();assert'AFFINITY-ARM64-DIVERGENCE-QUALIFIED records=22 controls8=2'in arm
 assert len(re.findall(r'ARM64-AFFINITY \d+ form=\d+ value=-1 errno=22',arm))==18 and len(re.findall(r'ARM64-AFFINITY-POISON \d+ value=-1 errno=22',arm))==4 and len(re.findall(r'ARM64-LEN8-CONTROL form=\d+ value=0 errno=731',arm))==2
 # Same request C source, independently native-compiled. This explicit
 # adapter maps Android122 to HOST SYS_sched_setaffinity, not host number122.
 nativecc=Path('/usr/bin/clang-18');external[str(nativecc.resolve())]=sha(nativecc.resolve());pin['external_pins']=external;(out/'source-pin.json').write_text(json.dumps(pin,indent=2)+'\n')
 native_objects=[]
 for name,extra in [('affinity_guest.c',['-Dsyscall=android_affinity_syscall']),('affinity_ref.c',['-Dsyscall=android_affinity_syscall','-DAFFINITY_NATIVE_LINUX=1']),('affinity_native_linux.c',[]),('affinity_native_linux.S',[])]:
  obj=out/('native-'+Path(name).name.replace('.','-')+'.o');cf=[]if name.endswith('.S')else['-std=c11','-fno-builtin'];run([nativecc,*cf,'-O1','-Wall','-Wextra','-Werror',*extra,'-I'+str(S/'windows'),'-c',S/'windows'/name,'-o',obj],'native-'+name+'.log');native_objects.append(obj)
 native_reference=out/'native-reference';run([nativecc,*native_objects,'-pthread','-o',native_reference],'native-reference-build.log');run([native_reference],'native-kernel-reference.log',45)
 native=(out/'native-kernel-reference.log').read_text();assert'AFFINITY-NATIVE-KERNEL-SUCCESS records=22'in native
 (out/'oracle-platform.json').write_text(json.dumps(dict(native_machine=platform.machine(),native_kernel=platform.release(),native_linux_is_behavior_oracle_for_size4=True,ARM64_QEMU_size4_is_divergence_only=True,ARM64_QEMU_size8_is_separate_transport_control=True),indent=2)+'\n')
 D=out/'focused-guest';run([sys.executable,S/'whole/compile.py',library,'--out',D,'--base','0x5c000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift.log',240)
 m=read(D/'manifest.json');assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.toolchain/'include'),'-I'+wp(S/'windows'),'-I'+wp(D),f'-DAFFINITY_LIBRARY="{wp(library)}"']
 run([wx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/affinity_test.cpp')],'windows-new-precheck.log')
 loader=out/'elfload.o';run([wc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader.log');objects=[]
 for rel in('whole/runtime.cpp','windows/pthread_host.cpp','windows/thread_affinity.cpp'):
  obj=out/(Path(rel).stem+'.o');extra=['-Wall','-Wextra','-Werror']if rel.endswith('thread_affinity.cpp')else[]
  run([wx,*opts,*extra,'-c',wp(S/rel),'-o',wp(obj)],obj.name+'.log');objects.append(obj)
 binary=out/'affinity.exe';run([wx,*opts,'-Wall','-Wextra','-Werror',wp(S/'windows/affinity_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-o',wp(binary)],'windows-focused-build.log');run([binary],'windows-focused.log',60)
 win=(out/'windows-focused.log').read_text();assert re.search(r'AFFINITY-WINDOWS-SUCCESS checks=\d+ records=32 canonical=22',win)
 def canonical(text,prefix):
  ordinary=[tuple(map(int,x))for x in re.findall(prefix+r'-AFFINITY (\d+) form=(\d+) value=(-?\d+) errno=(\d+)',text)if int(x[0])<=8]
  poison=[tuple(map(int,x))for x in re.findall(prefix+r'-AFFINITY-POISON (\d+) value=(-?\d+) errno=(\d+)',text)]
  assert len(ordinary)==18 and len(poison)==4
  expected=[]
  for case in range(9):
   value=-1 if case>=5 else 0;error={5:22,6:3,7:14,8:14}.get(case,731)
   expected.extend((case,form,value,error)for form in range(2))
  assert ordinary==expected and poison==[(0,0,731),(1,0,731),(2,0,731),(3,-1,3)]
  return dict(ordinary=ordinary,poison=poison)
 canonical_native=canonical(native,'NATIVE');assert canonical(win,'WINDOWS')==canonical_native
 capture=out/'native-status.ps1';capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo;$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296};@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
 negatives={}
 for mode,needle in [('length','cpusetsize profile'),('number','low32 number'),('unowned','owned thread catalog')]:
  row=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(binary),'-Mode',mode],text=True,timeout=45));(out/('negative-'+mode+'.json')).write_text(json.dumps(row,indent=2)+'\n');assert row['exit_code']==0xc0000409 and needle in row['stderr'],row;negatives[mode]=row
 for group in(pins,tools,external,prereq):
  for name,digest in group.items():assert sha(name)==digest,name
 for name,digest in core.items():assert sha(prep/'source/recomp'/name)==digest,name
 for name,digest in own.items():assert sha(HERE/name)==digest,name
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,scope='Actual Windows4B owned-worker profile versus independent real native Linux4B kernel oracle. Same strict NDK/Bionic ARM64 caller records QEMU8.2.2 len4 divergence plus separate len8 transport controls. No Windows/ARM64 affinity behavior parity claim, game or Linux Pthreads provider port.',core_sources=core,fixture_sources=own,protected_source_files=protected,canonical_records=canonical_native,native_linux_records=22,native_linux_stdout=native,arm64_divergence_records=22,arm64_len8_controls=2,arm64_stdout=arm,windows_records=32,windows_checks=int(re.search(r'AFFINITY-WINDOWS-SUCCESS checks=(\d+)',win)[1]),windows_stdout=win,native_negatives=negatives,heads=len(m['traces']),objects=len(m['objects']),same_ndk_objects=[sha(f)for f in ndk_objects],source_pin_sha256=sha(out/'source-pin.json'),executable_sha256=sha(binary),reference_sha256=sha(reference),native_kernel_reference_sha256=sha(native_reference),limits='Four-byte masks/untagged lower48/native Windows single-group indices only. QEMU rejects len4 before copy/target; its recorded EINVAL is not realAndroid/Linuxkernel4B parity and is never used as the Windows oracle. Separate8B ARM64 transport control is outside Windows profile. NativeLinux maps Android122 explicitly to host SYS_sched_setaffinity; only its real4B results compare toWindows. No foreign/process affinity/default CPU-set mutation, game mask/role inference, signal/root admission, OS failure injection or forced TID reuse. Existing protected providers byte-exact; no duplicate legacy suites.',evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and'source'not in f.relative_to(out).parts})
 (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('THREAD-AFFINITY-FOCUSED-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
