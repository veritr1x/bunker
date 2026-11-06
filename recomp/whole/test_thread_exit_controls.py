"""Native-only synthetic call-protocol ownership controls; not a lifted guest claim."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, traceback

R=Path(__file__).resolve().parent.parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--qualified-workers',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);Q=a.qualified_workers.resolve();held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(args,label,fail=False):
  args=list(map(str,args));commands.append(dict(stage=label,argv=args));p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60);log=out/(label+'.log');log.write_bytes(p.stdout);text=p.stdout.decode(errors='replace')
  assert (p.returncode!=0)==fail,(label,p.returncode,text)
  return dict(exit_code=p.returncode,stdout=text,log=desc(log))
 try:
  worker=json.loads((Q/'acceptance.json').read_text());assert worker['passed'];pin(Q/'acceptance.json')
  for n,h in worker['reviewed_production_sources'].items():assert sha(R/n)==h;pin(R/n)
  assert sha(Q/'source/whole/runtime.cpp')==sha(R/'whole/runtime.cpp');assert sha(Q/'source/whole/runtime.h')==sha(R/'whole/runtime.h');pin(Q/'runtime.o')
  for n in ['thread_exit_controls_test.cpp','runtime.h']:
   shutil.copyfile(R/'whole'/n,out/n);pin(R/'whole'/n)
  shutil.copyfile(Path(__file__),out/Path(__file__).name);pin(Path(__file__))
  cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cxx)
  exe=out/'controls.exe';run([cxx,'-std=c++17','-O2','-Wall','-Wextra','-Werror','-DADDRESS_SIZE_BITS=64','-ffunction-sections','-fdata-sections','-isystem',wp(W/'remill-src/include'),wp(out/'thread_exit_controls_test.cpp'),wp(Q/'runtime.o'),'-static','-pthread','-latomic','-Wl,--gc-sections','-o',wp(exe)],'compile-link')
  actual=run([exe],'actual-controls');match=re.search(r'THREAD-EXIT-CONTROLS-PASS checks=(\d+) negatives=(\d+) Memory64=1 synthetic_guarded_protocol=1',actual['stdout']);assert match,actual
  memory=run([exe,'--bad-memory'],'changed-Memory-token-rejected',True);assert 'terminal thread exit changed its Memory token'in memory['stdout']
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,reviewed_production_sources=worker['reviewed_production_sources'],qualified_actual_workers=desc(Q/'acceptance.json'),runtime_object=desc(Q/'runtime.o'),fixture=desc(out/'thread_exit_controls_test.cpp'),runner=desc(out/Path(__file__).name),executable=desc(exe),checks=int(match[1]),negative_checks=int(match[2])+1,State_bytes=1200,Memory_bytes=64,Memory_nonnull_and_byte_exact=True,foreign_Runtime_consume_rejected=True,foreign_native_thread_consume_and_Run_rejected=True,opaque_nested_Run_request_rejected=True,shared_domain_nested_Run_retires_all_frames=True,exact_result_and_consumed_outcome_cleared=True,duplicate_and_active_consume_rejected=True,pending_Run_reentry_rejected=True,normal_Run_unaffected=True,actual=actual,changed_Memory_token_rejected=memory,pre_fix_failure=desc(W/'thread-exit-controls-qualification1/failure.json'),held_inputs=held,commands=commands,limits='Explicit synthetic native traces exercise the real Runtime guarded-call protocol. These are ownership and token controls, not lifted/original guest or full-game execution. Separate actual NDK workers qualify the real lifted guards and Pthreads/TLS lifecycle.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('THREAD-EXIT-CONTROLS-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
