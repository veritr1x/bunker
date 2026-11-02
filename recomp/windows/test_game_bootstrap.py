"""Verify frozen dual-engine inputs and observe one natural native startup process.

Run from WSL. A fatal original boundary is recorded as incomplete, never passed.
The frame process has no automatic timeout that could terminate a live worker.
"""
import argparse,hashlib,json,pathlib,re,subprocess
from il2cpp_stack_prepare import hashes,absolute
HERE=pathlib.Path(__file__).resolve().parent

def sha(path):
 with pathlib.Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--profile',choices=['default','init','surface','frame'],default='default');p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);p.add_argument('--verify-only',action='store_true');a=p.parse_args();b=a.build.resolve()
 m=json.loads((b/'game_inputs.json').read_text());record=json.loads((b/'game_build.json').read_text());assert m['status']=='prepared'and m['union_trace_count']==456684 and len(m['objects'])==3575
 expected={**m['original_object_hashes'],**m['input_hashes'],**{x['path']:x['sha256']for x in m['objects']},**{str(b/'sources'/k):v for k,v in m['source_sha256'].items()},**{str(b/k):v for field in ['frozen_support_sha256','generated_header_sha256']for k,v in m[field].items()},str(b/'game_inputs.json'):record['inputs_sha256'],str(b/'bunker-game-bootstrap.exe'):record['executable_sha256'],str(b/'libz-inflate.a'):m['zlib_sha256'],str(b/'host-source.tar'):m['host_archive_sha256']}
 expected.update({str(pathlib.Path(m['angle_directory'])/k):v for k,v in m['angle_dll_sha256'].items()})
 expected.update({str(b/'native'/('lib'+mod['name']+'.so')):mod['sha256']for mod in m['modules']})
 def verify():
  win=[pathlib.Path(k)for k in expected if k.startswith('/mnt/')];actual=hashes(win)
  assert all(actual[str(absolute(k))]==expected[str(k)]for k in win),'frozen Windows artifact differs'
  assert all(sha(k)==v for k,v in expected.items()if not k.startswith('/mnt/')),'frozen WSL artifact differs'
 verify()
 if a.verify_only:print('All accepted objects, source/support, inputs, native data and executable verified; no guest execution');return
 def wp(path):return subprocess.check_output(['wslpath','-m',str(pathlib.Path(path).resolve())],text=True).strip()
 storage=b/('data-'+a.profile)
 if storage.exists():raise RuntimeError('Use a fresh build/profile; preserve old data and logs')
 storage.mkdir();log=b/('game-'+a.profile+'.log');command=[str(b/'bunker-game-bootstrap.exe'),wp(b/'native'),wp(m['apk']),wp(storage)]
 if a.profile=='init':command+=['--init-jni']
 elif a.profile=='surface':command+=['--surface-gate',str(a.width),str(a.height)]
 elif a.profile=='frame':command+=['--frame-gate',str(a.width),str(a.height),wp(m['angle_directory'])]
 with log.open('wb')as out:run=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
 verify();text=log.read_text(errors='replace')
 ctors=re.findall(r'Game bootstrap: IL2CPP constructor (\d+)/9 entry=',text);finis=re.findall(r'Game bootstrap: IL2CPP finalizer (\d+)/2 entry=',text)
 lifecycle_order=ctors==list(map(str,range(1,len(ctors)+1)))and finis==list(map(str,range(1,len(finis)+1)))and len(ctors)<=9 and len(finis)<=2
 frame_returned='first nativeRender returned continue='in text
 before=re.search(r'before original nativeRender IL2CPP constructors=(\d+) refs=(\d+)',text)
 lazy=(not int(before[1])and not int(before[2]))if before else(None if a.profile=='frame'else not ctors and not finis)
 terminal='Game bootstrap: normal profile completion='+a.profile+'; original constructors/JNI, lifecycle and ownership checks complete'in text
 unity_complete='ALL 417 real constructors completed in order'in text and'all 42 evidenced native bindings match original ELF/DEX'in text
 complete=run.returncode==0 and terminal and unity_complete and lifecycle_order and(a.profile=='frame'or lazy)and(a.profile!='frame'or(frame_returned and len(ctors)==9))
 result=dict(status='profile passed'if complete else'original startup boundary reached; incomplete',profile=a.profile,exit_code=run.returncode,normal_terminal_record=terminal,unity_constructors_and_jni_complete=unity_complete,host_commit=m['host_commit'],executable_sha256=record['executable_sha256'],inputs_sha256=record['inputs_sha256'],log_sha256=sha(log),il2cpp_constructors=len(ctors),il2cpp_finalizers=len(finis),lifecycle_order=lifecycle_order,il2cpp_lazy_before_frame=lazy,native_render_returned=frame_returned,all_frozen_inputs_and_original_objects_reverified=True,limits='Unpolled exploratory cohorts; no stop-world/collection, rendered-image, full Java lifecycle or playable-game claim')
 (b/('game-'+a.profile+'-audit.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print('Full log:',log)
 if not complete:raise SystemExit(1)
if __name__=='__main__':main()
