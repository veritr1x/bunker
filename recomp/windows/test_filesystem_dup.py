"""Freeze bounded real dup/OFD providers, actual NDK callers and existing FS/mapping gates."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
PRODUCTION=('filesystem.h','filesystem.cpp')
OWN=('filesystem_dup_guest.c','filesystem_dup_test.cpp','test_filesystem_dup.py')
def sha(path):
 with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
 p.add_argument('--lift',type=Path,default=HERE.parent/'work/ushll-toolchain/fa80a8edb3f33d18-9524e65b09c51e5b/remill-lift')
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);work=HERE.parent/'work'
 commit=subprocess.check_output(['git','rev-parse','48a2e64'],cwd=ROOT,text=True).strip()
 archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=ROOT)
 (out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';pins={}
 for name in PRODUCTION+OWN:
  pins[name]=sha(HERE/name);shutil.copy2(HERE/name,source/'windows'/name)
 shutil.copytree(work/'remill-src/include',out/'remill-include')
 support={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()}
 headers={str(f.relative_to(out/'remill-include')):sha(f)for f in(out/'remill-include').rglob('*')if f.is_file()}
 result={'support_commit':commit,'support_archive_sha256':sha(out/'support.tar'),'overlay':pins,'support_sources':support,'remill_headers':headers,'passed':False}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 print('Frozen '+commit+' + five exact overlays',flush=True)
 def run(command,log,timeout=None):
  with log.open('w')as stream:r=subprocess.run(list(map(str,command)),stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
  text=log.read_text(errors='replace')
  if r.returncode:raise RuntimeError(f'{log}: exit{r.returncode}\n{text[-8000:]}')
  return text
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe'
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 result['native_compiler']={'version':run([cxx,'--version'],out/'native-compiler.log').strip(),'sha256':sha(cxx)}
 result['ndk_compiler']={'version':run([ndk,'--version'],out/'ndk-compiler.log').strip(),'sha256':sha(ndk)}
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(out/'remill-include')]
 def fixture(filename,name,base):
  so=out/(name+'.so');run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*(['-Wall','-Wextra','-Werror']if name=='dup'else[]),source/'windows'/filename,'-o',so],out/(name+'-ndk.log'))
  guest=out/(name+'-guest');run([sys.executable,source/'whole/compile.py',so,'--out',guest,'--base',base,'--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],out/(name+'-lift.log'))
  manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  return so,guest,manifest
 fixture_image,guest,manifest=fixture('filesystem_dup_guest.c','dup','0x76000000')
 data=out/'focused-data';data.mkdir()
 focused_flags=flags+['-Wall','-Wextra','-Werror','-I'+wp(guest),f'-DDUP_IMAGE="{wp(fixture_image)}"',f'-DDUP_ROOT="{wp(data)}"']
 # New sources must pass their own warning flags before any provider compilation/runs.
 run([cxx,*focused_flags,'-fsyntax-only',wp(source/'windows/filesystem_dup_test.cpp')],out/'focused-precheck.log')
 loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],out/'elfload-build.log')
 objects=[]
 for rel in('windows/filesystem.cpp','windows/growdown_memory.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');run([cxx,*flags,*(['-g']if rel=='windows/filesystem.cpp'else[]),'-c',wp(source/rel),'-o',wp(obj)],out/(Path(rel).stem+'-build.log'));objects.append(obj)
 exe=out/'filesystem-dup.exe';run([cxx,*focused_flags,wp(source/'windows/filesystem_dup_test.cpp'),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(exe)],out/'focused-link.log')
 positive=run([exe],out/'focused.log',180);print(positive.strip(),flush=True)
 result['focused']={'stdout':positive.strip(),'binary_sha256':sha(exe),'fixture_sha256':sha(fixture_image),'traces':len(manifest['traces']),'objects':len(manifest['objects']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain']}
 (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 # Unchanged mapping-use source: real file view/pins and actual lease races.
 mapping_image,mapping_guest,mm=fixture('mapping_use_guest.c','mapping','0x75000000')
 mapping_exe=out/'mapping-regression.exe'
 run([cxx,*flags,'-I'+wp(mapping_guest),f'-DMAPPING_IMAGE="{wp(mapping_image)}"',f'-DMAPPING_ROOT="{wp(out)}"',wp(source/'windows/mapping_use_test.cpp'),*map(wp,objects),wp(loader),*map(wp,mm['objects']),'-static','-pthread','-latomic','-o',wp(mapping_exe)],out/'mapping-link.log')
 mapped=run([mapping_exe],out/'mapping.log',120);print(mapped.strip(),flush=True);negatives={}
 for mode,message in {'guest-pinned-unmap':'unsupported munmap of active mapping use','guest-pinned-protect':'unsupported mprotect of active mapping use','destroy-pinned':'FileSystem destruction with active mapping use'}.items():
  log=out/('mapping-'+mode+'.log')
  with log.open('w')as stream:failed=subprocess.run([str(mapping_exe),'--'+mode],stdout=stream,stderr=subprocess.STDOUT,timeout=30)
  assert failed.returncode and message in log.read_text(errors='replace'),(mode,failed.returncode)
  negatives[mode]={'returncode':failed.returncode,'log_sha256':sha(log)}
 # Immutable accepted FS116 NDK objects with fresh regression files and frozen support.
 regression_data=out/'filesystem-data'
 run([sys.executable,source/'windows/prepare_files.py','--apk',work/'inputs/game-9ded0797.apk','--ndk',a.ndk,'--out',regression_data,'--aapt','/home/user/bunker-tools/android-sdk/build-tools/36.0.0/aapt'],out/'filesystem-data.log')
 old=work/'windows-files';shutil.copy2(old/'file_traces.h',regression_data/'file_traces.h');prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets']
 old_objects=[old/'guest'/Path(item).name for item in prior['objects']]
 inputs=[*old_objects,old/'file-guest.so',old/'file_traces.h',old/'guest/manifest.json',work/'zlib-native/libz-inflate.a']
 immutable={str(f):sha(f)for f in inputs}
 ff=flags+['-I'+wp(regression_data),'-I'+wp(work/'zlib-native/zlib-1.3.2'),f'-DFILES_ROOT="{wp(regression_data)}"','-DHAVE_GUEST_FILE_FIXTURE',f'-DGUEST_FILES_IMAGE="{wp(old/"file-guest.so")}"']
 extra=[]
 for name in('jni_host','android_context','windows_android_id','android_assets','apk_assets'):
  obj=out/(name+'-regression.o');run([cxx,*ff,'-c',wp(source/f'windows/{name}.cpp'),'-o',wp(obj)],out/(name+'-regression-build.log'));extra.append(obj)
 fs_exe=out/'filesystem-regression.exe';run([cxx,*ff,wp(source/'windows/filesystem_test.cpp'),*map(wp,extra+objects),wp(loader),*map(wp,old_objects),wp(work/'zlib-native/libz-inflate.a'),'-static','-pthread','-latomic','-ladvapi32','-o',wp(fs_exe)],out/'filesystem-link.log')
 fs_result=run([fs_exe],out/'filesystem.log',120);print(fs_result.strip(),flush=True)
 assert immutable=={str(f):sha(f)for f in inputs}
 for name,pin in pins.items():assert sha(HERE/name)==pin and sha(source/'windows'/name)==pin
 for name,pin in support.items():assert sha(source/name)==pin
 for name,pin in headers.items():assert sha(out/'remill-include'/name)==pin
 result['regressions']={'mapping_use':{'stdout':mapped.strip(),'binary_sha256':sha(mapping_exe),'named_boundaries':negatives},'filesystem':{'stdout':fs_result.strip(),'binary_sha256':sha(fs_exe),'immutable_inputs':immutable}}
 result['objects']={str(p):sha(p)for p in[loader,*objects,*extra]}
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name not in('acceptance.json','progress.json')}
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
