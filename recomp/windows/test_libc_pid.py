"""Actual Android getpid callers against independent Windows/Linux process identity."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWNED=('libc.h','libc.cpp','libc_pid_guest.c','libc_pid_test.cpp')

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Use a fresh result directory'
 out.mkdir(parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWNED:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kwargs):return subprocess.run(list(map(str,command)),check=True,**kwargs)
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def digest(path):
  with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 guest=out/'pid.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/libc_pid_guest.c','-o',guest])
 result={'fixture_sha256':digest(guest),'platforms':{},'source_sha256':{str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},'owned_overlay':list(OWNED),'support_source':str(a.support_source),'runner_sha256':digest(__file__)}
 for windows in(True,False):
  platform='windows'if windows else'linux';build=out/platform;build.mkdir();translated=build/'guest'
  run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x59000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  path=hp if windows else lambda p:str(p)
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
  loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(HERE.parent/'work/remill-src/include')]
  objects=[]
  for rel in('windows/libc.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  exe=build/('test.exe'if windows else'test')
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+path(translated),f'-DPID_LIBRARY="{path(guest)}"',path(source/'windows/libc_pid_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
  test=run([exe],capture_output=True,text=True,timeout=90);print(platform+': '+test.stdout,end='');print(test.stderr,end='',file=sys.stderr)
  regressions={}
  for name,prior,library,macro in [('process','libc-process-windows'if windows else'libc-process-linux','process.so','PROCESS_LIBRARY')]+([('wall_time','libc-wall-time','wall.so','WALL_LIBRARY')]if windows else[]):
   previous=HERE.parent/'work'/prior;prior_manifest=json.loads((previous/'guest/manifest.json').read_text());assert not prior_manifest['unsupported_traces']and not prior_manifest['unresolved_direct_targets']
   regression=build/(name+('-regression.exe'if windows else'-regression'))
   run([cxx,*flags,'-I'+path(previous/'guest'),f'-D{macro}="{path(previous/library)}"',path(source/f'windows/libc_{name}_test.cpp'),*map(path,objects),path(loader),*map(path,prior_manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(regression)])
   reg=run([regression],capture_output=True,text=True,timeout=90);print(platform+' '+name+': '+reg.stdout,end='');print(reg.stderr,end='',file=sys.stderr)
   regressions[name]={'stdout':reg.stdout,'stderr':reg.stderr,'binary_sha256':digest(regression),'fixture_sha256':digest(previous/library)}
  result['platforms'][platform]={'stdout':test.stdout,'stderr':test.stderr,'binary_sha256':digest(exe),'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'regressions':regressions}
  (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
