"""Modern NDK phdr iteration and retained genuine original FDE lookup, Windows only."""
import argparse,concurrent.futures,hashlib,io,json,re,shutil,subprocess,sys,tarfile,threading,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('dl_iterate_phdr_guest.c','dl_iterate_phdr_test.cpp','test_dl_iterate_phdr.py')
PROOF='de64c04590d872dd978b0ef48f41ed0d501a09c097e1309632a538c1b0a168e2'
EXTRACTION='e5af35c48aaf82d6f54cefe06e4abe51b75c7ecbc98280940a889b2350d7ff77'
AUDIT='5584ff03184dae76a459629c6b8f037a181f9b453d052e234aa4b198168af0ff'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--guest-sha',required=True);p.add_argument('--fixture-sha',required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 commands=[];pins={};lock=threading.Lock()
 def pin(path,expected=None):
  path=Path(path).resolve();value=sha(path);assert expected is None or value==expected,str(path);pins[str(path)]=value;return value
 def run(label,cmd):
  cmd=list(map(str,cmd))
  with lock:commands.append(dict(label=label,argv=cmd));save(out/'commands.json',commands)
  print('STAGE '+label,flush=True)
  with(out/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  text=(out/(label+'.log')).read_text(errors='replace')
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-6000:])
  return dict(exit_code=r.returncode,stdout=text)
 try:
  pin(HERE/'dl_iterate_phdr_guest.c',a.guest_sha);pin(HERE/'dl_iterate_phdr_test.cpp',a.fixture_sha)
  proofpath=W/'phdr-iteration-preparation1/source-proof.json';pin(proofpath,PROOF);proof=read(proofpath);assert proof['passed']is True
  extraction=W/'original-phdr-callback-extract5/acceptance.json';pin(extraction,EXTRACTION);extracted=read(extraction);assert extracted['passed']is True
  for path,h in extracted['evidence'].items():pin(path,h)
  audit=W/'worker-futex1-phdr-boundary1/acceptance.json';pin(audit,AUDIT);assert read(audit)['passed']is True
  base=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'rev-parse','HEAD'],text=True).strip()
  archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',base,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
  with tarfile.open(fileobj=io.BytesIO(archive))as t:assert t.pax_headers['comment']==base;t.extractall(out/'source',filter='data')
  source=out/'source/recomp'
  for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
  for name,h in proof['owned_sources'].items():pin(HERE.parent/name,h);shutil.copyfile(HERE.parent/name,source/name)
  owned={'windows/'+name:sha(source/'windows'/name)for name in OWN};production={name:sha(source/name)for name in proof['owned_sources']};assert production==proof['owned_sources']
  sources={f.relative_to(source).as_posix():sha(f)for f in source.rglob('*')if f.is_file()};save(out/'source-hashes.json',sources)
  for n in OWN:assert b'\r'not in(source/'windows'/n).read_bytes(),n
  for module,h in [('libunity.so','3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'),('libil2cpp.so','ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522')]:
   original=W/'windows-first-frame-worker-futex1/native'/module;pin(original,h);shutil.copyfile(original,out/module);pin(out/module,h)
  extractdir=extraction.parent
  for name in('original-phdr-expectations.h','original-phdr-heads.h'):shutil.copyfile(extractdir/name,out/name)
  shutil.copyfile(extractdir/'windows.o',out/'original-callback.o')
  tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4';ndkroot=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64');ndk=ndkroot/'bin/aarch64-linux-android24-clang';cxx='/mnt/c/mingw64/bin/g++.exe';cc='/mnt/c/mingw64/bin/gcc.exe'
  for f in(ndk.resolve(),ndkroot/'sysroot/usr/include/link.h',tool/'remill-lift',tool/'aarch64.bc',Path(cxx),Path(cc),Path('/usr/bin/clang++-18').resolve()):pin(f)
  for f in(tool/'include').rglob('*'):
   if f.is_file():pin(f)
  lib=out/'phdr.so';run('NDK-strict-build',[ndk,'-Wall','-Wextra','-Werror','-O1','-shared','-nostdlib','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/dl_iterate_phdr_guest.c','-o',lib]);pin(lib)
  guest=out/'guest';run('translate',[sys.executable,source/'whole/compile.py',lib,'--out',guest,'--base','0x76000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'])
  manifest=read(guest/'manifest.json');assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(guest),'-I'+wp(out),'-DSAMPLE_IMAGE="'+wp(lib)+'"','-DUNITY_IMAGE="'+wp(out/'libunity.so')+'"','-DIL2CPP_IMAGE="'+wp(out/'libil2cpp.so')+'"']
  run('strict-fixture-provider-syntax',[cxx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',wp(source/'windows/dl_iterate_phdr_test.cpp'),wp(source/'windows/module_registry.cpp'),wp(source/'windows/module_registry_elf.cpp')])
  common=[];objects={};jobs=[]
  for name in('windows/module_registry.cpp','windows/module_registry_elf.cpp','windows/pthread_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'):
   obj=out/(Path(name).stem+'.o');common.append(obj);objects[name]=obj;jobs.append((Path(name).stem,[cxx,*opts,'-c',wp(source/name),'-o',wp(obj)]))
  loader=out/'elfload.o';jobs.append(('elfload',[cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)]))
  with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
   futures=[pool.submit(run,label,cmd)for label,cmd in jobs]
   for f in futures:f.result()
  exe=out/'dl-iterate-phdr.exe';run('link',[cxx,*opts,'-Wall','-Wextra','-Werror',wp(source/'windows/dl_iterate_phdr_test.cpp'),*map(wp,common),wp(loader),wp(out/'original-callback.o'),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-ladvapi32','-o',wp(exe)])
  result=run('focused',[exe]);match=re.search(r'DL-ITERATE-PHDR-PASS checks=(\d+) ndk_calls=(\d+) callbacks=(\d+) genuine_queries=(\d+) mutations=(\d+)',result['stdout']);assert match,result['stdout']
  result.update(zip(('checks','ndk_calls','callbacks','genuine_queries','mutations'),map(int,match.groups())));result['binary_sha256']=sha(exe)
  unit=out/'module-registry-unit.exe';run('unit-link',[cxx,*opts,wp(source/'windows/module_registry_test.cpp'),wp(objects['windows/module_registry.cpp']),wp(objects['whole/runtime.cpp']),'-static','-pthread','-latomic','-o',wp(unit)]);unitresult=run('module-registry-unit',[unit]);unitresult['checks']=int(re.search(r'(\d+) checks passed',unitresult['stdout'])[1]);unitresult['binary_sha256']=sha(unit)
  # Recompile the retained dladdr harness against these new loader sources but
  # reuse its original NDK caller/library/fixtures and native reference records.
  prior=W/'module-dladdr6';pin(prior/'acceptance.json');previous=read(prior/'acceptance.json');assert previous['passed']is True
  pin(prior/'windows/guest/manifest.json');old=read(prior/'windows/guest/manifest.json');assert not old['unsupported_traces']and not old['unresolved_direct_targets']
  for f in[prior/'caller.so',prior/'sysv.so',prior/'gnu.so',prior/'windows/guest/traces.h',*map(Path,old['objects'])]:pin(f)
  assert sha(source/'windows/module_dladdr_test.cpp')==previous['overlays']['windows/module_dladdr_test.cpp']
  oldopts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(prior/'windows/guest'),'-DCALLER_LIBRARY="'+wp(prior/'caller.so')+'"','-DSYSV_LIBRARY="'+wp(prior/'sysv.so')+'"','-DGNU_LIBRARY="'+wp(prior/'gnu.so')+'"','-DUNITY_LIBRARY="'+wp(out/'libunity.so')+'"','-DIL2CPP_LIBRARY="'+wp(out/'libil2cpp.so')+'"']
  oldexe=out/'retained-dladdr.exe';run('retained-dladdr-link',[cxx,*oldopts,'-Wall','-Wextra','-Werror',wp(source/'windows/module_dladdr_test.cpp'),wp(objects['windows/module_registry.cpp']),wp(objects['windows/module_registry_elf.cpp']),wp(objects['whole/runtime.cpp']),wp(loader),*map(wp,old['objects']),'-static','-pthread','-latomic','-o',wp(oldexe)]);oldresult=run('retained-dladdr',[oldexe]);oldresult['checks']=int(re.search(r'DLADDR-SUCCESS checks=(\d+)',oldresult['stdout'])[1]);oldresult['binary_sha256']=sha(oldexe)
  rows=lambda text:[s for s in text.splitlines()if s.startswith('reference-')]
  assert rows(oldresult['stdout'])==rows(previous['platforms']['windows']['stdout'])
  for name,h in sources.items():assert sha(source/name)==h,name
  for name,h in owned.items():assert sha(HERE.parent/name)==h,name
  for name,h in production.items():assert sha(HERE.parent/name)==h,name
  for path,h in pins.items():assert sha(path)==h,path
  receipt=dict(passed=True,scope='Actual Windows translated NDK modern64 iteration plus retained genuine original unwinder callback over both original mapped ELFs, with independent FDE expectations. No game launch.',owned_sources=owned,production_sources=production,source_proof=dict(path=str(proofpath),sha256=PROOF),original_extraction=dict(path=str(extraction),sha256=EXTRACTION),original_boundary_audit=dict(path=str(audit),sha256=AUDIT),results={'windows':result},regressions={'module_registry':unitresult,'retained_dladdr':oldresult},manifest=dict(path=str(guest/'manifest.json'),sha256=sha(guest/'manifest.json'),traces=len(manifest['traces']),unsupported=0,unresolved=0),retained_dladdr_reference=dict(path=str(prior/'acceptance.json'),sha256=sha(prior/'acceptance.json'),no_old_guest_relift=True),support_sources=sources,inputs=pins,limits='Original ELF mappings/import relocations are data-only TEST mappings, with no original constructors or game execution. The real original FDE callback and its selected helper closure execute; metadata recording/mutations/lifecycle are explicit fixture callbacks. Only no-PT_TLS modules admitted, unsupported TLS/catalog paths fail closed. Counters cover registered guest ELF generations, not host PE or unrepresented system modules.')
  receipt['evidence']={f.relative_to(out).as_posix():sha(f)for f in out.rglob('*')if f.is_file()and f.name!='acceptance.json'};save(out/'acceptance.json',receipt);print('DL-ITERATE-PHDR-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
