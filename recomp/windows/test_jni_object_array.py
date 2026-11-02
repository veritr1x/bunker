"""Build actual NDK object-array callers and run them on both native hosts."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('jni_host.h','jni_host.cpp','jni_object_array_guest.c','jni_object_array_test.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve earlier candidates';out.mkdir(parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.c','.cpp','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 guest=out/'object-array.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/jni_object_array_guest.c','-o',guest])
 result=dict(fixture_sha256=sha(guest),source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},runner_sha256=sha(__file__),support_source=str(a.support_source),platforms={})
 for windows in(True,False):
  label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
  run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';loader=build/'elfload.o'
  run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  exe=build/('object-array.exe'if windows else'object-array');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(HERE.parent/'work/remill-src/include'),'-I'+path(translated),f'-DARRAY_IMAGE="{path(guest)}"']
  run([cxx,*flags,path(source/'windows/jni_object_array_test.cpp'),path(source/'windows/jni_host.cpp'),path(source/'whole/runtime.cpp'),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60);(build/'stdout.log').write_text(r.stdout);(build/'stderr.log').write_text(r.stderr);print(label+': '+r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode()
  result['platforms'][label]=dict(traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],toolchain=manifest['toolchain'],binary_sha256=sha(exe),stdout=r.stdout,stderr=r.stderr)
  (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
