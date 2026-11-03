"""Focused original NDK texture ABI to real Windows ANGLE; synthetic component QA."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('gl_texture_commands.inc','gl_texture_impl.inc','gl_texture_guest.c','gl_texture_test.cpp','test_gl_texture.py')
PROTECTED=('windows/egl_host.h','windows/egl_host.cpp','windows/native_window.h','windows/native_window.cpp','windows/jni_host.h','windows/jni_host.cpp','whole/runtime.h','whole/runtime.cpp','whole/bridge.h')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--support-commit',required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);W=HERE.parent/'work'
 def wp(q):return subprocess.check_output(['wslpath','-m',str(Path(q).resolve())],text=True).strip()
 commands=[]
 def run(cmd,label,timeout=180):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',label,flush=True)
  with (O/(label+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit '+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-5000:])
  return (O/(label+'.log')).read_text()
 commit=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'rev-parse',a.support_commit],text=True).strip()
 archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp'
 # Root owns the central composition; capture every actually included group.
 composition={'gl_host.cpp','gl_host.h','gl_scalar_commands.inc'}|{f.name for f in HERE.glob('gl_*_commands.inc')}|{f.name for f in HERE.glob('gl_*_impl.inc')}
 for n in set(OWN)|composition:shutil.copy2(HERE/n,S/'windows'/n)
 protected={n:sha(HERE.parent/n) for n in PROTECTED}
 for n,h in protected.items():assert sha(S/n)==h,'protected support source changed: '+n
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');CC=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ANGLE=W/'angle-native';DLL=ANGLE/'bundle/bin'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'
 assert sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');gcc=Path('/mnt/c/mingw64/bin/gcc.exe')
 sources={str(f):sha(f) for f in S.rglob('*') if f.is_file()}
 inputs={str(f):sha(f) for f in [CC.resolve(),T/'remill-lift',T/'aarch64.bc',cxx,gcc,Path(shutil.which('clang++-18')).resolve()]}
 for directory in (T/'include',ANGLE/'src/include',DLL):
  for f in directory.rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
 live={str(HERE/n):sha(HERE/n) for n in set(OWN)|composition}
 (O/'source-pin.json').write_text(json.dumps(dict(commit=commit,archive_sha256=sha(O/'support.tar'),sources=sources,inputs=inputs,live=live,protected=protected,composition={n:sha(S/'windows'/n) for n in sorted(composition)}),indent=2)+'\n')
 guest=O/'texture.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/gl_texture_guest.c','-o',guest],'strict-ndk-build')
 B=O/'windows';B.mkdir();G=B/'guest'
 run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x5d000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'ndk-translate')
 m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces'] and not m['unresolved_direct_targets']
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(G),'-I'+wp(S/'windows'),'-I'+wp(ANGLE/'src/include'),f'-DGL_TEXTURE_IMAGE="{wp(guest)}"',f'-DGL_TEXTURE_DLL_DIRECTORY=L"{wp(DLL)}"']
 run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/gl_texture_test.cpp')],'strict-windows-test')
 run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/gl_host.cpp')],'strict-windows-provider')
 loader=B/'loader.o';run([gcc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'native-loader');objects=[]
 for rel in ('windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  obj=B/(Path(rel).stem+'.o');run([cxx,*flags,'-c',wp(S/rel),'-o',wp(obj)],'native-'+obj.stem);objects.append(obj)
 exe=B/'texture.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(S/'windows/gl_texture_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'native-link')
 result=run([exe],'capture-texture-component',100);match=re.search(r'GL-TEXTURE-PASS checks=(\d+) calls=(\d+) commands=14 real_ANGLE=1 synthetic_component=1',result);assert match
 # Fresh post-execution hashes, without memoized lookup.
 for group in (sources,inputs,live):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 acceptance=dict(passed=True,commit=commit,source_pin_sha256=sha(O/'source-pin.json'),owned_sources={n:sha(S/'windows'/n) for n in OWN},composition_sources={n:sha(S/'windows'/n) for n in sorted(composition)},protected_sources=protected,windows=dict(stdout=result,checks=int(match[1]),NDK_calls=int(match[2]),heads=len(m['traces']),objects=len(m['objects']),binary_sha256=sha(exe)),scope='Synthetic texture component QA: actual NDK callers and real Windows ANGLE, test-only native sampling oracle; no Unity frame, original game or Linux/ARM graphics parity claim.',evidence={str(f):sha(f) for f in O.rglob('*') if f.is_file() and 'source' not in f.relative_to(O).parts})
 (O/'acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n');print('GL-TEXTURE-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
