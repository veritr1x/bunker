"""Real Windows mapping-use leases, strict NDK calls and existing FS116."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
OWN=('filesystem.h','filesystem.cpp','growdown_memory.h','growdown_memory.cpp','mapping_use_guest.c','mapping_use_test.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('ndk','lift','semantics-dir','support-source','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve old candidate directories';out.mkdir(parents=True);source=out/'source';work=HERE.parent/'work'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 fixture=out/'mapping-use.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/mapping_use_guest.c','-o',fixture])
 guest=out/'guest';run([sys.executable,source/'whole/compile.py',fixture,'--out',guest,'--base','0x75000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'])
 m=json.loads((guest/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 cxx='/mnt/c/mingw64/bin/g++.exe';cc='/mnt/c/mingw64/bin/gcc.exe';loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(work/'remill-src/include'),'-I'+wp(guest),f'-DMAPPING_IMAGE="{wp(fixture)}"',f'-DMAPPING_ROOT="{wp(out)}"'];objects=[]
 for rel in('windows/filesystem.cpp','windows/growdown_memory.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');run([cxx,*flags,'-c',wp(source/rel),'-o',wp(obj)]);objects.append(obj)
 exe=out/'mapping-use.exe';run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'windows/mapping_use_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-latomic','-pthread','-static','-o',wp(exe)])
 observed=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);(out/'stdout.log').write_text(observed.stdout);(out/'stderr.log').write_text(observed.stderr);print(observed.stdout,end='',flush=True);print(observed.stderr,end='',file=sys.stderr,flush=True);observed.check_returncode()
 negatives={}
 for arg,message in {'--guest-pinned-unmap':'unsupported munmap of active mapping use','--guest-pinned-protect':'unsupported mprotect of active mapping use','--destroy-pinned':'FileSystem destruction with active mapping use'}.items():
  failed=subprocess.run([str(exe),arg],capture_output=True,text=True,timeout=30);(out/(arg[2:]+'.stderr.log')).write_text(failed.stderr);assert failed.returncode!=0 and message in failed.stderr,(arg,failed.returncode,failed.stderr);negatives[arg]=dict(returncode=failed.returncode,stderr=failed.stderr)
 result=dict(passed=False,source_sha256={str(f.relative_to(source)):sha(f)for f in source.rglob('*')if f.is_file()},support_source=str(a.support_source),owned_overlay=list(OWN),runner_sha256=sha(__file__),fixture_sha256=sha(fixture),binary_sha256=sha(exe),stdout=observed.stdout,stderr=observed.stderr,explicit_failures=negatives,traces=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],toolchain=m['toolchain'])
 (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 # Use fresh regression data. Never write in the old accepted windows-files tree.
 data=out/'regression-data';run([sys.executable,source/'windows/prepare_files.py','--apk',work/'inputs/game-9ded0797.apk','--ndk',a.ndk,'--out',data,'--aapt','/home/user/bunker-tools/android-sdk/build-tools/36.0.0/aapt'])
 old=work/'windows-files';shutil.copyfile(old/'file_traces.h',data/'file_traces.h');prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets']
 old_objects=[old/'guest'/Path(obj).name for obj in prior['objects']];old_hashes={str(f):sha(f)for f in old_objects+[old/'file-guest.so',old/'file_traces.h',old/'guest/manifest.json']}
 rf=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(work/'remill-src/include'),'-I'+wp(data),'-I'+wp(work/'zlib-native/zlib-1.3.2'),f'-DFILES_ROOT="{wp(data)}"','-DHAVE_GUEST_FILE_FIXTURE',f'-DGUEST_FILES_IMAGE="{wp(old/"file-guest.so")}"'];ro=[]
 for name in('jni_host','android_context','windows_android_id','android_assets','apk_assets'):
  obj=out/(name+'-regression.o');run([cxx,*rf,'-c',wp(source/f'windows/{name}.cpp'),'-o',wp(obj)]);ro.append(obj)
 regression=out/'filesystem-regression.exe';run([cxx,*rf,wp(source/'windows/filesystem_test.cpp'),*map(wp,ro+objects),wp(loader),*map(wp,old_objects),wp(work/'zlib-native/libz-inflate.a'),'-latomic','-pthread','-static','-ladvapi32','-o',wp(regression)])
 r=subprocess.run([str(regression)],capture_output=True,text=True,timeout=120);(out/'regression.stdout.log').write_text(r.stdout);(out/'regression.stderr.log').write_text(r.stderr);print(r.stdout,end='',flush=True);print(r.stderr,end='',file=sys.stderr,flush=True);r.check_returncode();assert old_hashes=={str(f):sha(f)for f in old_objects+[old/'file-guest.so',old/'file_traces.h',old/'guest/manifest.json']}
 result['regression']=dict(stdout=r.stdout,stderr=r.stderr,binary_sha256=sha(regression),apk_sha256=sha(data/'base.apk'),old_immutable_sha256=old_hashes);result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
