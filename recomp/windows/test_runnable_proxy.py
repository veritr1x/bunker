"""Freeze the exact Runnable singleton proxy and unchanged three profile regressions."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
OWN=('jni_interface_proxy.h','jni_interface_proxy.cpp','runnable_proxy_guest.c','runnable_proxy_test.cpp','test_runnable_proxy.py')

def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',default='3c7309a7df49c19e2333b1f3d6ccc88be3f8e8f3')
 for name,default in [('ndk','/home/sattam/bunker-tools/android-sdk/ndk/27.2.12479018'),('lift',HERE.parent/'work/ushll-toolchain/fa80a8edb3f33d18-9524e65b09c51e5b/remill-lift')]:p.add_argument('--'+name,type=Path,default=default)
 a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Preserve prior candidates';out.mkdir(parents=True);work=HERE.parent/'work';source=out/'source';host=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',host],cwd=ROOT)))as t:t.extractall(source)
 windows=source/'recomp/windows';whole=source/'recomp/whole';overlay={}
 for name in OWN:overlay[name]=sha(HERE/name);shutil.copyfile(HERE/name,windows/name)
 result={'host':host,'owned_overlay':overlay,'source_sha256':{str(f.relative_to(source)):sha(f)for d in('windows','whole','fastaes')for f in(source/'recomp'/d).iterdir()if f.is_file()and f.suffix in('.h','.c','.cpp','.inc','.py')},'platforms':{}}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n');print('Frozen '+host+' + '+str(len(OWN))+' owned files',flush=True)
 def run(command,log,**kw):
  with log.open('w')as f:r=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,**kw)
  if r.returncode:raise RuntimeError(str(log)+'\n'+log.read_text(errors='replace')[-8000:])
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 native_exit=out/'native-exit.ps1';native_exit.write_text('''param([string]$Binary,[string]$Mode,[string]$Stdout,[string]$Stderr,[string]$Result)
$ErrorActionPreference='Stop'
$child=Start-Process -FilePath $Binary -ArgumentList @($Mode) -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
$child.Refresh()
@{exit_code=$child.ExitCode} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $Result
''')
 for name in('sample.h','jni.h'):shutil.copyfile(work/'java-init-candidate4'/name,out/name)
 fixture=out/'runnable-proxy.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[windows/n for n in('package_guest_fixture.c','jni_interface_proxy_guest.c','audio_focus_proxy_guest.c','location_proxy_guest.c','runnable_proxy_guest.c')],'-o',fixture],out/'ndk-build.log')
 result['fixture_sha256']=sha(fixture);result['generated_headers']={n:sha(out/n)for n in('sample.h','jni.h')}
 service_failures={'--wrong-profile':'unsupported loader/interface profile','--null-list':'unsupported loader/interface profile','--duplicate-profile':'unsupported loader/interface profile','--null-interface':'unsupported loader/interface profile','--active-service':'active ServiceConnection callback is unsupported','--active-toString':'Object callback is unsupported: toString','--active-equals':'Object callback is unsupported: equals','--active-hashCode':'unsupported JNIEnv slot 49','--wrong-disable':'proxy metadata/reference operation failed','--enabled-unload':'remains enabled before unload'}
 focus_failures={**{f'--active-focus-{n}':'active audio-focus callback is unsupported'for n in range(3)},'--mixed-profile':'unsupported loader/interface profile','--duplicate-focus':'unsupported loader/interface profile','--enabled-focus-unload':'remains enabled before unload'}
 location_failures={**{f'--active-{method}-{form}':'active location callback is unsupported'for method in range(6)for form in range(3)},'--mixed-service':'unsupported loader/interface profile','--mixed-audio':'unsupported loader/interface profile','--duplicate-location':'unsupported loader/interface profile','--enabled-location-unload':'remains enabled before unload'}
 runnable_failures={**{f'--active-{form}-{interface}':'active Runnable callback is unsupported: run()V'for form in range(3)for interface in range(2)},**{f'--mixed-{n}':'unsupported loader/interface profile'for n in range(3)},'--duplicate-runnable':'unsupported loader/interface profile','--enabled-unload':'remains enabled before unload','--retired-enabled':'retired while enabled','--expired-owner':'adapter owner expired','--object-0':'Object callback is unsupported: toString','--object-1':'Object callback is unsupported: equals','--object-2':'unsupported JNIEnv slot 49'}
 for win in(True,False):
  label='windows'if win else'linux';build=out/label;build.mkdir();guest=build/'guest';path=wp if win else str
  run([sys.executable,whole/'compile.py',fixture,'--out',guest,'--base','0x74000000','--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu'if win else'x86_64-linux-gnu','--cxx','clang++-18'],build/'lift.log')
  manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if win else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if win else'clang++-18';loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'recomp/fastaes/elfload.c'),'-o',path(loader)],build/'loader.log')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(work/'remill-src/include'),'-I'+path(out),'-I'+path(guest),'-I'+path(work/'zlib-native/zlib-1.3.2'),f'-DPACKAGE_IMAGE="{path(fixture)}"'];objects=[]
  for rel in('windows/jni_host.cpp','windows/android_context.cpp','windows/windows_android_id.cpp','windows/jni_interface_proxy.cpp','windows/android_assets.cpp','windows/apk_assets.cpp','whole/runtime.cpp'):
   obj=build/(Path(rel).stem+'.o');run([cxx,*flags,'-c',path(source/'recomp'/rel),'-o',path(obj)],build/(Path(rel).stem+'-build.log'));objects.append(obj)
  tests={};backend=work/('zlib-native/libz-inflate.a'if win else'zlib-linux/backend/libz-inflate.a')
  for test,failures in(('runnable_proxy',runnable_failures),('jni_interface_proxy',service_failures),('audio_focus_proxy',focus_failures),('location_proxy',location_failures)):
   exe=build/(test+('.exe'if win else''));run([cxx,*flags,'-Wall','-Wextra',*(['-Werror']if test=='runnable_proxy'else[]),path(windows/(test+'_test.cpp')),*map(path,objects),path(loader),*map(path,manifest['objects']),path(backend),'-latomic','-pthread',*(['-static','-ladvapi32']if win else[]),'-o',path(exe)],build/(test+'-link.log'))
   log=build/(test+'.log');run([exe],log,timeout=90);text=log.read_text();print(label+' '+test+': positive passed',flush=True);tests[test]={'binary_sha256':sha(exe),'log_sha256':sha(log),'stdout':text,'explicit_failures':{}}
   for arg,message in failures.items():
    log=build/(test+arg+'.log')
    if win:
     stdout=build/(test+arg+'.stdout.log');status=build/(test+arg+'.status.json');run(['powershell.exe','-NoProfile','-NonInteractive','-File',wp(native_exit),'-Binary',wp(exe),'-Mode',arg,'-Stdout',wp(stdout),'-Stderr',wp(log),'-Result',wp(status)],build/(test+arg+'-runner.log'),timeout=90)
     code=json.loads(status.read_text(encoding='utf-8-sig'))['exit_code'];stderr=log.read_text(errors='replace');entry={'returncode':code,'windows_status':hex(code&0xffffffff),'status_sha256':sha(status),'stdout_sha256':sha(stdout)}
    else:
     failed=subprocess.run([str(exe),arg],capture_output=True,text=True,timeout=30);log.write_text(failed.stdout+failed.stderr);code=failed.returncode;stderr=failed.stderr;entry={'returncode':code}
    assert code!=0 and message in stderr,(arg,code,stderr);tests[test]['explicit_failures'][arg]={**entry,'stderr':stderr,'log_sha256':sha(log)}
    result['platforms'][label]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'tests':tests};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
   result['platforms'][label]={'traces':len(manifest['traces']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],'toolchain':manifest['toolchain'],'tests':tests};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 for name,expected in overlay.items():assert sha(HERE/name)==expected and sha(windows/name)==expected
 for name,expected in result['source_sha256'].items():assert sha(source/name)==expected
 result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
