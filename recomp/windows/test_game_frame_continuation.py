"""Exact bootstrap policy extraction plus the selected real lifecycle/JNI host.

Uses transparent test callbacks, without an original game, HWND or fake frame.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
PARENT=W/'windows-first-frame-gl-draw1';PARENT_SHA='382957667390947ffe8e7af58c38a980ea53bacf4221fb802ebf9cd74b1760e5'
BASELINE=W/'game-frame-continuation-preparation1/baseline/windows/game_bootstrap.cpp';BASELINE_SHA='ca534837b26bfeba85e64fb27845eb920d273f10cbec88c438d3a2a4e0261c74'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--production-sha256',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  assert sha(PARENT/'overlay.json')==PARENT_SHA and sha(BASELINE)==BASELINE_SHA;parent=json.loads((PARENT/'overlay.json').read_text());production=HERE/'game_bootstrap.cpp';assert sha(production)==a.production_sha256;pin(production);pin(BASELINE);pin(PARENT/'overlay.json')
  old=BASELINE.read_bytes();new=production.read_bytes();begin=b'// BEGIN_GAME_FRAME_RUN_POLICY\n';end=b'// END_GAME_FRAME_RUN_POLICY\n';assert new.count(begin)==new.count(end)==1;policy=new[new.index(begin)+len(begin):new.index(end)];(out/'game_frame_run_policy.h').write_bytes(policy)
  # Retain the original default witness line, genuine scheduling calls and hold
  # body verbatim; the sole hold change is the explicit continuation guard.
  witness=next(x for x in old.splitlines()if b'First frame: witness=%d nativeRenderReturned='in x);assert witness in new.splitlines();hold=old[old.index(b'              std::fputs("First frame: retaining original surface/window'):old.index(b'\n            }\n          }\n          if(volume)volume->Pause();',old.index(b'              std::fputs("First frame: retaining original surface/window'))];assert hold in new
  for call in [b'poll_volume();lifecycle.ActivityResumed();',b'if(next_frame&&lifecycle.RequestNextFrame())',b'if(auto result=lifecycle.PollFrame())']:
   assert new.count(call)==old.count(call)
  assert b'if(witness&&!frame_run.Continuing())'in new and b'if(!keep_running||frame_run.StopAfterReturnedFrame(completed_frames,witness))break;'in new
  snapshot=out/'source';required={'windows/unity_lifecycle.cpp','windows/jni_host.cpp','whole/runtime.cpp'}
  for folder in ['windows','whole']:
   target=snapshot/folder;target.mkdir(parents=True)
   for p in(PARENT/'sources/recomp'/folder).iterdir():
    if p.is_file()and(p.suffix in ['.h','.inc']or folder+'/'+p.name in required):shutil.copyfile(p,target/p.name)
  test=HERE/'game_frame_continuation_test.cpp';shutil.copyfile(test,snapshot/'windows'/test.name);pin(test);pin(__file__);shutil.copyfile(__file__,out/'executed-controller.py')
  source_pins={p.relative_to(snapshot).as_posix():sha(p)for p in snapshot.rglob('*')if p.is_file()};(out/'bootstrap-candidate.cpp').write_bytes(new);cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cxx);remill=W/'remill-src/include'
  for p in remill.rglob('*'):
   if p.is_file():pin(p)
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(remill),'-I'+wp(out)];objects=[]
  for name in ['windows/game_frame_continuation_test.cpp','windows/unity_lifecycle.cpp','windows/jni_host.cpp','whole/runtime.cpp']:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('game_frame_continuation_test.cpp')else[]),'-c',wp(snapshot/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'continuation.exe';run([cxx,*map(wp,objects),'-static','-pthread','-latomic','-o',wp(exe)],'link');run([exe],'actual-policy-lifecycle',30)
  text=(out/'actual-policy-lifecycle.log').read_text();m=re.search(r'FRAME-CONTINUATION-PASS checks=(\d+) bounded=180 default=3 close=17 guest_false=7 stable_worker=1 native_resume=1 snapshot_hooks=1 parser_negative=20 transparent_callbacks=1 State=1200 Memory64=1',text);assert m
  for p,h in source_pins.items():assert sha(snapshot/p)==h,p
  for p,h in held.items():assert sha(p)==h,p
  r=dict(passed=True,prepared_only=True,reviewed_production_sources={'windows/game_bootstrap.cpp':a.production_sha256},production_sources={'windows/game_bootstrap.cpp':a.production_sha256},parent_manifest=desc(PARENT/'overlay.json'),baseline=desc(BASELINE),candidate=desc(out/'bootstrap-candidate.cpp'),policy_extracted_byte_exact=True,extracted_policy=desc(out/'game_frame_run_policy.h'),checks=int(m[1]),returned_frames_case180=180,default_first_witness_case=3,explicit_close_case=17,guest_false_case=7,parser_negative_controls=20,stable_UnityMain_worker=True,native_resume_calls_per_case=1,actual_focus_prerequisite_rejection=True,later_snapshot_policy_hooks=1,default_ten_second_hold_body_preserved_byte_exact=True,default_first_frame_witness_line_preserved_byte_exact=True,existing_lifecycle_poll_request_calls_preserved=True,State_size=1200,Memory64=True,transparent_test_callbacks=True,actual_original_game_executed=False,full_bootstrap_main_compiled=False,actual_frame_or_GL_snapshot_claim=False,source_snapshot=source_pins,held_inputs=held,commands=commands,stdout=desc(out/'actual-policy-lifecycle.log'),executable=desc(exe),limits='Actual production CLI/policy block compiled byte-exact and exercised with selected UnitySurfaceLifecycle/JNI source. Native entry callbacks and close/focus events are explicit transparent test fixtures. No original Unity/IL2CPP invocation, desktop input, GLFW/ANGLE frame, full bootstrap compilation or game continuation run claimed.')
  (out/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('GAME-FRAME-CONTINUATION-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
