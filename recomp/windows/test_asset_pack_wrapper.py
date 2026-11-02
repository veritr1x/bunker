"""Frozen exact-APK missing-PlayCore wrapper gate; run with the WSL tools Python."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
OWNED=('android_asset_pack_wrapper.h','android_asset_pack_wrapper.cpp','asset_pack_wrapper_guest.c','asset_pack_wrapper_test.cpp','test_asset_pack_wrapper.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(command,log,**kwargs):
 with log.open('w')as f:r=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,**kwargs)
 if r.returncode:raise RuntimeError(f'{log}: exit{r.returncode}\n{log.read_text(errors="replace")[-8000:]}')
 return log.read_text(errors='replace')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',default='21b12c4');p.add_argument('--focus-only',action='store_true')
 p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));p.add_argument('--lift',type=Path,default=HERE.parent/'work/fp-fmul-indexed-linux/lifted/.toolchain/78e33b4cc37e8b2d-098d2e4b3214af9b/remill-lift');p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 commit=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip();frozen=out/'host';frozen.mkdir()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',commit,'recomp'],cwd=ROOT)))as t:t.extractall(frozen)
 src=frozen/'recomp';owned={}
 for name in OWNED:owned[name]=sha(HERE/name);shutil.copy2(HERE/name,src/'windows'/name)
 proof=HERE.parent/'work/playcore-init-audit/approved-input-profile.json';assert sha(proof)=='b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689';profile=json.loads(proof.read_text());shutil.copy2(proof,out/'approved-input-profile.json')
 assert profile['total_class_definitions']==22777 and len(profile['code_containers'])==4 and all(not c['factory_definitions']for c in profile['code_containers'])
 (out/'asset_pack_proof.h').write_text(f'constexpr const char*kAssetApkSha256="{profile["apk_sha256"]}";\nconstexpr const char*kAssetCatalogSha256="{sha(proof)}";\n')
 shutil.copy2(a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h',out/'jni.h');shutil.copy2(HERE.parent/'work/windows-files/sample.h',out/'sample.h')
 source_hashes={str(f.relative_to(src)):sha(f)for f in src.rglob('*')if f.is_file()};result={'host':commit,'owned':owned,'support_sources':source_hashes,'profile_sha256':sha(proof),'platforms':{}}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n');print(f'Frozen {commit} + {len(owned)} exact overlays',flush=True)
 ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'asset-wrapper.so';run([ndkcc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',src/'windows/asset_pack_wrapper_guest.c','-o',library],out/'ndk-build.log')
 regression=out/'jni-regression.so'
 if not a.focus_only:run([ndkcc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',src/'windows/package_guest_fixture.c','-o',regression],out/'regression-ndk-build.log')
 negatives={'--changed-apk':'complete APK code-catalog profile','--unknown-code':'complete APK code-catalog profile','--present-code':'complete APK code-catalog profile','--open-scope':'complete APK code-catalog profile','--visible-factory':'availability/class-loader profile','--path':'Java method has no host implementation','--get-instance':'Java method has no host implementation','--retired-owner':'adapter owner expired'}
 for win in (True,False):
  platform='windows'if win else'linux';build=out/platform;build.mkdir()
  def hp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()if win else str(p)
  cc='/mnt/c/mingw64/bin/gcc.exe'if win else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if win else'clang++-18'
  def lift(elf,target,base):
   run([sys.executable,src/'whole/compile.py',elf,'--out',target,'--base',base,'--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu'if win else'x86_64-linux-gnu','--cxx','clang++-18'],build/(target.name+'-lift.log'))
   m=json.loads((target/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets'];return m
  guest=build/'guest';manifest=lift(library,guest,'0x78000000');loader=build/'elfload.o';run([cc,'-O2','-c',hp(src/'fastaes/elfload.c'),'-o',hp(loader)],build/'loader-build.log')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.remill/'include'),'-I'+hp(out)]
  objects=[]
  for relative in ('windows/jni_host.cpp','windows/android_asset_pack_wrapper.cpp','whole/runtime.cpp'):
   obj=build/(Path(relative).stem+'.o');run([cxx,*flags,'-c',hp(src/relative),'-o',hp(obj)],build/(Path(relative).stem+'-build.log'));objects.append(obj)
  exe=build/('asset-wrapper.exe'if win else'asset-wrapper');run([cxx,*flags,'-I'+hp(guest),f'-DASSET_LIBRARY="{hp(library)}"',hp(src/'windows/asset_pack_wrapper_test.cpp'),*map(hp,objects),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic',*(['-static']if win else[]),'-o',hp(exe)],build/'focused-build.log')
  positive=run([exe],build/'focused.log',timeout=45);assert 'checks passed'in positive;print(platform+': '+positive.strip(),flush=True);failures={}
  for mode,needle in negatives.items():
   log=build/(mode[2:]+'.log')
   with log.open('w')as f:r=subprocess.run([str(exe),mode],stdout=f,stderr=subprocess.STDOUT,timeout=20)
   assert r.returncode and needle in log.read_text(errors='replace'),(mode,r.returncode,log.read_text(errors='replace'));failures[mode]=r.returncode
  tests={}
  if not a.focus_only:
   regdir=build/'regression-guest';regmanifest=lift(regression,regdir,'0x74000000')
   for test in ('jni_host','jni_callback_frame','jni_constructor_frame'):
    binary=build/(test+('.exe'if win else''));run([cxx,*flags,'-I'+hp(regdir),f'-DPACKAGE_IMAGE="{hp(regression)}"',hp(src/f'windows/{test}_test.cpp'),*map(hp,objects),hp(loader),*map(hp,regmanifest['objects']),'-pthread','-latomic',*(['-static']if win else[]),'-o',hp(binary)],build/(test+'-build.log'));tests[test]=run([binary],build/(test+'.log'),timeout=45).strip();print(platform+' '+tests[test],flush=True)
  result['platforms'][platform]={'positive':positive.strip(),'expected_boundaries':failures,'regressions':tests,'traces':len(manifest['traces']),'objects':len(manifest['objects']),'toolchain':manifest['toolchain'],'binary_sha256':sha(exe)};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 for name,h in owned.items():assert sha(HERE/name)==h and sha(src/'windows'/name)==h
 for name,h in source_hashes.items():assert sha(src/name)==h
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and 'host'not in f.relative_to(out).parts and f.name not in ('acceptance.json','progress.json')};result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
