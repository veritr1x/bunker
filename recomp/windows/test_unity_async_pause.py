"""Delayed genuine lifecycle acknowledgment with transparent callback fixtures."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;R=HERE.parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
PARENT=W/'windows-first-frame-unity-worker-switch1';PARENT_SHA='d4c99ca5999c40bd018843b1b9ab13684de91149fa380cec64de68c7a30ad601'
PRODUCTION=['windows/unity_lifecycle.cpp','windows/unity_lifecycle.h']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',type=Path);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);S=out/'source';held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:p=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  text=(out/(label+'.log')).read_text(errors='replace');assert p.returncode==0,(label,p.returncode,text[-6000:]);return text
 try:
  assert sha(PARENT/'overlay.json')==PARENT_SHA;pin(PARENT/'overlay.json');production_pins={n:sha(R/n)for n in PRODUCTION}
  for folder in ['whole','windows']:
   target=S/folder;target.mkdir(parents=True)
   for p in(PARENT/'sources/recomp'/folder).iterdir():
    if p.is_file()and(p.suffix in ['.h','.inc']or folder+'/'+p.name in ['windows/jni_host.cpp','whole/runtime.cpp']):shutil.copyfile(p,target/p.name);pin(p)
  for n in PRODUCTION:shutil.copyfile(R/n,S/n);pin(R/n)
  tests=['unity_async_pause_test.cpp','unity_frame_test.cpp','unity_lifecycle_test.cpp']
  for n in tests:shutil.copyfile(HERE/n,S/'windows'/n);pin(HERE/n)
  shutil.copyfile(__file__,out/'executed-controller.py');pin(__file__)
  cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cxx);remill=W/'remill-src/include';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(remill)]
  for p in remill.rglob('*'):
   if p.is_file():pin(p)
  common=[]
  for n in ['windows/unity_lifecycle.cpp','windows/jni_host.cpp','whole/runtime.cpp']:
   obj=out/(Path(n).stem+'.o')
   if a.reuse and sha(S/n)==sha(a.reuse/'source'/n):shutil.copyfile(a.reuse/obj.name,obj);pin(a.reuse/obj.name)
   else:run([cxx,*flags,'-c',wp(S/n),'-o',wp(obj)],'compile-'+obj.stem)
   common.append(obj)
  results={}
  for n in tests:
   obj=out/(Path(n).stem+'.o')
   if a.reuse and sha(S/'windows'/n)==sha(a.reuse/'source/windows'/n):shutil.copyfile(a.reuse/obj.name,obj);pin(a.reuse/obj.name)
   else:run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n=='unity_async_pause_test.cpp'else[]),'-c',wp(S/'windows'/n),'-o',wp(obj)],'compile-'+obj.stem)
   exe=out/(Path(n).stem+'.exe');run([cxx,wp(obj),*map(wp,common),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+obj.stem);text=run([exe],'actual-'+obj.stem,30);results[n]=dict(executable=desc(exe),stdout=desc(out/('actual-'+obj.stem+'.log')),text=text)
  text=results[tests[0]]['text'];m=re.search(r'ASYNC-PAUSE-PASS checks=(\d+) negatives=(\d+) delayed_over4s=1 legacy_timeout4s=1 cases=5 native_callbacks=6 same_worker=1 exact_finishing_branch=1 genuine_exception=1 providers_retained=1',text);assert m,text
  for n in tests[1:]:assert 'checks passed'in results[n]['text']
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,prepared_only=True,reviewed_production_sources=production_pins,production_sources=production_pins,parent_manifest=desc(PARENT/'overlay.json'),checks=int(m[1]),negative_checks=int(m[2]),cases=5,native_callbacks=6,actual_delayed_over_four_seconds=True,legacy_four_second_timeout_preserved=True,timeout_does_not_cancel_actual_job=True,actual_same_UnityMain_and_FIFO=True,finishing_short_circuit_byte_exact=True,actual_pending_completion_and_exception=True,duplicate_self_invalid_poll_and_resume_reentry_rejected=True,providers_and_JNI_retained_through_actual_callback=True,acknowledgment_consumed_exactly_once=True,State_bytes=1200,Memory64=True,old_frame_and_surface_fixtures_passed=True,transparent_callbacks=True,original_game_executed=False,full_bootstrap_main_compiled=False,results=results,source_snapshot={str(p.relative_to(S)):desc(p)for p in S.rglob('*')if p.is_file()},held_inputs=held,commands=commands,limits='Real selected lifecycle/JNI/Runtime providers with transparent test native callbacks, real native UnityMain thread, actual greater-than-four-second wait and cleanup ordering. No original Unity entry, HWND, full host, Firebase shutdown or game completion claim. Bootstrap asynchronous event-loop integration is separate.')
  before=(W/'async-pause-preparation1/baseline/windows/unity_lifecycle.cpp').read_bytes();after=(S/'windows/unity_lifecycle.cpp').read_bytes();branch=b'if(job.finishing||static_cast<int32_t>(Native(frame_entries.pause,receiver))!=0)NativeDone(receiver);';assert before.count(branch)==after.count(branch)==1
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ASYNC-PAUSE-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),held_inputs=held,commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
