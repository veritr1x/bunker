"""Pinned Firebase9.6 Windows SDK with actual translated AArch64 callback ABI."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(p)],text=True).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',type=Path);a=ap.parse_args();o=a.out;o.mkdir(exist_ok=False);s=o/'source';packet=W/'firebase-startup-java-audit1/source-manifest5.json';assert sha(packet)=='144d754dc1c9b234779cd52d7c949288461328244af96fcc5117e8428579341f';p=json.loads(packet.read_text());production={n:d['live']['sha256']for n,d in p['production_sources'].items()};commands=[];reused=[]
 units=['windows/firebase_app.cpp','windows/module_registry.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/firebase_app_test.cpp'];needed=set(units)|{'fastaes/elfload.c','windows/firebase_app_guest.c','windows/test_firebase_app.py'}
 for folder in ['windows','whole','fastaes']:
  (s/folder).mkdir(parents=True)
  for f in(HERE.parent/folder).iterdir():
   if f.is_file()and(f.suffix in('.h','.inc')or folder+'/'+f.name in needed):shutil.copyfile(f,s/folder/f.name)
 for n,h in production.items():assert sha(s/n)==h==sha(HERE.parent/n)
 sdk=W/'firebase-windows-sdk1/package/Firebase/Plugins/x86_64/FirebaseCppApp-9_6_0.dll';assert sha(sdk)=='f85bb9f82d79176d3d5da322780d437c023191370e608c45723ad6d83c4d1a12';frozen_sdk=o/'native/FirebaseCppApp-9_6_0.dll';frozen_sdk.parent.mkdir();shutil.copyfile(sdk,frozen_sdk)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(o/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(o/(label+'.log')).open('w')as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');tool=W/'integer-popcount8b-preparation1/toolchains/f967bf3b57f889d7-469903ec4d84cbd3';guest=o/'firebase-app.so'
 if a.reuse:
  assert sha(a.reuse/'source/windows/firebase_app_guest.c')==sha(s/'windows/firebase_app_guest.c');shutil.copyfile(a.reuse/'firebase-app.so',guest);shutil.copytree(a.reuse/'guest',o/'guest');reused+=[desc(a.reuse/'commands.json'),desc(a.reuse/'guest/manifest.json'),desc(a.reuse/'firebase-app.so')]
 else:
  run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-vectorize','-fno-slp-vectorize','-Wall','-Wextra','-Werror',s/'windows/firebase_app_guest.c','-o',guest],'compile-NDK')
  run([sys.executable,HERE.parent/'whole/compile.py',guest,'--out',o/'guest','--base','0x62000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK')
 m=json.loads((o/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets'];shutil.copyfile(o/'guest/traces.h',o/'traces.h')
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(o),'-DFIREBASE_GUEST="'+wp(guest)+'"','-DFIREBASE_DLL=L"'+wp(frozen_sdk)+'"'];objects=[]
 for n in units:
  obj=o/(Path(n).stem+'.o')
  if a.reuse and not n.endswith('firebase_app_test.cpp') and sha(a.reuse/'source'/n)==sha(s/n):
   assert sha(a.reuse/'source'/n)==sha(s/n)
   for d in ['windows','whole']:
    for h in(s/d).glob('*.h'):
     old=a.reuse/'source'/d/h.name
     if old.exists():assert sha(old)==sha(h)
   obj=a.reuse/obj.name;reused.append(desc(obj))
  else:run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('firebase_app_test.cpp')else[]),'-c',wp(s/n),'-o',wp(obj)],'compile-'+obj.stem)
  objects.append(obj)
 loader=o/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(s/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=o/'firebase-app.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,map(Path,m['objects'])),'-Wl,--wrap=__imp_GetProcAddress','-Wl,--wrap=_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE','-static','-pthread','-latomic','-lbcrypt','-o',wp(exe)],'link');run([exe],'actual-NDK-Windows');run([exe,'foreign'],'actual-foreign-callback')
 text=(o/'actual-NDK-Windows.log').read_text();match=re.search(r'FIREBASE-PASS checks=(\d+) actual_NDK_calls=(\d+) callback_runs=(\d+) replayed_callbacks=15 allocations=3 frees=3 installed_calls=(\d+) commands=18 native_dependency=(-?\d+) State=1200 Memory64=8',text);assert match;assert 'FIREBASE-FOREIGN-PASS' in(o/'actual-foreign-callback.log').read_text()
 for n,h in production.items():assert sha(HERE.parent/n)==h
 result=dict(passed=True,production_source_manifest=desc(packet),production_sources=production,native_sdk=desc(frozen_sdk),original_string_ownership=desc(W/'firebase-string-ownership1/acceptance.json'),original_sdk=desc(sdk),guest=desc(guest),guest_manifest=desc(o/'guest/manifest.json'),toolchain={n:desc(tool/n)for n in['remill-lift','aarch64.bc']},guest_runtime_support_sources={n:desc(s/n)for n in needed},source_snapshot={str(f.relative_to(s)):sha(f)for f in s.rglob('*')if f.is_file()},reused_inputs=reused,commands=commands,focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),translated_callback_runs=int(match[3]),installed_calls=int(match[4]),native_dependency_result=int(match[5]),callback_registrations=dict(exception=11,argument=3,string=1,log=1),artificial_native_callback_replays=15,actual_SDK_string_callbacks=3,C_allocations=3,C_frees=3,traces=len(m['traces']),objects=len(m['objects']),stdout=desc(o/'actual-NDK-Windows.log'),foreign_callback_stdout=desc(o/'actual-foreign-callback.log'),executable=desc(exe)),limits='Actual pinned official Windows SDK synchronous profile only. Genuine DefaultName invokes translated TEST C callback; 14 exception plus log routing are explicitly TEST replay of transparently observed native SDK registration pointers during that genuine callback, not SDK-generated exceptions. No original Android JNI_OnLoad, original managed reverse-PInvoke execution, App/Future creation, network credentials/dependency repair, asynchronous callback ownership or first-frame claim. Native dependency result is compared unchanged with actual DLL, not forced Available.')
 (o/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(desc(o/'acceptance.json')),flush=True)
if __name__=='__main__':main()
