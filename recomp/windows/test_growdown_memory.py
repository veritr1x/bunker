"""Native Windows opt-in growth with actual hardware/NDK faults and frozen FS regressions."""
from pathlib import Path
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
PRODUCTION=('filesystem.h','filesystem.cpp','growdown_memory.h','growdown_memory.cpp')
OWN=('growdown_memory_guest.c','growdown_memory_test.cpp','test_growdown_memory.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',default='74798fb');p.add_argument('--focus-only',action='store_true');p.add_argument('--production-from',type=Path,help='Only qualify direct production imports; verify and reuse unchanged full candidate evidence')
 p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));p.add_argument('--lift',type=Path,default=HERE.parent/'work/ushll-toolchain/fa80a8edb3f33d18-9524e65b09c51e5b/remill-lift');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);work=HERE.parent/'work';frozen=out/'host';frozen.mkdir();commit=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',commit,'recomp'],cwd=ROOT)))as t:t.extractall(frozen)
 src=frozen/'recomp';pins={}
 for n in PRODUCTION+OWN:pins[n]=sha(HERE/n);shutil.copy2(HERE/n,src/'windows'/n)
 support={str(f.relative_to(src)):sha(f)for f in src.rglob('*')if f.is_file()};result={'host':commit,'overlay':pins,'support_sources':support,'production_overlay':list(PRODUCTION),'fixture_overlay':list(OWN),'test_hooks':False,'production_game_claim':False}
 (out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n');print('Frozen '+commit+' + '+str(len(pins))+' exact overlays',flush=True)
 def run(command,log,timeout=None):
  with log.open('w')as f:r=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  text=log.read_text(errors='replace')
  if r.returncode:raise RuntimeError(f'{log}: exit{r.returncode}\n{text[-8000:]}')
  return text
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 loader=out/'elfload.o';run([cc,'-O2','-c',hp(src/'fastaes/elfload.c'),'-o',hp(loader)],out/'loader-build.log')
 flags=['-std=c++17','-static','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(work/'remill-src/include')]
 objects=[]
 for rel in('windows/filesystem.cpp','windows/growdown_memory.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');run([cxx,*flags,'-c',hp(src/rel),'-o',hp(obj)],out/(Path(rel).stem+'-build.log'));objects.append(obj)
 def fixture(names,target,base):
  so=out/(target+'.so');run([ndkcc,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',*[src/'windows'/n for n in names],'-o',so],out/(target+'-ndk.log'));guest=out/(target+'-guest')
  run([sys.executable,src/'whole/compile.py',so,'--out',guest,'--base',base,'--lift',a.lift,'--semantics-dir',a.lift.parent,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],out/(target+'-lift.log'));m=json.loads((guest/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets'];return so,guest,m
 so,guest,m=fixture(['growdown_memory_guest.c'],'growth','0x7b000000');binary=out/'growth.exe'
 run([cxx,*flags,'-Wall','-Wextra','-I'+hp(guest),f'-DGROWTH_LIBRARY="{hp(so)}"',hp(src/'windows/growdown_memory_test.cpp'),*map(hp,objects),hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-o',hp(binary)],out/'growth-link.log')
 if a.production_from:
  prior=a.production_from.resolve();accepted=json.loads((prior/'acceptance.json').read_text());assert accepted['passed']and accepted['regressions']
  for n in PRODUCTION:
   if n!='filesystem.cpp':assert pins[n]==accepted['overlay'][n]
  old=(prior/'host/recomp/windows/filesystem.cpp').read_text();new=(src/'windows/filesystem.cpp').read_text();anchor='void FileSystem::Install(recomp::Runtime &runtime) {';op,oi=old.split(anchor,1);np,ni=new.split(anchor,1)
  assert op==np.replace('#include <utility>\n','')
  old_first=oi.index('  runtime.AddImport(Marker("__errno")');new_first=ni.index('  add("__errno"')
  assert ni.startswith(oi[:old_first]);fence=ni[len(oi[:old_first]):new_first];assert 'catch(const std::exception &error)'in fence and 'catch(...)'in fence and 'std::abort()'in fence and 'std::fflush(stderr)'in fence
  after=re.sub(r'\badd\(([^,\n]+),',r'runtime.AddImport(Marker(\1),',ni[new_first:]);assert after==oi[old_first:];assert after.count('runtime.AddImport(')==30
  old_test=(prior/'host/recomp/windows/growdown_memory_test.cpp').read_text();new_test=(src/'windows/growdown_memory_test.cpp').read_text()
  restored=re.sub(r'(?m)^\s*// BEGIN PRODUCTION [^\n]*\n.*?^\s*// END PRODUCTION [^\n]*\n','\n',new_test,flags=re.S|re.M)
  for x,y in [('Guest(FileSystem &f,bool production=false)','Guest(FileSystem &f)'),('if(production){f.Install(runtime);}else{f.Install(bridges);','f.Install(bridges);'),('}runtime.AddTraces','runtime.AddTraces'),('Negative(const std::string &mode,bool production=false)','Negative(const std::string &mode)'),('Guest guest(*files,production);','Guest guest(*files);')]:restored=restored.replace(x,y)
  assert ''.join(restored.split())==''.join(old_test.split()),'new test delta extends production transport only'
  old_guest=(prior/'host/recomp/windows/growdown_memory_guest.c').read_text();new_guest=(src/'windows/growdown_memory_guest.c').read_text();assert new_guest.replace('#include <errno.h>\n','').replace('uint32_t growth_errno(void){return (uint32_t)errno;}\n','')==old_guest
  assert sha(out/'growdown_memory.o')==sha(prior/'growdown_memory.o')
  normal=run([binary,'--production-normal'],out/'production-normal.log',30);assert 'PASS production FS.Install normal transport:'in normal;print(normal.strip(),flush=True)
  native_exit=out/'native-exit.ps1';native_exit.write_text((prior/'native-exit.ps1').read_text());boundaries={}
  needles={'default-disabled':'file system mmap: unsupported mmap MAP_GROWSDOWN','partial-unmap':'file system munmap: unsupported partial munmap','partial-protect':'file system mprotect: unsupported partial mprotect','reserved-noreplace':'file system mmap: unsupported MAP_FIXED_NOREPLACE','pinned-unmap':'file system munmap: unsupported munmap of active mapping use','pinned-protect':'file system mprotect: unsupported mprotect of active mapping use'}
  for mode,needle in needles.items():
   log=out/(mode+'.log');stdout=out/(mode+'.stdout.log');status=out/(mode+'.status.json')
   run(['powershell.exe','-NoProfile','-NonInteractive','-File',hp(native_exit),'-Binary',hp(binary),'-Mode','production-'+mode,'-Stdout',hp(stdout),'-Stderr',hp(log),'-Result',hp(status)],out/(mode+'-runner.log'),30)
   code=json.loads(status.read_text(encoding='utf-8-sig'))['exit_code'];text=log.read_text(errors='replace');assert (code&0xffffffff)==0xc0000409 and needle in text,(mode,code,text);boundaries[mode]={'exit':code,'windows_status':hex(code&0xffffffff),'log_sha256':sha(log),'status_sha256':sha(status)}
  for n,h in pins.items():assert sha(HERE/n)==h and sha(src/'windows'/n)==h
  for n,h in support.items():assert sha(src/n)==h
  for n,h in accepted['evidence'].items():assert sha(prior/n)==h
  result['targeted_production_install']={'normal':normal.strip(),'boundaries':boundaries,'fixture_sha256':sha(so),'binary_sha256':sha(binary),'traces':len(m['traces']),'objects':len(m['objects']),'toolchain':m['toolchain']}
  result['reused_qualification']={'candidate':str(prior),'acceptance_sha256':sha(prior/'acceptance.json'),'focused':accepted['focused'],'regressions':accepted['regressions'],'same_helper_object_sha256':sha(out/'growdown_memory.o'),'all_preinstall_hotpaths_identical':True,'all30registration_expressions_identical':True,'fixture_existing_bodies_identical':True,'scope':'FS.Install adds fatal exception transport; test adds direct production mode and errno accessor only'}
  result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name not in('acceptance.json','progress.json')};result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS targeted '+str(out/'acceptance.json'),flush=True);return
 positive=run([binary],out/'positive.log',120);assert 'PASS real growdown:'in positive;print(positive.strip(),flush=True)
 negatives={}
 for mode,needle in {'default-disabled':'owned downward expansion is not implemented','destroy-pinned':'FileSystem destruction with active mapping use','partial-unmap':'unsupported partial munmap','partial-protect':'unsupported partial mprotect','reserved-noreplace':'reserved-only'}.items():
  log=out/(mode+'.log')
  with log.open('w')as f:r=subprocess.run([str(binary),'--'+mode],stdout=f,stderr=subprocess.STDOUT,timeout=30)
  assert r.returncode and needle in log.read_text(errors='replace'),(mode,r.returncode,log.read_text(errors='replace'));negatives[mode]={'exit':r.returncode,'log_sha256':sha(log)}
 # WSL interop truncates a Windows exception status to its low eight bits.
 # Capture ExitCode in native PowerShell, then read the full signed32 status.
 native_exit=out/'native-exit.ps1';native_exit.write_text('''param([string]$Binary,[string]$Mode,[string]$Stdout,[string]$Stderr,[string]$Result)
$ErrorActionPreference='Stop'
$child=Start-Process -FilePath $Binary -ArgumentList @('--'+$Mode) -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
$child.Refresh()
@{exit_code=$child.ExitCode} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $Result
''')
 hardware={}
 for mode in('lower-guard','limit-beyond-gap','upper-guard','ro-write','ro-growth-write','noaccess-read','foreign-fault','retired-fault','execute-fault'):
  log=out/(mode+'.log');stdout=out/(mode+'.stdout.log');status=out/(mode+'.status.json')
  run(['powershell.exe','-NoProfile','-NonInteractive','-File',hp(native_exit),'-Binary',hp(binary),'-Mode',mode,'-Stdout',hp(stdout),'-Stderr',hp(log),'-Result',hp(status)],out/(mode+'-runner.log'),30)
  code=json.loads(status.read_text(encoding='utf-8-sig'))['exit_code'];text=log.read_text(errors='replace');assert (code&0xffffffff)==0xc0000005 and 'EXPECTED native'in text,(mode,code,text);hardware[mode]={'exit':code,'windows_status':hex(code&0xffffffff),'log_sha256':sha(log),'status_sha256':sha(status)}
 budgets={}
 for mode in('active-budget','lifetime-budget'):budgets[mode]=run([binary,'--'+mode],out/(mode+'.log'),180).strip();print(budgets[mode],flush=True)
 result['focused']={'stdout':positive.strip(),'native_fault_boundaries':hardware,'named_boundaries':negatives,'budgets':budgets,'fixture_sha256':sha(so),'binary_sha256':sha(binary),'traces':len(m['traces']),'objects':len(m['objects']),'toolchain':m['toolchain']};(out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
 if not a.focus_only:
  # Run the existing actual test sources directly with the new helper. No live
  # runner dependency, mutable old output path or unpinned live Context is used.
  mapping,mg,mm=fixture(['mapping_use_guest.c'],'mapping','0x75000000');mapping_exe=out/'mapping-regression.exe'
  run([cxx,*flags,'-I'+hp(mg),f'-DMAPPING_IMAGE="{hp(mapping)}"',f'-DMAPPING_ROOT="{hp(out)}"',hp(src/'windows/mapping_use_test.cpp'),*map(hp,objects),hp(loader),*map(hp,mm['objects']),'-pthread','-latomic','-o',hp(mapping_exe)],out/'mapping-link.log');mapped=run([mapping_exe],out/'mapping-positive.log',120);print(mapped.strip(),flush=True)
  mp={}
  for mode,needle in {'guest-pinned-unmap':'unsupported munmap of active mapping use','guest-pinned-protect':'unsupported mprotect of active mapping use','destroy-pinned':'FileSystem destruction with active mapping use'}.items():
   log=out/('mapping-'+mode+'.log')
   with log.open('w')as f:r=subprocess.run([str(mapping_exe),'--'+mode],stdout=f,stderr=subprocess.STDOUT,timeout=30)
   assert r.returncode and needle in log.read_text(errors='replace');mp[mode]=r.returncode
  data=out/'filesystem-data';run([sys.executable,src/'windows/prepare_files.py','--apk',work/'inputs/game-9ded0797.apk','--ndk',a.ndk,'--out',data,'--aapt','/home/user/bunker-tools/android-sdk/build-tools/36.0.0/aapt'],out/'filesystem-data.log')
  old=work/'windows-files';shutil.copy2(old/'file_traces.h',data/'file_traces.h');prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets'];old_objects=[old/'guest'/Path(o).name for o in prior['objects']];immutable={str(f):sha(f)for f in old_objects+[old/'file-guest.so',old/'file_traces.h',old/'guest/manifest.json']}
  ff=flags+['-I'+hp(data),'-I'+hp(work/'zlib-native/zlib-1.3.2'),f'-DFILES_ROOT="{hp(data)}"','-DHAVE_GUEST_FILE_FIXTURE',f'-DGUEST_FILES_IMAGE="{hp(old/"file-guest.so")}"'];extra=[]
  for n in('jni_host','android_context','windows_android_id','android_assets','apk_assets'):
   obj=out/(n+'-regression.o');run([cxx,*ff,'-c',hp(src/f'windows/{n}.cpp'),'-o',hp(obj)],out/(n+'-regression-build.log'));extra.append(obj)
  fs_exe=out/'filesystem-regression.exe';run([cxx,*ff,hp(src/'windows/filesystem_test.cpp'),*map(hp,extra+objects),hp(loader),*map(hp,old_objects),hp(work/'zlib-native/libz-inflate.a'),'-latomic','-pthread','-ladvapi32','-o',hp(fs_exe)],out/'filesystem-link.log');fsout=run([fs_exe],out/'filesystem-positive.log',120);print(fsout.strip(),flush=True);assert immutable=={str(f):sha(Path(f))for f in immutable}
  result['regressions']={'mapping_use':{'stdout':mapped.strip(),'named_boundaries':mp,'binary_sha256':sha(mapping_exe)},'filesystem':{'stdout':fsout.strip(),'binary_sha256':sha(fs_exe),'immutable_old_inputs':immutable}}
 for n,h in pins.items():assert sha(HERE/n)==h and sha(src/'windows'/n)==h
 for n,h in support.items():assert sha(src/n)==h
 result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name not in('acceptance.json','progress.json')};result['passed']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
