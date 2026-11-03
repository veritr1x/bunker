"""Immutable real ELF / Android caller dladdr and opt-in Bionic ABS gates."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('module_registry.h','module_registry.cpp','module_registry_elf.h','module_registry_elf.cpp','module_dladdr_guest.c','module_dladdr_fixture.c','module_dladdr_fixture.S','module_dladdr_ref.c','module_dladdr_test.cpp','test_module_dladdr.py')
ROOT_OWN=('fastaes/elfload.h','fastaes/elfload.c')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in('out','ndk','toolchain','glibc','game-support'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[]
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(command,name,timeout=300):
  command=list(map(str,command));commands.append(command)
  with(out/name).open('w')as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name} exit{r.returncode}\n{(out/name).read_text(errors="replace")[-6000:]}')
 commit='40a290b3241f50d5dfb0953372049178180beec7';archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as t:t.extractall(out/'host',filter='data')
 source=out/'host/recomp';overlays={}
 for n in OWN:overlays['windows/'+n]=sha(HERE/n);shutil.copy2(HERE/n,source/'windows'/n)
 for n in ROOT_OWN:overlays[n]=sha(HERE.parent/n);shutil.copy2(HERE.parent/n,source/n)
 sources={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};external={str(f):sha(f)for f in a.glibc.rglob('*')if f.is_file()}
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ndkflags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror']
 obj=out/'caller.o';run([cc,*ndkflags,'-c',source/'windows/module_dladdr_guest.c','-o',obj],'ndk-caller.log')
 caller=out/'caller.so';run([cc,'-shared','-nostdlib',obj,'-Wl,--pack-dyn-relocs=none','-o',caller],'ndk-library.log')
 libraries=[];versions=out/'versions.map';versions.write_text('V1 {}; V2 {} V1;\n')
 for style in('sysv','gnu'):
  lib=out/(style+'.so');run([cc,*ndkflags,'-shared','-nostdlib',source/'windows/module_dladdr_fixture.c',source/'windows/module_dladdr_fixture.S','-Wl,--hash-style='+style,'-Wl,--version-script='+str(versions),'-Wl,--pack-dyn-relocs=none','-Wl,-soname,fixture.so','-o',lib],style+'-fixture.log');libraries.append(lib)
 # This is dynamic ARM64 glibc, not the NDK static dladdr always-false stub.
 libdir=a.glibc/'usr/aarch64-linux-gnu/lib';refobj=out/'reference.o';run([cc,*ndkflags,'-c',source/'windows/module_dladdr_ref.c','-o',refobj],'reference-compile.log')
 ref=out/'reference';run([cc,'-nostdlib','-no-pie','-Wl,--dynamic-linker=/lib/ld-linux-aarch64.so.1',libdir/'crt1.o',libdir/'crti.o',refobj,obj,libdir/'libc.so.6',libdir/'libdl.so.2',libdir/'crtn.o','-o',ref],'reference-link.log')
 qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
 for library in libraries:run([qemu,'-L',a.glibc/'usr/aarch64-linux-gnu',ref,library],'arm64-'+library.stem+'.log',60);assert'DLADDR-ARM64-GLIBC-SUCCESS records=10'in(out/('arm64-'+library.stem+'.log')).read_text()
 original=a.game_support/'native/libil2cpp.so';assert sha(original)=='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522';external[str(original)]=sha(original)
 unity=a.game_support/'native/libunity.so';assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';external[str(unity)]=sha(unity)
 primary=HERE.parent/'work/game23-dladdr-audit/evidence.json';record=json.loads(primary.read_text());external[str(primary)]=sha(primary)
 for key in('files','artifacts','artifact_sha256'):
  for name,digest in record.get(key,{}).items():
   if isinstance(digest,str)and len(digest)==64:
    actual=Path(subprocess.check_output(['wslpath','-u',name],text=True).strip())if re.match(r'^[A-Za-z]:',name)else Path(name)
    assert sha(actual)==digest,name;external[str(actual)]=digest
 for f in[cc,qemu,Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe')]:external[str(f.resolve())]=sha(f.resolve())
 (out/'source-pin.json').write_text(json.dumps(dict(overlays=overlays,sources=sources,tools=tools,external=external),indent=2)+'\n');platforms={}
 for windows in(False,True):
  label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;translated=build/'guest'
  run([sys.executable,source/'whole/compile.py',caller,'--out',translated,'--base','0x5d000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-lift.log')
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';ccompiler='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(translated),f'-DCALLER_LIBRARY="{path(caller)}"',f'-DSYSV_LIBRARY="{path(libraries[0])}"',f'-DGNU_LIBRARY="{path(libraries[1])}"',f'-DIL2CPP_LIBRARY="{path(original)}"',f'-DUNITY_LIBRARY="{path(unity)}"']
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',path(source/'windows/module_dladdr_test.cpp'),path(source/'windows/module_registry_elf.cpp'),path(source/'windows/module_registry.cpp')],label+'-new-source-precheck.log')
  loader=build/'loader.o';run([ccompiler,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');objects=[]
  for rel in('windows/module_registry.cpp','windows/module_registry_elf.cpp','whole/runtime.cpp'):
   o=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(o)],label+'-'+Path(rel).stem+'.log');objects.append(o)
  exe=build/('dladdr.exe'if windows else'dladdr');run([cxx,*flags,'-Wall','-Wextra','-Werror',path(source/'windows/module_dladdr_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(exe)],label+'-focused-build.log');run([exe],label+'-focused.log',120);text=(out/(label+'-focused.log')).read_text();assert'DLADDR-SUCCESS'in text
  for i,library in enumerate(libraries,1):
   reference=[line for line in(out/('arm64-'+library.stem+'.log')).read_text().splitlines()if not line.startswith('DLADDR-')]
   observed=[line.split(' ',1)[1]for line in text.splitlines()if line.startswith(f'reference-{i} ')]
   assert len(reference)==11 and observed==reference,(label,library,observed,reference)
  negatives={}
  capture=out/'native-status.ps1'
  if windows:capture.write_text('''param([string]$Exe,[string]$Mode)
$i=New-Object System.Diagnostics.ProcessStartInfo
$i.FileName=$Exe;$i.Arguments=$Mode;$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardOutput=$true;$i.RedirectStandardError=$true
$p=New-Object System.Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();$o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd();$p.WaitForExit();$c=[long]$p.ExitCode;if($c-lt 0){$c+=4294967296};@{exit_code=$c;stdout=$o;stderr=$e}|ConvertTo-Json -Compress
''')
  for mode in('incomplete','ifunc','tls','ambiguity'):
   if windows:value=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-File',wp(capture),'-Exe',wp(exe),'-Mode',mode],text=True,timeout=30));assert value['exit_code']==3,value
   else:
    r=subprocess.run([str(exe),mode],capture_output=True,text=True,timeout=30);value=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);assert r.returncode==-6,value
   expected='incomplete active'if mode=='incomplete'else'ambiguous default'if mode=='ambiguity'else'IFUNC/TLS';assert expected in value['stderr']and'module registry dl'in value['stderr'];negatives[mode]=value;(out/(label+'-'+mode+'.json')).write_text(json.dumps(value,indent=2)+'\n')
  unit=build/('module-unit.exe'if windows else'module-unit');run([cxx,*flags,path(source/'windows/module_registry_test.cpp'),path(build/'module_registry.o'),path(build/'runtime.o'),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(unit)],label+'-unit-build.log');run([unit],label+'-unit.log');assert'checks passed'in(out/(label+'-unit.log')).read_text()
  platforms[label]=dict(stdout=text,unit=(out/(label+'-unit.log')).read_text(),negatives=negatives,heads=len(manifest['traces']),objects=len(manifest['objects']),executable_sha256=sha(exe))
 for name,digest in sources.items():assert sha(name)==digest,name
 for name,digest in tools.items():assert sha(name)==digest,name
 for name,digest in external.items():assert sha(name)==digest,name
 for name,digest in overlays.items():assert sha(HERE.parent/name)==digest,name
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');receipt=dict(passed=True,commit=commit,platforms=platforms,arm64_reference='Actual dynamic glibc under QEMU: same NDK caller object and same NDK SysV/GNU ELF fixtures; only common Bionic/glibc behavior compared. Android-specific ABS/tag/local/order cases qualified from pinned primary plus strict component oracle, not glibc.',original_execution='Original IL2CPP relocation/data only; no constructors or guest original code executed.',overlays=overlays,source_pin_sha256=sha(out/'source-pin.json'),evidence={str(f):sha(f)for f in out.rglob('*')if f.is_file()and 'host'not in f.relative_to(out).parts})
 (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('MODULE-DLADDR-PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
