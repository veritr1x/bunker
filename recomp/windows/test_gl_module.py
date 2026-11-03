"""Actual NDK libdl to existing typed GLES markers; real ANGLE queries only."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('module_registry.h','module_registry.cpp','gles_service_module.h','gl_module_guest.c','gl_module_test.cpp','test_gl_module.py')
PROTECTED=('windows/gl_host.h','windows/gl_host.cpp','windows/egl_host.h','windows/egl_host.cpp','windows/native_window.h','windows/native_window.cpp','windows/jni_host.h','windows/jni_host.cpp','windows/module_registry_elf.h','windows/module_registry_elf.cpp','windows/module_registry_test.cpp','whole/runtime.h','whole/runtime.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--support-commit',default='HEAD');p.add_argument('--reuse-registry',type=Path,help='Reuse only the pinned prior unchanged registry unit results');a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);W=HERE.parent/'work'
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
 for n in OWN:shutil.copy2(HERE/n,S/'windows'/n)
 protected={n:sha(HERE.parent/n)for n in PROTECTED}
 for n,h in protected.items():assert sha(S/n)==h,'protected source differs from archive: '+n
 reuse=None
 if a.reuse_registry:
  prior_path=a.reuse_registry.resolve();prior_sha=sha(prior_path);assert prior_sha=='a0e4d39898323a00760f3a118ccdec1471859cfd20849a151f78b1a17178793d','unqualified prior registry receipt'
  prior=json.loads(prior_path.read_text());assert prior.get('passed')is True
  required={**{'windows/'+n:prior['owned_sources'][n]for n in('module_registry.h','module_registry.cpp')},**{n:prior['protected_sources'][n]for n in('windows/module_registry_test.cpp','whole/runtime.h','whole/runtime.cpp')}}
  for n,h in required.items():assert sha(S/n)==h and sha(HERE.parent/n)==h,'registry reuse source differs: '+n
  for label in('linux','windows'):assert prior['legacy'][label]['stdout']=='Translated module registry: 22 checks passed.\n'
  reuse=dict(prior_acceptance_path=str(prior_path),prior_acceptance_sha256=prior_sha,exact_source_hashes=required)
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');CC=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ANGLE=W/'angle-native';DLL=ANGLE/'bundle/bin'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'and sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 sources={str(f):sha(f)for f in S.rglob('*')if f.is_file()};inputs={str(f):sha(f)for f in [CC.resolve(),T/'remill-lift',T/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve()]}
 for directory in(T/'include',ANGLE/'src/include',DLL):
  for f in directory.rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
 for n in OWN:inputs[str(HERE/n)]=sha(HERE/n)
 if reuse:inputs[reuse['prior_acceptance_path']]=reuse['prior_acceptance_sha256']
 (O/'source-pin.json').write_text(json.dumps(dict(commit=commit,archive_sha256=sha(O/'support.tar'),sources=sources,inputs=inputs,protected=protected,owned={n:sha(HERE/n)for n in OWN}),indent=2)+'\n')
 guest=O/'gl-module.so';run([CC,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/gl_module_guest.c','-o',guest],'ndk-build');B=O/'windows';B.mkdir();G=B/'guest'
 run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x5c000000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'windows-translate')
 m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 cxx='/mnt/c/mingw64/bin/g++.exe';gcc='/mnt/c/mingw64/bin/gcc.exe';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(G),'-I'+wp(S/'windows'),'-I'+wp(ANGLE/'src/include'),f'-DGL_MODULE_IMAGE="{wp(guest)}"',f'-DGL_MODULE_DLL_DIRECTORY=L"{wp(DLL)}"']
 run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(S/'windows/gl_module_test.cpp')],'windows-strict-source');loader=B/'loader.o';run([gcc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'windows-loader');objects=[]
 for rel in ('windows/module_registry.cpp','windows/module_registry_elf.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  obj=B/(Path(rel).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if rel=='windows/module_registry.cpp'else[]),'-c',wp(S/rel),'-o',wp(obj)],'windows-'+obj.stem);objects.append(obj)
 exe=B/'gl-module.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(S/'windows/gl_module_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'windows-focused-link');result=run([exe],'windows-focused',90);assert'GLES-MODULE-PASS'in result
 legacy={}
 if reuse:
  for label in('linux','windows'):legacy[label]=dict(prior['legacy'][label],executed_in_this_qualification=False,reused=True,**reuse)
 else:
  for windows in(False,True):
   label='windows'if windows else'linux';D=O/('legacy-'+label);D.mkdir();conv=wp if windows else str;cc=cxx if windows else'clang++-18';base=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(S/'windows')];obs=[]
   if windows:obs=[B/'module_registry.o',B/'runtime.o']
   else:
    for rel in('windows/module_registry.cpp','whole/runtime.cpp'):
     obj=D/(Path(rel).stem+'.o');run([cc,*base,'-c',conv(S/rel),'-o',conv(obj)],label+'-legacy-'+obj.stem);obs.append(obj)
   unit=D/('module-unit.exe'if windows else'module-unit');run([cc,*base,conv(S/'windows/module_registry_test.cpp'),*map(conv,obs),'-pthread','-latomic',*(['-static']if windows else[]),'-o',conv(unit)],label+'-legacy-link');text=run([unit],label+'-legacy');assert'checks passed'in text;legacy[label]=dict(stdout=text,binary_sha256=sha(unit))
 for group in(sources,inputs):
  for n,h in group.items():assert sha(n)==h,n
 for n,h in protected.items():assert sha(HERE.parent/n)==h
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');r=dict(passed=True,commit=commit,source_pin_sha256=sha(O/'source-pin.json'),owned_sources={n:sha(S/'windows'/n)for n in OWN},protected_sources=protected,windows=dict(stdout=result,binary_sha256=sha(exe),heads=len(m['traces']),objects=len(m['objects'])),legacy=legacy,registry_regression_reuse=reuse,scope='Actual NDK libdl and EGL procedure lookup to existing typed GLES/EGL bridges, real Windows ANGLE pbuffer; nullable optional commands; known real caller ELF and explicit service exclusion only. No rendering/game/full GL API or Linux graphics qualification.',evidence={str(f):sha(f)for f in O.rglob('*')if f.is_file()and'source'not in f.relative_to(O).parts});(O/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('GL-MODULE-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
