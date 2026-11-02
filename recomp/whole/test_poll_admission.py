"""Immutable admission/defer checks and unchanged cooperative-poll regressions."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('poll_admission_test.cpp','poll_admission_guest.S','test_poll_admission.py','poll_admission.md')
PRODUCTION=('cooperative_poll.h','cooperative_poll.cpp','cooperative_poll.md')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('out','toolchain'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--support-commit',default='0f5c574');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 root=HERE.parent.parent;native_root=subprocess.check_output(['wslpath','-m',str(root)],text=True).strip();git=['git.exe','-C',native_root];commit=subprocess.check_output([*git,'rev-parse',a.support_commit],text=True).strip();archive=subprocess.check_output([*git,'archive',commit,'recomp/whole','recomp/windows','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';overlays={}
 for name in OWN+PRODUCTION:overlays[name]=sha(HERE/name);shutil.copy2(HERE/name,source/'whole'/name)
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()};result={'passed':False,'support_commit':commit,'overlays':overlays,'source_pins':pins,'tool_pins':tools,'support_archive_sha256':sha(out/'support.tar')};(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 def run(cmd,name,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text(errors="replace")[-6000:]}')
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';external={str(x.resolve()):sha(x.resolve())for x in(ndk,Path('/usr/bin/clang++-18'),Path('/usr/bin/clang-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))}
 for tool in external:run([tool,'--version'],Path(tool).name+'-version.log')
 instrument=out/'poll-instrument';run([sys.executable,source/'whole/build_poll_instrument.py','--out',instrument],'instrument-build.log');library=out/'admission.so';run([ndk,'-shared','-nostdlib','-fPIC','-Wall','-Wextra','-Werror',source/'whole/poll_admission_guest.S','-o',library],'ndk-build.log')
 platforms={}
 for windows in(False,True):
  label='windows'if windows else'linux';build=out/label;path=wp if windows else str;run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x59000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--poll-instrument',instrument,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],label+'-compile.log')
  manifest=json.loads((build/'manifest.json').read_text());assert manifest['cooperative_polls']and not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(source/'whole'),'-I'+path(source/'fastaes'),'-I'+path(build),f'-DADMISSION_LIBRARY="{path(library)}"'];loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');objects=[]
  for filename,new in(('whole/runtime.cpp',False),('whole/cooperative_poll.cpp',False),('windows/module_registry.cpp',False),('whole/poll_admission_test.cpp',True)):
   obj=build/(Path(filename).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if new else[]),'-c',path(source/filename),'-o',path(obj)],label+'-'+Path(filename).stem+'-build.log');objects.append(obj)
  binary=build/('admission.exe'if windows else'admission');run([cxx,*map(path,objects),path(loader),*map(path,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',path(binary)],label+'-link.log');run([binary],label+'-focused.log',45);text=(out/(label+'-focused.log')).read_text();assert'POLL-ADMISSION-SUCCESS 'in text and'exclusive_profiles=2 registry_phases=2'in text
  print(label+' admission focused PASS',flush=True);platforms[label]={'focused_stdout':text.strip(),'binary_sha256':sha(binary),'traces':len(manifest['traces']),'objects':len(manifest['objects']),'instrument_sha256':sha(instrument),'toolchain':manifest['toolchain']}
  (out/'progress.json').write_text(json.dumps({'passed':False,'focused':platforms},indent=2)+'\n')
 # The unchanged older runner has no --semantics-dir argument. Give its
 # existing discovery rule a private legacy layout of exact immutable bytes.
 legacy=out/'legacy-tool-layout';legacy_lift=legacy/'prefix/bin/remill-lift';legacy_semantics=legacy/'lib/Arch/AArch64/Runtime/aarch64.bc';legacy_lift.parent.mkdir(parents=True);legacy_semantics.parent.mkdir(parents=True);shutil.copy2(a.toolchain/'remill-lift',legacy_lift);shutil.copy2(a.toolchain/'aarch64.bc',legacy_semantics);assert sha(legacy_lift)==sha(a.toolchain/'remill-lift')and sha(legacy_semantics)==sha(a.toolchain/'aarch64.bc')
 # These unchanged runners write only under this NEW copied support tree.
 for windows in(False,True):
  label='windows'if windows else'linux';command=[sys.executable,source/'whole/test_cooperative_poll.py','--lift',legacy_lift,'--remill',a.toolchain,*(['--windows']if windows else[])];run(command,label+'-old-regression.log',180);text=(out/(label+'-old-regression.log')).read_text();assert'Integrated cooperative polling:'in text and'260 same-thread pauses'in text and'Opt-in compiler/runtime LLVM18'in text;platforms[label]['old_regression_stdout']=text.strip();print(label+' existing cooperative poll PASS',flush=True)
 for name,pin in overlays.items():assert sha(HERE/name)==pin and sha(source/'whole'/name)==pin
 for name,pin in{**pins,**tools,**external}.items():assert sha(name)==pin
 result.update({'passed':True,'platforms':platforms,'instrument_sha256':sha(instrument),'fixture_sha256':sha(library),'external_tools':external,'limits':'Generic admission/defer policy only; no production-provider root safety, original collector handlers or GC claim'})
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and('host'not in f.relative_to(out).parts or'/work/'in str(f.relative_to(out)))and f.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('POLL-ADMISSION-ALL-HOSTS-SUCCESS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
