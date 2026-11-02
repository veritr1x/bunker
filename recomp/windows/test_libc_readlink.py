"""Strict NDK ABI + native process-image reference; closed readlink profile only."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('libc.h','libc.cpp','libc_readlink_guest.c','libc_readlink_ref.c','libc_readlink_test.cpp','test_libc_readlink.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in('out','ndk','toolchain'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--reuse-linux',type=Path)
 p.add_argument('--reuse-windows',type=Path)
 a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);work=HERE.parent/'work'
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 commands=[]
 def run(command,name,timeout=300):
  command=list(map(str,command));commands.append(command)
  with(out/name).open('w')as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name} exit{r.returncode}\n{(out/name).read_text(errors="replace")[-6000:]}')
 commit='91c4b6799ca0378735c9cebb42aec20b920e53e6';archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';old=(source/'windows/libc.cpp').read_text();overlay={}
 for n in OWN:overlay[n]=sha(HERE/n);shutil.copy2(HERE/n,source/'windows'/n)
 def markers(s):return re.findall(r'"([^\"]+)"',s.split('const char *const imports[] = {',1)[1].split('};',1)[0])
 oldmarkers=markers(old);assert markers((source/'windows/libc.cpp').read_text())==oldmarkers+['readlink']
 (out/'old_markers.h').write_text('#pragma once\ninline constexpr const char*kOldMarkers[]={'+','.join(json.dumps(x)for x in oldmarkers)+'};\n')
 sources={str(p):sha(p)for p in source.rglob('*')if p.is_file()};tools={str(p):sha(p)for p in a.toolchain.rglob('*')if p.is_file()};cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 ndkflags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror']
 obj=out/'caller.o';run([cc,*ndkflags,'-c',source/'windows/libc_readlink_guest.c','-o',obj],'ndk-caller.log')
 library=out/'readlink.so';run([cc,'-shared','-nostdlib',obj,'-o',library],'ndk-library.log')
 ref=out/'reference';run([cc,*ndkflags,'-static',source/'windows/libc_readlink_ref.c',obj,'-o',ref],'ndk-reference.log')
 qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');run([qemu,ref],'arm64-reference.log',60)
 reftext=(out/'arm64-reference.log').read_text();records=[]
 for line in reftext.splitlines():
  m=re.fullmatch(r'(\S+) mode=(\d) count=(-?\d+) errno=(\d+) canary=([0-9a-f]+)(?: bytes=([0-9a-f]+))?',line);assert m,line
  label,mode,count,error,canary=m[1],int(m[2]),int(m[3]),int(m[4]),m[5];data=bytes.fromhex(m[6]or'')
  assert canary=='a5'
  if label in('self','pid'):assert data==str(ref).encode()and count==len(data)and error==731
  elif label=='one':assert count==1 and data==b'/'and error==731
  elif label=='zero':assert count==-1 and error==22
  else:assert count==-1 and error==14 # Measured QEMU pointer-first divergence for cap0.
  records.append(dict(label=label,mode=mode,count=count,errno=error))
 assert len(records)==18
 primary=work/'readlink-native-audit2/android13-fs-stat.c';assert sha(primary)=='6fb1827c360595213c71e828d97d8ad452eb62ffd4c544ad1a4c579742bc3dd9'
 native_evidence={str(p):sha(p)for p in[primary,work/'readlink-native-audit2/linux-native.stdout',work/'readlink-native-audit2/reference.stdout',work/'readlink-native-audit2/reference-evidence.json']}
 external={str(p.resolve()):sha(p.resolve())for p in[cc,qemu,Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe')]};platforms={};prior_inputs={}
 (out/'source-pin.json').write_text(json.dumps(dict(overlays=overlay,sources=sources,tools=tools,native_reference_inputs=native_evidence,external=external),indent=2)+'\n')
 for windows in(False,True):
  if not windows and a.reuse_linux:
   previous=a.reuse_linux.resolve();oldpin=json.loads((previous/'source-pin.json').read_text());assert {k:v for k,v in oldpin['overlays'].items()if k!='test_libc_readlink.py'}=={k:v for k,v in overlay.items()if k!='test_libc_readlink.py'}
   for group in('sources','tools','native_reference_inputs','external'):
    for name,h in oldpin[group].items():assert sha(name)==h,name;prior_inputs[name]=h
   for name in('linux-focused.log','linux-unit.log','linux-startup.log'):
    text=(previous/name).read_text();assert ('READLINK-SUCCESS'if name=='linux-focused.log'else'4293 checks passed'if name=='linux-unit.log'else'7 startup gates passed')in text
   for file in [previous/'source-pin.json',*previous.glob('linux-*.log'),*(previous/'linux').rglob('*')]:
    if file.is_file():prior_inputs[str(file)]=sha(file)
   pm=json.loads((previous/'linux/guest/manifest.json').read_text());platforms['linux']=dict(reused_candidate=str(previous),reused_input_equivalence='Only runner Windows fatal-status transport changed; all five other overlays and frozen inputs revalidated.',focused_stdout=(previous/'linux-focused.log').read_text(),executable_sha256=sha(previous/'linux/readlink'),unit_stdout=(previous/'linux-unit.log').read_text(),startup_stdout=(previous/'linux-startup.log').read_text(),heads=len(pm['traces']),objects=len(pm['objects']))
   print('linux qualified unchanged prior positive/unit/startup reused',flush=True);continue
  label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;translated=build/'guest'
  reused=windows and a.reuse_windows is not None
  if reused:
   previous=a.reuse_windows.resolve();oldpin=json.loads((previous/'source-pin.json').read_text());assert {k:v for k,v in oldpin['overlays'].items()if k!='test_libc_readlink.py'}=={k:v for k,v in overlay.items()if k!='test_libc_readlink.py'}
   for group in('sources','tools','native_reference_inputs','external'):
    for name,h in oldpin[group].items():assert sha(name)==h,name;prior_inputs[name]=h
   for file in[previous/'source-pin.json',*previous.glob('windows-*.log'),*previous.glob('windows-*.json'),*(previous/'windows').rglob('*')]:
    if file.is_file():prior_inputs[str(file)]=sha(file)
   translated=previous/'windows/guest'
  else:run([sys.executable,source/'whole/compile.py',library,'--out',translated,'--base','0x5c000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-lift.log')
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';ccompiler='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(out),'-I'+path(translated),f'-DREADLINK_LIBRARY="{path(library)}"']
  if reused:
   loader=previous/'windows/loader.o';objects=[previous/'windows/libc.o',previous/'windows/runtime.o'];exe=previous/'windows/readlink.exe';text=(previous/'windows-focused.log').read_text();assert'READLINK-SUCCESS 'in text
  else:
   run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',path(source/'windows/libc_readlink_test.cpp')],label+'-new-source-precheck.log')
   loader=build/'loader.o';run([ccompiler,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');objects=[]
   for rel in('windows/libc.cpp','whole/runtime.cpp'):
    o=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(o)],label+'-'+Path(rel).stem+'.log');objects.append(o)
   exe=build/('readlink.exe'if windows else'readlink');run([cxx,*flags,'-Wall','-Wextra','-Werror',path(source/'windows/libc_readlink_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(exe)],label+'-focused-build.log')
   run([exe],label+'-focused.log',90);text=(out/(label+'-focused.log')).read_text();assert'READLINK-SUCCESS 'in text
  negatives={}
  for mode in('foreign','otherlink'):
   if reused:
    value=json.loads((previous/(label+'-'+mode+'.json')).read_text());assert value['exit_code']==3
   elif windows:
    capture=out/'native-status.ps1'
    if not capture.exists():capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo
$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start()
$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296}
@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
    # This fixture disables UCRT abort reporting and genuinely exits3; measure
    # the full native status rather than confusing it with a truncated NT code.
    value=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',wp(capture),'-Exe',wp(exe),'-Mode',mode],text=True,timeout=30));assert value['exit_code']==3,value
   else:
    r=subprocess.run([str(exe),mode],capture_output=True,text=True,timeout=30);value=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);assert r.returncode==-6
   (out/(label+'-'+mode+'.json')).write_text(json.dumps(value,indent=2)+'\n');assert'unsupported readlink path outside current-process executable profile'in value['stderr']and'libc import readlink failed'in value['stderr']and'guest libc fatal: readlink'in value['stderr'];negatives[mode]=value
  variants=[]
  if windows:
   capture=out/'native-positive.ps1';capture.write_text('''param([string]$Exe)
$ErrorActionPreference='Stop'
$i=New-Object System.Diagnostics.ProcessStartInfo
$i.FileName=$Exe;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i
try{[void]$p.Start()}catch{$e=$_.Exception;while($null-ne $e.InnerException){$e=$e.InnerException};@{exit_code=$null;launch_error=$e.Message;native_error=$e.NativeErrorCode}|ConvertTo-Json -Compress;exit 0}
$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit()
@{exit_code=$p.ExitCode;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
   for longpath in(False,True):
    directory=out/'windows'/'unicode-\u03a9-\u6d4b\u8bd5'
    if longpath:
     for i in range(4):directory/=str(i)+'-'+('native-image-long-'*3)
    directory.mkdir(parents=True,exist_ok=True);copy=directory/'readlink.exe';shutil.copy2(exe,copy)
    assert (len(wp(copy))>256)==longpath
    launch='\\\\?\\'+wp(copy).replace('/','\\')if longpath else wp(copy)
    raw=subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',wp(capture),'-Exe',launch],text=True,timeout=90);value=json.loads(raw);name=label+'-unicode'+('-longpath'if longpath else'')+'.json';(out/name).write_text(json.dumps(value,indent=2)+'\n')
    if value.get('launch_error'):
     assert longpath and value['native_error']==206,value
     variants.append(dict(path=str(copy),native_launch_path=launch,sha256=sha(copy),qualified=False,limit='Native launcher rejected path before child/provider; query-growth branch unexecuted',**value))
    else:
     assert value['exit_code']==0 and'READLINK-SUCCESS 'in value['stdout'],value
     variants.append(dict(path=str(copy),native_launch_path=launch,sha256=sha(copy),qualified=True,**value))
  regression=build/('libc-regression.exe'if windows else'libc-regression');run([cxx,*flags,path(source/'windows/libc_test.cpp'),*map(path,objects),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(regression)],label+'-unit-build.log');run([regression],label+'-unit.log',90)
  prior=work/('libc-windows'if windows else'libc-linux');pm=json.loads((prior/'manifest.json').read_text());assert not pm['unsupported_traces']and not pm['unresolved_direct_targets']
  for p in[prior/'manifest.json',prior/'libc-guest.so',prior/'traces.h',*map(Path,pm['objects'])]:prior_inputs[str(p)]=sha(p)
  startup=build/('startup.exe'if windows else'startup');run([cxx,*[f for f in flags if not f.startswith('-I'+path(translated))],'-I'+path(prior),f'-DLIBC_LIBRARY="{path(prior/"libc-guest.so")}"',path(source/'windows/libc_guest_test.cpp'),*map(path,objects),path(loader),*map(path,pm['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(startup)],label+'-startup-build.log');run([startup],label+'-startup.log',90)
  platforms[label]=dict(focused_stdout=text,executable_path=str(exe),executable_sha256=sha(exe),reused_positive_and_negatives_candidate=str(previous)if reused else None,negative_modes=negatives,variants=variants,unit_stdout=(out/(label+'-unit.log')).read_text(),startup_stdout=(out/(label+'-startup.log')).read_text(),heads=len(manifest['traces']),objects=len(manifest['objects']));print(label,'passed',flush=True)
 for n,h in overlay.items():assert sha(HERE/n)==h and sha(source/'windows'/n)==h,n
 for p,h in{**sources,**tools,**external,**native_evidence,**prior_inputs}.items():assert sha(p)==h,p
 result=dict(passed=True,support_commit=commit,archive_sha256=sha(out/'support.tar'),overlays=overlay,source_pins=sources,tool_pins=tools,external_tools=external,native_reference_inputs=native_evidence,prior_inputs=prior_inputs,arm64_reference=records,platforms=platforms,commands=commands,limits='Current native process-image metadata only, no VFS alias/mount/reopen or general links. Android primary signedlow32/capacity-first error ordering; measured QEMU null-pointer-first differences separately asserted. No game/GC or new ISA execution.')
 result['evidence']={str(p.relative_to(out)):sha(p)for p in out.rglob('*')if p.is_file()and'host'not in p.relative_to(out).parts and p.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('READLINK-ALL-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
