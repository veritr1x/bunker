"""Real Windows directory handles and Android dirent through strict NDK callers."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True)
 p.add_argument('--semantics-dir',type=Path);p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
 p.add_argument('--support-source',type=Path,default=HERE.parent);p.add_argument('--regression',action='store_true')
 a=p.parse_args();out=HERE.parent/'work/filesystem-directory';out.mkdir(exist_ok=True,parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(exist_ok=True,parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.cpp','.c','.inc'):shutil.copyfile(f,target/f.name)
 for name in('filesystem.h','filesystem.cpp','unicode.h','tracked_memory_test.h','filesystem_directory_guest.c','filesystem_directory_test.cpp','filesystem_test.cpp'):
  shutil.copyfile(HERE/name,source/'windows'/name)
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'directory.so'
 subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(source/'windows/filesystem_directory_guest.c'),'-o',str(library)],check=True)
 command=[sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(a.lift),'--cxx','clang++-18','--base','0x58000000','--target','x86_64-w64-windows-gnu','--resume']
 if a.semantics_dir:command+=['--semantics-dir',str(a.semantics_dir)]
 subprocess.run(command,check=True);m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 gcc='/mnt/c/mingw64/bin/gcc.exe';gxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o'
 subprocess.run([gcc,'-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
 base=[gxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.remill/'include'),'-I'+hp(out/'guest'),f'-DDIRECTORY_IMAGE="{hp(library)}"',f'-DDIRECTORY_ROOT="{hp(out)}"']
 objects=[]
 for rel in('windows/filesystem_directory_test.cpp','windows/filesystem.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');strict=['-Wall','-Wextra','-Werror']if rel.endswith('_test.cpp')else[]
  subprocess.run([*base,*strict,'-c',hp(source/rel),'-o',hp(obj)],check=True);objects.append(obj)
 binary=out/'test.exe';subprocess.run([gxx,'-static',*map(hp,objects),hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-o',hp(binary)],check=True)
 run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=180)
 (out/'stdout.log').write_text(run.stdout);(out/'stderr.log').write_text(run.stderr);print(run.stdout,end='');print(run.stderr,end='',file=sys.stderr);run.check_returncode()
 regression=None
 if a.regression:
  old=HERE.parent/'work/windows-files';prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets']
  rb=[gxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.remill/'include'),'-I'+hp(old),f'-DFILES_ROOT="{hp(old)}"','-DHAVE_GUEST_FILE_FIXTURE',f'-DGUEST_FILES_IMAGE="{hp(old/"file-guest.so")}"','-I'+hp(HERE.parent/'work/zlib-native/zlib-1.3.2')]
  ro=[]
  for name in('filesystem_test','jni_host','android_context','android_assets','apk_assets'):
   obj=out/(name+'-regression.o');subprocess.run([*rb,'-c',hp(source/'windows'/(name+'.cpp')),'-o',hp(obj)],check=True);ro.append(obj)
  exe=out/'regression.exe';subprocess.run([gxx,'-static',*map(hp,ro),*map(hp,objects[1:]),hp(loader),*map(hp,prior['objects']),hp(HERE.parent/'work/zlib-native/libz-inflate.a'),'-pthread','-latomic','-o',hp(exe)],check=True)
  result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr);result.check_returncode();regression=dict(stdout=result.stdout,stderr=result.stderr,binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
 sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
 proof=dict(passed=True,stdout=run.stdout,stderr=run.stderr,traces=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],fixture_sha256=sha(library),binary_sha256=sha(binary),toolchain=m['toolchain'],source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},runner_sha256=sha(Path(__file__)),regression=regression)
 (out/'acceptance.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
