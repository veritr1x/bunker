"""Optional futex dispatcher, exact default projection and retained native references."""
import argparse,concurrent.futures,difflib,hashlib,io,json,re,shutil,subprocess,tarfile,threading,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('futex_dispatcher_test.cpp','test_futex_dispatcher.py')
CORE=('windows/signal_futex.h','windows/signal_futex.cpp')
OLD={'windows/signal_futex.h':'60f48b313475c0129fbb9bef197869ab7fe8a24435488ce52be628d22727f7b5','windows/signal_futex.cpp':'16ca0a9bdceb3b5bb61c13f3211c03c8f85f64a897430ea3d1cdc58a957aa1e9'}
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 commands=[];pins={};lock=threading.Lock()
 def pin(p,h=None):
  p=Path(p).resolve();value=sha(p);assert h is None or value==h,str(p);pins[str(p)]=value;return value
 def run(label,cmd):
  cmd=list(map(str,cmd))
  with lock:commands.append({'label':label,'argv':cmd});save(out/'commands.json',commands)
  print('STAGE '+label,flush=True)
  with(out/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
  text=(out/(label+'.log')).read_text(errors='replace')
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-6000:])
  return {'exit_code':r.returncode,'stdout':text}
 try:
  base=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'rev-parse','HEAD'],text=True).strip()
  archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',base,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
  with tarfile.open(fileobj=io.BytesIO(archive))as t:assert t.pax_headers['comment']==base;t.extractall(out/'source',filter='data')
  source=out/'source/recomp'
  for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
  for name in CORE:shutil.copyfile(HERE.parent/name,source/name)
  owned={'windows/'+n:sha(source/'windows'/n)for n in OWN};core={n:sha(source/n)for n in CORE}
  prep=W/'futex-dispatcher-preparation1';files={}
  for name in CORE:
   oldpath=prep/('old-'+Path(name).name);pin(oldpath,OLD[name]);old=oldpath.read_bytes();new=(source/name).read_bytes();ops=[]
   for tag,i,j,k,l in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
    if tag!='equal':ops.append(dict(old_offset=i,new_offset=k,old_hex=old[i:j].hex(),new_hex=new[k:l].hex()))
   restored=new
   for op in reversed(ops):
    off=op['new_offset'];chunk=bytes.fromhex(op['new_hex']);assert restored[off:off+len(chunk)]==chunk;restored=restored[:off]+bytes.fromhex(op['old_hex'])+restored[off+len(chunk):]
   assert restored==old
   files[name]=dict(old_sha256=OLD[name],new_sha256=core[name],operations=ops,exact_whole_file_inverse=True)
  oldcpp=(prep/'old-signal_futex.cpp').read_text();newcpp=(source/'windows/signal_futex.cpp').read_text()
  # Complete existing wait bodies project by exactly the two callee-token edits.
  def body(s,start,end):return s[s.index(start):s.index(end,s.index(start))]
  wait_methods=(' int64_t TimedWait(',' int64_t Wait(')
  timed_old=body(oldcpp,wait_methods[0],wait_methods[1]);timed_new=body(newcpp,wait_methods[0],wait_methods[1])
  untimed_old=body(oldcpp,wait_methods[1],'\n};');untimed_new=body(newcpp,wait_methods[1],'\n};')
  for old,new in ((timed_old,timed_new),(untimed_old,untimed_new)):
   assert new.count('const auto result=Dispatch(token,allowed,')==1
   assert new.replace('const auto result=Dispatch(token,allowed,','const auto result=signals.DispatchOneAdmitted(token,allowed,')==old
  proof=dict(passed=True,scope='Optional dispatcher routing only; exact complete wait-method projection and whole-source inverse. No runtime admission claim.',base_core_sources=OLD,core_sources=core,files=files,timed_wait_body_preserved_except_dispatch_callee=True,untimed_wait_body_preserved_except_dispatch_callee=True,default_dispatch='signals.DispatchOneAdmitted(token,allowed,wrapped)',wrapped_boundary_not_raw_boundary=True)
  proofpath=prep/'source-proof.json'
  if proofpath.exists():assert read(proofpath)==proof
  else:save(proofpath,proof)
  proofsha=pin(proofpath)
  prior=W/'futex-timed-fixture1/qualification2';old=W/'futex-fixture1/qualification3'
  pin(prior/'acceptance.json','bd680027ad0578d98b491001930e2afd1a1786b63faf3a90f477352e8a517c64');native=read(prior/'acceptance.json');assert native['passed']and native['core_sources']==OLD
  pin(old/'acceptance.json','3d1bd842e61a88dd162b3a59e454ea3a7e8e921b99bcd0f94bc9b900a90f87ac');untimed=read(old/'acceptance.json');assert untimed['passed']
  for name,h in native['fixture_sources'].items():assert sha(source/'windows'/name)==h,name
  for name,h in native['untimed_fixture_sources'].items():assert sha(source/'windows'/name)==h,name
  for f in ('arm64-reference.log','source-pin.json'):pin(prior/f)
  pin(old/'futex.so');tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4'
  for f in(tool/'include').rglob('*'):
   if f.is_file():pin(f)
  for c in('/mnt/c/mingw64/bin/g++.exe','/mnt/c/mingw64/bin/gcc.exe','/usr/bin/clang++-18','/usr/bin/clang-18'):pin(Path(c).resolve())
  sources={f.relative_to(source).as_posix():sha(f)for f in source.rglob('*')if f.is_file()};save(out/'source-hashes.json',sources)
  for name in OWN:assert b'\r'not in(source/'windows'/name).read_bytes(),name
  platforms={}
  for windows in(True,False):
   label='windows'if windows else'linux';D=out/label;D.mkdir();convert=wp if windows else str;cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
   guest=old/label/'guest';m=read(guest/'manifest.json');assert not m['unsupported_traces']and not m['unresolved_direct_targets']
   for f in[guest/'manifest.json',guest/'traces.h',*map(Path,m['objects'])]:pin(f)
   opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',convert(tool/'include'),'-I'+convert(guest),'-DFUTEX_LIBRARY="'+convert(old/'futex.so')+'"']
   run(label+'-strict-syntax',[cxx,*opts,'-Wall','-Wextra','-Werror','-fsyntax-only',convert(source/'windows/futex_dispatcher_test.cpp'),convert(source/'windows/signal_futex.cpp')])
   common=[];jobs=[]
   for rel in('whole/runtime.cpp','whole/signal_frame.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_futex.cpp'):
    obj=D/(Path(rel).stem+'.o');common.append(obj);jobs.append((label+'-'+obj.stem,[cxx,*opts,'-c',convert(source/rel),'-o',convert(obj)]))
   loader=D/'elfload.o';jobs.append((label+'-loader',[cc,'-O2','-c',convert(source/'fastaes/elfload.c'),'-o',convert(loader)]))
   with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
    futures=[pool.submit(run,n,c)for n,c in jobs]
    for f in futures:f.result()
   results={}
   for stem in('futex_dispatcher_test','futex_timed_test'):
    exe=D/(stem+('.exe'if windows else''));extra=[]if stem=='futex_dispatcher_test'else[loader,*map(Path,m['objects'])]
    run(label+'-'+stem+'-link',[cxx,*opts,'-Wall','-Wextra','-Werror',convert(source/'windows'/(stem+'.cpp')),*map(convert,common),*map(convert,extra),'-pthread','-latomic',*(['-static']if windows else[]),'-o',convert(exe)])
    result=run(label+'-'+stem,[exe]);result['binary_sha256']=sha(exe);results[stem]=result
   new=results['futex_dispatcher_test'];new['checks']=int(re.search(r'FUTEX-DISPATCHER-PASS checks=(\d+) cases=12',new['stdout'])[1])
   text=results['futex_timed_test']['stdout'];u=[s for s in text.splitlines()if s.startswith(('PROBE ','GROUP ','RACES ','SIGNAL '))];t=[s for s in text.splitlines()if s.startswith(('TIMED ','TIMED-DEADLINE ','TIMED-WAKE ','TIMED-LONGWAKE ','TIMED-SIGNAL ','TIMED-OVERRUN '))]
   assert u==untimed['canonical_records']and len(u)==23
   assert t==native['canonical_records']and len(t)==38
   results['futex_timed_test'].update(untimed_records=u,timed_records=t,checks=int(re.search(r'FUTEX-TIMED-HOST-SUCCESS records=38 checks=(\d+)',text)[1]))
   platforms[label]=results;save(out/'progress.json',platforms)
  for name,h in sources.items():assert sha(source/name)==h,name
  for name,h in owned.items():assert sha(HERE.parent/name)==h,name
  for name,h in core.items():assert sha(HERE.parent/name)==h,name
  for path,h in pins.items():assert sha(path)==h,path
  receipt=dict(passed=True,scope='Optional dispatcher component controls plus exact existing default timed/untimed NDK tests, Windows/Linux; no game or worker root admission.',owned_sources=owned,core_sources=core,source_proof=dict(path=str(proofpath),sha256=proofsha),platforms=platforms,retained_native_timed_reference=dict(path=str(prior/'acceptance.json'),sha256=sha(prior/'acceptance.json'),records=38),retained_native_untimed_reference=dict(path=str(old/'acceptance.json'),sha256=sha(old/'acceptance.json'),records=23),inputs=pins,support_sources=sources,no_guest_relift=True,default_dispatcher_unset_regression=True,limits='New dispatcher tests invoke the real provider and signal model with labelled TEST boundary callbacks, not original Boehm handlers or compiler safepoints. Existing default NDK callers and native records are reused byte exact. Timing bounds prove fixed timeout behavior, not scheduling equivalence.')
  receipt['evidence']={f.relative_to(out).as_posix():sha(f)for f in out.rglob('*')if f.is_file()and f.name!='acceptance.json'};save(out/'acceptance.json',receipt);print('FUTEX-DISPATCHER-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
