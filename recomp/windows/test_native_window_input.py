"""Hidden owned-HWND input contract and matching native-window NDK regression."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');PARENT=W/'windows-first-frame-thread-exit1';PARENT_SHA='57430fa2285cb1bc9400e82ea3c1ed296e49ff28498cf4709ce0524e95643581';OLD=W/'native-window-reader-qualification2'
OWN=['native_window.cpp','native_window.h','native_window_input_test.cpp','test_native_window_input.py','native_window_input.md']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def hp(p):
 p=str(p).replace('\\','/');return Path('/mnt/'+p[0].lower()+p[2:])if len(p)>1 and p[1]==':'else Path(p)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  assert sha(PARENT/'overlay.json')==PARENT_SHA;parent=json.loads((PARENT/'overlay.json').read_text());pin(PARENT/'overlay.json');oldq=json.loads((OLD/'acceptance.json').read_text());assert oldq['passed']is True;pin(OLD/'acceptance.json')
  source=out/'source';required={'windows/native_window.cpp','windows/native_window_test.cpp','windows/native_window_guest.c','windows/jni_host.cpp','whole/runtime.cpp','fastaes/elfload.c'}
  support={}
  for folder in ['windows','whole','fastaes']:
   target=source/folder;target.mkdir(parents=True)
   for p in(PARENT/'sources/recomp'/folder).iterdir():
    if p.is_file()and(p.suffix in ['.h','.inc']or folder+'/'+p.name in required):
     name=folder+'/'+p.name;row=desc(p);assert row['sha256']==parent['frozen_files']['thread_exit1_source_recomp/'+name]['sha256'];support[name]=row;pin(p);shutil.copyfile(p,target/p.name)
  production={}
  for name in OWN:
   p=HERE/name;pin(p);shutil.copyfile(p,source/'windows'/name)
   if name in ['native_window.cpp','native_window.h']:production['windows/'+name]=sha(p)
  basecpp=(PARENT/'sources/recomp/windows/native_window.cpp').read_text();newcpp=(source/'windows/native_window.cpp').read_text();start='  static LRESULT CALLBACK Procedure(';finish='\n private:'
  original_proc=basecpp[basecpp.index(start):basecpp.index(finish,basecpp.index(start))];assert newcpp[newcpp.index(start):newcpp.index(finish,newcpp.index(start))]==original_proc
  assert 'TranslateMessage(&message);DispatchMessageW(&message);'in newcpp and not any(s in newcpp for s in ['SetCapture(','SetFocus(','SetForegroundWindow(','SendInput('])
  assert sha(source/'windows/native_window_test.cpp')==sha(OLD/'source/recomp/windows/native_window_test.cpp')and sha(source/'windows/native_window_guest.c')==sha(OLD/'source/recomp/windows/native_window_guest.c')
  guest=OLD/'guest';manifest=guest/'manifest.json';gm=json.loads(manifest.read_text());assert not gm['unsupported_traces']and not gm['unresolved_direct_targets'];reuse=[OLD/'window.so',manifest,guest/'traces.h',*map(Path,gm['objects'])]
  for p in reuse:assert sha(p)==oldq['evidence'][str(p)];pin(p)
  cxx=Path('/mnt/c/mingw64/bin/g++.exe');gcc=Path('/mnt/c/mingw64/bin/gcc.exe');pin(cxx);pin(gcc);remill=hp(parent['compile_argv'][4][2:])
  for p in remill.rglob('*'):
   if p.is_file():pin(p)
  source_pins={p.relative_to(source).as_posix():sha(p)for p in source.rglob('*')if p.is_file()};(out/'source-binding.json').write_text(json.dumps(dict(parent_manifest=desc(PARENT/'overlay.json'),production_sources=production,frozen_parent_support_sources=support,source_snapshot=source_pins,legacy_guest_objects=[desc(Path(p))for p in gm['objects']],legacy_guest_manifest=desc(manifest),unchanged_existing_WndProc=True),indent=2)+'\n');shutil.copyfile(__file__,out/'executed-controller.py')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(remill),'-I'+wp(guest),'-DNATIVE_WINDOW_LIBRARY="'+wp(OLD/'window.so')+'"'];provider=[]
  for name in ['windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp']:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('native_window.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);provider.append(obj)
  results={}
  for name,label in [('native_window_input_test.cpp','focused-input'),('native_window_test.cpp','legacy-window')]:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows'/name),'-o',wp(obj)],'compile-'+label);extra=[]
   if label=='legacy-window':
    loader=out/'elfload.o';run([gcc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');extra=[loader,*map(Path,gm['objects'])]
   exe=out/(label+'.exe');run([cxx,*map(wp,[obj,*provider,*extra]),'-static','-pthread','-latomic','-luser32','-o',wp(exe)],'link-'+label);run([exe],'actual-'+label,45);text=(out/('actual-'+label+'.log')).read_text();results[label]=dict(executable=desc(exe),stdout=desc(out/('actual-'+label+'.log')),text=text)
  fm=re.search(r'NATIVE-INPUT-PASS checks=(\d+) messages=(\d+) hidden=1 timestamp_oracle=1 signed_client=1 wheel_screen_conversion=1 key_metadata=1 old_lifecycle=1 State=1200 Memory64=1 test_stimuli_only=1',results['focused-input']['text']);lm=re.search(r'Native Windows window provider: (\d+) checks, six imports through actual NDK caller',results['legacy-window']['text']);assert fm and lm and int(fm[2])==23 and int(lm[1])==300
  for p,h in source_pins.items():assert sha(source/p)==h,p
  for p,h in held.items():assert sha(p)==h,p
  r=dict(passed=True,prepared_only=True,selected=False,production_sources=production,reviewed_production_sources=production,parent_manifest=desc(PARENT/'overlay.json'),focused=dict(checks=int(fm[1]),queued_test_messages=int(fm[2]),fixture_owned_hidden_HWND=True,never_foreground=True,actual_MSG_time_matches_WndProc_oracle=True,queued_time_not_dispatch_time=True,signed_client_coordinates=True,actual_wheel_screen_to_client=True,key_repeat_scan_extended_metadata=True,raw_button_state_preserved=True,ordering_and_kind_preserved=True,legacy_kind_ordinals_and_aggregate_preserved=True,unchanged_existing_WndProc=True,resize_and_close_semantics_preserved=True,State_bytes=1200,Memory64=True),legacy=dict(checks=int(lm[1]),actual_NDK_imports=6,guest_objects_linked_byte_exact=True,matching_fixture_source_unchanged=True,hidden_HWND_lifetime_and_geometry=True,original_qualification=desc(OLD/'acceptance.json'),guest_manifest=desc(manifest),guest_objects=[desc(Path(p))for p in gm['objects']]),source_binding=desc(out/'source-binding.json'),source_snapshot=source_pins,held_inputs=held,results=results,commands=commands,original_game_executed=False,user_or_game_window_input_injected=False,JNI_input_integration=False,OS_focus_capture_or_settings_changed=False,limits='Hidden fixture-owned Win32 queued-message contract with explicit posted stimuli; independent WndProc clock oracle. Matching existing NDK/native-window regression freshly linked to the same new provider/frozen57430 support. No physical-hardware origin, original Unity injection, user-window event, fullhost build or original game claim.')
  (out/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print('NATIVE-WINDOW-INPUT-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
