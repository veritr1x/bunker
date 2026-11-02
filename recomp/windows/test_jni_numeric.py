"""Numeric JNI scalar transport against real ARM64 promotions and frozen JNI regressions."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('jni_host.h','jni_host.cpp','jni_numeric_guest.c','jni_numeric_test.cpp','jni_numeric_reference.c','test_jni_numeric.py')
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
 fixture=out/'numeric.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[source/'windows'/name for name in('package_guest_fixture.c','java_init_guest.c','jni_object_array_guest.c','jni_long_array_guest.c','jni_array_result_guest.c','jni_numeric_guest.c')],'-o',fixture])
 reference=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root');gcc=reference/'usr/lib/gcc-cross/aarch64-linux-gnu/13';sysroot=reference/'usr/aarch64-linux-gnu'
 ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';ndk_object=out/'numeric-reference-guest.o'
 run([ndkcc,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-c',source/'windows/jni_numeric_guest.c','-o',ndk_object])
 arm=out/'numeric-arm64-reference';run(['clang-18','--target=aarch64-linux-gnu',f'--sysroot={sysroot}',f'-B{gcc}',f'-L{gcc}','-fuse-ld=lld','-static','-O2',source/'windows/jni_numeric_reference.c',ndk_object,'-o',arm])
 rows=subprocess.check_output([reference/'usr/bin/qemu-aarch64-static','-cpu','cortex-a53',arm],text=True);(out/'arm64-reference.log').write_text(rows)
 expected=[tuple(int(v,16)for v in row.split())for row in rows.splitlines()];assert len(expected)==18
 (out/'numeric_expected.h').write_text('#pragma once\n#include <cstdint>\nstruct NumericExpected{uint32_t raw,promoted;};\ninline constexpr NumericExpected kNumericExpected[]={'+','.join('{0x%xu,0x%xu}'%v for v in expected)+'};\n')
 result=dict(support_source=str(a.support_source),source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},owned_overlay=list(OWN),fixture_sha256=sha(fixture),arm64_reference_sha256=sha(arm),arm64_reference_log_sha256=sha(out/'arm64-reference.log'),arm64_reference_guest_sha256=sha(ndk_object),runner_sha256=sha(__file__),generated_header_sha256={n:sha(out/n)for n in('sample.h','jni.h')},platforms={})
 for windows in(True,False):
  label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
  run([sys.executable,source/'whole/compile.py',fixture,'--out',translated,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';loader=build/'elfload.o'
  run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(work/'remill-src/include'),'-I'+path(out),'-I'+path(translated),'-I'+path(work/'zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(fixture)}"',f'-DARRAY_IMAGE="{path(fixture)}"']
  objects=[]
  for rel in('windows/jni_host.cpp','windows/android_context.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  backend=work/('zlib-native/libz-inflate.a'if windows else'zlib-linux/backend/libz-inflate.a');tests={}
  for test in('jni_numeric','jni_host','java_init','jni_constructor_frame','jni_callback_frame','jni_long_array','jni_array_result'):
   exe=build/(test+('.exe'if windows else''));run([cxx,*flags,path(source/f'windows/{test}_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
   r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);(build/(test+'.stdout.log')).write_text(r.stdout);(build/(test+'.stderr.log')).write_text(r.stderr);print(label+' '+test+': '+r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode()
   tests[test]=dict(stdout=r.stdout,stderr=r.stderr,binary_sha256=sha(exe))
   result['platforms'][label]=dict(traces=len(manifest['traces']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],toolchain=manifest['toolchain'],tests=tests);(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
