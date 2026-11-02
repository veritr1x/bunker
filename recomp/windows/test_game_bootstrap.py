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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--profile',choices=['default','init','surface','frame','frame-muted'],default='default');p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);p.add_argument('--verify-only',action='store_true');a=p.parse_args();b=a.build.resolve();frame=a.profile in ('frame','frame-muted')
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
 elif frame:
  command+=['--frame-gate',str(a.width),str(a.height),wp(m['angle_directory'])]
  if a.profile=='frame-muted':command+=['--mute-audio']
 with log.open('wb')as out:run=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
 verify();text=log.read_text(errors='replace')
 ctors=re.findall(r'Game bootstrap: IL2CPP constructor (\d+)/9 entry=',text);finis=re.findall(r'Game bootstrap: IL2CPP finalizer (\d+)/2 entry=',text)
 lifecycle_order=ctors==list(map(str,range(1,len(ctors)+1)))and finis==list(map(str,range(1,len(finis)+1)))and len(ctors)<=9 and len(finis)<=2
 frame_returned='first nativeRender returned continue='in text
 before=re.search(r'before original nativeRender IL2CPP constructors=(\d+) refs=(\d+)',text)
 lazy=(not int(before[1])and not int(before[2]))if before else(None if frame else not ctors and not finis)
 terminal='Game bootstrap: normal profile completion='+a.profile+'; original constructors/JNI, lifecycle and ownership checks complete'in text
 unity_complete='ALL 417 real constructors completed in order'in text and'all 42 evidenced native bindings match original ELF/DEX'in text
 muted='Game bootstrap: explicit muted diagnostic; original nativeMuteMasterAudio(true) returned; hardware-volume observer disabled; no endpoint/volume or audio-output qualification'in text
 assert not muted or a.profile=='frame-muted','muted mode must be requested explicitly'
 complete=run.returncode==0 and terminal and unity_complete and lifecycle_order and(frame or lazy)and(not frame or(frame_returned and len(ctors)==9))and(a.profile!='frame-muted'or muted)
 result=dict(status='profile passed'if complete else'original startup boundary reached; incomplete',profile=a.profile,exit_code=run.returncode,normal_terminal_record=terminal,unity_constructors_and_jni_complete=unity_complete,host_commit=m['host_commit'],executable_sha256=record['executable_sha256'],inputs_sha256=record['inputs_sha256'],log_sha256=sha(log),il2cpp_constructors=len(ctors),il2cpp_finalizers=len(finis),lifecycle_order=lifecycle_order,il2cpp_lazy_before_frame=lazy,native_render_returned=frame_returned,all_frozen_inputs_and_original_objects_reverified=True,limits='Unpolled exploratory cohorts; no stop-world/collection, rendered-image, full Java lifecycle or playable-game claim')
 result['audio_profile']='explicit-muted' if a.profile=='frame-muted' else 'normal'
 result['original_master_mute_request_returned']=muted
 result['hardware_volume_observer_created']='real read-only music-volume observer ready' in text
 if a.profile=='frame-muted':assert not result['hardware_volume_observer_created'],'muted mode must not create the hardware-volume observer'
 result['actual_interface_proxy_requests']=[dict(native_handle=match[1],loader=match[2],count=int(match[3]),interfaces=match[4].split(',')if match[4]else[])for match in re.finditer(r'JNI interface proxy: actual handle=(0x[0-9a-f]+|0) loader=(0x[0-9a-f]+|0) Class\[\] count=(-?\d+) \[([^\]\r\n]*)\]',text)]
 result['actual_sigaltstack_calls']=[dict(new=match[1],old=match[2],sp=match[3],lr=match[4],result=int(match[5]),configured=match[6],flags=int(match[7]),size=int(match[8]))for match in re.finditer(r'Game bootstrap: original sigaltstack new=(0x[0-9a-f]+|0) old=(0x[0-9a-f]+|0) SP=(0x[0-9a-f]+|0) LR=(0x[0-9a-f]+|0) result=(-?\d+) configured=(0x[0-9a-f]+|0) flags=(\d+) size=(\d+)',text)]
 result['actual_mmap_calls']=[dict(length=int(match[1]),flags=match[2],lr=match[3],result=match[4],errno=int(match[5])if match[5]else None,failure=match[6])for match in re.finditer(r'Game bootstrap: original mmap length=(\d+) flags=(0x[0-9a-f]+|0) LR=(0x[0-9a-f]+|0) (?:result=(0x[0-9a-f]+|0) errno=(-?\d+)|failed:([^\r\n]*))',text)]
 result['actual_library_opens']=[dict(argument=match[1],name=match[2],result=match[3],lr=match[4],unity_refs=int(match[5]),il2cpp_refs=int(match[6]))for match in re.finditer(r'Game bootstrap: original dlopen argument=(0x[0-9a-f]+|0) name=([^\r\n]*?) result=(0x[0-9a-f]+|0) LR=(0x[0-9a-f]+|0) Unity refs=(\d+) IL2CPP refs=(\d+)',text)]
 result['actual_symbol_requests']=[dict(handle=match[1],name=match[2],result=match[3],lr=match[4])for match in re.finditer(r'Game bootstrap: original dlsym argument=(0x[0-9a-f]+|0) name=([^\r\n]*?) result=(0x[0-9a-f]+|0) LR=(0x[0-9a-f]+|0) Unity refs=\d+ IL2CPP refs=\d+',text)]
 result['actual_preferences_reads']=[dict(store=match[1],observed=match[2],entries=int(match[3]))for match in re.finditer(r'Game bootstrap: original preferences read store=(legacy|v2) observed=(present|absent) entries=(\d+)',text)]
 result['actual_preferences_writes']=[dict(store=match[1],entries=int(match[2]),version_kind=int(match[3]),version_bits=match[4],status=int(match[5]))for match in re.finditer(r'Game bootstrap: original preferences write store=(legacy|v2) entries=(\d+) version_kind=(\d+) version_bits=(0x[0-9a-f]+|0) status=(\d+)',text)]
 result['actual_sscanf_calls']=[dict(format=match[1],lr=match[2],result=int(match[3]),assigned=bool(int(match[4])),value=int(match[5]),errno=int(match[6]))for match in re.finditer(r'Game bootstrap: original sscanf format=([^\r\n]*?) LR=(0x[0-9a-f]+|0) result=(-?\d+) assigned=([01]) value=(\d+) errno=(-?\d+)',text)]
 result['actual_setlocale_calls']=[dict(category=int(match[1]),name_null=bool(int(match[2])),name_read=bool(int(match[3])),requested=match[4],result_null=bool(int(match[5])),returned=match[6],lr=match[7],errno=int(match[8]))for match in re.finditer(r'Game bootstrap: original setlocale category=(-?\d+) name_null=([01]) name_read=([01]) requested=\[([^\]\r\n]*)\] result_null=([01]) returned=\[([^\]\r\n]*)\] LR=(0x[0-9a-f]+|0) errno=(-?\d+)',text)]
 result['actual_dup_calls']=[dict(source=int(match[1]),result=int(match[2]),lr=match[3],errno=int(match[4]))for match in re.finditer(r'Game bootstrap: original dup source=(-?\d+) result=(-?\d+) LR=(0x[0-9a-f]+|0) errno=(-?\d+)',text)]
 (b/('game-'+a.profile+'-audit.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print('Full log:',log)
 if not complete:raise SystemExit(1)
if __name__=='__main__':main()
