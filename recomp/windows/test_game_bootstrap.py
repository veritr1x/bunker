"""Verify frozen dual-engine inputs and observe one natural native startup process.

Run from WSL. A fatal original boundary is recorded as incomplete, never passed.
The frame process has no automatic timeout that could terminate a live worker.
"""
import argparse,hashlib,json,pathlib,re,subprocess
from il2cpp_stack_prepare import hashes,absolute
HERE=pathlib.Path(__file__).resolve().parent

def sha(path):
 with pathlib.Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def validate_cooperative_contract(proof,descriptor,objects,parent_proof=None,grandparent_proof=None):
 assert (proof['trace_heads'],len(proof['objects']),len(objects))in((456684,3575,3575),(456689,3576,3576))and proof['unique_definitions'] is True and proof['missing_direct_targets']==[],'incomplete cooperative cohort'
 assert [(x['path'],x['sha256'])for x in proof['objects']]==[(x['path'],x['sha256'])for x in objects],'cooperative cohort object selection differs'
 contract=proof['contract'];version=contract.get('version',1)
 assert type(version)is int and version in(1,2,3,4),'unknown cooperative contract version'
 assert (proof['trace_heads'],len(objects))==((456689,3576)if version==4 else(456684,3575)),'cooperative contract version/shape differs'
 assert contract['poll_instrument_sha256']=='716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa'and contract['target']=='x86_64-w64-windows-gnu','unqualified cooperative instrumentation profile'
 if version==1:
  assert contract['input_plan_sha256']=='14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9'and contract['no_relift']is True and contract['source_ir_and_semantics_preserved']is True,'unqualified original cooperative contract'
 elif version==2:
  expected={'profile':'qualified-sparse-prefetch-v2','input_plan_sha256':'9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95','base_input_plan_sha256':'14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9','base_cohort_acceptance_sha256':'0a5e6b164855d7c745962ec744d2e7bf1c7209a679065cc117c0575446d9687d','sparse_overlay_sha256':'7fdc6f8b2e6eef9f5bafc9a4c5168318bf092ae1ec7e8988b44cd4b60b4dee7f','prefetch_fixture_acceptance_sha256':'e387dc78d1f3c2d21999b8e105916faa1c53f86e67084cc31ffa6aebbddb71fc','prefetch_lifter_sha256':'7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126','prefetch_semantics_sha256':'c5f0d94e6b234f5f0f376eeb999bc9bfbaee62d654381751c3080e5c621ac3b5','old_polled_object_sha256':'f1dfc4ccd067c68f509bd067766deff504d225bd17754742035ec86c849e2ee6','new_polled_object_sha256':'e8ed4af6efde5f9df1d73905baf5f1f934931ded38327a1f36110b9dfe100358'}
  assert descriptor['acceptance_sha256']=='7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','unqualified sparse cooperative proof hash'
  assert all(contract.get(k)==v for k,v in expected.items()),'unqualified sparse cooperative provenance'
  assert contract['no_relift']is False and contract['source_ir_and_semantics_preserved']is False,'sparse cooperative contract must disclose changed source/semantics'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'qualified_sparse_relifts':1,'replaced_object_index':1553,'unchanged_objects':3574}.items()),'sparse cooperative replacement scope differs'
  assert proof['objects'][1553]['sha256']==expected['new_polled_object_sha256'],'sparse cooperative replacement object differs'
  assert isinstance(contract.get('input_plan_path'),str)and contract['input_plan_path'],'sparse cooperative plan path is absent'
 elif version==3:
  # Exact qualified one-sort repair over the pinned v2 parent; no global refresh.
  expected={'profile':'qualified-sparse-unity-ext-sort-v3','input_plan_sha256':'4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb','parent_acceptance_sha256':'7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','parent_input_plan_sha256':'9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95','sparse_overlay_sha256':'9ad375fa793aa5ba92ee626abe6316f85a97d31379bd4d6fe34a7b80c267e343','ext_fixture_acceptance_sha256':'b4412315ade9aef3bd02aeb1ea0610692cdd52113e2d46c2bd40498ab95acf24','sort_fixture_acceptance_sha256':'be2afc2eb5b37e92b45eac72e8aebd5ab1640c8bb12d5060eb6a65acef81ba0f','ext_lifter_sha256':'2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e','ext_semantics_sha256':'06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a','old_polled_object_sha256':'71e7e8bc2f79bb88be46c8c39e89dca57f41687ba0d110f6f70786fd1530726a','new_polled_object_sha256':'f15e35212a7ea11597c885f990822018be23acf850080b84f919c114e3392327','target_head':'0x70255e38','target_end_exclusive':'0x7025603c','optimization':'-O2'}
  acceptance='68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67'
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v3 cooperative pins are not qualified'
  assert descriptor['acceptance_sha256']==acceptance,'unqualified v3 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v3 cooperative provenance'
  assert contract['no_relift']is False and contract['source_ir_and_semantics_preserved']is False and contract['no_global_semantics_refresh']is True and contract['production_signal_delivery_enabled']is False,'v3 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':2,'replaced_object_index':78,'unchanged_objects':3574}.items()),'v3 cooperative replacement scope differs'
  assert type(contract.get('cumulative_changed_indices'))is list and len(contract['cumulative_changed_indices'])==2 and all(type(x)is int for x in contract['cumulative_changed_indices'])and contract['cumulative_changed_indices']==[78,1553],'v3 cumulative replacement set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v3 cooperative plan/parent path is absent'
  assert type(parent_proof)is dict and type(parent_proof['contract'].get('version'))is int and parent_proof['contract']['version']==2,'v3 exact parent v2 proof is absent'
  parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent_proof,parent_descriptor,parent_proof['objects'])==2,'v3 parent contract differs'
  assert parent_proof['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v3 parent plan differs'
  assert parent_proof['objects'][78]['sha256']==expected['old_polled_object_sha256']and objects[78]['sha256']==expected['new_polled_object_sha256'],'v3 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent_proof['objects']))if index!=78),'v3 changed a second parent object'
 else:
  # Exact qualified additive entries over the pinned v3 parent; no old object refresh.
  acceptance='5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3'
  expected={'profile':'qualified-additive-unity-vararg-v4','input_plan_sha256':'57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae','parent_acceptance_sha256':'68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67','parent_input_plan_sha256':'4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb','additive_candidate_sha256':'88e29cd4c8853af8a6f9111b8e56504db556b2ef2fa6eb31bc81f310b98e85f2','prefix_fixture_acceptance_sha256':'ed69b5f9076507a58c57f95ef569172db08e5f94fc9a72215d03ac90d74574ee','lifter_sha256':'2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e','semantics_sha256':'06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a','new_polled_object_sha256':'f2bd9a1606dfc26ccbfa02f331f708df94cab70fe24fcbffbc511ef6d1a181cc','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v4 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v4 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v4 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'existing_objects_preserved':True,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v4 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'added_object_index':3575,'added_objects':1,'added_trace_count':5,'preserved_objects':3575,'inherited_cumulative_sparse_relifts':2}.items()),'v4 additive scope differs'
  assert type(contract.get('added_trace_heads'))is list and all(type(x)is str for x in contract['added_trace_heads'])and contract['added_trace_heads']==['0x70b5b488','0x70b5b4b0','0x70b5b4bc','0x70b5b648','0x70b5b674'],'v4 additive head set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v4 cooperative plan/parent path is absent'
  assert type(parent_proof)is dict and type(parent_proof['contract'].get('version'))is int and parent_proof['contract']['version']==3,'v4 exact parent v3 proof is absent'
  parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent_proof,parent_descriptor,parent_proof['objects'],grandparent_proof)==3,'v4 parent contract differs'
  assert parent_proof['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v4 parent plan differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for current,previous in zip(proof['objects'][:3575],parent_proof['objects'])),'v4 changed an existing parent object'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v4 trace count differs'
  assert type(objects[3575].get('path'))is str and objects[3575]['path']and objects[3575]['sha256']==expected['new_polled_object_sha256'],'v4 additive object differs'
 return version


def load_cooperative_parent(proof):
 version=proof['contract'].get('version',1)
 if type(version)is not int or version not in(3,4):return None
 contract=proof['contract']
 anchors={3:('7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95'),4:('68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67','4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb')}
 assert (contract.get('parent_acceptance_sha256'),contract.get('parent_input_plan_sha256'))==anchors[version],f'v{version} parent anchors differ'
 assert all(type(contract.get(k))is str and contract[k]for k in ('parent_acceptance_path','parent_input_plan_path')),f'v{version} parent path is absent'
 assert sha(contract['parent_acceptance_path'])==contract['parent_acceptance_sha256'],f'v{version} parent proof file differs'
 parent=json.loads(pathlib.Path(contract['parent_acceptance_path']).read_text())
 assert sha(contract['parent_input_plan_path'])==contract['parent_input_plan_sha256'],f'v{version} parent plan file differs'
 return parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--profile',choices=['default','init','surface','frame','frame-muted','frame-muted-gc'],default='default');p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);p.add_argument('--verify-only',action='store_true');a=p.parse_args();b=a.build.resolve();frame=a.profile in ('frame','frame-muted','frame-muted-gc');gc=a.profile=='frame-muted-gc';muted_profile=a.profile in ('frame-muted','frame-muted-gc')
 m=json.loads((b/'game_inputs.json').read_text());record=json.loads((b/'game_build.json').read_text());assert m['status']=='prepared'and (m['union_trace_count'],len(m['objects']))in((456684,3575),(456689,3576))
 expected={**m['original_object_hashes'],**m['input_hashes'],**{x['path']:x['sha256']for x in m['objects']},**{str(b/'sources'/k):v for k,v in m['source_sha256'].items()},**{str(b/k):v for field in ['frozen_support_sha256','generated_header_sha256']for k,v in m[field].items()},str(b/'game_inputs.json'):record['inputs_sha256'],str(b/'bunker-game-bootstrap.exe'):record['executable_sha256'],str(b/'libz-inflate.a'):m['zlib_sha256'],str(b/'host-source.tar'):m['host_archive_sha256']}
 expected.update({str(pathlib.Path(m['angle_directory'])/k):v for k,v in m['angle_dll_sha256'].items()})
 expected.update({str(b/'native'/('lib'+mod['name']+'.so')):mod['sha256']for mod in m['modules']})
 poll_cohort=m.get('cooperative_poll_cohort')
 assert m['union_trace_count']!=456689 or poll_cohort,'additive shape requires an accepted cooperative cohort'
 if gc and(not poll_cohort or record.get('collector_delivery_profile')!='original-finalizer-single-condwait-v1'):raise RuntimeError('Original collector profile is unavailable: explicit build option and accepted cooperative cohort are required')
 if poll_cohort:expected[poll_cohort['acceptance_path']]=poll_cohort['acceptance_sha256']
 def verify():
  win=[pathlib.Path(k)for k in expected if k.startswith('/mnt/')];actual=hashes(win)
  assert all(actual[str(absolute(k))]==expected[str(k)]for k in win),'frozen Windows artifact differs'
  assert all(sha(k)==v for k,v in expected.items()if not k.startswith('/mnt/')),'frozen WSL artifact differs'
 verify()
 if poll_cohort:
  proof=json.loads(pathlib.Path(poll_cohort['acceptance_path']).read_text())
  parent_proof=load_cooperative_parent(proof)
  grandparent_proof=load_cooperative_parent(parent_proof)if proof['contract'].get('version')==4 else None
  version=validate_cooperative_contract(proof,poll_cohort,m['objects'],parent_proof,grandparent_proof)
  assert m['union_trace_count']==proof['trace_heads'],'manifest/cohort head count differs'
  if version in(3,4):
   expected[proof['contract']['parent_acceptance_path']]=proof['contract']['parent_acceptance_sha256'];expected[proof['contract']['parent_input_plan_path']]=proof['contract']['parent_input_plan_sha256']
  if version==4:
   expected[parent_proof['contract']['parent_acceptance_path']]=parent_proof['contract']['parent_acceptance_sha256'];expected[parent_proof['contract']['parent_input_plan_path']]=parent_proof['contract']['parent_input_plan_sha256']
  if version in(2,3,4):
   plan=proof['contract']['input_plan_path'];plan_hash=proof['contract']['input_plan_sha256'];assert sha(plan)==plan_hash,'sparse cooperative plan file differs';expected[plan]=plan_hash
 if a.verify_only:print('All accepted objects, source/support, inputs, native data and executable verified; no guest execution');return
 def wp(path):return subprocess.check_output(['wslpath','-m',str(pathlib.Path(path).resolve())],text=True).strip()
 storage=b/('data-'+a.profile)
 if storage.exists():raise RuntimeError('Use a fresh build/profile; preserve old data and logs')
 storage.mkdir();log=b/('game-'+a.profile+'.log');command=[str(b/'bunker-game-bootstrap.exe'),wp(b/'native'),wp(m['apk']),wp(storage)]
 if a.profile=='init':command+=['--init-jni']
 elif a.profile=='surface':command+=['--surface-gate',str(a.width),str(a.height)]
 elif frame:
  command+=['--frame-gate',str(a.width),str(a.height),wp(m['angle_directory'])]
  if muted_profile:command+=['--mute-audio']
  if gc:command+=['--collector-delivery']
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
 assert not muted or muted_profile,'muted mode must be requested explicitly'
 complete=run.returncode==0 and terminal and unity_complete and lifecycle_order and(frame or lazy)and(not frame or(frame_returned and len(ctors)==9))and(not muted_profile or muted)
 result=dict(status='profile passed'if complete else'original startup boundary reached; incomplete',profile=a.profile,exit_code=run.returncode,normal_terminal_record=terminal,unity_constructors_and_jni_complete=unity_complete,host_commit=m['host_commit'],executable_sha256=record['executable_sha256'],inputs_sha256=record['inputs_sha256'],log_sha256=sha(log),il2cpp_constructors=len(ctors),il2cpp_finalizers=len(finis),lifecycle_order=lifecycle_order,il2cpp_lazy_before_frame=lazy,native_render_returned=frame_returned,all_frozen_inputs_and_original_objects_reverified=True,limits='Exploratory cohorts without production target signal delivery; no stop-world/collection, rendered-image, full Java lifecycle or playable-game claim')
 result['cooperative_poll_instrumented']=bool(poll_cohort)
 configured='Game GC: explicit original-finalizer single-condwait profile configured; virtual Android real UID=10000; no Windows/device UID claim'in text
 result['collector_delivery_requested']=gc
 result['target_signal_delivery_enabled']=gc and configured
 result['collector_delivery_profile']=record.get('collector_delivery_profile')if gc else None
 result['audio_profile']='explicit-muted' if muted_profile else 'normal'
 result['original_master_mute_request_returned']=muted
 result['hardware_volume_observer_created']='real read-only music-volume observer ready' in text
 if muted_profile:assert not result['hardware_volume_observer_created'],'muted mode must not create the hardware-volume observer'
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
 result['actual_worker_create_witnesses']=[dict(lr=x[1],entry=x[2],record=x[3],callback=x[4],payload=x[5])for x in re.finditer(r'Game bootstrap: original worker create witness LR=(0x[0-9a-f]+|0) entry=(0x[0-9a-f]+|0) record=(0x[0-9a-f]+|0) callback=(0x[0-9a-f]+|0) payload=(0x[0-9a-f]+|0); before child start',text)]
 result['actual_worker_payloads']=[dict(owner=x[1],function=x[2],argument=x[3],bytes=24)for x in re.finditer(r'Game bootstrap: original worker payload owner=(0x[0-9a-f]+|0) function=(0x[0-9a-f]+|0) argument=(0x[0-9a-f]+|0) bytes=24; before child start, no post-create read',text)]
 result['worker_lifecycle_observations']=[dict(phase=x[1],token=x[2],parent=x[3],native_tid=int(x[4]),stack_low=x[5],stack_high=x[6],tls=x[7])for x in re.finditer(r'Game bootstrap: worker lifecycle phase=(\w+) token=(0x[0-9a-f]+|0) parent=(0x[0-9a-f]+|0) native_tid=(\d+) stack_low=(0x[0-9a-f]+|0) stack_high=(0x[0-9a-f]+|0) tls=(0x[0-9a-f]+|0); observation only',text)]
 result['worker_wait_observations']=[dict(phase=x[1],import_name=x[2],token=x[3],native_tid=int(x[4]),pc=x[5],sp=x[6],fp=x[7],lr=x[8],x0=x[9],x1=x[10],x2=x[11])for x in re.finditer(r'Game bootstrap: worker wait phase=(ENTER|RETURN) import=(\w+) token=(0x[0-9a-f]+|0) native_tid=(\d+) PC=(0x[0-9a-f]+|0) SP=(0x[0-9a-f]+|0) FP=(0x[0-9a-f]+|0) LR=(0x[0-9a-f]+|0) x0=(0x[0-9a-f]+|0) x1=(0x[0-9a-f]+|0) x2=(0x[0-9a-f]+|0); call observation, not blocked-state proof',text)]
 result['worker_observation_limits']='Numeric same-thread call/lifecycle observations only; no signal model binding, queueing, blocking-state snapshot or GC suspension claim.'
 if gc:
  result['original_collector_requests']=[dict(signal=int(x[1]),target=x[2],record=x[3],epoch=int(x[4]),lr=x[5])for x in re.finditer(r'Game GC: original request signal=(30|24) target=(0x[0-9a-f]+) record=(0x[0-9a-f]+) epoch=(\d+) LR=(0x[0-9a-f]+); source validated before actual pthread_kill',text)]
  result['original_collector_handler_returns']=[dict(target=x[1],epoch=int(x[2]),duplicate=bool(int(x[3])),actual_posts=int(x[4]),observed_record_epoch=int(x[5]))for x in re.finditer(r'Game GC: original stop handler returned target=(0x[0-9a-f]+) epoch=(\d+) duplicate=([01]) actual_posts=(\d+) observed_record_epoch=(\d+);',text)]
  result['original_collector_post_returns']=[dict(target=x[1],ordinal=int(x[2]),lr=x[3])for x in re.finditer(r'Game GC: original sem_post returned target=(0x[0-9a-f]+) ordinal=(\d+) LR=(0x[0-9a-f]+); epoch store follows in original code',text)]
  result['actual_collector_signal_returns']=[dict(signal=int(x[1]),target=x[2],status=int(x[3]))for x in re.finditer(r'Game GC: actual pthread_kill returned signal=(30|24) target=(0x[0-9a-f]+) status=(-?\d+);',text)]
  result['physical_interrupted_frame_checks']=[dict(target=x[1],frame=x[2],published_fp=x[3],original_sp=x[4],stack_high=x[5])for x in re.finditer(r'Game GC: physical interrupted roots verified target=(0x[0-9a-f]+) frame=(0x[0-9a-f]+) published_fp=(0x[0-9a-f]+) original_sp=(0x[0-9a-f]+) stack_high=(0x[0-9a-f]+) GPR=31 Q=32;',text)]
  result['configured_virtual_android_real_uid']=10000 if configured else None
  result['worker_observation_limits']='Only explicitly captured finalizer/single-condwait and exact nested restart profile; requests are pre-call observations, posts and handler returns are original-code observations. No general provider/parent-root safety or collector retention/reclamation claim.'
  result['limits']='Bounded original stop/restart delivery profile only; original observed acknowledgments/epochs do not establish collection correctness, initialization return, a rendered image or a playable game.'
 (b/('game-'+a.profile+'-audit.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print('Full log:',log)
 if not complete:raise SystemExit(1)
if __name__=='__main__':main()
