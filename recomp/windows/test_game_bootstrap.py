"""Verify frozen dual-engine inputs and observe one natural native startup process.

Run from WSL. A fatal original boundary is recorded as incomplete, never passed.
The frame process has no automatic timeout that could terminate a live worker.
"""
import argparse,hashlib,json,pathlib,re,subprocess
from il2cpp_stack_prepare import hashes,absolute
HERE=pathlib.Path(__file__).resolve().parent

def sha(path):
 with pathlib.Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def native_render_returns(text):
 # Record completed invocations in observed order, including actual false.
 # An entered or requested render is not a returned frame.
 return [{'frame':int(m[1]),'continue':m[2]=='1'}for m in re.finditer(r'First frame: original nativeRender returned frame=(\d+) continue=([01])(?:\s|$)',text)]

def validate_cooperative_contract(proof,descriptor,objects,parent_proof=None,grandparent_proof=None,great_grandparent_proof=None,ancestor_chain=None):
 assert (proof['trace_heads'],len(proof['objects']),len(objects))in((456684,3575,3575),(456689,3576,3576),(456700,3577,3577),(456706,3578,3578))and proof['unique_definitions'] is True and proof['missing_direct_targets']==[],'incomplete cooperative cohort'
 assert [(x['path'],x['sha256'])for x in proof['objects']]==[(x['path'],x['sha256'])for x in objects],'cooperative cohort object selection differs'
 contract=proof['contract'];version=contract.get('version',1)
 assert type(version)is int and version in(1,2,3,4,5,6,7,8,9,10,11,12,13,14),'unknown cooperative contract version'
 assert (proof['trace_heads'],len(objects))==((456706,3578)if version==14 else(456700,3577)if version==13 else(456689,3576)if version in(4,5,6,7,8,9,10,11,12)else(456684,3575)),'cooperative contract version/shape differs'
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
 elif version==4:
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
 elif version==5:
  # Exact qualified single-wrapper FCSEL repair over the pinned additive v4.
  acceptance='9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14'
  expected={'profile':'qualified-sparse-unity-fcsel-refresh-v5','input_plan_sha256':'6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9','parent_acceptance_sha256':'5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3','parent_input_plan_sha256':'57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae','sparse_overlay_sha256':'8911f23e4fa017fda6148a1883b176bc841749f73c6e2d900e75dee92d4dd838','fcsel_fixture_acceptance_sha256':'4a0af97c4130ee43c294addde6fba772f4ae792a7c24c7c050b5459864cc6cf7','fcsel_lifter_sha256':'7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126','fcsel_semantics_sha256':'316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3','old_polled_object_sha256':'142b008353679001d265e7288cd2a37d16062b39eebf28f9cdfd246c6fa8d5c3','new_polled_object_sha256':'61dac83d8cb59610d51924673888f4d4c4ab7ad3960d277717100cbde48215c2','target_head':'0x70acc13c','target_end_exclusive':'0x70acc1d0','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v5 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v5 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v5 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v5 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':3,'replaced_object_index':459,'unchanged_objects':3575}.items()),'v5 cooperative replacement scope differs'
  assert type(contract.get('cumulative_changed_indices'))is list and all(type(x)is int for x in contract['cumulative_changed_indices'])and contract['cumulative_changed_indices']==[78,459,1553],'v5 cumulative replacement set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v5 cooperative plan/parent path is absent'
  assert type(parent_proof)is dict and type(parent_proof['contract'].get('version'))is int and parent_proof['contract']['version']==4,'v5 exact parent v4 proof is absent'
  parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent_proof,parent_descriptor,parent_proof['objects'],grandparent_proof,great_grandparent_proof)==4,'v5 parent contract differs'
  assert parent_proof['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v5 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v5 trace count differs'
  assert parent_proof['objects'][459]['sha256']==expected['old_polled_object_sha256']and objects[459]['sha256']==expected['new_polled_object_sha256'],'v5 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent_proof['objects']))if index!=459),'v5 changed a second parent object'
 elif version==6:
  # Exact qualified five-definition caller repair over the pinned v5 cohort.
  acceptance='1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893'
  expected={'profile':'qualified-sparse-unity-fcsel-callers-v6','input_plan_sha256':'3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b','parent_acceptance_sha256':'9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14','parent_input_plan_sha256':'6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9','sparse_overlay_sha256':'5af486e926556cfa0de9d1cfeb01db7ae8e7f73253a076c6fe0f92735d4248bc','fcsel_fixture_acceptance_sha256':'5d7d768ad4332255d483f4c939fd2f9abde75c538a88ecb3ba474e85bc368ede','fcsel_lifter_sha256':'7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126','fcsel_semantics_sha256':'316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3','old_polled_object_sha256':'ab19f24618b5fe9cda0ba6716bd47e2da87026de4427029e377056146cc916e1','new_polled_object_sha256':'d33641796aa959871443201ac2f8ffccc067a19326a5ad0c1f8afe6a73e99e9e','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v6 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v6 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v6 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v6 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':4,'replaced_object_index':161,'unchanged_objects':3575,'changed_function_count':5,'unchanged_functions_in_shard':123}.items()),'v6 cooperative replacement scope differs'
  assert type(contract.get('cumulative_changed_indices'))is list and all(type(x)is int for x in contract['cumulative_changed_indices'])and contract['cumulative_changed_indices']==[78,161,459,1553],'v6 cumulative replacement set differs'
  assert type(contract.get('target_heads'))is list and all(type(x)is str for x in contract['target_heads'])and contract['target_heads']==['0x7042377c','0x704238f4','0x70423908','0x70423918','0x70423928'],'v6 exact changed definitions differ'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v6 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==4 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==5,'v6 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],*ancestor_chain[1:])==5,'v6 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v6 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v6 trace count differs'
  assert parent['objects'][161]['sha256']==expected['old_polled_object_sha256']and objects[161]['sha256']==expected['new_polled_object_sha256'],'v6 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=161),'v6 changed a second parent object'
 elif version==7:
  # Original object initialization with qualified ST2 multiple-structure stores.
  acceptance='5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049'
  expected={'profile':'qualified-sparse-unity-st2-object-v7','input_plan_sha256':'e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621','parent_acceptance_sha256':'1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893','parent_input_plan_sha256':'3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b','sparse_overlay_sha256':'d3078449b770caa61630df63faff7dd6772a2733778e49bf556dbf6c8c0d88d3','st2_fixture_acceptance_sha256':'28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed','original_fixture_acceptance_sha256':'ad2aec850d93eb8cf1650c09636c3d7766f29f14c24cc79389882e2b484cf982','st2_lifter_sha256':'a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa','st2_semantics_sha256':'1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658','old_polled_object_sha256':'5504d089df69da73b12002d7e84dc9e9ecc2cac88a8e0d79b7b12df7d1089d47','new_polled_object_sha256':'910d1a15ce49da0b48e6f54abd879a5b544d624101763845105ad475008ca12b','target_head':'0x707bb458','target_end_exclusive':'0x707bb55c','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v7 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v7 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v7 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v7 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':5,'replaced_object_index':270,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items()),'v7 cooperative replacement scope differs'
  assert type(contract.get('cumulative_changed_indices'))is list and all(type(x)is int for x in contract['cumulative_changed_indices'])and contract['cumulative_changed_indices']==[78,161,270,459,1553],'v7 cumulative replacement set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v7 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==5 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==6,'v7 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==6,'v7 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v7 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v7 trace count differs'
  assert parent['objects'][270]['sha256']==expected['old_polled_object_sha256']and objects[270]['sha256']==expected['new_polled_object_sha256'],'v7 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=270),'v7 changed a second parent object'
 elif version==8:
  # One fully qualified vector batch over the exact current selected parent.
  acceptance='4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569'
  expected={'profile':'qualified-fcsel-vector-batch-v8','input_plan_sha256':'d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4','parent_acceptance_sha256':'5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049','parent_input_plan_sha256':'e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621','batch_acceptance_sha256':'a790ab1e8cbfeb90b5c91b533ee161626e1a2ce10d3b730a87ee06c72060c09a','batch_manifest_sha256':'faecdde9e83aa7fa9bbfe2a1264f5e914a6c9f3aa970431ef5d3807774dfd864','checker_qualification_sha256':'09c13e1636abe9b566e7fc26ae6829f46a9c0126dce08cef16a6815152ba7ba5','fcsel_fixture_acceptance_sha256':'b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b','fcsel_lifter_sha256':'a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa','fcsel_semantics_sha256':'1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658','compiled_identity_sha256':'70c0e7ecedf707a43b968bd2bdf48419951d31e96781ca6cf842c98449063938','replacement_vector_sha256':'a5c19e5bf534730f9e697d5d237a98f3f41ad324e4956109a56c92c96d19c70b','condition_qualification_sha256':'cd99aa583e4121e4a2369b9348d4731914f103bc64c902166c7a3d9daf867b56','proof_mode':'exact-attributed-fcsel-transport-v1','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v8 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v8 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v8 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':True,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False,'non_fcsel_instructions_preserved':True,'all_replacements_qualified':True}.items()),'v8 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'replacement_count':556,'unchanged_objects':3020,'changed_function_count':2164,'legacy_fcsel_copy_count':5766}.items()),'v8 cooperative replacement scope differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v8 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==6 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==7,'v8 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==7,'v8 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v8 parent plan differs'
  vector=contract.get('replacement_vector');assert type(vector)is list and len(vector)==556,'v8 replacement vector shape differs'
  payload=[];changed=set();previous=-1
  for row in vector:
   assert type(row)is dict and set(row)=={'index','old_path','old_sha256','new_path','new_sha256'},'v8 replacement row shape differs'
   index=row['index'];assert type(index)is int and previous<index<3576,'v8 replacement indices differ'
   assert all(type(row[k])is str and row[k]and not re.search('[\x00-\x1f\x7f-\x9f]',row[k])for k in ('old_path','new_path','old_sha256','new_sha256')),'v8 replacement descriptor encoding differs'
   assert all(re.fullmatch('[0-9a-f]{64}',row[k])for k in ('old_sha256','new_sha256')),'v8 replacement descriptor hash differs'
   payload.append(str(index)+'\t'+row['old_path']+'\t'+row['old_sha256']+'\t'+row['new_path']+'\t'+row['new_sha256']+'\n');previous=index;changed.add(index)
   assert (parent['objects'][index]['path'],parent['objects'][index]['sha256'])==(row['old_path'],row['old_sha256']),'v8 old replacement descriptor differs'
   assert (objects[index]['path'],objects[index]['sha256'])==(row['new_path'],row['new_sha256']),'v8 new replacement descriptor differs'
  try:vector_hash=hashlib.sha256(''.join(payload).encode('utf-8')).hexdigest()
  except UnicodeError:raise AssertionError('v8 replacement descriptor encoding differs')
  assert vector_hash==expected['replacement_vector_sha256'],'v8 replacement payload differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index not in changed),'v8 changed an unlisted parent object'
 elif version==9:
  acceptance='9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea'
  expected={'profile':'qualified-sparse-unity-st2-constructor-v9','input_plan_sha256':'d3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058','parent_acceptance_sha256':'4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569','parent_input_plan_sha256':'d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4','sparse_overlay_sha256':'6791fa803510090f27a2b0d08a2f371fd9b8b2201bf555f14da2214f30d2ce4d','st2_fixture_acceptance_sha256':'28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed','original_fixture_acceptance_sha256':'6b6dbfb3d20b080b4f029c410a776d088a28dbe7e0f05c9a68b4c739b30f3597','st2_lifter_sha256':'a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa','st2_semantics_sha256':'1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658','old_polled_object_sha256':'963b56f892d06428753bad028ad396eb97eeaff9d9ee8770fc9c144e62aa5d48','new_polled_object_sha256':'ad6b08dbcebe0d007c60a6ccc6a8b71f6a8be8a80693cec4fda0223fab53fe5e','target_head':'0x707520c4','target_end_exclusive':'0x707521bc','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v9 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v9 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v9 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v9 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'inherited_vector_replacements':556,'replaced_object_index':249,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items()),'v9 cooperative replacement scope differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v9 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==7 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==8,'v9 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==8,'v9 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v9 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v9 trace count differs'
  assert parent['objects'][249]['sha256']==expected['old_polled_object_sha256']and objects[249]['sha256']==expected['new_polled_object_sha256'],'v9 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=249),'v9 changed a second parent object'
 elif version==10:
  acceptance='0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5'
  expected={'profile': 'qualified-sparse-unity-fcvtzu-fixed-v10', 'input_plan_sha256': 'ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3', 'parent_acceptance_sha256': '9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea', 'parent_input_plan_sha256': 'd3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058', 'sparse_overlay_sha256': '303e3bfd8a245e354eff8c1a8219fe2e7f1cb3499823bafd8fa38675d1f0a1c8', 'fcvtzu_fixed_fixture_acceptance_sha256': '73a166570129008d44061237cea546504534c0f6c79f59d4242ca17b4506e675', 'original_fixture_acceptance_sha256': '87b27ab5a230225ee1de843392215c0a0a7d3136839a86dad21dace684514f7b', 'compiled_identity_sha256': '2886ee6e5252abe176a99a2f0ae429fb6d8f89cfd2b869fc59e19c4de796cac9', 'fcvtzu_fixed_lifter_sha256': '3d6beaa96e010c7b5424fba8960fe19eca3c261d6da164df08e4adadd75fbf88', 'fcvtzu_fixed_semantics_sha256': '0d5c2c427b2f43d2f5b01db564e3141837c86df0afe79dee5c32ae48c3237409', 'old_polled_object_sha256': 'f30ae550a205c93624049b720eca1a88503cc6335744372340ca68162d07b418', 'new_polled_object_sha256': '87149852496090c1c5084d79e024514c07da34c60974f537cfe3f4fdb655200f', 'target_head': '0x70362a2c', 'target_end_exclusive': '0x70362a8c', 'optimization': '-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v10 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v10 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v10 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v10 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'inherited_vector_replacements':556,'replaced_object_index':123,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items()),'v10 cooperative replacement scope differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v10 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==8 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==9,'v10 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==9,'v10 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v10 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v10 trace count differs'
  assert parent['objects'][123]['sha256']==expected['old_polled_object_sha256']and objects[123]['sha256']==expected['new_polled_object_sha256'],'v10 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=123),'v10 changed a second parent object'
 elif version==11:
  acceptance='64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e'
  expected={'profile':'qualified-sparse-unity-st3-store-v11','input_plan_sha256':'57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93','parent_acceptance_sha256':'0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5','parent_input_plan_sha256':'ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3','sparse_overlay_sha256':'1c832a98fbdd491c53038ca20779d36e8f47f6fde62a29d11d8546abb3293118','st3_fixture_acceptance_sha256':'15404cfbfca518caa3393c428e9585d0456086232892ff95e75b73d6cfabfa98','original_block_fixture_acceptance_sha256':'4f6bfd4533f5c04514e433fb6ddef2592823d403454f32aa17ff465589c68b25','compiled_identity_sha256':'a2ab71354a31cd0fee124252d5310b760a5915875206458129a760f32a9c97b7','st3_lifter_sha256':'8e5b529295a67f9387dbf1d1dcbed4e71aebcb741e11f09103a17899ee44df2c','st3_semantics_sha256':'e289429a3da24b4dd08b4dcc1471572f06d940cb2958db8e66dd8554965c7b30','old_polled_object_sha256':'be26cf4231b66f7f069f0aa8b95e2ec784b0ed97a6cfb864182215917162f577','new_polled_object_sha256':'cddd5852024875161cef458b8b3d1e825721a32965ad79f66fc7157d92ab53b6','target_head':'0x704fd850','target_end_exclusive':'0x704fdb60','optimization':'-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v11 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v11 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v11 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v11 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'inherited_vector_replacements':556,'replaced_object_index':200,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items()),'v11 cooperative replacement scope differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v11 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==9 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==10,'v11 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==10,'v11 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v11 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v11 trace count differs'
  assert parent['objects'][200]['sha256']==expected['old_polled_object_sha256']and objects[200]['sha256']==expected['new_polled_object_sha256'],'v11 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=200),'v11 changed a second parent object'
 elif version==12:
  acceptance='34a41fc3f8fa21e5df3d23d702d455e52805bfd21a6f33161b5176245d241601'
  expected={'profile': 'qualified-sparse-unity-ushll-mask-v12', 'input_plan_sha256': '0385129c17c6b2db060aa938127edf2993490b78b4adcbd551d24840fa006aea', 'parent_acceptance_sha256': '64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e', 'parent_input_plan_sha256': '57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93', 'sparse_overlay_sha256': '03b57f5e4a16488f364975e9f79c406308454fafe46f5a47056a5f30caedeebf', 'ushll_fixture_acceptance_sha256': '623082c62ae71210756c08a92eec56bf0e3e8b94cc07d6650818e855d0b41e9b', 'original_block_fixture_acceptance_sha256': 'be35d41e14bd385469ddb11778e1cb4ff2a22936765b658d83b4a0d7824fbecd', 'compiled_identity_sha256': 'd2918f90adb54fa2d720b9ca9a6e7c776fed66bb0fe58af54ad5065feb7899b8', 'ushll_lifter_sha256': '8e5b529295a67f9387dbf1d1dcbed4e71aebcb741e11f09103a17899ee44df2c', 'ushll_semantics_sha256': 'e289429a3da24b4dd08b4dcc1471572f06d940cb2958db8e66dd8554965c7b30', 'old_polled_object_sha256': '8d74124a34e0511ba0bbaf71d11c031290d9e8db431bdd228c5775b834ef2e42', 'new_polled_object_sha256': 'c28559fea099d8d2091ec876061345fd7b6aa80e6740745cf30586e9930ea5d5', 'target_head': '0x702b3d34', 'target_end_exclusive': '0x702b4034', 'optimization': '-O2'}
  assert re.fullmatch('[0-9a-f]{64}',acceptance)and all(re.fullmatch('[0-9a-f]{64}',v)for k,v in expected.items()if k.endswith('_sha256')),'v12 cooperative pins are not qualified'
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v12 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v12 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift':False,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False}.items()),'v12 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'incremental_sparse_relifts':1,'inherited_vector_replacements':556,'replaced_object_index':94,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items()),'v12 cooperative replacement scope differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v12 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==10 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==11,'v12 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==11,'v12 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v12 parent plan differs'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456689,'v12 trace count differs'
  assert parent['objects'][94]['sha256']==expected['old_polled_object_sha256']and objects[94]['sha256']==expected['new_polled_object_sha256'],'v12 replacement object differs'
  assert all((current['path'],current['sha256'])==(previous['path'],previous['sha256'])for index,(current,previous)in enumerate(zip(proof['objects'],parent['objects']))if index!=94),'v12 changed a second parent object'
 elif version==13:
  acceptance='02d5545fd8da4a4103e3e64e364786d2fc8629f84fb88a855ada5afee8dfd16a'
  expected={'profile': 'qualified-unity-plane-switch-v13', 'input_plan_sha256': '2dac17b452eab5e5d01419a5ca8c80fb201641724f1a24213bf84312a678aebb', 'parent_acceptance_sha256': '34a41fc3f8fa21e5df3d23d702d455e52805bfd21a6f33161b5176245d241601', 'parent_input_plan_sha256': '0385129c17c6b2db060aa938127edf2993490b78b4adcbd551d24840fa006aea', 'additive_candidate_sha256': 'f0f28ce13a622c239a499950d429860899642b59e3cc674813d2da61e47d90fb', 'original_dispatch_fixture_acceptance_sha256': 'a0f5edc580780807c0e5b6050ef514f25825b45194691a1614a333c563e39659', 'lifter_sha256': '8e5b529295a67f9387dbf1d1dcbed4e71aebcb741e11f09103a17899ee44df2c', 'semantics_sha256': 'e289429a3da24b4dd08b4dcc1471572f06d940cb2958db8e66dd8554965c7b30', 'new_polled_object_sha256': '6f455965ea0d584e80428b8a30372bfbb5211a83ac9455a07466b5327d99ab5c', 'helper_overlay_sha256': 'c28604eb62e0a879d037152711b6bf9e3af1d555d7f1d348a2bff8f4fdd443b3', 'helper_family_acceptance_sha256': '7a799a7745ba530a93444b453e37759ee186611bd0408600899e9c51d6f96b06', 'helper_lifter_sha256': 'bce34d408b57a2eaa085194599fe20a0fd34325d0d34327426b6c226fd04253d', 'helper_semantics_sha256': '5d2fc4bb5f4c8be48e82c5d291a8d0bda5c0e3300cda166b871b37e5650e970c', 'old_helper_object_sha256': '52988ae65b3135bbca2a40e41f8c9d2f9cbea06f831dc7526b3f023ce90b88a3', 'new_helper_object_sha256': '9b6c22b8fe1114a9c73888683621ce3248f62c808cc3cb85aea422728a70f0e3', 'helper_target_head': '0x70ae31f0', 'optimization': '-O2'}
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v13 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v13 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift': False, 'source_ir_and_semantics_preserved': False, 'existing_objects_preserved': False, 'no_global_semantics_refresh': True, 'production_signal_delivery_enabled': False}.items()),'v13 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'added_object_index': 3576, 'added_objects': 1, 'added_trace_count': 11, 'preserved_objects': 3575, 'changed_existing_objects': 1, 'replaced_object_index': 466, 'changed_function_count': 1, 'unchanged_functions_in_shard': 105, 'inherited_vector_replacements': 556, 'parent_trace_heads': 456689}.items()),'v13 additive scope differs'
  assert type(contract.get('added_trace_heads'))is list and all(type(x)is str for x in contract['added_trace_heads'])and contract['added_trace_heads']==['0x70ae3f7c', '0x70ae3f84', '0x70ae400c', '0x70ae4094', '0x70ae4134', '0x70ae4208', '0x70ae42ec', '0x70ae4300', '0x70ae4308', '0x70ae4310', '0x70ae4428'],'v13 exact added head set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in ('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v13 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==11 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==12,'v13 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==12,'v13 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v13 parent plan differs'
  assert type(objects[466].get('path'))is str and objects[466]['path']and parent['objects'][466]['sha256']==expected['old_helper_object_sha256']and objects[466]['sha256']==expected['new_helper_object_sha256'],'v13 helper replacement differs'
  assert all((now['path'],now['sha256'])==(old['path'],old['sha256'])for index,(now,old)in enumerate(zip(proof['objects'][:3576],parent['objects']))if index!=466),'v13 changed a second existing parent object'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456700,'v13 trace count differs'
  assert type(objects[3576].get('path'))is str and objects[3576]['path']and objects[3576]['sha256']==expected['new_polled_object_sha256'],'v13 additive object differs'
 else:
  acceptance='0496c62a7a1db0e6325c94b946c93fca8427847c4972cc6748dbc85a673b3f30';expected={'profile': 'qualified-additive-fmod-pure-callbacks-v14', 'input_plan_sha256': 'd506ef966942e3858c3f8b991f33d6a91c0a4390a07c26d3aff65d67bbb50bbe', 'parent_acceptance_sha256': '02d5545fd8da4a4103e3e64e364786d2fc8629f84fb88a855ada5afee8dfd16a', 'parent_input_plan_sha256': '2dac17b452eab5e5d01419a5ca8c80fb201641724f1a24213bf84312a678aebb', 'additive_candidate_sha256': 'd003701628ab5a25d1dd0c8807d9140e10d90f1a34fc921d7a40b8581553ba24', 'original_callbacks_fixture_acceptance_sha256': 'b1f943a722126baa3687c8a9c85bb9adf193e3f823460a27221725b76b0bcb40', 'lifter_sha256': 'bce34d408b57a2eaa085194599fe20a0fd34325d0d34327426b6c226fd04253d', 'semantics_sha256': '5d2fc4bb5f4c8be48e82c5d291a8d0bda5c0e3300cda166b871b37e5650e970c', 'new_polled_object_sha256': '2a2e7c19a20de2b8b96bde3a7c25ada9c6ead42acf707e2175dd565f25ec91f1', 'optimization': '-O2'}
  assert type(descriptor.get('acceptance_sha256'))is str and descriptor['acceptance_sha256']==acceptance,'unqualified v14 cooperative proof hash'
  assert all(type(contract.get(k))is str and contract[k]==v for k,v in expected.items()),'unqualified v14 cooperative provenance'
  assert all(contract.get(k)is v for k,v in {'no_relift': False, 'source_ir_and_semantics_preserved': False, 'existing_objects_preserved': True, 'no_global_semantics_refresh': True, 'production_signal_delivery_enabled': False}.items()),'v14 cooperative policy disclosure differs'
  assert all(type(contract.get(k))is int and contract[k]==v for k,v in {'added_object_index': 3577, 'added_objects': 1, 'added_trace_count': 6, 'preserved_objects': 3577, 'parent_trace_heads': 456700, 'inherited_vector_replacements': 556}.items()),'v14 additive scope differs'
  assert type(contract.get('added_trace_heads'))is list and all(type(h)is str for h in contract['added_trace_heads'])and contract['added_trace_heads']==['0x70b3bbfc', '0x70b3bc5c', '0x70b3bd90', '0x70b3be80', '0x70b3bef8', '0x70b3bf1c'],'v14 exact added head set differs'
  assert all(type(contract.get(k))is str and contract[k]for k in('input_plan_path','parent_acceptance_path','parent_input_plan_path')),'v14 cooperative plan/parent path is absent'
  assert type(ancestor_chain)is list and len(ancestor_chain)==12 and type(ancestor_chain[0])is dict and ancestor_chain[0]['contract'].get('version')==13,'v14 exact ancestor chain is absent'
  parent=ancestor_chain[0];parent_descriptor={'acceptance_path':contract['parent_acceptance_path'],'acceptance_sha256':contract['parent_acceptance_sha256']}
  assert validate_cooperative_contract(parent,parent_descriptor,parent['objects'],ancestor_chain=ancestor_chain[1:])==13,'v14 parent contract differs'
  assert parent['contract']['input_plan_sha256']==contract['parent_input_plan_sha256'],'v14 parent plan differs'
  assert proof['objects'][:3577]==parent['objects'],'v14 changed an existing parent object'
  assert type(proof.get('trace_heads'))is int and proof['trace_heads']==456706,'v14 trace count differs'
  assert type(objects[3577].get('path'))is str and objects[3577]['path']and objects[3577]['sha256']==expected['new_polled_object_sha256'],'v14 additive object differs'
 return version


def load_cooperative_parent(proof):
 version=proof['contract'].get('version',1)
 if type(version)is not int or version not in(3,4,5,6,7,8,9,10,11,12,13,14):return None
 contract=proof['contract']
 anchors={3:('7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95'),4:('68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67','4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb'),5:('5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3','57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae'),6:('9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14','6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9')}
 anchors[7]=('1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893','3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b')
 anchors[8]=('5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049','e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621')
 anchors[9]=('4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569','d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4')
 anchors[10]=('9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea','d3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058')
 anchors[11]=('0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5','ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3')
 anchors[12]=('64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e', '57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93')
 anchors[13]=('34a41fc3f8fa21e5df3d23d702d455e52805bfd21a6f33161b5176245d241601', '0385129c17c6b2db060aa938127edf2993490b78b4adcbd551d24840fa006aea')
 anchors[14]=('02d5545fd8da4a4103e3e64e364786d2fc8629f84fb88a855ada5afee8dfd16a', '2dac17b452eab5e5d01419a5ca8c80fb201641724f1a24213bf84312a678aebb')
 assert (contract.get('parent_acceptance_sha256'),contract.get('parent_input_plan_sha256'))==anchors[version],f'v{version} parent anchors differ'
 assert all(type(contract.get(k))is str and contract[k]for k in ('parent_acceptance_path','parent_input_plan_path')),f'v{version} parent path is absent'
 assert sha(contract['parent_acceptance_path'])==contract['parent_acceptance_sha256'],f'v{version} parent proof file differs'
 parent=json.loads(pathlib.Path(contract['parent_acceptance_path']).read_text())
 assert sha(contract['parent_input_plan_path'])==contract['parent_input_plan_sha256'],f'v{version} parent plan file differs'
 return parent

def load_cooperative_ancestors(proof):
 version=proof['contract'].get('version')
 assert type(version)is int and version in(6,7,8,9,10,11,12,13,14),'ancestor loading requires v6 through v14'
 result=[];current=proof
 for expected_version in range(version-1,1,-1):
  parent=load_cooperative_parent(current)
  assert type(parent)is dict and type(parent['contract'].get('version'))is int and parent['contract']['version']==expected_version,'v6 ancestor version differs'
  result.append(parent);current=parent
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--profile',choices=['default','init','surface','frame','frame-muted','frame-muted-gc'],default='default');p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);p.add_argument('--verify-only',action='store_true');p.add_argument('--first-frame',action='store_true');a=p.parse_args();b=a.build.resolve();frame=a.profile in ('frame','frame-muted','frame-muted-gc');gc=a.profile=='frame-muted-gc';muted_profile=a.profile in ('frame-muted','frame-muted-gc')
 if a.first_frame and not gc:p.error('--first-frame requires --profile frame-muted-gc')
 m=json.loads((b/'game_inputs.json').read_text());record=json.loads((b/'game_build.json').read_text());assert m['status']=='prepared'and (m['union_trace_count'],len(m['objects']))in((456684,3575),(456689,3576),(456700,3577),(456706,3578))
 expected={**m['original_object_hashes'],**m['input_hashes'],**{x['path']:x['sha256']for x in m['objects']},**{str(b/'sources'/k):v for k,v in m['source_sha256'].items()},**{str(b/k):v for field in ['frozen_support_sha256','generated_header_sha256']for k,v in m[field].items()},str(b/'game_inputs.json'):record['inputs_sha256'],str(b/'bunker-game-bootstrap.exe'):record['executable_sha256'],str(b/'libz-inflate.a'):m['zlib_sha256'],str(b/'host-source.tar'):m['host_archive_sha256']}
 expected.update({str(pathlib.Path(m['angle_directory'])/k):v for k,v in m['angle_dll_sha256'].items()})
 expected.update({str(b/'native'/('lib'+mod['name']+'.so')):mod['sha256']for mod in m['modules']})
 poll_cohort=m.get('cooperative_poll_cohort')
 assert m['union_trace_count']not in(456689,456700,456706)or poll_cohort,'additive shape requires an accepted cooperative cohort'
 if gc and(not poll_cohort or record.get('collector_delivery_profile')!='original-finalizer-single-condwait-v1'):raise RuntimeError('Original collector profile is unavailable: explicit build option and accepted cooperative cohort are required')
 if poll_cohort:expected[poll_cohort['acceptance_path']]=poll_cohort['acceptance_sha256']
 def verify():
  win=[pathlib.Path(k)for k in expected if k.startswith('/mnt/')];actual=hashes(win)
  assert all(actual[str(absolute(k))]==expected[str(k)]for k in win),'frozen Windows artifact differs'
  assert all(sha(k)==v for k,v in expected.items()if not k.startswith('/mnt/')),'frozen WSL artifact differs'
 verify()
 if poll_cohort:
  proof=json.loads(pathlib.Path(poll_cohort['acceptance_path']).read_text())
  if proof['contract'].get('version')in(6,7,8,9,10,11,12,13,14):
   ancestor_chain=load_cooperative_ancestors(proof)
   version=validate_cooperative_contract(proof,poll_cohort,m['objects'],ancestor_chain=ancestor_chain)
   for node in [proof]+ancestor_chain[:-1]:
    expected[node['contract']['parent_acceptance_path']]=node['contract']['parent_acceptance_sha256'];expected[node['contract']['parent_input_plan_path']]=node['contract']['parent_input_plan_sha256']
  else:
   parent_proof=load_cooperative_parent(proof)
   grandparent_proof=load_cooperative_parent(parent_proof)if proof['contract'].get('version')in(4,5)else None
   great_grandparent_proof=load_cooperative_parent(grandparent_proof)if proof['contract'].get('version')==5 else None
   version=validate_cooperative_contract(proof,poll_cohort,m['objects'],parent_proof,grandparent_proof,great_grandparent_proof)
  assert m['union_trace_count']==proof['trace_heads'],'manifest/cohort head count differs'
  if version in(3,4,5):
   expected[proof['contract']['parent_acceptance_path']]=proof['contract']['parent_acceptance_sha256'];expected[proof['contract']['parent_input_plan_path']]=proof['contract']['parent_input_plan_sha256']
  if version in(4,5):
   expected[parent_proof['contract']['parent_acceptance_path']]=parent_proof['contract']['parent_acceptance_sha256'];expected[parent_proof['contract']['parent_input_plan_path']]=parent_proof['contract']['parent_input_plan_sha256']
  if version==5:
   expected[grandparent_proof['contract']['parent_acceptance_path']]=grandparent_proof['contract']['parent_acceptance_sha256'];expected[grandparent_proof['contract']['parent_input_plan_path']]=grandparent_proof['contract']['parent_input_plan_sha256']
  if version in(2,3,4,5,6,7,8,9,10,11,12,13,14):
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
  if a.first_frame:command+=['--first-frame']
 with log.open('wb')as out:run=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
 verify();text=log.read_text(errors='replace')
 ctors=re.findall(r'Game bootstrap: IL2CPP constructor (\d+)/9 entry=',text);finis=re.findall(r'Game bootstrap: IL2CPP finalizer (\d+)/2 entry=',text)
 lifecycle_order=ctors==list(map(str,range(1,len(ctors)+1)))and finis==list(map(str,range(1,len(finis)+1)))and len(ctors)<=9 and len(finis)<=2
 render_returns=native_render_returns(text)
 frame_returned=bool(render_returns)or'first nativeRender returned continue='in text
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
 result['first_frame_diagnostic_requested']=a.first_frame
 result['native_render_returns']=render_returns
 result['successful_presentations']=[int(n)for n in re.findall(r'First frame: EGL RETURN eglSwapBuffers x0=0x1 successfulPresentations=(\d+)',text)]
 result['first_frame_witness']='First frame: witness=1 'in text
 result['first_frame_png_sha256']=sha(storage/'first-frame.png')if(storage/'first-frame.png').is_file()else None
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
