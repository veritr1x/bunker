"""Reached resolver/ServiceConnection/disabled-AR JNI behavior and core regressions."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
OWNED=('jni_host.h','jni_host.cpp','android_context.h','android_context.cpp','java_init_guest.c','java_init_test.cpp')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Use a fresh candidate directory';out.mkdir(parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.c','.cpp','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWNED:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kwargs):return subprocess.run(list(map(str,command)),check=True,**kwargs)
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def digest(path):
  with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
 sample=(HERE.parent/'work/windows-files/sample.h').read_text()
 metadata=json.loads((HERE.parent/'work/java-native8-audit/manifest-metadata-proof.json').read_text())
 assert metadata['exact_match_native8']and metadata['unity_tango_enable_absent']
 sample+='\ninline void ApplyActualMetadata(bunker::windows::AndroidContextConfig &config){using bunker::windows::LaunchExtra;\n'
 literal=lambda text:'u'+json.dumps(text,ensure_ascii=True)
 for name,row in metadata['fresh_aapt_complete_metadata'].items():
  value=row['value'];kind=row['type'];expr=f'LaunchExtra::String({literal(value)})'if kind=='string'else f'LaunchExtra::Boolean({str(value).lower()})'if kind=='boolean'else f'LaunchExtra::Integer({value})'
  sample+=f' config.application_metadata.emplace({literal(name)},{expr});\n'
 sample+='}\n';(out/'sample.h').write_text(sample)
 jni=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copyfile(jni,out/'jni.h')
 guest=out/'java-init.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/package_guest_fixture.c',source/'windows/java_init_guest.c','-o',guest])
 result={'fixture_sha256':digest(guest),'source_sha256':{str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},'owned_overlay':list(OWNED),'support_source':str(a.support_source),'generated_sample_sha256':digest(out/'sample.h'),'jni_header_sha256':digest(jni),'metadata_proof_sha256':digest(HERE.parent/'work/java-native8-audit/manifest-metadata-proof.json'),'platforms':{},'runner_sha256':digest(__file__)}
 for windows in(True,False):
  platform='windows'if windows else'linux';build=out/platform;build.mkdir();translated=build/'guest';path=hp if windows else lambda p:str(p)
  run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18'
  loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(HERE.parent/'work/remill-src/include'),'-I'+path(out),'-I'+path(translated),'-I'+path(HERE.parent/'work/zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(guest)}"']
  objects=[]
  for rel in('windows/jni_host.cpp','windows/android_context.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  backend=HERE.parent/'work'/('zlib-native/libz-inflate.a'if windows else'zlib-linux/backend/libz-inflate.a')
  results={}
  for test in('java_init','jni_host','android_context','package_manager','jni_callback_frame','jni_constructor_frame'):
   exe=build/(test+('.exe'if windows else''));run([cxx,*flags,'-Wall','-Wextra',*(['-Werror']if test=='java_init'else[]),path(source/f'windows/{test}_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)])
   test_result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
   (build/(test+'.stdout.log')).write_text(test_result.stdout);(build/(test+'.stderr.log')).write_text(test_result.stderr)
   print(platform+' '+test+': '+test_result.stdout,end='',flush=True);print(test_result.stderr,end='',file=sys.stderr,flush=True);test_result.check_returncode()
   results[test]={'stdout':test_result.stdout,'stderr':test_result.stderr,'binary_sha256':digest(exe)}
   if test=='java_init':
    enabled=subprocess.run([str(exe),'--enabled-ar'],capture_output=True,text=True,timeout=60)
    (build/'enabled-ar.stdout.log').write_text(enabled.stdout);(build/'enabled-ar.stderr.log').write_text(enabled.stderr)
    assert enabled.returncode!=0 and 'enabled Google ARCore requires original native initialize/resume side effects; no host implementation'in enabled.stderr
    results[test]['enabled_ar_expected_failure']={'returncode':enabled.returncode,'stdout':enabled.stdout,'stderr':enabled.stderr}
   result['platforms'][platform]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'tests':results}
   (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
