"""First supported APK proxy factory/disable port with strict NDK callers."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
OWNED=('jni_interface_proxy.h','jni_interface_proxy.cpp','jni_interface_proxy_guest.c','jni_interface_proxy_test.cpp')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--focus-only',action='store_true',help='Recheck only the proxy gate after a proxy-only change; preserve prior regression evidence')
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
 sample=(HERE.parent/'work/windows-files/sample.h').read_text();metadata=json.loads((HERE.parent/'work/java-native8-audit/manifest-metadata-proof.json').read_text())
 assert metadata['exact_match_native8']and metadata['unity_tango_enable_absent']
 sample+='\ninline void ApplyActualMetadata(bunker::windows::AndroidContextConfig &config){using bunker::windows::LaunchExtra;\n'
 literal=lambda text:'u'+json.dumps(text,ensure_ascii=True)
 for name,row in metadata['fresh_aapt_complete_metadata'].items():
  value=row['value'];kind=row['type'];expr=f'LaunchExtra::String({literal(value)})'if kind=='string'else f'LaunchExtra::Boolean({str(value).lower()})'if kind=='boolean'else f'LaunchExtra::Integer({value})';sample+=f' config.application_metadata.emplace({literal(name)},{expr});\n'
 (out/'sample.h').write_text(sample+'}\n');jni=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h';shutil.copyfile(jni,out/'jni.h')
 guest=out/'jni-interface-proxy.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[source/'windows'/n for n in ['package_guest_fixture.c','java_init_guest.c','settings_secure_guest.c','jni_interface_proxy_guest.c']],'-o',guest])
 result={'fixture_sha256':digest(guest),'source_sha256':{str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},'owned_overlay':list(OWNED),'support_source':str(a.support_source),'jni_header_sha256':digest(jni),'platforms':{},'runner_sha256':digest(__file__)}
 failures={'--wrong-profile':'unsupported loader/interface profile','--null-list':'unsupported loader/interface profile','--duplicate-profile':'unsupported loader/interface profile','--null-interface':'unsupported loader/interface profile','--active-service':'active ServiceConnection callback is unsupported','--active-toString':'Object callback is unsupported: toString','--active-equals':'Object callback is unsupported: equals','--active-hashCode':'unsupported JNIEnv slot 49','--wrong-disable':'proxy metadata/reference operation failed','--enabled-unload':'remains enabled before unload'}
 for windows in(True,False):
  platform='windows'if windows else'linux';build=out/platform;build.mkdir();translated=build/'guest';path=hp if windows else lambda p:str(p)
  run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'])
  manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)])
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(HERE.parent/'work/remill-src/include'),'-I'+path(out),'-I'+path(translated),'-I'+path(HERE.parent/'work/zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(guest)}"'];objects=[]
  for rel in('windows/jni_host.cpp','windows/android_context.cpp','windows/windows_android_id.cpp','windows/jni_interface_proxy.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/rel),'-o',path(obj)]);objects.append(obj)
  backend=HERE.parent/'work'/('zlib-native/libz-inflate.a'if windows else'zlib-linux/backend/libz-inflate.a');tests={}
  for test in(('jni_interface_proxy',)if a.focus_only else('jni_interface_proxy','jni_host','android_context','package_manager','jni_callback_frame','jni_constructor_frame','java_init','settings_secure')):
   exe=build/(test+('.exe'if windows else''));run([cxx,*flags,'-Wall','-Wextra',*(['-Werror']if test=='jni_interface_proxy'else[]),path(source/f'windows/{test}_test.cpp'),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static','-ladvapi32']if windows else[]),'-o',path(exe)])
   observed=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60);(build/(test+'.stdout.log')).write_text(observed.stdout);(build/(test+'.stderr.log')).write_text(observed.stderr);print(platform+' '+test+': '+observed.stdout,end='',flush=True);print(observed.stderr,end='',file=sys.stderr,flush=True);observed.check_returncode();tests[test]={'stdout':observed.stdout,'stderr':observed.stderr,'binary_sha256':digest(exe)}
   if test=='jni_interface_proxy':
    negatives={}
    for arg,message in failures.items():
     failed=subprocess.run([str(exe),arg],capture_output=True,text=True,timeout=30);assert failed.returncode!=0 and message in failed.stderr,(arg,failed.returncode,failed.stderr);negatives[arg]={'returncode':failed.returncode,'stderr':failed.stderr}
    tests[test]['explicit_failures']=negatives
   result['platforms'][platform]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'tests':tests};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
