"""Actual NDK/JNI queued HandlerThread and nominal Windows Choreographer gate."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
PRODUCTION={'android_choreographer.h':'120aa599d694d5c02120731b804d7a710814575cc7f3a6203a23be6718b3cc6f','android_choreographer.cpp':'0c4ccb8e01ce6230df0bb310eea4b1e41cee14630a4cc56190fd695d5bdb1ada','jni_interface_proxy.h':'f1eb2ae25f64b248bfdf8c25c54e017e2bc0043ac5742a7adf9e17592b714b11','jni_interface_proxy.cpp':'e5ca33e583861408e9e37147c5049346805cde04c5addca8a3461e8daffbdc45','jni_host.h':'f3c388af6040842b94d54224e66809700907b0deac4fc0f5c46490afc8521af7','jni_host.cpp':'a71e9f0053c080329d74a90c766e3397a9a56bcaf48b2646b69e8522877e9a9a'}
OWN=('android_choreographer_guest.c','android_choreographer_test.cpp','test_android_choreographer.py')
CPP=('jni_host.cpp','jni_interface_proxy.cpp','android_choreographer.cpp','pthread_host.cpp','signal_host.cpp','libc.cpp','android_context.cpp','windows_android_id.cpp','windows_display_service.cpp','android_assets.cpp','apk_assets.cpp','thread_priority.cpp','android_process.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--focus-only',action='store_true',help='Preserved preliminary internal-worker candidate; no final original-constructor/regression claim')
 p.add_argument('--reuse-build',type=Path,help='Reuse only actual unchanged caller/object inputs from a preserved previous attempt; recompile changed local include closures')
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=out/'source';work=HERE.parent/'work';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=None):
  argv=list(map(str,argv));commands.append({'stage':label,'argv':argv});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(HERE.parent/folder).iterdir():
    if f.is_file()and(f.suffix in('.h','.inc','.py')or f.name in OWN or f.name in CPP or f.name in('runtime.cpp','elfload.c','jni_interface_proxy_guest.c','jni_interface_proxy_test.cpp','package_guest_fixture.c','java_init_guest.c','settings_secure_guest.c','jni_numeric_test.cpp')):shutil.copyfile(f,target/f.name)
  for name,h in PRODUCTION.items():assert sha(source/'windows'/name)==h and sha(HERE/name)==h;pin(HERE/name)
  for name in OWN:pin(HERE/name)
  for name in('sample.h',):shutil.copyfile(work/'windows-files'/name,out/name)
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';jni=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copyfile(jni,out/'jni.h')
  for f in(ndk,jni,a.lift,a.semantics_dir/'aarch64.bc'):pin(f)
  primary=work/'android-choreographer-primary1/sources.json';pin(primary)
  result={'production_sources':{'windows/'+n:h for n,h in PRODUCTION.items()},'fixture_sources':{n:sha(source/'windows'/n)for n in OWN},'primary_framework_sources':desc(primary),'scope':'Actual NDK/JNI internal HandlerThread queue and registered TEST native bridge; explicit nominal Windows observed-refresh/monotonic clock, no Android/DWM vsync equivalence or original Unity constructor claim.','preliminary_focus_only':a.focus_only}
  (out/'source-binding.json').write_text(json.dumps(result,indent=2)+'\n')
  guest=out/'choreographer.so';reuse=a.reuse_build.resolve()if a.reuse_build else None;reused={}
  if reuse:
   old_commands=json.loads((reuse/'commands.json').read_text());completed={row['stage']for row in old_commands[:-1]};assert 'lift-NDK-callers'in completed
   for name in('android_choreographer_guest.c','jni_interface_proxy_guest.c'):assert sha(source/'windows'/name)==sha(reuse/'source/windows'/name)
   assert sha(out/'jni.h')==sha(reuse/'jni.h');shutil.copyfile(reuse/'choreographer.so',guest);translated=reuse/'guest';pin(reuse/'commands.json');pin(reuse/'source-binding.json');pin(guest);reused['NDK_library']=desc(reuse/'choreographer.so')
  else:
   run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/android_choreographer_guest.c',source/'windows/jni_interface_proxy_guest.c','-o',guest],'compile-NDK-callers');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7e000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-callers')
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets'];pin(translated/'manifest.json')
  for obj in manifest['objects']:pin(obj)
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx)
  def local_closure(relative,root):
   seen={}
   def visit(path):
    path=path.resolve()
    if path in seen or not path.is_relative_to(root):return
    seen[path]=sha(path)
    for name in re.findall(r'^\s*#\s*include\s*"([^"]+)"',path.read_text(errors='replace'),re.M):
     for parent in(path.parent,root/'windows',root/'whole',root/'fastaes'):
      candidate=parent/name
      if candidate.is_file():visit(candidate);break
   visit(root/relative);return {str(p.relative_to(root)):h for p,h in seen.items()}
  def reuse_object(relative,destination,stage):
   if not reuse or stage not in completed:return False
   old=local_closure(relative,(reuse/'source').resolve());new=local_closure(relative,source.resolve())
   if old!=new:return False
   prior=reuse/destination.name;assert prior.is_file();pin(prior);shutil.copyfile(prior,destination);reused[relative]={'object':desc(prior),'identical_local_source_closure':new,'successful_compile_stage':stage};return True
  loader=out/'elfload.o'
  if not reuse_object('fastaes/elfload.c',loader,'compile-loader'):run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(work/'remill-src/include'),'-I'+wp(out),'-I'+wp(translated),'-I'+wp(work/'zlib-native/zlib-1.3.2')];objects={}
  for relative in['windows/'+n for n in CPP]+['whole/runtime.cpp']:
   obj=out/(Path(relative).stem+'.o')
   if not reuse_object(relative,obj,'compile-'+obj.stem):run([cxx,*flags,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem)
   objects[Path(relative).stem]=obj
  result['unchanged_artifact_reuse']=reused
  backend=work/'zlib-native/libz-inflate.a';pin(backend);exe=out/'choreographer.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror','-DCHOREOGRAPHER_LIBRARY="'+wp(guest)+'"','-DCHOREOGRAPHER_RESULT="'+wp(out/'focus-result.txt')+'"',wp(source/'windows/android_choreographer_test.cpp'),*map(wp,objects.values()),wp(loader),*map(wp,manifest['objects']),wp(backend),'-static','-pthread','-latomic','-ladvapi32','-luser32','-lgdi32','-o',wp(exe)],'link-focus');run([exe],'focus',60);text=(out/'focus-result.txt').read_text();m=re.search(r'ANDROID-CHOREOGRAPHER-PASS checks=(\d+) actual_NDK_calls=(\d+) registered_native_calls=(\d+) attached_workers=(\d+) detached_workers=(\d+) clock_reads=(\d+) refresh=(\d+)/(\d+)',text);assert m;assert int(m[4])==int(m[5])==2 and int(m[6])>0 and int(m[7])>0 and int(m[8])>0
  result['focus']={'checks':int(m[1]),'actual_NDK_calls':int(m[2]),'registered_native_calls':int(m[3]),'attached_workers':int(m[4]),'detached_workers':int(m[5]),'clock_reads':int(m[6]),'observed_refresh_ratio':[int(m[7]),int(m[8])],'traces':len(manifest['traces']),'objects':len(manifest['objects']),'guest':desc(guest),'manifest':desc(translated/'manifest.json'),'executable':desc(exe),'stdout':desc(out/'focus.log'),'result':desc(out/'focus-result.txt')};print(m[0],flush=True)
  if not a.focus_only:
   proxy=out/'old-proxy';proxy.mkdir();pg=proxy/'proxy.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[source/'windows'/n for n in('package_guest_fixture.c','java_init_guest.c','settings_secure_guest.c','jni_interface_proxy_guest.c')],'-o',pg],'old-proxy-NDK');pt=proxy/'guest';run([sys.executable,source/'whole/compile.py',pg,'--out',pt,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'old-proxy-lift');pm=json.loads((pt/'manifest.json').read_text());assert not pm['unsupported_traces']and not pm['unresolved_direct_targets'];pf=[f for f in flags if f!='-I'+wp(translated)]+['-I'+wp(pt)];pe=proxy/'proxy.exe';run([cxx,*pf,'-Wall','-Wextra','-Werror','-DPACKAGE_IMAGE="'+wp(pg)+'"',wp(source/'windows/jni_interface_proxy_test.cpp'),*map(wp,objects.values()),wp(loader),*map(wp,pm['objects']),wp(backend),'-static','-pthread','-latomic','-ladvapi32','-luser32','-lgdi32','-o',wp(pe)],'old-proxy-build');run([pe],'old-proxy',60);assert '237 checks passed' in(out/'old-proxy.log').read_text();result['old_proxy_regression']={'stdout':desc(out/'old-proxy.log'),'executable':desc(pe),'manifest':desc(pt/'manifest.json')}
   numeric=work/'jni-numeric3';prior=json.loads((numeric/'acceptance.json').read_text());assert prior['passed'];pin(numeric/'acceptance.json');pin(numeric/'numeric_expected.h');shutil.copyfile(numeric/'numeric_expected.h',out/'numeric_expected.h');nm=json.loads((numeric/'windows/guest/manifest.json').read_text());assert not nm['unsupported_traces']and not nm['unresolved_direct_targets'];pin(numeric/'windows/guest/manifest.json');ng=numeric/'numeric.so';pin(ng)
   assert prior['source_sha256']['windows/jni_numeric_test.cpp']==sha(source/'windows/jni_numeric_test.cpp')
   nf=[f for f in flags if f!='-I'+wp(translated)]+['-I'+wp(numeric/'windows/guest')];ne=out/'old-numeric.exe';run([cxx,*nf,'-DPACKAGE_IMAGE="'+wp(ng)+'"','-DARRAY_IMAGE="'+wp(ng)+'"',wp(source/'windows/jni_numeric_test.cpp'),*map(wp,objects.values()),wp(loader),*map(wp,nm['objects']),wp(backend),'-static','-pthread','-latomic','-ladvapi32','-luser32','-lgdi32','-o',wp(ne)],'old-numeric-build');run([ne],'old-numeric',60);result['old_numeric_regression']={'stdout':desc(out/'old-numeric.log'),'executable':desc(ne),'reference':desc(numeric/'acceptance.json')}
  for path,h in held.items():assert sha(path)==h,path
  result.update(passed=True,source_snapshot={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},held_inputs=held,commands=commands)
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CHOREOGRAPHER-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps({'passed':False,'error':str(error),'traceback':traceback.format_exc(),'commands':commands,'held_inputs':held},indent=2)+'\n');raise
if __name__=='__main__':main()
