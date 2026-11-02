"""Recognize valid ARM64 MAP_GROWSDOWN and stop at an honest unsupported boundary."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OWNED=('filesystem.h','filesystem.cpp','growdown_memory.h','growdown_memory.cpp','mmap_growdown_guest.c','mmap_growdown_test.cpp','test_mmap_growdown.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,log,**kwargs):
 with log.open('w')as f:r=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,**kwargs)
 if r.returncode:raise RuntimeError(str(log)+': '+log.read_text(errors='replace')[-8000:])
 return log.read_text(errors='replace')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',default='944a091');p.add_argument('--regression-from',type=Path,help='Reuse the passed prior regressions only for the exact growth-only zero-NOREPLACE correction');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));p.add_argument('--lift',type=Path,default=HERE.parent/'work/fp-fmul-indexed-linux/lifted/.toolchain/78e33b4cc37e8b2d-098d2e4b3214af9b/remill-lift');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);commit=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip();frozen=out/'host';frozen.mkdir()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',commit,'recomp'],cwd=ROOT)))as t:t.extractall(frozen)
 src=frozen/'recomp';owned={}
 for name in OWNED:owned[name]=sha(HERE/name);shutil.copy2(HERE/name,src/'windows'/name)
 support={str(f.relative_to(src)):sha(f)for f in src.rglob('*')if f.is_file()};result={'host':commit,'owned':owned,'support_sources':support};(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n');print('Frozen '+commit,flush=True)
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'growdown.so';run([cc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',src/'windows/mmap_growdown_guest.c','-o',library],out/'ndk-build.log');guest=out/'guest';run([sys.executable,src/'whole/compile.py',library,'--out',guest,'--base','0x7a000000','--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],out/'lift.log');m=json.loads((guest/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 def hp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 loader=out/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(src/'fastaes/elfload.c'),'-o',hp(loader)],out/'loader-build.log');binary=out/'growdown.exe';run(['/mnt/c/mingw64/bin/g++.exe','-std=c++17','-static','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(HERE.parent/'work/remill-src/include'),'-I'+hp(guest),f'-DGROWDOWN_IMAGE="{hp(library)}"',f'-DGROWDOWN_ROOT="{hp(out)}"',*[hp(src/x)for x in('windows/mmap_growdown_test.cpp','windows/filesystem.cpp','windows/growdown_memory.cpp','whole/runtime.cpp')],hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-o',hp(binary)],out/'host-build.log');positive=run([binary],out/'focused.log',timeout=30);assert 'checks passed'in positive;print(positive,flush=True)
 boundaries={}
 for mode in('original','zero-noreplace'):
  log=out/(mode+'-request.log')
  with log.open('w')as f:r=subprocess.run([str(binary),'--guest-'+mode],stdout=f,stderr=subprocess.STDOUT,timeout=30)
  assert r.returncode and 'MAP_GROWSDOWN: owned downward expansion is not implemented'in log.read_text(errors='replace');boundaries[mode]=r.returncode
 result['focused']={'stdout':positive.strip(),'actual_ndk_boundaries':boundaries,'binary_sha256':sha(binary),'traces':len(m['traces']),'objects':len(m['objects']),'toolchain':m['toolchain']}
 # The accepted canonical runner uses frozen support plus exactly FS h/cpp and
 # its unchanged mapping fixture overlay; old data/object inputs stay read-only.
 regression_inputs={}
 if a.regression_from:
  prior=a.regression_from.resolve();acceptance=prior/'acceptance.json';accepted=json.loads(acceptance.read_text());assert accepted['passed']and accepted['mapping_regression']['passed']
  old=(prior/'host/recomp/windows/filesystem.cpp').read_text();new=(src/'windows/filesystem.cpp').read_text();before='((flags & linux_flags::map_fixed_no_replace) && (!address || address % kPage))';after='((flags & linux_flags::map_fixed_no_replace) && address % kPage)';assert old.count(before)==1 and old.replace(before,after)==new
  assert owned['filesystem.h']==accepted['owned']['filesystem.h']
  result['regression_reuse']={'prior_candidate':str(prior),'acceptance_sha256':sha(acceptance),'executed_prior_cpp_sha256':accepted['owned']['filesystem.cpp'],'reason':'Exact sole provider delta removes zero from growth-only malformed NOREPLACE classification; ordinary mmap and MappingUse paths unchanged. These are prior executions, not new candidate executions.'}
 else:
  regression_inputs={n:sha(HERE/n)for n in('test_mapping_use.py','mapping_use_guest.c','mapping_use_test.cpp')};regression=out/'mapping-regression';text=run([sys.executable,HERE/'test_mapping_use.py','--ndk',a.ndk,'--lift',a.lift,'--semantics-dir',a.lift.parent,'--support-source',src,'--out',regression],out/'regressions.log',timeout=240);print(text[-1800:],flush=True)
  accepted=json.loads((regression/'acceptance.json').read_text());assert accepted['passed'];result['mapping_regression']=accepted;result['regression_inputs']=regression_inputs
  for name in('filesystem.h','filesystem.cpp'):assert sha(regression/'source/windows'/name)==owned[name]
 for name,h in owned.items():assert sha(HERE/name)==h and sha(src/'windows'/name)==h
 for name,h in regression_inputs.items():assert sha(HERE/name)==h
 for name,h in support.items():assert sha(src/name)==h
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name!='acceptance.json'};result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
