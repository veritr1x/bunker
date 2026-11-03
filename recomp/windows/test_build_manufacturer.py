"""Explicit absent-product-property manufacturer fallback; focused actual NDK JNI only."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='da638ad866b21750a506ba1f68eff7587dfee873'
OWNED=('android_build_manufacturer.h','build_manufacturer_guest.c','build_manufacturer_test.cpp','test_build_manufacturer.py')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 def sha(p):
  with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 commands=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:q=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
  if q.returncode:raise RuntimeError(name+' exit'+str(q.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-5000:])
  return(O/(name+'.log')).read_text()
 archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'base-recomp.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp'
 for n in OWNED:shutil.copy2(HERE/n,S/'windows'/n)
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');CC=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'and sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 primary=W/'android-api-profile-audit/Android13-Build.java';assert sha(primary)=='77d6b4a7fef0ac88197bd269a2a9c1c4e37d20a3fa026b3b0654930187147e95'
 text=primary.read_text();assert 'public static final String UNKNOWN = "unknown";'in text and 'public static final String MANUFACTURER = getString("ro.product.manufacturer");'in text and 'return SystemProperties.get(property, UNKNOWN);'in text
 jni=NDK/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copy2(jni,O/'jni.h')
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()}
 inputs={str(f):sha(f)for f in[primary,jni,CC.resolve(),T/'remill-lift',T/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang-18')).resolve(),Path(shutil.which('clang++-18')).resolve()]}
 for f in(T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 for n in OWNED:inputs[str(HERE/n)]=sha(HERE/n)
 guest=O/'manufacturer.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/build_manufacturer_guest.c','-o',guest],'ndk-build')
 results={};manifests={}
 for windows in(False,True):
  label='windows'if windows else'linux';D=O/label;D.mkdir();conv=wp if windows else str;G=D/'guest'
  run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x74000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-translate')
  m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets'];manifests[label]=dict(heads=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],sha256=sha(G/'manifest.json'))
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(O),'-I'+conv(G),'-I'+conv(S/'windows'),f'-DMANUFACTURER_IMAGE="{conv(guest)}"']
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'windows/build_manufacturer_test.cpp')],label+'-strict-source')
  loader=D/'elfload.o';run([cc,'-O2','-c',conv(S/'fastaes/elfload.c'),'-o',conv(loader)],label+'-loader');objs=[]
  for rel in('windows/jni_host.cpp','whole/runtime.cpp'):
   obj=D/(Path(rel).stem+'.o');run([cxx,*flags,'-c',conv(S/rel),'-o',conv(obj)],label+'-'+obj.stem);objs.append(obj)
  exe=D/('manufacturer.exe'if windows else'manufacturer');run([cxx,*flags,'-Wall','-Wextra','-Werror',conv(S/'windows/build_manufacturer_test.cpp'),*map(conv,objs),conv(loader),*map(conv,m['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',conv(exe)],label+'-link')
  result=run([exe],label+'-focused');assert 'explicit absent-property AOSP fallback unknown, SDK33 preserved; no vendor query'in result;results[label]=dict(stdout=result,executable_sha256=sha(exe))
 sourcepin=dict(base_commit=BASE,base_archive_sha256=sha(O/'base-recomp.tar'),sources=sources,inputs=inputs,owned_sources={n:sha(S/'windows'/n)for n in OWNED})
 (O/'source-pin.json').write_text(json.dumps(sourcepin,indent=2)+'\n')
 for group in(sources,inputs):
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 r=dict(passed=True,base_commit=BASE,owned_sources=sourcepin['owned_sources'],source_pin_sha256=sha(O/'source-pin.json'),primary_path=str(primary),primary_sha256=sha(primary),policy='Explicit absent Android product properties; exact AOSP MANUFACTURER fallback unknown',platforms=results,manifests=manifests,evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts},scope='Manufacturer static String only; actual NDK field/StringUTF8 and ownership/lifetime/error tests. No Android property/device vendor query, display API, game run or unrelated matrix.')
 (O/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('MANUFACTURER-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
