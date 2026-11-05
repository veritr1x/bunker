"""Read-only manual Windows proxy snapshot and actual NDK typed-callback tests."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,traceback,re
HERE=Path(__file__).resolve().parent
OWN=('unity_network_proxy_guest.c','unity_network_proxy_test.cpp','unity_network_proxy.md','test_unity_network_proxy.py')
PRODUCTION=('windows/unity_network_proxy.cpp','windows/unity_network_proxy.h')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p.resolve()),sha256=sha(p))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';commands=[];held={}
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def pin(p):held[str(p.resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(label=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  qualified=a.support_source/'work/jni-string-bytes-qualification2';assert sha(qualified/'acceptance.json')=='aa302c91fbd533728ed25a50a96ea50555d99477f403080c768f678c5fd51c9b';q=json.loads((qualified/'acceptance.json').read_bytes());assert q['passed']is True;pin(qualified/'acceptance.json')
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
  for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  for n in PRODUCTION:pin(a.support_source/n);assert sha(source/n)==sha(a.support_source/n)
  for n,h in q['production_sources'].items():assert sha(a.support_source/n)==h;pin(a.support_source/n)
  binding=dict(passed=True,scope='Exact current source binding only; actual focused qualification below',production_sources={n:sha(source/n)for n in PRODUCTION},qualified_JNI_sources=q['production_sources'],JNI_qualification=desc(qualified/'acceptance.json'));(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'proxy.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/unity_network_proxy_guest.c','-o',guest],'compile-NDK-JNIEnv-caller')
  translated=out/'guest';run([__import__('sys').executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x79000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-Windows');manifest=json.loads((translated/'manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include'),'-I'+wp(source/'windows'),'-I'+wp(translated),'-DPROXY_IMAGE="'+wp(guest)+'"'];objects=[]
  for relative in('windows/unity_network_proxy.cpp','windows/unity_network_proxy_test.cpp'):
   obj=out/(Path(relative).stem+'.o');run([cxx,*flags,'-Wall','-Wextra','-Werror','-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  reused=[qualified/'windows/jni_host.o',qualified/'windows/runtime.o'];[pin(p)for p in reused];exe=out/'proxy-test.exe';run([cxx,*map(wp,objects),*map(wp,reused),wp(loader),*map(wp,manifest['objects']),'-static','-latomic','-pthread','-lwinhttp','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows-proxy')
  text=(out/'actual-Windows-proxy.log').read_text();m=re.search(r'UNITY-NETWORK-PROXY-PASS checks=(\d+) NDK_calls=(\d+) forms=3 State=1200 Memory64=1 networkRequests=0 PACresolved=0',text);assert m,text[-2000:];observed=re.search(r'WINDOWS-MANUAL-PROXY serverPresent=(\d) bypassPresent=(\d) autoDetect=(\d) PACmetadataPresent=(\d) effectiveRouteResolved=0',text);assert observed
  for f,h in held.items():assert sha(f)==h,f
  result=dict(passed=True,production_sources={n:sha(source/n)for n in PRODUCTION},owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),qualified_JNI_sources=q['production_sources'],JNI_qualification=desc(qualified/'acceptance.json'),reused_qualified_objects=[desc(p)for p in reused],platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=1,JNI_forms=['direct','V','A'],traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/'actual-Windows-proxy.log'))),live_manual_snapshot=dict(manual_server_present=observed[1]=='1',manual_bypass_present=observed[2]=='1',autoDetect=observed[3]=='1',PAC_metadata_present=observed[4]=='1',effective_route_resolved=False,network_requests=0),controls=['exactcase-sensitiveDEXhttp/httpsformat','null-vs-empty host and rawport/bypass skip','rawUnicode/NUL/unusualporttext exactUTF16','unknownschemenoReader','nullURLJavaNPE','anyvalidUnityPlayerreceiver','puremanualsingle/perScheme/numericport/bracketIPv6/bypassgrammar','rejectunqualifiedfallback/auth/URL/localmarker','realWinHTTPrawmanual/autodetect/PACindependentread','reader/observerexceptionspropagate','Revoke/destructor/reentrantcancelcallbackguards','global/weak/frameStringlifetime','State1200align16SIMD128highcellMemory64'],commands=commands,held_inputs=held,limits='Actual Windows current-user manual configuration and metadata only, not an effective proxy route. No PAC download/evaluation, WPAD/network request, authentication or setting change. Genuine NDK direct/V/A typed-JNI callbacks against qualified checked host, not ART runtime. Parser supports explicit representable subset and fails closed on others; injected formatting preserves raw Java properties independently. No old JNI/String gate replay, production source edits, fullhost link/game/observer. Live fields compared in memory; proxy/PAC values are not printed.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-NETWORK-PROXY-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
