"""One focused native-Windows display/JNI gate; no game or OS settings changes."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 def sha(p):
  with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(cmd,name):
  print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:r=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,timeout=300)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-5000:])
 S=O/'source';S.mkdir()
 for directory in ['windows','whole','fastaes']:
  (S/directory).mkdir()
  for f in(HERE.parent/directory).iterdir():
   if f.is_file()and f.suffix in ['.h','.cpp','.c','.py']:shutil.copy2(f,S/directory/f.name)
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()}
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';CC=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');guest=O/'display.so'
 run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/windows_display_service_guest.c','-o',guest],'ndk')
 G=O/'guest';run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x74000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate');manifest=json.loads((G/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
 cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';loader=O/'elfload.o';run([cc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader')
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(G),'-I'+wp(W/'zlib-native/zlib-1.3.2'),f'-DDISPLAY_IMAGE="{wp(guest)}"'];objects=[]
 for rel in ['windows/jni_host.cpp','windows/android_context.cpp','windows/windows_android_id.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','windows/windows_display_service.cpp','whole/runtime.cpp']:
  obj=O/(Path(rel).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if rel.endswith('windows_display_service.cpp')else[]),'-c',wp(S/rel),'-o',wp(obj)],Path(rel).stem);objects.append(obj)
 exe=O/'display-test.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(S/'windows/windows_display_service_test.cpp'),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),wp(W/'zlib-native/libz-inflate.a'),'-static','-latomic','-pthread','-ladvapi32','-luser32','-o',wp(exe)],'link');run([exe],'actual-windows')
 for n,h in sources.items():assert sha(n)==h,n
 current={n:sha(HERE/n)for n in ['windows_display_service.h','windows_display_service.cpp','windows_display_service_guest.c','windows_display_service_test.cpp','test_windows_display_service.py']}
 for n,h in current.items():assert sha(S/'windows'/n)==h,n
 result=dict(passed=True,scope='One actual Windows native topology + actual NDK JNI method gate; no game, topology mutation or Android hardware emulation claim',owned_sources=current,sources=sources,JNI_core={n:sha(S/'windows'/n)for n in ['jni_host.h','jni_host.cpp']},Context_sha256=sha(S/'windows/android_context.cpp'),NDK_guest_sha256=sha(guest),traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],actual_output=(O/'actual-windows.log').read_text(),executable_sha256=sha(exe))
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('WINDOWS-DISPLAY-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
