"""Genuine Crashlytics 9.6 desktop stubs, original APK config, translated NDK ABI."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=['windows/firebase_crashlytics_guest.c','windows/firebase_crashlytics_test.cpp','windows/test_firebase_crashlytics.py']
PRODUCTION=['windows/firebase_app.cpp','windows/firebase_app.h']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout);(out/(label+'.stdout.log')).write_bytes(r.stdout);(out/(label+'.stderr.log')).write_bytes(r.stderr);text=r.stdout.decode(errors='replace')+r.stderr.decode(errors='replace');(out/(label+'.log')).write_text(text)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'; inspect owned raw log')
  return text
 try:
  units=['windows/firebase_app.cpp','windows/module_registry.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/firebase_crashlytics_test.cpp'];todo=units+PRODUCTION+OWN+['windows/firebase_app_test.cpp','windows/firebase_app_guest.c','windows/firebase_app_lifetime_test.cpp','windows/firebase_app_lifetime_guest.c','fastaes/elfload.c'];seen=set()
  while todo:
   name=todo.pop();p=(ROOT/name).resolve();name=str(p.relative_to(ROOT))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    child=(p.parent/inc).resolve()
    if child.is_file()and child.is_relative_to(ROOT):todo.append(str(child.relative_to(ROOT)))
  production={n:sha(source/n)for n in PRODUCTION}
  sdk=W/'firebase-windows-sdk1/package/Firebase/Plugins/x86_64/FirebaseCppApp-9_6_0.dll';assert sha(sdk)=='f85bb9f82d79176d3d5da322780d437c023191370e608c45723ad6d83c4d1a12';pin(sdk);native=out/'native';native.mkdir();frozen_sdk=native/'FirebaseCppApp-9_6_0.dll';shutil.copyfile(sdk,frozen_sdk)
  apk=W/'swappy-disabled-config1/game-audio-disabled-swappy-disabled.apk';assert sha(apk)=='fd0d0d357a4e8c316d0e732783d795f0e100a675d0c7a0fcf252873deb84f538';pin(apk)
  config=native/'config';config.mkdir();empty=native/'empty';empty.mkdir()
  entry='assets/google-services-desktop.json'
  with zipfile.ZipFile(apk)as z:configuration=z.read(entry);crc=z.getinfo(entry).CRC
  (config/'google-services-desktop.json').write_bytes(configuration)
  config_proof=dict(source_apk=desc(apk),member=entry,member_bytes=len(configuration),member_sha256=hashlib.sha256(configuration).hexdigest(),zip_member_crc=crc,extracted=desc(config/'google-services-desktop.json'),byte_exact=True,contents_or_credentials_printed=False,configuration_values_modified=False)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');tool=W/'integer-popcount8b-preparation1/toolchains/f967bf3b57f889d7-469903ec4d84cbd3';cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe')
  for p in(ndk,tool/'remill-lift',tool/'aarch64.bc',cxx,cc,ROOT/'whole/compile.py'):pin(p)
  guest=out/'firebase-app.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-vectorize','-fno-slp-vectorize','-Wall','-Wextra','-Werror',source/'windows/firebase_crashlytics_guest.c','-o',guest],'compile-NDK')
  run([sys.executable,ROOT/'whole/compile.py',guest,'--out',out/'guest','--base','0x62000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK');m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'guest'),'-DFIREBASE_GUEST="'+wp(guest)+'"','-DFIREBASE_DLL=L"'+wp(frozen_sdk)+'"','-DFIREBASE_CONFIG="'+wp(config)+'"','-DFIREBASE_EMPTY_CONFIG="'+wp(empty)+'"'];objects=[]
  for name in units:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('firebase_crashlytics_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=out/'firebase-crashlytics.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,m['objects']),'-Wl,--wrap=__imp_GetProcAddress','-Wl,--wrap=_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE','-static','-pthread','-latomic','-lbcrypt','-o',wp(exe)],'link')
  results={}
  for mode in ['normal','foreign']:
   text=run([exe,*([]if mode=='normal'else[mode])],'actual-crash-'+mode,120)
   if mode=='normal':
    match=re.search(r'FIREBASE-CRASH-PASS checks=(\d+) NDK_calls=(\d+) callbacks=(\d+) allocations=(\d+) frees=(\d+) instance_calls=(\d+) native_status=(-?\d+) commands=41 State=1200 Memory64=8',text);assert match
    values=list(map(int,match.groups()));assert values[3]==values[4]==8;assert values[5]==2
    results[mode]=dict(zip(['checks','NDK_calls','callbacks','allocations','frees','instance_calls','native_status'],values))
   else:assert 'FIREBASE-CRASH-FOREIGN-PASS'in text;results[mode]=dict(passed=True)
   results[mode]['log']=desc(out/('actual-crash-'+mode+'.log'))
  old=W/'firebase-app-lifetime-qualification2';old_m=json.loads((old/'guest/manifest.json').read_text())
  for n in ['windows/firebase_app_lifetime_test.cpp','windows/firebase_app_lifetime_guest.c','windows/firebase_app_test.cpp','windows/firebase_app_guest.c']:
   assert sha(source/n)==sha(old/'source'/n),n
  for p in [old/'firebase-app.so',old/'guest/manifest.json',old/'guest/traces.h',*map(Path,old_m['objects'])]:pin(p)
  regression_flags=[x.replace(wp(out/'guest'),wp(old/'guest')).replace(wp(guest),wp(old/'firebase-app.so'))for x in flags]
  regression_obj=out/'regression-lifetime.o'
  run([cxx,*regression_flags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows/firebase_app_lifetime_test.cpp'),'-o',wp(regression_obj)],'compile-regression')
  regression=out/'firebase-old22-regression.exe';run([cxx,*map(wp,objects[:-1]),wp(regression_obj),wp(loader),*map(wp,old_m['objects']),'-Wl,--wrap=__imp_GetProcAddress','-Wl,--wrap=_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE','-static','-pthread','-latomic','-lbcrypt','-o',wp(regression)],'link-regression')
  for mode in ['original-config','missing','legacy','foreign']:
   text=run([regression,*([]if mode=='original-config'else[mode])],'regression-'+mode,120)
   assert ('FIREBASE-APP-LIFETIME-PASS'in text if mode in ['original-config','missing']else 'FIREBASE-PASS'in text if mode=='legacy'else 'FIREBASE-FOREIGN-PASS'in text)
   if mode!='foreign':assert 'commands=41'in text
   results['old22-'+mode]=dict(passed=True,unchanged_fixture_and_NDK_guest=True,log=desc(out/('regression-'+mode+'.log')))
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,owned_sources={n:sha(source/n)for n in OWN},source_snapshot={str(p.relative_to(source)):sha(p)for p in source.rglob('*')if p.is_file()},original_configuration=config_proof,native_sdk=desc(frozen_sdk),guest=desc(guest),guest_manifest=desc(out/'guest/manifest.json'),executable=desc(exe),results=results,held_inputs=held,commands=commands,scope='19 stripped Crashlytics exports appended after unchanged22 App markers; genuine desktop stub APIs; real translated NDK direct/pointer and callback allocating/free ABI; per-family routing and native output publication; parent/refcount and owned/borrowed object profile.',limits='Pinned Windows SDK Crashlytics is officially nonfunctional desktop local stubs; no collected/uploaded fixture events or changed collection settings. Additional real SDK Frame getters are transparent test observer instrumentation only. Crash instance allocations retained until process exit matching original SWIG Dispose TODO; logical parent revocation only. No ABA/universal vector pointer stability, original managed execution, or original game/frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FIREBASE-CRASH-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
