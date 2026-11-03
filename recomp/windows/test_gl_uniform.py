"""Actual NDK fourteen-uniform gate against independent native ANGLE program state."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('gl_uniform_commands.inc','gl_uniform_impl.inc','gl_uniform_guest.c','gl_uniform_test.cpp','test_gl_uniform.py')
SHARED=('gl_host.cpp','gl_host.h','gles_service_module.h','gl_scalar_commands.inc','gl_draw_commands.inc','gl_texture_commands.inc','gl_texture_impl.inc','gl_framebuffer_commands.inc','gl_framebuffer_impl.inc','gl_misc_commands.inc','gl_misc_impl.inc','gl_indexed_commands.inc','gl_indexed_impl.inc')
PROTECTED=('windows/egl_host.h','windows/egl_host.cpp','windows/native_window.h','windows/native_window.cpp','windows/jni_host.h','windows/jni_host.cpp','whole/runtime.h','whole/runtime.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--support-commit',default='HEAD');a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);W=HERE.parent/'work'
 def wp(q):return subprocess.check_output(['wslpath','-m',str(Path(q).resolve())],text=True).strip()
 commands=[]
 def run(cmd,name,timeout=180):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with(O/(name+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit'+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-4000:])
  return(O/(name+'.log')).read_text()
 commit=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp'
 # Derive old marker names from the preserved, qualified pre-core2 source.
 oldroot=W/'gl-module-qualification1/source/recomp/windows';oldcpp=(oldroot/'gl_host.cpp').read_text();draw=re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types',oldcpp,re.S);assert draw
 names=['glGetString','glGetStringi','glGetIntegerv','glGetFloatv','glGetBooleanv','glGetError']+re.findall(r'GL_SCALAR\((\w+),',(oldroot/'gl_scalar_commands.inc').read_text())+re.findall(r'X\((\w+),',draw[1]);assert len(names)==63 and len(set(names))==63
 (O/'gl_uniform_old_commands.h').write_text('#pragma once\nstatic const char*const kOldUniformCommands[]={'+','.join(json.dumps(n)for n in names)+'};\n')
 copied=[]
 for n in OWN+SHARED:
  if(HERE/n).is_file():shutil.copy2(HERE/n,S/'windows'/n);copied.append(n)
 for n in OWN:assert n in copied
 protected={n:sha(HERE.parent/n)for n in PROTECTED}
 for n,h in protected.items():assert sha(S/n)==h,'protected provider differs from archive: '+n
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');CC=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ANGLE=W/'angle-native';DLL=ANGLE/'bundle/bin'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'and sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()};inputs={str(f.resolve()):sha(f.resolve())for f in(CC,T/'remill-lift',T/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve())}
 for directory in(T/'include',ANGLE/'src/include',DLL):
  for f in directory.rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
 for n in copied:inputs[str(HERE/n)]=sha(HERE/n)
 for n in('gl_host.cpp','gl_scalar_commands.inc'):inputs[str(oldroot/n)]=sha(oldroot/n)
 (O/'source-pin.json').write_text(json.dumps(dict(commit=commit,archive_sha256=sha(O/'support.tar'),sources=sources,inputs=inputs,owned={n:sha(S/'windows'/n)for n in OWN},shared={n:sha(S/'windows'/n)for n in copied if n not in OWN},protected=protected),indent=2)+'\n')
 guest=O/'uniforms.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-jump-tables','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/gl_uniform_guest.c','-o',guest],'ndk-build');G=O/'guest';run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x5c000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate');m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 cxx='/mnt/c/mingw64/bin/g++.exe';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(O),'-I'+wp(G),'-I'+wp(S/'windows'),'-I'+wp(ANGLE/'src/include'),f'-DGL_UNIFORM_IMAGE="{wp(guest)}"',f'-DGL_UNIFORM_DLL_DIRECTORY=L"{wp(DLL)}"'];run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/gl_uniform_test.cpp')],'test-syntax');loader=O/'loader.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader');objects=[]
 for rel in('windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  obj=O/(Path(rel).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if rel=='windows/gl_host.cpp'else[]),'-c',wp(S/rel),'-o',wp(obj)],Path(rel).stem+'-build');objects.append(obj)
 exe=O/'uniforms.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(S/'windows/gl_uniform_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'link');text=run([exe],'focused',100);assert'GL-UNIFORM-PASS'in text
 for group in(sources,inputs):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');r=dict(passed=True,commit=commit,owned_sources={n:sha(S/'windows'/n)for n in OWN},shared_sources={n:sha(S/'windows'/n)for n in copied if n not in OWN},protected_sources=protected,source_pin_sha256=sha(O/'source-pin.json'),stdout=text,heads=len(m['traces']),objects=len(m['objects']),executable_sha256=sha(exe),scope='Fourteen observed uniform APIs via actual NDK resolver, real Windows ANGLE and independent native-updated program; no game/frame or Linux graphics claim; GLES2 uniform types with native ES3 transpose behavior.',evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts});(O/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('GL-UNIFORM-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
