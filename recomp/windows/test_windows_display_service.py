"""One frozen native-Windows Activity/window-display + actual NDK JNI gate."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent;W=HERE.parent/'work'
OWN=('windows_display_service.h','windows_display_service.cpp','windows_display_service_guest.c','windows_display_service_test.cpp','test_windows_display_service.py')
NATIVE=('native_window.h','native_window.cpp')
PROTECTED=('windows/jni_host.h','windows/jni_host.cpp','windows/android_context.h','windows/android_context.cpp','windows/windows_android_id.h','windows/windows_android_id.cpp','windows/android_assets.h','windows/android_assets.cpp','windows/apk_assets.h','windows/apk_assets.cpp','whole/runtime.h','whole/runtime.cpp','whole/bridge.h')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--support-commit',required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 commands=[]
 def run(cmd,name,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-5000:])
 commit=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'rev-parse',a.support_commit],text=True).strip();assert commit=='5525d90ef65ab7576a9f11ce43ceb1fab9514659'
 archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp'
 for n in OWN+NATIVE:shutil.copy2(HERE/n,S/'windows'/n)
 native_receipt=W/'native-window-reader-qualification2/acceptance.json';assert sha(native_receipt)=='9c3d4e4e09613cebecdfc1316253f60e112e47b0cd4ae02055f2ab849f402e0c';nr=json.loads(native_receipt.read_text());assert nr['passed']
 native_sources={n:sha(S/'windows'/n)for n in NATIVE}
 assert native_sources=={'native_window.h':'ada261e7c297915da3fd79ac5c0887911748fea4758de9b9284968b6584d8d7a','native_window.cpp':'d1b3ecb4c646df0e2edcf5502e0e17f25c6c509e64fbddd923a227c4a291ac26'}
 protected={n:sha(HERE.parent/n)for n in PROTECTED}
 for n,h in protected.items():assert sha(S/n)==h,n
 assert protected['whole/runtime.cpp']=='56c28270e218dcb62ddecc6048dda9e9e727a876478eaa4b0f87823881c5ace1'
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';CC=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe');zlib=W/'zlib-native/zlib-1.3.2';zarchive=W/'zlib-native/libz-inflate.a'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e';assert sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()};live={str(HERE/n):sha(HERE/n)for n in OWN+NATIVE};inputs={str(f):sha(f)for f in [CC.resolve(),cxx,cc,T/'remill-lift',T/'aarch64.bc',zarchive,Path(shutil.which('clang++-18')).resolve(),native_receipt]}
 for directory in (T/'include',zlib):
  for f in directory.rglob('*'):
   if f.is_file()and(directory==T/'include'or f.suffix=='.h'):inputs[str(f)]=sha(f)
 (O/'source-pin.json').write_text(json.dumps(dict(commit=commit,archive_sha256=sha(O/'support.tar'),sources=sources,live=live,inputs=inputs,protected=protected,native_window_sources=native_sources),indent=2)+'\n')
 guest=O/'display.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/windows_display_service_guest.c','-o',guest],'strict-ndk')
 G=O/'guest';run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x74000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate');manifest=json.loads((G/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(G),'-I'+wp(zlib),f'-DDISPLAY_IMAGE="{wp(guest)}"']
 for n in ('windows_display_service_test.cpp','windows_display_service.cpp'):run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows'/n)],'strict-'+Path(n).stem)
 loader=O/'elfload.o';run([cc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader');objects=[]
 for rel in ['windows/jni_host.cpp','windows/android_context.cpp','windows/windows_android_id.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','windows/windows_display_service.cpp','windows/native_window.cpp','whole/runtime.cpp']:
  obj=O/(Path(rel).stem+'.o');run([cxx,*flags,'-c',wp(S/rel),'-o',wp(obj)],'native-'+Path(rel).stem);objects.append(obj)
 exe=O/'display-test.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(S/'windows/windows_display_service_test.cpp'),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),wp(zarchive),'-static','-latomic','-pthread','-ladvapi32','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'link');run([exe],'actual-windows',120)
 output=(O/'actual-windows.log').read_text();m=re.search(r'Windows display JNI: (\d+) checks, (\d+) native logical displays;',output);wm=re.search(r'Windows activity-window JNI: (\d+) actual associated outputs;',output);assert m and wm
 for group in (sources,inputs,live):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,commit=commit,scope='One actual Windows native topology + actual NDK JNI Activity-owned WindowManager chain; actual HWND monitor association, unchanged Display SDR/scheduling policy; no game/topology mutation or Java NativeActivity construction',owned_sources={n:sha(S/'windows'/n)for n in OWN},native_window_sources=native_sources,native_window_qualification=dict(path=str(native_receipt),sha256=sha(native_receipt)),protected_sources=protected,source_pin_sha256=sha(O/'source-pin.json'),sources=sources,windows=dict(checks=int(m[1]),native_displays=int(m[2]),associated_outputs=int(wm[1]),heads=len(manifest['traces']),objects=len(manifest['objects']),binary_sha256=sha(exe)),traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],actual_output=output,executable_sha256=sha(exe),evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and 'source'not in f.relative_to(O).parts})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('WINDOWS-DISPLAY-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
