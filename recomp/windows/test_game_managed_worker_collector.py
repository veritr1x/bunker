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
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--header-sha',required=True);parser.add_argument('--pthread-header-sha',required=True);parser.add_argument('--pthread-source-sha',required=True);parser.add_argument('--reuse',type=Path);args=parser.parse_args();out=args.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];lock=threading.Lock();hashes={};reused=[]
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
   allowed_queue=label in('reject-bad-LR','reject-bad-opaque-send','reject-bad-mutex-LR','reject-bad-mutex-FP','reject-bad-mutex-TLS')
   assert result.returncode!=0 and 'Game GC: unsupported bounded profile:'in text and 'watchdog'not in text and 'TEST-only unsupported'not in text and text.count('ACTUAL-SIGNAL-QUEUE')<=(1 if allowed_queue else 0) and 'original sem_post returned'not in text,(label,result.returncode,text[-5000:])
  elif result.returncode:raise RuntimeError(label+' exit='+str(result.returncode)+'\n'+text[-6000:])
  return dict(exit_code=result.returncode,stdout=desc(log)),text
 try:
  production={'windows/game_collector_delivery.h':args.header_sha,'windows/pthread_host.h':args.pthread_header_sha,'windows/pthread_host.cpp':args.pthread_source_sha}
  assert all(re.fullmatch('[0-9a-f]{64}',h)and sha(REPO/n)==h for n,h in production.items())
  for n in COMPILE+OWN+['windows/game_collector_delivery.h','windows/pthread_wait_test.cpp','windows/pthread_wait_guest.c','fastaes/elfload.c']:freeze(REPO/n)
  save(out/'source-hashes.json',hashes)
  extraction=W/'original-gc-protocol-extract1/extraction.json';original=W/'original-gc-protocol-extract1/windows.o'
  assert sha(extraction)=='ace8c5cd9da8460c110d6a8da6dd91e4a31a36cfc4ed598cd256ab9bcd222f3a'
  assert json.loads(extraction.read_text())['passed']and sha(original)=='c353c4bb96e6fba4081c522215771a563eb1f1680c23251b902f7ab5ecc4b8e0'
  shutil.copyfile(original,out/'original-protocol.o')
  provenance=W/'firebase-runtime5-worker-provenance1/acceptance.json';assert sha(provenance)=='844c352e0439406b1036cd6062adb37bf2f927cc4b68a7ac1a232e51f42586ff'
  native_provenance=W/'runtime6-managed-wait-boundary1/acceptance.json';assert sha(native_provenance)=='638e4efb4100a60ba1925f0827440cafdb24def8e4c3973d6590eec10847e92d'
  cxx=Path('/mnt/c/mingw64/bin/g++.exe');tool=W/'remill-src/include';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool)]
  run('strict-fixture',[cxx,*flags,'-Wall','-Wextra','-Werror','-fmax-errors=6','-fsyntax-only',wp(source/COMPILE[0])])
  objects=[];jobs=[]
  for name in COMPILE:
   obj=out/(Path(name).stem+'.o')
   if args.reuse and name!=COMPILE[0]:
    old=args.reuse/obj.name
    assert sha(args.reuse/'source'/name)==hashes[name]
    for frozen in source.rglob('*.h'):
     if frozen.relative_to(source).as_posix()=='windows/game_collector_delivery.h':continue # Included only by the freshly compiled fixture, never these provider units.
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
  for mode,cycles in [('race-timeout',1),('race-reacquire',1),('timed',2),('untimed',1),('native-timed',2),('native-untimed',1),('finalizer',1),('unknown',0),('opaque',0),('nested',0)]:
   result,text=run('original-GC-'+mode,[exe,mode]);match=re.search(r'MANAGED-WORKER-ORIGINAL-GC-PASS mode='+mode+r' cycles=(\d+) posts=(\d+) stops=(\d+) restarts=(\d+) physical=(\d+) checks=(\d+) State=1200 Memory64=8',text);assert match,text[-5000:]
   c,posts,stops,restarts,physical,checks=map(int,match.groups());assert(c,posts,stops,restarts,physical)==(cycles or 1,cycles*2,cycles,cycles,cycles*2)
   assert text.count('physical interrupted roots verified')==physical
   environment=re.search(r'checkpoint_env=(\d+) FPCR_FPSR=(\d+)',text);assert environment and int(environment[1])>=(cycles or 1) and int(environment[2])==(cycles or 1)
   finish=re.search(r'finish_calls=(\d+)',text);assert finish and int(finish[1])>=c*2
   finish_environment=re.search(r'finish_env=(\d+)',text);assert finish_environment and int(finish_environment[1])==int(finish[1])
   result.update(cycles=cycles,actual_wait_calls=c,actual_posts=posts,stop_deliveries=stops,restart_deliveries=restarts,physical_root_frames=physical,checks=checks,checkpoint_native_environment_checks=int(environment[1]),interrupted_FPCR_FPSR_checks=int(environment[2]),actual_provider_finish_calls=int(finish[1]),finish_native_environment_checks=int(finish_environment[1]));results[mode]=result
  rejected={}
  between={}
  for mode in ['between-event','between-queue-a','between-queue-b']:
   result,text=run('original-GC-'+mode,[exe,mode]);match=re.search(r'MANAGED-BETWEEN-WAITS-PASS mode='+mode+r' cycles=1 posts=2 stops=1 restarts=1 physical=2 checks=(\d+) timeout_result=110 mutex_result=0 fresh_checkpoints=(\d+) State=1200 Memory64=8',text);assert match,text[-5000:];assert text.count('physical interrupted roots verified')==2 and text.count('ACTUAL-SIGNAL-QUEUE')==2;result.update(cycles=1,actual_posts=2,stop_deliveries=1,restart_deliveries=1,physical_root_frames=2,checks=int(match[1]),fresh_mutex_checkpoints=int(match[2]),old_timed_wait_result=110,new_mutex_lock_result=0,only_actual_unlock_allows_acquisition=True);between[mode]=result
  for mode in ['bad-actually-retired','bad-function','bad-owner','bad-argument','bad-wrapper','bad-LR','bad-FP','bad-request','bad-TLS','bad-native-FP','bad-native-TLS','bad-opaque-send','bad-mutex-LR','bad-mutex-FP','bad-mutex-TLS']:
   rejected[mode],_=run('reject-'+mode,[exe,mode],True)
  # Existing real-provider wait regression, with its exact previously lifted
  # NDK object. No retranslation or repeated Android/reference campaign.
  legacy=W/'pthread-wait3';manifest=legacy/'focused/manifest.json';guest=legacy/'pthread-wait.so'
  assert sha(manifest)=='0257dd335c4483be30dcb832ed11c3411401ea510919a8bd08f17b04972e47e2'and sha(guest)=='2cd40db058e3efdcb4401ae47e2edf2d6202569689abf5f6a534b5d797217a2f'
  assert sha(legacy/'sources/recomp/windows/pthread_wait_guest.c')==hashes['windows/pthread_wait_guest.c']
  shutil.copyfile(legacy/'focused/pthread_wait_traces.h',out/'pthread_wait_traces.h');guest_manifest=json.loads(manifest.read_text());assert not guest_manifest['unsupported_traces']and not guest_manifest['unresolved_direct_targets']
  regression_object=out/'pthread_wait_test.o';run('compile-existing-wait-regression',[cxx,*flags,'-I'+wp(out),'-DPTHREAD_WAIT_IMAGE="'+wp(guest)+'"','-Wall','-Wextra','-Werror','-c',wp(source/'windows/pthread_wait_test.cpp'),'-o',wp(regression_object)])
  loader=out/'elfload.o';run('compile-regression-loader',['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)])
  regression_exe=out/'existing-pthread-wait.exe';run('link-existing-wait-regression',[cxx,wp(regression_object),*[wp(p)for p in objects[1:]],wp(loader),*[wp(p)for p in guest_manifest['objects']],'-static','-pthread','-latomic','-ladvapi32','-lbcrypt','-o',wp(regression_exe)])
  regression,regression_text=run('existing-pthread-wait-regression',[regression_exe]);regression_match=re.search(r'Windows optional pthread wait passed: (\d+) checks',regression_text);assert regression_match
  regression.update(checks=int(regression_match[1]),original_NDK_manifest=desc(manifest),original_NDK_guest=desc(guest),original_NDK_objects=[desc(p)for p in guest_manifest['objects']],executed_once=True)
  for name,digest in hashes.items():assert sha(source/name)==digest and sha(REPO/name)==digest,name
  receipt=dict(passed=True,production_sources=production,source_snapshot=hashes,owned_sources={n:hashes[n]for n in OWN},reused_support_objects=reused,original_protocol_extraction=desc(extraction),original_protocol_object=desc(out/'original-protocol.o'),original_managed_worker_provenance=desc(provenance),compiler=desc(cxx),binary=desc(exe),results=results,between_waits=between,rejections=rejected,existing_pthreads_regression=regression,cycles=12,actual_posts=24,physical_root_frames=24,ordinary_unknown_waits=1,ordinary_opaque_waits=1,ordinary_nested_waits=1,ordinary_no_pending_waits=3,checks=sum(r['checks']for r in results.values())+sum(r['checks']for r in between.values()),negative_controls=len(rejected),scope='Actual Windows Pthreads creator-owned managed waits with sender/provider-finish race handoff and new post-timeout queue-to-fresh-contended-mutex delivery. Twelve original stop/restart cycles and twenty-four physical GPR/Q frames/posts; all three original mutex sites. Timeout110 and later mutex0 unchanged; only real unlock permits acquisition. Existing finalizer and three ordinary no-pending modes retained.',limits=['Initial GC registry, creator-shaped record/payload, and interrupted helper-shaped State are TEST-owned. Original managed thread trampoline, full original wait helpers, heap scanner/reclamation and game are not executed.','No synthetic wait phase, wake, semaphore acknowledgment or signal completion. Original coordinator and handler code own all epoch/world/post transitions.','Q9 bad-retired-send was a live-worker restriction and is superseded by the positive between-waits ordering. New actual-worker-retired/wrong-role and malformed fresh mutex cases reject without acknowledgment. No arbitrary compiler-poll or asynchronous native callback root admission.'])
  receipt['native_condition_boundary']=desc(native_provenance)
  save(out/'acceptance.json',receipt);print(json.dumps(desc(out/'acceptance.json')),flush=True)
 except BaseException as error:save(out/'failure.json',dict(passed=False,error=str(error),traceback=traceback.format_exc(),source_hashes=hashes));raise
if __name__=='__main__':main()
