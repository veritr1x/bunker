"""Reference-array object returns and frozen JNI ownership/array regressions."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('jni_host.cpp','jni_array_result_guest.c','jni_array_result_test.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve previous candidate directories';out.mkdir(parents=True);source=out/'source';work=HERE.parent/'work'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 for name in('sample.h','jni.h'):shutil.copyfile(work/'java-init-candidate4'/name,out/name)
 fixture=out/'array-result.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[source/'windows'/name for name in('package_guest_fixture.c','jni_object_array_guest.c','jni_array_result_guest.c')],'-o',fixture])
 result=dict(support_source=str(a.support_source),source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},owned_overlay=list(OWN),fixture_sha256=sha(fixture),runner_sha256=sha(__file__),generated_header_sha256={n:sha(out/n)for n in('sample.h','jni.h')},platforms={})
 for windows in(True,False):
  label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
  run([sys.executable,source/'whole/compile.py',fixture,'--out',translated,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';loader=build/'elfload.o'
  run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(work/'remill-src/include'),'-I'+path(out),'-I'+path(translated),'-I'+path(work/'zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(fixture)}"',f'-DARRAY_IMAGE="{path(fixture)}"']
  objects=[]
  for rel in('windows/jni_host.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  backend=work/('zlib-native/libz-inflate.a'if windows else'zlib-linux/backend/libz-inflate.a');tests={}
  for test in('jni_array_result','jni_host','jni_constructor_frame','jni_callback_frame','jni_object_array'):
   exe=build/(test+('.exe'if windows else''));run([cxx,*flags,path(source/f'windows/{test}_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
   r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);(build/(test+'.stdout.log')).write_text(r.stdout);(build/(test+'.stderr.log')).write_text(r.stderr);print(label+' '+test+': '+r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode()
   tests[test]=dict(stdout=r.stdout,stderr=r.stderr,binary_sha256=sha(exe))
   result['platforms'][label]=dict(traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],toolchain=manifest['toolchain'],tests=tests);(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
