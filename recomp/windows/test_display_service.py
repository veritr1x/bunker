"""Exact Android13 Context.DISPLAY_SERVICE, actual NDK JNI and old field gates."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
BASE='da638ad866b21750a506ba1f68eff7587dfee873'
OWNED=('android_context.cpp','display_service_guest.c','display_service_test.cpp','test_display_service.py')
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 def sha(path):
  with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 R=HERE.parent.parent;commands=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:q=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  if q.returncode:raise RuntimeError(name+' exit'+str(q.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-6000:])
  return(O/(name+'.log')).read_text(errors='replace')
 archive=subprocess.check_output(['git.exe','-C',wp(R),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'base-recomp.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as t:t.extractall(O/'source',filter='data')
 S=O/'source/recomp';m=json.loads((W/'windows-game31/game_inputs.json').read_text());assert m['host_commit']==BASE
 for f in S.rglob('*'):
  if f.is_file():assert sha(f)==m['source_sha256'][str(f.relative_to(O/'source'))],str(f)
 for n in OWNED:shutil.copy2(HERE/n,S/'windows'/n)
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:old=tf.extractfile('recomp/windows/android_context.cpp').read()
 now=(S/'windows/android_context.cpp').read_bytes();nl=b'\r\n'if b'\r\n'in old else b'\n'
 line1=b'  host.DefineField("android/content/Context","DISPLAY_SERVICE","Ljava/lang/String;",true);'+nl
 line2=b'  auto display_field=env(144,context_class,reinterpret_cast<addr_t>("DISPLAY_SERVICE"),reinterpret_cast<addr_t>("Ljava/lang/String;")),display_key=host.NewString(u"display");env(154,context_class,display_field,display_key);host.DeleteLocalReference(display_key);'+nl
 assert now.count(line1)==now.count(line2)==1 and now.replace(line1,b'').replace(line2,b'')==old
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');CC=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'and sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 primary=W/'location-after-proxy-audit/Android13-Context.java';assert sha(primary)=='31f106e272391fc0d9679b6a7c369fc77940e37c5fac8fb9089bbed8df12de15'and primary.read_text().splitlines()[5346].strip()=='public static final String DISPLAY_SERVICE = "display";'
 jni=NDK/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copy2(jni,O/'jni.h');sample=W/'location-service1/sample.h';shutil.copy2(sample,O/'sample.h')
 inputs={str(q):sha(q)for q in[W/'windows-game31/game_inputs.json',primary,jni,sample,CC.resolve(),T/'remill-lift',T/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve(),Path(shutil.which('clang-18')).resolve()]}
 for f in(T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 for f in(W/'zlib-native/zlib-1.3.2').glob('*.h'):inputs[str(f)]=sha(f)
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()}
 for n in OWNED:inputs[str(HERE/n)]=sha(HERE/n)
 guest=O/'display-service.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/location_service_guest.c',S/'windows/display_service_guest.c','-o',guest],'ndk-compile')
 results={};manifests={}
 for windows in(False,True):
  label='windows'if windows else'linux';B=O/label;B.mkdir();conv=wp if windows else str;G=B/'guest'
  run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x74000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-translate')
  manifest=json.loads((G/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets'];manifests[label]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'manifest_sha256':sha(G/'manifest.json'),'toolchain':manifest['toolchain']}
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(O),'-I'+conv(G),'-I'+conv(W/'zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{conv(guest)}"']
  loader=B/'elfload.o';run([cc,'-O2','-c',conv(S/'fastaes/elfload.c'),'-o',conv(loader)],label+'-loader')
  objects=[]
  for rel in['windows/jni_host.cpp','windows/android_context.cpp','windows/windows_android_id.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp']:
   obj=B/(Path(rel).stem+'.o');run([cxx,*flags,'-c',conv(S/rel),'-o',conv(obj)],label+'-'+obj.stem);objects.append(obj)
  backend=W/('zlib-native/libz-inflate.a'if windows else'zlib-linux/backend/libz-inflate.a');inputs[str(backend)]=sha(backend);results[label]={}
  for test in['display_service','location_service','android_context']:
   exe=B/(test+('.exe'if windows else''));run([cxx,*flags,'-Wall','-Wextra',*(['-Werror']if test=='display_service'else[]),conv(S/f'windows/{test}_test.cpp'),*map(conv,objects),conv(loader),*map(conv,manifest['objects']),conv(backend),'-latomic','-pthread',*(['-static','-ladvapi32']if windows else[]),'-o',conv(exe)],label+'-'+test+'-link')
   stdout=run([exe],label+'-'+test);results[label][test]={'stdout':stdout,'executable_sha256':sha(exe)}
  assert 'DISPLAY_SERVICE: 57 checks'in results[label]['display_service']['stdout'];assert 'LOCATION_SERVICE: 56 checks'in results[label]['location_service']['stdout'];assert '14 checks passed'in results[label]['android_context']['stdout']
 sourcepin=dict(base_commit=BASE,base_archive_sha256=sha(O/'base-recomp.tar'),sources=sources,inputs=inputs,owned_sources={n:sha(S/'windows'/n)for n in OWNED},reverse_proof_only2_context_lines=True)
 (O/'source-pin.json').write_text(json.dumps(sourcepin,indent=2)+'\n')
 for n,s in {**sources,**inputs}.items():assert sha(n)==s,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,base_commit=BASE,owned_sources=sourcepin['owned_sources'],source_pin_sha256=sha(O/'source-pin.json'),primary_path=str(primary),primary_sha256=sha(primary),actual_NDK_GetStaticFieldID_GetStaticObjectField_SetStaticObjectField=True,platforms=results,manifests=manifests,evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts},scope='Exact class-owned DISPLAY_SERVICE String only, focused actualJNI and unchanged LOCATION_SERVICE/Context regressions; no displaymanager/service/hardware result or game run')
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('DISPLAY-SERVICE-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
