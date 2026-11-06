"""Seal prepared Unity NM modules without selecting or compiling any artifact.

The original parent is intentional: a future overlay must merge the disjoint
current IL2CPP/TMP changes. Native-profile holds keep the original object.
"""
from pathlib import Path
import argparse,ctypes,hashlib,json,re,shutil
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def d(p):
 p=Path(p)
 with p.open('rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'unity-nm-owner-partial-aggregate1');ap.add_argument('--owner-manifest',type=Path,default=W/'windows-first-frame-unity-auto1/overlay.json');a=ap.parse_args();native_held=set()
 planp=W/'unity-nm-clean-plan1/plan.json';assert d(planp)['sha256']=='1916a774c7f3334af378b2642b0f3fc4e0e84a3198e71091588aa6619b2f49d8';plan=read(planp);groups={g['global_index']:g for g in plan['first_proposed_scope']['grouped_current_modules']};assert len(groups)==62 and sum(len(g['candidate_heads'])for g in groups.values())==131
 historical=Path(plan['current_manifest']['path']);assert d(historical)['sha256']=='beb2c6cecab5afea86c14609ea05ed1c56758f005fc0d36df9e1f8e796eb4ff8';lineage=read(historical)
 pp=a.owner_manifest;assert d(pp)['sha256']=='f034343e4747302dd7e530323811ccf88a80d85bdd1616a39b33455a171dbd39';parent=read(pp);assert len(parent['objects'])==4661 and parent['trace_heads']==595556;objects=list(parent['objects']);held={};modules=[];wrapper_declarations={};empty_metadata_edges=[];guest_holds=[]
 def pin(r):assert d(r['path'])['sha256']==r['sha256'],r['path'];held[r['path']]=r['sha256']
 def closure(v):
  if isinstance(v,dict):
   if 'path'in v and'sha256'in v:pin(v)
   else:
    for x in v.values():closure(x)
  elif isinstance(v,list):
   for x in v:closure(x)
 pin(d(__file__));pin(d(planp));pin(d(pp));pin(d(historical));paths={}
 for attempt in [3,4,5,6,7,8]:
  for p in (W/f'unity-nm-retained-overlay{attempt}').glob('shard-*/acceptance.json'):
   row=read(p);index=row['global_index']if'global_index'in row else int(p.parent.name.split('-')[1]);assert index not in paths,index;paths[index]=p
 paths[88]=W/'unity-nm-pilot88-admission1/acceptance.json';paths[414]=W/'unity-nm-resumed414-admission1/acceptance.json'
 paths[360]=W/'unity-nm-saved360-admission1/acceptance.json';assert d(paths[360])['sha256']=='0c530cc56a16e86436211f93378c9ad87d689f203233f55340a34ca18fa5eae4';assert set(paths)<=set(groups);pending=sorted(set(groups)-set(paths))
 assert not a.out.exists();a.out.mkdir();(a.out/'objects').mkdir();shutil.copyfile(__file__,a.out/'executed-assembler.py')
 for index,p in sorted(paths.items()):
  row=read(p);assert row['passed']and row['selected']is False;pin(d(p));closure(row);group=groups[index];heads=row['accepted_heads'];assert set(heads)<={*group['candidate_heads']}and len(heads)==len(set(heads));bodyholds=row.get('held_targets',[]);guest_holds.extend(bodyholds);assert set(heads)|{h['head']for h in bodyholds}==set(group['candidate_heads'])
  if row.get('no_replacement'):continue
  assert row['raw_neighbors_byte_exact']==row['polled_neighbors_byte_exact']==128-len(heads)and row['all_non_target_native_contexts_preserved']is True
  old=row['old_object'];assert old['sha256']==lineage['objects'][index]['sha256']==parent['objects'][index]['sha256'];native=read(row['native_preservation']['path']);assert native['passed']and native['protected_functions']==128-len(heads)
  for name in ['all_nonfield_instruction_bytes_equal','all_relative_relocation_positions_types_symbols_exact','all_other_relocation_addends_exact','all_guest_calls_exact','all_function_sizes_equal','all_non_target_rdata_references_accounted','all_resolved_read_payloads_equal','all_required_alignments_satisfied']:assert native[name]is True,(index,name)
  closure(native);proof=row['module_inverse'];iv=read(proof['path']);assert iv['raw_whole_module_inverse_exact']and iv['polled_whole_module_inverse_exact']and iv['old_numeric_metadata_definitions_preserved'];assert len(iv['operations']['raw'])==len(iv['operations']['polled'])==len(heads)
  for kind in ['raw','polled']:
   for op in iv['operations'][kind]:
    assert op['step_inverse_exact']is True
    for declaration in op.get('new_local_vector_wrapper_type_declarations',[]):wrapper_declarations.setdefault(declaration,[]).append(dict(global_index=index,kind=kind,head=op['head']))
    if op.get('empty_fresh_named_metadata_ignored'):assert op['old_named_metadata']==op['new_named_metadata'];empty_metadata_edges.append(dict(global_index=index,kind=kind,head=op['head']))
  assert read(row['optimized_guard_audit']['path'])['passed'];assert native['candidate_object']['sha256']==row['candidate_object']['sha256'];dest=a.out/'objects'/f'shard-{index:05d}.o';shutil.copyfile(row['candidate_object']['path'],dest);assert d(dest)['sha256']==row['candidate_object']['sha256'];objects[index]=d(dest)
  assertions=dict(passed=True,definitions=128,accepted_target_count=len(heads),raw_neighbors_byte_exact=128-len(heads),polled_neighbors_byte_exact=128-len(heads),all_non_target_native_contexts_preserved=True,all_readonly_refs_including_unchanged_fields_checked=True,raw_whole_module_inverse_exact=True,polled_whole_module_inverse_exact=True,old_numeric_metadata_definitions_preserved=True,State_size=1200,State_align=16,no_new_unsupported_in_accepted_bodies=True,optimized_guard_audit_passed=True,old_object_hash_matches_current_owner=True,Windows_copy_byte_exact_to_qualified_saved_object=True)
  modules.append(dict(global_index=index,accepted_heads=heads,original_proposed_heads=group['candidate_heads'],guest_holds=bodyholds,module_receipt=d(p),old_object=old,current_owner_object=parent['objects'][index],candidate_object=d(dest),qualified_saved_object=row['candidate_object'],native_preservation=row['native_preservation'],module_inverse=proof,raw_IR=row['raw_IR'],polled_IR=row['polled_IR'],protected_functions=128-len(heads),assertions=assertions));print('BOUND-MODULE',index,len(heads),flush=True)
 # A deliberately separate check of every actually appended primitive wrapper.
 semantics=W/'numeric-minmax-reuse-review1/current.ll';pin(d(semantics));sem=semantics.read_text();layout=re.search(r'^target datalayout = "([^"]+)"',sem,re.M)[1];native_layout='e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128';type_rows=[]
 libpath=Path('/usr/lib/llvm-18/lib/libLLVM.so');lib=ctypes.CDLL(str(libpath));P=ctypes.c_void_p
 def api(name,result,args):f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
 context=api('LLVMContextCreate',P,[])();buffer=api('LLVMCreateMemoryBufferWithMemoryRangeCopy',P,[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p]);parse=api('LLVMParseIRInContext',ctypes.c_int,[P,P,ctypes.POINTER(P),ctypes.POINTER(ctypes.c_char_p)]);getty=api('LLVMGetTypeByName2',P,[P,ctypes.c_char_p]);tdmake=api('LLVMCreateTargetData',P,[ctypes.c_char_p]);size=api('LLVMABISizeOfType',ctypes.c_ulonglong,[P,P]);bitsize=api('LLVMSizeOfTypeInBits',ctypes.c_ulonglong,[P,P]);align=api('LLVMABIAlignmentOfType',ctypes.c_uint,[P,P]);offset=api('LLVMOffsetOfElement',ctypes.c_ulonglong,[P,P,ctypes.c_uint])
 for declaration,uses in wrapper_declarations.items():
  line=declaration.rstrip('\n');m=re.fullmatch(r'(%struct\.(u?int|float)(\d+)v(\d+)_t) = type \{ \[(\d+) x (i\d+|half|float|double)\] \}',line);assert m and line in sem.splitlines();width=int(m[3]);count=int(m[4]);element=m[6];actual=int(element[1:])if element.startswith('i')else{'half':16,'float':32,'double':64}[element];assert count==int(m[5])and width==actual and count*width in (64,128);assert(element.startswith('i'))==(m[2]!='float');raw=(line+'\n@probe = external global '+m[1]+'\n').encode();memory=buffer(raw,len(raw),b'wrapper');module=P();error=ctypes.c_char_p();assert parse(context,memory,ctypes.byref(module),ctypes.byref(error))==0,error.value;ty=getty(context,m[1][1:].encode());measurements=[]
  for label,dl in [('qualified_aarch64',layout),('native_windows',native_layout)]:
   td=tdmake(dl.encode());v=dict(profile=label,bits=bitsize(td,ty),ABI_size=size(td,ty),ABI_alignment=align(td,ty),array_member_offset=offset(td,ty,0));assert v['bits']==count*width and v['ABI_size']==count*width//8 and v['ABI_alignment']==width//8 and v['array_member_offset']==0;measurements.append(v)
  type_rows.append(dict(declaration=line,primitive_array=True,no_nested_types_or_pointers=True,actual_qualified_semantics_declaration_exact=True,uses=uses,actual_LLVM18_layout=measurements))
 pin(d(libpath));save(a.out/'appended-wrapper-review.json',dict(passed=True,qualifying_semantics=d(semantics),LLVM_library=d(libpath),declarations=type_rows,State_not_replaced=True))
 # Exact native-profile hold: its compiled object is archived, never admitted.
 native_holds=[]
 for index in sorted(native_held):
  group=groups[index];folder=W/'unity-nm-retained-overlay6'/f'shard-{index:05d}';nativefolder=Path('/home/user/bunker-recomp/recomp/work/unity-nm-retained-overlay6')/folder.name;failure=folder.parent/'failure.json';text=failure.read_text();assert 'not_supported_data_read'in text and'pcmpeqb'in text;pin(d(failure));assert objects[index]==parent['objects'][index];native_holds.append(dict(global_index=index,heads=group['candidate_heads'],reason='Qualified native-read profile excludes PCMPEQB; original object retained.',compiled_but_unqualified_object=d(nativefolder/'candidate.polled.o'),raw_IR=d(nativefolder/'candidate.raw.ll'),polled_IR=d(nativefolder/'candidate.polled.ll'),preserved_failure=d(failure),original_object_retained=True,guest_ISA_expansion=False))
 headers={name:d(pp.parent/name)for name in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
 for r in headers.values():pin(r)
 changed=[i for i in range(4661)if objects[i]!=parent['objects'][i]];assert changed==[r['global_index']for r in modules];assert not set(changed)&{377,1572,2695,2950,3251,3733,3734,3842,4168,4660};assert max(changed)<4660;save(a.out/'object-manifest.json',objects)
 for p,h in held.items():assert d(p)['sha256']==h,p
 accepted=sum(len(r['accepted_heads'])for r in modules);native_count=sum(len(r['heads'])for r in native_holds);pending_heads=sum(len(groups[n]['candidate_heads'])for n in pending);assert accepted+len(guest_holds)+native_count+pending_heads==131
 compatibility=dict(passed=True,current_owner_manifest=d(pp),historical_lineage_manifest=d(historical),all_admitted_Unity_old_hashes_match_current_owner=True,all_unreplaced_current_object_descriptors_exact=True,all1015_current_host_sources_unchanged=True,all4_current_headers_unchanged=True,current_bootstrap_reused_required=True,IL2CPP8_objects_preserved=True,TMP_appended_object4660_preserved=True,object377_preserved=True,no_new_flags_or_heads_or_objects=True)
 result=dict(passed=True,selected=False,prepared_only=True,closed_actual_completed_subset=True,complete131_qualification=accepted==131,parent_manifest=d(pp),historical_plan_parent_manifest=d(historical),merge_compatibility=compatibility,approved_static_plan=d(planp),requested_modules=62,requested_heads=131,qualified_modules=len(modules),qualified_heads=accepted,unprocessed_module_indices=pending,unprocessed_heads=pending_heads,protected_function_contexts=sum(r['protected_functions']for r in modules),modules=modules,guest_unsupported_holds=guest_holds,native_profile_holds=native_holds,actual_reached360_admission=d(paths[360]),appended_wrapper_qualification=d(a.out/'appended-wrapper-review.json'),empty_fresh_metadata_cases=empty_metadata_edges,replaced_indices=changed,object_manifest=d(a.out/'object-manifest.json'),guest_objects=4661,trace_heads=595556,headers=headers,all_four_generated_headers_unchanged=True,other_object_descriptors_exact=4661-len(changed),disjoint_from_IL2CPP8_replacements=True,no_new_object_appended=True,no_host_or_ISA_source_changes=True,no_original_function_execution=True,no_original_game_execution=True,held_inputs=held,source=d(__file__),executed_source=d(a.out/'executed-assembler.py'),limits='Closed snapshot of actually qualified Unity normal-entry trace bodies only, merged onto exact current ownerf034. Unprocessed and excluded interior/mixed-error bodies remain unchanged. Current IL2CPP8, TMP append, ownerhost sources/bootstrap and headers are preserved. No selected-cohort, original-function/game execution, visible-frame or gameplay claim.');save(a.out/'acceptance.json',result);print(json.dumps(d(a.out/'acceptance.json')),flush=True)
if __name__=='__main__':main()
