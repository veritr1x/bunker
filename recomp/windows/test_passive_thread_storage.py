"""Freeze and qualify passive Windows thread-container lifetimes and existing providers."""
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('pthread_host.cpp','egl_host.cpp','game_bootstrap_detail.h','game_bootstrap.cpp','passive_thread_storage_guest.c','passive_thread_storage_test.cpp','test_passive_thread_storage.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--reuse-build',type=Path)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve all previous runs';out.mkdir(parents=True);work=HERE.parent/'work'
 commit='a82c88635235cffb60b4efa481c074144ede72c2';archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=HERE.parent.parent);(out/'host-source.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out,filter='data')
 source=out/'recomp'
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 shutil.copytree(work/'remill-src/include',out/'remill-include')
 def run(cmd,**kw):return subprocess.run(list(map(str,cmd)),check=True,**kw)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 fixture=out/'storage.so';translated=out/'guest'
 if a.reuse_build:
  previous=a.reuse_build.resolve()
  for f in(source).rglob('*'):
   if f.is_file()and f.name!='test_passive_thread_storage.py':assert sha(f)==sha(previous/'recomp'/f.relative_to(source)),f
  assert all(sha(f)==sha(previous/'remill-include'/f.relative_to(out/'remill-include'))for f in(out/'remill-include').rglob('*')if f.is_file())
  shutil.copyfile(previous/'storage.so',fixture);shutil.copytree(previous/'guest',translated)
 else:
  run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/passive_thread_storage_guest.c','-o',fixture])
  run([sys.executable,source/'whole/compile.py',fixture,'--out',translated,'--base','0x5c000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'])
 m=json.loads((translated/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 result=dict(support_commit=commit,archive_sha256=sha(out/'host-source.tar'),source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},headers_sha256={str(f.relative_to(out/'remill-include')):sha(f)for f in(out/'remill-include').rglob('*')if f.is_file()},owned_overlay=list(OWN),runner_sha256=sha(__file__),fixture_sha256=sha(fixture),traces=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],toolchain=m['toolchain'],tests={},inputs={})
 cxx='/mnt/c/mingw64/bin/g++.exe';cc='/mnt/c/mingw64/bin/gcc.exe';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(out/'remill-include')];loader=(a.reuse_build.resolve()if a.reuse_build else out)/'elfload.o'
 if not a.reuse_build:run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
 objs={}
 for rel in('windows/pthread_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','windows/nonlocal_jmp.cpp','windows/signal_host.cpp','windows/libc.cpp','whole/runtime.cpp','whole/format.cpp'):
  obj=(a.reuse_build.resolve()if a.reuse_build else out)/(Path(rel).stem+'.o')
  if not a.reuse_build:run([cxx,*flags,'-c',wp(source/rel),'-o',wp(obj)])
  objs[Path(rel).stem]=obj
 angle=work/'angle-scaling/bundle/bin';result['inputs'].update({str(f):sha(f)for f in angle.iterdir()if f.is_file()})
 def build(name,test,manifest,includes,defines,providers):
  exe=out/(name+'.exe');cmd=[cxx,*flags,*(['-Wall','-Wextra','-Werror']if name in('focused','window','egl')else[]),*['-I'+wp(d)for d in includes],*defines,wp(source/'windows'/test),*[wp(objs[k])for k in providers],wp(loader),*[wp(x)for x in manifest['objects']],'-static','-pthread','-latomic','-lbcrypt','-luser32','-o',wp(exe)];run(cmd)
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);(out/(name+'.stdout.log')).write_text(r.stdout);(out/(name+'.stderr.log')).write_text(r.stderr);print(name+': '+r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode();result['tests'][name]=dict(stdout=r.stdout,stderr=r.stderr,binary_sha256=sha(exe));(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n');return exe
 build('focused','passive_thread_storage_test.cpp',m,[translated],[f'-DPASSIVE_IMAGE="{wp(fixture)}"',f'-DPASSIVE_ANGLE=L"{wp(angle)}"'],['pthread_host','egl_host','native_window','jni_host','nonlocal_jmp','runtime'])
 def prior(directory,manifest='guest/manifest.json'):
  d=work/directory;mp=d/manifest;v=json.loads(mp.read_text());assert not v['unsupported_traces']and not v['unresolved_direct_targets'];result['inputs'][str(mp)]=sha(mp)
  for obj in v['objects']:result['inputs'][str(obj)]=sha(obj)
  return d,v
 old,pm=prior('worker-lifecycle3/regression');build('pthreads','pthread_test.cpp',pm,[old],[f'-DPTHREAD_GUEST_IMAGE="{wp(old/"fixture.so")}"'],['pthread_host','runtime']);result['inputs'][str(old/'fixture.so')]=sha(old/'fixture.so')
 old,pm=prior('worker-lifecycle3/focused');build('workers','worker_lifecycle_test.cpp',pm,[old],[f'-DWORKER_LIFECYCLE_IMAGE="{wp(old/"fixture.so")}"'],['pthread_host','signal_host','nonlocal_jmp','libc','runtime','format']);result['inputs'][str(old/'fixture.so')]=sha(old/'fixture.so')
 old,pm=prior('native-window');build('window','native_window_test.cpp',pm,[old/'guest'],[f'-DNATIVE_WINDOW_LIBRARY="{wp(old/"window.so")}"'],['native_window','jni_host','runtime']);result['inputs'][str(old/'window.so')]=sha(old/'window.so')
 old,pm=prior('egl-scaling');count=len(re.findall(r'\bPUT\(', (source/'windows/egl_scaling_guest.c').read_text()))-1;build('egl','egl_scaling_test.cpp',pm,[old/'guest'],[f'-DEGL_SCALING_RESULTS={count}',f'-DEGL_SCALING_LIBRARY="{wp(old/"scaling.so")}"',f'-DEGL_SCALING_DLL_DIRECTORY=L"{wp(angle)}"'],['egl_host','native_window','jni_host','runtime']);result['inputs'][str(old/'scaling.so')]=sha(old/'scaling.so')
 # Compile the real game translation unit with accepted generated metadata, no linking/init.
 game=work/'windows-game12';syntax=[cxx,*flags,'-fsyntax-only','-I'+wp(game),'-I'+wp(game/'angle-include'),'-I'+wp(game/'zlib-include'),wp(source/'windows/game_bootstrap.cpp')];run(syntax);result['game_syntax_check']={'command':list(map(str,syntax)),'headers':{n:sha(game/n)for n in('game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h')}}
 result['reused_build']=str(a.reuse_build.resolve())if a.reuse_build else None
 result['object_sha256']={str(p):sha(p)for p in[loader,*objs.values(),*map(Path,m['objects'])]};result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
