"""Frozen focused instance jlong ABI/ownership gate; no original game execution."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
OWN=('jni_host.h','jni_host.cpp','jni_long_method_guest.c','jni_long_method_reference.c','jni_long_method_test.cpp','test_jni_long_method.py','jni_long_method.md')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('out','ndk','toolchain','base-archive'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve old candidates';out.mkdir();work=(HERE.parent/'work').resolve()
 def run(name,cmd):
  print(name,flush=True)
  with(out/(name+'.log')).open('w')as log:subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,check=True)
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 archive=out/'base.tar';shutil.copyfile(a.base_archive,archive)
 with tarfile.open(archive)as tar:tar.extractall(out/'base',filter='data')
 source=out/'base/recomp'
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 tc=a.toolchain.resolve();lift=tc/'remill-lift';sem=tc/'aarch64.bc';includes=tc/'include'
 ndk=a.ndk.resolve();cc=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 jni=ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copyfile(jni,out/'jni.h')
 for name in('sample.h',):shutil.copyfile(work/'java-init-candidate4'/name,out/name)
 expected_numeric=work/'jni-numeric3/numeric_expected.h';shutil.copyfile(expected_numeric,out/'numeric_expected.h')
 source_pins={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()}
 tools={str(f):sha(f)for f in [lift,sem,tc/'hashes.json',cc,Path('/usr/bin/clang++-18'),Path('/usr/bin/clang-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe')]}
 objects=[]
 for name in('jni_long_method_guest','jni_numeric_guest'):
  obj=out/(name+'.o');run('ndk-'+name,[cc,'-O1','-fPIC','-fno-stack-protector','-fno-builtin',*(['-Wall','-Wextra','-Werror']if name=='jni_long_method_guest'else[]),'-c',source/f'windows/{name}.c','-o',obj]);objects.append(obj)
 fixture=out/'long.so';run('ndk-link',[cc,'-shared','-nostdlib',*objects,'-o',fixture])
 refroot=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root');gcc=refroot/'usr/lib/gcc-cross/aarch64-linux-gnu/13';sysroot=refroot/'usr/aarch64-linux-gnu';qemu=refroot/'usr/bin/qemu-aarch64-static';arm=out/'arm64-reference'
 run('reference-build',['clang-18','--target=aarch64-linux-gnu',f'--sysroot={sysroot}',f'-B{gcc}',f'-L{gcc}','-fuse-ld=lld','-static','-O2','-Wall','-Wextra','-Werror','-I'+str(out),source/'windows/jni_long_method_reference.c',objects[0],'-o',arm])
 run('reference',[qemu,'-cpu','cortex-a53',arm]);expected=(out/'reference.log').read_text().splitlines();assert len(expected)==54
 values=[0,1,-1,-(1<<63),(1<<63)-1,1<<32,-((1<<32)+1),0x123456789abcdef,-0x123456789abcdef]
 canonical=[f'{i} {mixed} {form} {value&((1<<64)-1):016x} {(value&((1<<64)-1))^0xfedcba9876543210:016x}'for i,value in enumerate(values)for mixed in range(2)for form in range(3)];assert expected==canonical
 result=dict(passed=False,base_archive_path=str(a.base_archive.resolve()),base_archive_sha256=sha(archive),owned_source_hashes={name:source_pins['windows/'+name]for name in OWN},source_pins=source_pins,tools=tools,fixture_sha256=sha(fixture),shared_NDK_long_object_sha256=sha(objects[0]),actual_ARM64_reference_sha256=sha(arm),actual_ARM64_reference_log_sha256=sha(out/'reference.log'),reference_scope='Actual NDK caller and native JNI-table callbacks on ARM64; no JVM/framework equivalence',platforms={})
 for windows in(True,False):
  label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;translated=build/'translated'
  run(label+'-lift',[sys.executable,source/'whole/compile.py',fixture,'--out',translated,'--base','0x74000000','--lift',lift,'--semantics-dir',tc,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';nativecc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';loader=build/'elfload.o'
  run(label+'-loader',[nativecc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(includes),'-I'+path(out),'-I'+path(translated),f'-DPACKAGE_IMAGE="{path(fixture)}"',f'-DARRAY_IMAGE="{path(fixture)}"']
  hostobjects=[]
  for rel in('windows/jni_host.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run(label+'-'+Path(rel).stem,[cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);hostobjects.append(obj)
  tests={}
  for name in('jni_long_method','jni_numeric'):
   exe=build/(name+('.exe'if windows else''));run(label+'-'+name+'-build',[cxx,*flags,*(['-Wall','-Wextra','-Werror']if name=='jni_long_method'else[]),path(source/f'windows/{name}_test.cpp'),*map(path,hostobjects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
   run(label+'-'+name,[exe]);text=(out/(label+'-'+name+'.log')).read_text();rows=[line.removeprefix('RECORD ')for line in text.splitlines()if line.startswith('RECORD ')];assert rows==expected if name=='jni_long_method'else'JNI numeric:'in text
   tests[name]=dict(binary_path=str(exe),binary_sha256=sha(exe),log_sha256=sha(out/(label+'-'+name+'.log')),record_count=len(rows),final_line=text.splitlines()[-1])
  result['platforms'][label]=dict(traces=len(manifest['traces']),unsupported=[],unresolved_direct_targets=[],manifest_sha256=sha(translated/'manifest.json'),toolchain=manifest['toolchain'],tests=tests);(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 assert all(sha(source/f)==h for f,h in source_pins.items())
 assert all(sha(HERE/name)==result['owned_source_hashes'][name]for name in OWN)
 assert all(sha(Path(f))==h for f,h in tools.items())
 result['passed']=True;result['evidence']={str(f):sha(f)for f in out.rglob('*')if f.is_file()and not f.is_relative_to(out/'base')and f.name not in ('acceptance.json','progress.json')};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('JNI-LONG-METHOD-PASS',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
