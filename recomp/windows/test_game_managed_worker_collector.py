"""Actual Windows timed/untimed managed-worker waits and original GC handlers."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,re,shutil,subprocess,threading,traceback
HERE=Path(__file__).resolve().parent;REPO=HERE.parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
COMPILE=['windows/game_managed_worker_collector_test.cpp','windows/pthread_host.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_sleep.cpp','windows/semaphore_host.cpp','windows/worker_signal_lifecycle.cpp','whole/runtime.cpp','whole/signal_frame.cpp','whole/cooperative_poll.cpp']
OWN=['windows/game_managed_worker_collector_test.cpp','windows/test_game_managed_worker_collector.py']
def sha(p):
 with Path(p).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def save(p,value):Path(p).write_text(json.dumps(value,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--header-sha',required=True);parser.add_argument('--reuse',type=Path);args=parser.parse_args();out=args.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];lock=threading.Lock();hashes={};reused=[]
 def freeze(path):
  path=path.resolve();name=path.relative_to(REPO).as_posix()
  if name in hashes:return
  hashes[name]=sha(path);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
  for name in re.findall(r'^\s*#include\s+"([^"]+)"',path.read_text(),re.M):
   included=path.parent/name
   if included.is_file():freeze(included)
 def run(label,argv,expected_rejection=False):
  argv=list(map(str,argv))
  with lock:commands.append(dict(stage=label,argv=argv));save(out/'commands.json',commands)
  print('STAGE',label,flush=True)
  log=out/(label+'.log')
  with log.open('x')as stream:result=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,timeout=60)
  text=log.read_text(errors='replace')
  if expected_rejection:
   assert result.returncode!=0 and 'Game GC: unsupported bounded profile:'in text and 'watchdog'not in text and 'TEST-only unsupported'not in text,(label,result.returncode,text[-5000:])
  elif result.returncode:raise RuntimeError(label+' exit='+str(result.returncode)+'\n'+text[-6000:])
  return dict(exit_code=result.returncode,stdout=desc(log)),text
 try:
  assert re.fullmatch('[0-9a-f]{64}',args.header_sha)and sha(HERE/'game_collector_delivery.h')==args.header_sha
  for n in COMPILE+OWN+['windows/game_collector_delivery.h']:freeze(REPO/n)
  save(out/'source-hashes.json',hashes)
  extraction=W/'original-gc-protocol-extract1/extraction.json';original=W/'original-gc-protocol-extract1/windows.o'
  assert sha(extraction)=='ace8c5cd9da8460c110d6a8da6dd91e4a31a36cfc4ed598cd256ab9bcd222f3a'
  assert json.loads(extraction.read_text())['passed']and sha(original)=='c353c4bb96e6fba4081c522215771a563eb1f1680c23251b902f7ab5ecc4b8e0'
  shutil.copyfile(original,out/'original-protocol.o')
  provenance=W/'firebase-runtime5-worker-provenance1/acceptance.json';assert sha(provenance)=='844c352e0439406b1036cd6062adb37bf2f927cc4b68a7ac1a232e51f42586ff'
  cxx=Path('/mnt/c/mingw64/bin/g++.exe');tool=W/'remill-src/include';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool)]
  run('strict-fixture',[cxx,*flags,'-Wall','-Wextra','-Werror','-fmax-errors=6','-fsyntax-only',wp(source/COMPILE[0])])
  objects=[];jobs=[]
  for name in COMPILE:
   obj=out/(Path(name).stem+'.o')
   if args.reuse and name!=COMPILE[0]:
    old=args.reuse/obj.name
    assert sha(args.reuse/'source'/name)==hashes[name]
    for frozen in source.rglob('*.h'):
     previous=args.reuse/'source'/frozen.relative_to(source)
     assert previous.is_file()and sha(previous)==sha(frozen)
    obj=old;reused.append(desc(obj))
   else:jobs.append((Path(name).stem,[cxx,*flags,'-c',wp(source/name),'-o',wp(obj)]))
   objects.append(obj)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
   futures=[pool.submit(run,label,argv)for label,argv in jobs]
   for future in futures:future.result()
  exe=out/'managed-worker-gc.exe'
  run('link',[cxx,*map(wp,objects),wp(out/'original-protocol.o'),'-Wl,--wrap=_ZN6bunker7windows8Pthreads12SetWaitHooksENS1_9WaitHooksE','-static','-pthread','-latomic','-ladvapi32','-lbcrypt','-o',wp(exe)])
  results={}
  for mode,cycles in [('timed',2),('untimed',1),('finalizer',1)]:
   result,text=run('original-GC-'+mode,[exe,mode]);match=re.search(r'MANAGED-WORKER-ORIGINAL-GC-PASS mode='+mode+r' cycles=(\d+) posts=(\d+) stops=(\d+) restarts=(\d+) physical=(\d+) checks=(\d+) State=1200 Memory64=8',text);assert match,text[-5000:]
   c,posts,stops,restarts,physical,checks=map(int,match.groups());assert(c,posts,stops,restarts,physical)==(cycles,cycles*2,cycles,cycles,cycles*2)
   assert text.count('physical interrupted roots verified')==physical
   environment=re.search(r'checkpoint_env=(\d+) FPCR_FPSR=(\d+)',text);assert environment and int(environment[1])>=cycles*2 and int(environment[2])==cycles
   result.update(cycles=c,actual_posts=posts,stop_deliveries=stops,restart_deliveries=restarts,physical_root_frames=physical,checks=checks,checkpoint_native_environment_checks=int(environment[1]),interrupted_FPCR_FPSR_checks=int(environment[2]));results[mode]=result
  rejected={}
  for mode in ['bad-function','bad-owner','bad-argument','bad-wrapper','bad-LR','bad-FP','bad-request','bad-TLS']:
   rejected[mode],_=run('reject-'+mode,[exe,mode],True)
  for name,digest in hashes.items():assert sha(source/name)==digest and sha(REPO/name)==digest,name
  receipt=dict(passed=True,production_sources={'windows/game_collector_delivery.h':args.header_sha},source_snapshot=hashes,owned_sources={n:hashes[n]for n in OWN},reused_support_objects=reused,original_protocol_extraction=desc(extraction),original_protocol_object=desc(out/'original-protocol.o'),original_managed_worker_provenance=desc(provenance),compiler=desc(cxx),binary=desc(exe),results=results,rejections=rejected,cycles=4,actual_posts=8,physical_root_frames=8,checks=sum(r['checks']for r in results.values()),negative_controls=len(rejected),scope='Actual Windows Pthreads creator-owned managed timed/untimed and legacy-finalizer condition waits; retained original GC coordinators/handlers perform four genuine stop/restart cycles and eight physical GPR/Q frames/posts. Transparent TEST SetWaitHooks wrapper forwards the installed production checkpoint before observing real provider contexts.',limits=['Initial GC registry, creator-shaped record/payload, and interrupted helper-shaped State are TEST-owned. Original managed thread trampoline, full 0x70-frame helper, heap scanner/reclamation and game are not executed.','No synthetic wait phase, wake, semaphore acknowledgment or signal completion. Original coordinator and handler code own all epoch/world/post transitions.','Only exact managed timed/untimed sites and retained finalizer profile are tested; no arbitrary compiler-poll or asynchronous native callback root admission.'])
  save(out/'acceptance.json',receipt);print(json.dumps(desc(out/'acceptance.json')),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),source_hashes=hashes));raise
if __name__=='__main__':main()
