from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,re,difflib,tarfile
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--preparation',type=Path,required=True)
 for n in('out','ndk','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();PREP=a.preparation.resolve();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';shutil.copytree(PREP/'source',source);S=source/'recomp';commands=[]
 fixtures={}
 for n in('usleep_guest.c','usleep_guest.S','usleep_ref.c','usleep_test.cpp','test_usleep.py'):fixtures[n]=sha(HERE/n);shutil.copy2(HERE/n,S/'windows'/n)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(cmd,name,timeout=120):
  cmd=list(map(str,cmd));commands.append(cmd)
  with(out/name).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name} exit{r.returncode}\n'+(out/name).read_text(errors='replace')[-7000:])
 core={n:sha(S/'windows'/n)for n in('signal_host.h','signal_host.cpp','signal_sleep.h','signal_sleep.cpp')};pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()}
 with tarfile.open(PREP/'support.tar')as t:
  patch=[]
  for n in core:
   path='recomp/windows/'+n
   try:old=t.extractfile(path).read().decode()
   except KeyError:old=''
   patch.extend(difflib.unified_diff(old.splitlines(True),(S/'windows'/n).read_text().splitlines(True),fromfile='a/'+path if old else'/dev/null',tofile='b/'+path))
  (out/'usleep.patch').write_text(''.join(patch))
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror'];objects=[]
 for extension in('c','S'):
  obj=out/('guest-'+extension+'.o');run([cc,*flags,'-c',S/('windows/usleep_guest.'+extension),'-o',obj],'ndk-'+extension+'.log');objects.append(obj)
 library=out/'usleep.so';run([cc,'-shared','-nostdlib',*objects,'-o',library],'ndk-library.log');reference=out/'reference';run([cc,*flags,'-static',S/'windows/usleep_ref.c',*objects,'-pthread','-o',reference],'ndk-reference.log')
 qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');run([qemu,reference],'arm64-reference.log',45)
 def records(text):
  rows=[]
  for line in text.splitlines():
   if line.startswith('normal '):rows.append(line.split(' elapsed=',1)[0])
   if line.startswith('interrupt '):rows.append(line.split(' observed=',1)[0].replace('handlers=1','handlers=positive'))
  assert len(rows)==16
  return rows
 native=(out/'arm64-reference.log').read_text();assert'USLEEP-ARM64-SUCCESS records=16'in native;expected=records(native)
 external={str(f.resolve()):sha(f.resolve())for f in(cc,qemu,Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))};audit=PREP.parent/'game24-usleep-audit2/evidence.json';external[str(audit)]=sha(audit)
 for n,h in json.loads(audit.read_text())['artifacts'].items():assert sha(n)==h,n;external[n]=h
 (out/'source-pin.json').write_text(json.dumps(dict(core=core,fixtures=fixtures,sources=pins,tools=tools,external=external,base_preparation_sha256=sha(PREP/'preparation.json'),base_archive_sha256=sha(PREP/'support.tar')),indent=2)+'\n');platforms={};old_inputs={}
 for windows in(False,True):
  label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;translated=build/'guest'
  run([sys.executable,S/'whole/compile.py',library,'--out',translated,'--base','0x5b000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-lift.log',180)
  m=json.loads((translated/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';ccompiler='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cpp=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(S/'windows'),'-I'+path(translated),f'-DUSLEEP_LIBRARY="{path(library)}"']
  run([cxx,*cpp,'-Wall','-Wextra','-Werror','-fsyntax-only',path(S/'windows/signal_sleep.cpp'),path(S/'windows/usleep_test.cpp')],label+'-new-source-precheck.log')
  loader=build/'loader.o';run([ccompiler,'-O2','-c',path(S/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');compiled=[]
  for rel in('windows/signal_host.cpp','windows/signal_sleep.cpp','windows/signal_delivery.cpp','whole/signal_frame.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*cpp,'-c',path(S/rel),'-o',path(obj)],label+'-'+obj.stem+'.log');compiled.append(obj)
  exe=build/('usleep.exe'if windows else'usleep');run([cxx,*cpp,'-Wall','-Wextra','-Werror',path(S/'windows/usleep_test.cpp'),*map(path,compiled),path(loader),*map(path,m['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(exe)],label+'-focused-build.log');run([exe],label+'-focused.log',60);text=(out/(label+'-focused.log')).read_text();assert'USLEEP-HOST-SUCCESS records=16'in text and records(text)==expected
  negatives={}
  capture=out/'native-status.ps1'
  if windows:capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo;$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296};@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
  for mode in('excluded','throw'):
   if windows:value=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(exe),'-Mode',mode],text=True,timeout=20));assert value['exit_code']==3,value
   else:
    r=subprocess.run([str(exe),mode],capture_output=True,text=True,timeout=20);value=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);assert r.returncode==-6,value
   assert'signal sleep usleep:'in value['stderr']and('outside admitted'in value['stderr']if mode=='excluded'else'unknown exception'in value['stderr']);negatives[mode]=value;(out/(label+'-'+mode+'.json')).write_text(json.dumps(value,indent=2)+'\n')
  # Run only relevant unchanged foundation/allowed-dispatch regressions once
  # against this new frozen core. Reuse their accepted NDK objects, no relift.
  W=PREP.parent;sender=W/'signal-sender5';proof=sender/'acceptance.json';assert sha(proof)=='86d2f5d1b9292d1e089b94de3fd32071f6d78ebfa6104aad9c497b2e2286d410';old_inputs[str(proof)]=sha(proof);prior=sender/label;sm=json.loads((prior/'manifest.json').read_text());assert not sm['unsupported_traces']and not sm['unresolved_direct_targets']
  for f in[proof,sender/'sender.so',prior/'manifest.json',prior/'traces.h',*map(Path,sm['objects'])]:old_inputs[str(f)]=sha(f)
  extra={}
  for n in('libc','semaphore_host'):
   obj=build/(n+'.o');run([cxx,*cpp,'-c',path(S/('windows/'+n+'.cpp')),'-o',path(obj)],label+'-legacy-'+n+'.log');extra[n]=obj
  find=lambda n:next(f for f in compiled if f.stem==n)
  legacy=[flag for flag in cpp if flag!='-I'+path(translated)]
  allowed=build/('legacy-allowed.exe'if windows else'legacy-allowed');run([cxx,*legacy,'-I'+path(prior),f'-DSENDER_LIBRARY="{path(sender/"sender.so")}"',path(S/'windows/signal_dispatch_allowed_test.cpp'),*map(path,[find('runtime'),find('signal_host'),find('signal_delivery'),find('signal_frame'),extra['libc']]),path(loader),*map(path,sm['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(allowed)],label+'-legacy-allowed-build.log');run([allowed],label+'-legacy-allowed.log',60);at=(out/(label+'-legacy-allowed.log')).read_text();assert'SIGNAL-DISPATCH-ALLOWED-SUCCESS'in at
  foundation=W/('signal-host-'+label);fm=json.loads((foundation/'guest/manifest.json').read_text());assert not fm['unsupported_traces']and not fm['unresolved_direct_targets']
  for f in[foundation/'policy.so',foundation/'reference.bin',foundation/'guest/manifest.json',foundation/'guest/traces.h',*map(Path,fm['objects'])]:old_inputs[str(f)]=sha(f)
  default=build/('legacy-default.exe'if windows else'legacy-default');run([cxx,*legacy,'-I'+path(foundation/'guest'),f'-DSIGNAL_HOST_LIBRARY="{path(foundation/"policy.so")}"',f'-DSIGNAL_HOST_REFERENCE="{path(foundation/"reference.bin")}"',path(S/'windows/signal_host_test.cpp'),*map(path,[find('runtime'),find('signal_host'),extra['semaphore_host']]),path(loader),*map(path,fm['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(default)],label+'-legacy-default-build.log');run([default],label+'-legacy-default.log',60);dt=(out/(label+'-legacy-default.log')).read_text();assert'159 checks; NDK'in dt
  platforms[label]=dict(stdout=text,negatives=negatives,executable_sha256=sha(exe),heads=len(m['traces']),objects=len(m['objects']),legacy_allowed_stdout=at,legacy_default_stdout=dt)
 for name,h in pins.items():assert sha(name)==h,name
 for name,h in tools.items():assert sha(name)==h,name
 for name,h in external.items():assert sha(name)==h,name
 for name,h in old_inputs.items():assert sha(name)==h,name
 for n,h in core.items():assert sha(PREP/'source/recomp/windows'/n)==h,n
 for n,h in fixtures.items():assert sha(HERE/n)==h,n
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');receipt=dict(passed=True,scope='Isolated scratch only; actual NDK/Bionic reference and translated SignalHost/SignalDelivery component; no game/collector admission enabled.',core=core,fixtures=fixtures,platforms=platforms,arm64_records=16,source_pin_sha256=sha(out/'source-pin.json'),reused_legacy_inputs=old_inputs,evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and 'source'not in f.relative_to(out).parts})
 (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('USLEEP-SCRATCH-PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
