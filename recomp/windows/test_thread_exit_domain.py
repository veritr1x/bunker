"""Guarded actual NDK pthread_exit reaches native TLS after genuine Runtime retirement."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;R=HERE.parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=['thread_exit_domain_fixture.h','thread_exit_domain_guest.c','thread_exit_domain_test.cpp','test_thread_exit_domain.py'];PRODUCTION=['whole/runtime.h','whole/runtime.cpp','windows/pthread_host.cpp']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',type=Path);ap.add_argument('--preparation',type=Path,default=W/'thread-exit-domain-preparation1');a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);S=out/'source';held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180,expected_failure=False):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  text=(out/(label+'.log')).read_text(errors='replace')
  if not expected_failure and r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+text[-6000:])
  if expected_failure:assert r.returncode!=0,(label,text)
  return dict(exit_code=r.returncode,stdout=text,log=desc(out/(label+'.log')))
 try:
  pins=json.loads((a.preparation/'candidate-pins.json').read_text());assert set(pins)==set(PRODUCTION)
  for n,h in pins.items():assert sha(R/n)==h;pin(R/n)
  assert sha(HERE/'game_unity_worker_collector.h')=='1cd6de09cca69e42cc2bfce41d87fd45bb624417afd9683b450ee633286f8247'
  compile_names=['windows/thread_exit_domain_test.cpp','windows/pthread_host.cpp','windows/signal_host.cpp','windows/signal_delivery.cpp','windows/signal_futex.cpp','windows/semaphore_host.cpp','windows/worker_signal_lifecycle.cpp','whole/runtime.cpp','whole/signal_frame.cpp','whole/cooperative_poll.cpp']
  pending=compile_names+['windows/'+n for n in OWN]+['fastaes/elfload.c'];seen=set()
  while pending:
   n=pending.pop();p=(R/n).resolve();n=str(p.relative_to(R))
   if n in seen:continue
   seen.add(n);dest=S/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(R):pending.append(str(q.relative_to(R)))
  tool=W/'frinta-toolchain1/tools';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe')
  for p in[ndk,cxx,cc,tool/'remill-lift',tool/'aarch64.bc',R/'whole/compile.py']:pin(p)
  assert sha(tool/'remill-lift')=='73a1d6cf043bed30fc340059005a7ab931e9da350a057cc8e16b0304d614279d';assert sha(tool/'aarch64.bc')=='24e908b3be9b017ffb64e775df613a7aae675bdae59dd4995c402a0fdc303c2e'
  wrapper=out/'guarded-lift';wrapper.write_text('#!/usr/bin/python3\nimport os,sys\np='+repr(str(tool/'remill-lift'))+'\nos.execv(p,[p,"--guest_call_transfer=true",*sys.argv[1:]])\n');wrapper.chmod(0o755)
  library=out/'terminal.so';G=out/'guest'
  if a.reuse:
   assert sha(S/'windows/thread_exit_domain_guest.c')==sha(a.reuse/'source/windows/thread_exit_domain_guest.c');shutil.copyfile(a.reuse/'terminal.so',library);shutil.copytree(a.reuse/'guest',G);pin(a.reuse/'terminal.so');pin(a.reuse/'guest/manifest.json')
  else:
   library=out/'terminal.so';run([ndk,'-shared','-nostdlib','-fPIC','-O1','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',S/'windows/thread_exit_domain_guest.c','-o',library],'compile-NDK')
   G=out/'guest';run(['/home/user/bunker-recomp/recomp/work/tools/bin/python',R/'whole/compile.py',library,'--out',G,'--base','0x5d000000','--lift',wrapper,'--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18','--jobs','1'],'lift-guarded-NDK');guest=json.loads((G/'manifest.json').read_text());assert not guest['unsupported_traces']and not guest['unresolved_direct_targets']
   irs=[p for p in G.glob('*.ll')];ir='\n'.join(p.read_text()for p in irs);calls=len(re.findall(r'call [^\n]*@__bunker_guest_call\(',ir));guards=len(re.findall(r'call [^\n]*@__bunker_guest_transfer_pending\(',ir));assert calls and calls==guards,(calls,guards)
  guest=json.loads((G/'manifest.json').read_text());assert not guest['unsupported_traces']and not guest['unresolved_direct_targets'];ir='\n'.join(p.read_text()for p in G.glob('*.ll'));calls=len(re.findall(r'call [^\n]*@__bunker_guest_call\(',ir));guards=len(re.findall(r'call [^\n]*@__bunker_guest_transfer_pending\(',ir));assert calls and calls==guards
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-ffunction-sections','-fdata-sections','-isystem',wp(W/'remill-src/include'),'-I'+wp(G),'-DTHREAD_EXIT_LIBRARY="'+wp(library)+'"'];objects=[];common=[]
  for n in compile_names:
   obj=out/(Path(n).stem+'.o')
   if a.reuse and not n.endswith('thread_exit_domain_test.cpp') and sha(S/n)==sha(a.reuse/'source'/n):
    assert sha(S/n)==sha(a.reuse/'source'/n);shutil.copyfile(a.reuse/obj.name,obj);pin(a.reuse/obj.name)
   else:run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('thread_exit_domain_test.cpp')else[]),'-c',wp(S/n),'-o',wp(obj)],'compile-'+obj.stem)
   objects.append(obj)
   if n not in['windows/pthread_host.cpp','whole/runtime.cpp']:common.append(obj)
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader')
  def link(exe,obs,label):run([cxx,*map(wp,obs),wp(loader),*map(wp,guest['objects']),'-static','-pthread','-latomic','-lbcrypt','-ladvapi32','-Wl,--gc-sections','-o',wp(exe)],label)
  exe=out/'thread-exit.exe';link(exe,objects,'link-current');success=run([exe],'actual-guarded-workers',60);match=re.search(r'THREAD-EXIT-DOMAIN-PASS checks=(\d+) negatives=(\d+) workers=6 guarded_exit_workers=5 once_exit_levels=2 TLS=6 no_after_exit=1 actual_quiescence=1 strict_collector_unchanged=1',success['stdout']);assert match,success
  pending_result=run([exe,'--pending'],'actual-pending-rejection',30,True);assert 'worker reaches TLS with active/pending collector state'in pending_result['stdout']
  B=out/'baseline-source';shutil.copytree(S,B)
  for n in PRODUCTION:shutil.copyfile(W/'thread-exit-domain-preparation1/baseline'/n,B/n)
  baseline_objects=[]
  for n in['windows/pthread_host.cpp','whole/runtime.cpp']:
   obj=out/('baseline-'+Path(n).stem+'.o');run([cxx,*flags,'-c',wp(B/n),'-o',wp(obj)],'compile-'+obj.stem);baseline_objects.append(obj)
  baseline_exe=out/'baseline-exit.exe';link(baseline_exe,common+baseline_objects,'link-baseline');baseline_result=run([baseline_exe,'--baseline'],'actual-baseline-reproduction',30,True);assert 'same-worker binding retirement is not quiescent'in baseline_result['stdout']and 'pthread import:'in baseline_result['stdout'];assert re.search(r'TERMINAL-RETIRE[^\n]*State=(?!0+\b)[0-9A-Fa-f]+ native_same=1 pending=0',baseline_result['stdout']),baseline_result
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,reviewed_production_sources=pins,worker_collector_header_unchanged=desc(S/'windows/game_unity_worker_collector.h'),State_bytes=1200,Memory64=True,actual_NDK_ELF=desc(library),actual_NDK_guest=desc(G/'manifest.json'),guarded_call_count=calls,matching_pending_guard_count=guards,guarded_lifter_wrapper=desc(wrapper),underlying_qualified_lifter=desc(tool/'remill-lift'),underlying_qualified_semantics=desc(tool/'aarch64.bc'),focus=dict(checks=int(match[1]),negative_checks=int(match[2]),actual_native_workers=6,guarded_exit_workers=5,nested_once_levels=2,actual_TLS_destructors=6,post_exit_guest_statements=0,actual_Runtime_quiescence_at_before_TLS_and_retire=True),success=success,pending_signal_rejection=pending_result,baseline_fatal_reproduction=baseline_result,baseline_failing_term='!recomp::CurrentExecutionState() is false; current native owner and Pending are independently observed true/zero before unchanged Retire',baseline_executable=desc(baseline_exe),executable=desc(exe),source_snapshot={str(p.relative_to(S)):desc(p)for p in S.rglob('*')if p.is_file()},commands=commands,held_inputs=held,limits='Actual new NDK normal/direct/volatile/once/nested-once/detached entries execute with real native Pthreads, TLS destructors, signal lifecycle and strict unchanged ordinary workercollector retirement. Original Unity create witness is an explicit TEST alias; constructor original-code predicates are TEST metadata, no GC handler executes. Negative queued signal is never dispatched/acknowledged. Baseline oldsource abort reproduced independently. No original game/fullhost/firstframe execution; legacy regressions and standalone domain controls are separate qualifications.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('THREAD-EXIT-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:(out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
