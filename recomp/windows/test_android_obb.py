"""Freeze Context OBB capability support and run actual NDK callers plus regressions."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
OWN=('android_context.h','android_context.cpp','android_obb_storage.h','android_obb_storage.cpp','android_obb_guest.c','android_obb_test.cpp','test_android_obb.py')
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',default='81cd2d01fe53db2f42ab4aacd7a973d70f7322f1')
 for name,default in [('ndk','/home/sattam/bunker-tools/android-sdk/ndk/27.2.12479018'),('lift',HERE.parent/'work/ushll-toolchain/fa80a8edb3f33d18-9524e65b09c51e5b/remill-lift')]:p.add_argument('--'+name,type=Path,default=default)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve prior candidates';out.mkdir(parents=True);work=HERE.parent/'work';source=out/'source';host=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',host],cwd=ROOT)))as t:t.extractall(source)
 windows=source/'recomp/windows';whole=source/'recomp/whole';overlay={}
 for name in OWN:overlay[name]=sha(HERE/name);shutil.copyfile(HERE/name,windows/name)
 result={'host':host,'owned_overlay':overlay,'source_sha256':{str(f.relative_to(source)):sha(f)for d in('windows','whole','fastaes')for f in(source/'recomp'/d).iterdir()if f.is_file()and f.suffix in('.h','.c','.cpp','.inc','.py')},'platforms':{}}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n');print('Frozen '+host+' + '+str(len(OWN))+' owned files',flush=True)
 def run(command,log,**kw):
  with log.open('w')as f:r=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,**kw)
  if r.returncode:raise RuntimeError(str(log)+'\n'+log.read_text(errors='replace')[-8000:])
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 for name in('sample.h','jni.h'):shutil.copyfile(work/'java-init-candidate4'/name,out/name)
 fixture=out/'obb.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[windows/n for n in('package_guest_fixture.c','jni_object_array_guest.c','android_obb_guest.c')],'-o',fixture],out/'ndk-build.log')
 result['fixture_sha256']=sha(fixture);result['generated_headers']={n:sha(out/n)for n in('sample.h','jni.h')}
 for win in(True,False):
  label='windows'if win else'linux';build=out/label;build.mkdir();guest=build/'guest';path=wp if win else str
  run([sys.executable,whole/'compile.py',fixture,'--out',guest,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu'if win else'x86_64-linux-gnu','--cxx','clang++-18'],build/'lift.log')
  manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if win else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if win else'clang++-18';loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'recomp/fastaes/elfload.c'),'-o',path(loader)],build/'loader.log')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(work/'remill-src/include'),'-I'+path(out),'-I'+path(guest),'-I'+path(work/'zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(fixture)}"',f'-DARRAY_IMAGE="{path(fixture)}"',f'-DOBB_ROOT="{path(build/"real-volumes")}"',f'-DSTORAGE_TEST_DIRECTORY="{path(build/"internal-storage")}"']
  objects=[];sources=['windows/jni_host.cpp','windows/android_context.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp']
  if win:sources+=['windows/filesystem.cpp','windows/android_obb_storage.cpp','windows/android_internal_storage.cpp']
  if win and (windows/'growdown_memory.cpp').is_file():sources.append('windows/growdown_memory.cpp')
  for rel in sources:
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/'recomp'/rel),'-o',path(obj)],build/(Path(rel).stem+'-build.log'));objects.append(obj)
  tests={};backend=work/('zlib-native/libz-inflate.a'if win else'zlib-linux/backend/libz-inflate.a')
  for test in('android_obb','android_context','android_storage','jni_object_array'):
   exe=build/(test+('.exe'if win else''));run([cxx,*flags,'-Wall','-Wextra',path(windows/(test+'_test.cpp')),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static','-ladvapi32']if win else[]),'-o',path(exe)],build/(test+'-link.log'))
   log=build/(test+'.log');run([exe],log,timeout=90);text=log.read_text();print(label+' '+text.strip(),flush=True);tests[test]={'binary_sha256':sha(exe),'log_sha256':sha(log),'stdout':text}
   result['platforms'][label]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'tests':tests};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 for name,expected in overlay.items():assert sha(HERE/name)==expected and sha(windows/name)==expected
 result['passed']=True;result['real_fs_windows_only']=True;result['production_volume_catalog']=None;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
