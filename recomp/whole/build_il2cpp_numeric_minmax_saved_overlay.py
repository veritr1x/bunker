"""Assemble eight saved IL2CPP NM candidates after strict native qualification.

This performs no decoding, compilation, host build, selection or game execution.
It recomputes each saved whole-module inverse and binds the independent proof
of all non-target readonly references, including unchanged displacement fields.
"""
from pathlib import Path
import argparse,gc,hashlib,importlib.util,json,re,shutil,subprocess
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
INDICES=[1572,2695,2950,3251,3733,3734,3842,4168]
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def d(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--native-proof',type=Path,required=True);ap.add_argument('--native-proof-sha',required=True);ap.add_argument('--out',type=Path,default=W/'il2cpp-numeric-minmax-saved-overlay1');a=ap.parse_args()
 assert sha(a.native_proof)==a.native_proof_sha;proof=read(a.native_proof);assert proof['passed']and proof['actual_object_coverage']==8
 ip=W/'il2cpp-numeric-minmax-compiled-inventory1.json';assert sha(ip)=='cea9a7f0ec48ee5fc6c40f040bad4b90cc83ac20cf6ba3bfbed81ccee981e505';inventory=read(ip);assert proof['compiled_inventory']==d(ip)
 cp=W/'il2cpp-numeric-minmax-preparation1/plan.json';assert sha(cp)=='b9e29956fec6c5f8fca626315f6d48b77a5aa70a7f8628f9c352faa32a0fe20e';census=read(cp);pp=Path(census['parent_manifest']['path']);assert sha(pp)=='beb2c6cecab5afea86c14609ea05ed1c56758f005fc0d36df9e1f8e796eb4ff8';parent=read(pp)
 partialp=W/'numeric-minmax-fresh-followon1/acceptance.json';assert sha(partialp)=='fd3cf28232a0aa7c25be5bd49cfdc8c0a4125d35b7382606785cbab087aab76e';partial=read(partialp)
 helper=Path(__file__).with_name('build_unity_st2_constructor_overlay.py');assert sha(helper)=='37c2c4dfa49c285e545b7ed041ea07d20ee4b2c7bcb6e1026414eda199bc2e1b';base=load('saved_numeric_projection',helper)
 splice=load('saved_numeric_splice',Path(__file__).with_name('build_il2cpp_numeric_minmax_retained_overlay.py'))
 held={}
 def hold(p):p=Path(p);held[str(p)]=sha(p)
 def pin(r):assert sha(r['path'])==r['sha256']and Path(r['path']).stat().st_size==r['bytes'],r['path'];hold(r['path'])
 def closure(v):
  if isinstance(v,dict):
   if set(['path','sha256','bytes'])<=v.keys():pin(v)
   else:
    for x in v.values():closure(x)
  elif isinstance(v,list):
   for x in v:closure(x)
 for p in [Path(__file__),Path(splice.__file__),helper,ip,cp,pp,partialp,a.native_proof]:hold(p)
 gates={}
 for name,relative,expected in [
  ('toolchain','frinta-toolchain1/tools-ready.json','50b1c6fbe959c443eb89f197365ec8ca0c8b58333f39db290632500460d03180'),
  ('historical_primitive_family','fp-numeric-minmax-qualification1/acceptance.json','19d724b9b523f4d446c9231da9aea5661cd1ceaca8969d7661037c1bc29cecc3'),
  ('historical_decoder','fp-numeric-minmax-decode2/acceptance.json','09e4e2b647485cfc90d38410cb7cff2fadbdf0c5190c4b1a3698cb789f3c41ed'),
  ('compiled_semantic_reuse','numeric-minmax-reuse-review1/acceptance.json','d07c42d4b5fe9860e13da9ed95095cebda60d4557fda22764f888ef7572bc029'),
  ('current_tool_probe','runtime19-numeric-minmax-frontier1/acceptance.json','3e416efbcf2374cd5777369e103c3e6589ce49753d1e3cc9deb3522a52de593a'),
  ('original_instruction_cluster','numeric-minmax-cluster-qualification1/acceptance.json','bf9f81c76896901fb89fce6e2ce1b6b3ee2ff7371b18acaa160cdc672686cc39')]:
  p=W/relative;assert sha(p)==expected and read(p)['passed'];hold(p);gates[name]=d(p)
 closure(inventory);closure(proof);assert sorted(r['global_index']for r in proof['targets'])==INDICES
 assert not a.out.exists();a.out.mkdir();(a.out/'objects').mkdir();shutil.copyfile(__file__,a.out/'executed-assembler.py');objects=list(parent['objects']);rows=[]
 heads={int(h,16)for h in re.findall(r'^extern "C" Memory \*sub_([0-9a-f]+)\(',Path(parent['trace_header']['path']).read_text(),re.M)};assert len(heads)==595548
 nm='/usr/lib/llvm-18/bin/llvm-nm';hold(nm)
 for target in census['targets']:
  n=target['global_index'];head=int(target['head'],0);r=next(r for r in inventory['targets']if r['global_index']==n);pr=next(r for r in proof['targets']if r['global_index']==n)
  assert r['old_object']==pr['old_object']==target['current_object']and r['candidate_object']==pr['candidate_object']and pr['all_non_target_native_contexts_preserved']is True and pr['protected_functions']==127
  native=read(pr['certificate']['path']);assert native['passed']and native['protected_functions']==127
  for key in ['all_nonfield_instruction_bytes_equal','all_relative_relocation_positions_types_symbols_exact','all_other_relocation_addends_exact','all_guest_calls_exact','all_function_sizes_equal','all_non_target_rdata_references_accounted','all_resolved_read_payloads_equal','all_required_alignments_satisfied']:assert native[key]is True,key
  for item in [target['retained_raw'],target['retained_polled'],target['original_bytes']]:pin(item)
  old=Path(target['retained_raw']['path']).read_text();oldp=Path(target['retained_polled']['path']).read_text();fresh=Path(r['one_entry_raw_ir']['path']).read_text();single=Path(r['one_entry_polled_ir']['path']).read_text();raw=Path(r['candidate_raw_ir']['path']).read_text();polled=Path(r['candidate_polled_ir']['path']).read_text()
  of=base.functions(old);opf=base.functions(oldp);ff=base.functions(fresh);cf=base.functions(raw);pf=base.functions(polled);assert len(of)==len(opf)==128 and set(ff)=={head}and set(of)==set(cf)==set(opf)==set(pf)
  assert all(cf[h]==of[h]and pf[h]==opf[h]for h in of if h!=head)and base.internal_functions(polled)==base.internal_functions(oldp)
  expected,rawproof=splice.splice_polled_target(base,old,fresh,head);assert raw==expected
  expected,pollproof=splice.splice_polled_target(base,oldp,single,head);assert polled==expected
  assert all(base.state(t)==STATE for t in [old,oldp,fresh,single,raw,polled]);remaining=n==1572
  if remaining:assert ff==base.functions(Path(partial['fresh_one_entry_raw_ir']['path']).read_text())and ff[head].count('@__remill_error(')==1
  else:assert not base.errors(ff)
  olderrors=base.errors(of);expectederrors=sorted(h for h in olderrors if remaining or h!=hex(head));assert sorted(base.errors(cf))==sorted(base.errors(pf))==expectederrors
  folder=Path(r['candidate_object']['path']).parent;audit=folder/'optimized-guard-audit.json';stats=folder/'lowering-stats.json';assert read(audit)['passed'];lowering=read(stats);assert lowering['passed']and lowering['State_bytes']==1200 and lowering['SP_offset']==1040 and lowering['PC_offset']==1056;hold(audit);hold(stats)
  symbols=subprocess.check_output([nm,'--format=posix','--extern-only',r['candidate_object']['path']],text=True);defs={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M)};refs={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M)};assert defs==set(of)and refs<=heads
  obj=a.out/'objects'/f'shard-{n:05d}.o';shutil.copyfile(r['candidate_object']['path'],obj);assert sha(obj)==r['candidate_object']['sha256'];objects[n]=d(obj)
  equal=native['native_byte_and_rich_relocation_exact_functions'];equivalent=native['functions_with_changed_readonly_displacements'];assert equal+equivalent==127
  row=dict(global_index=n,target_head=hex(head),original_FDE_end=target['fde_end_exclusive'],original_bytes=target['original_bytes'],old_object=target['current_object'],candidate_object=d(obj),qualified_saved_object=r['candidate_object'],raw_ir=r['candidate_raw_ir'],polled_ir=r['candidate_polled_ir'],one_entry_raw_ir=r['one_entry_raw_ir'],one_entry_polled_ir=r['one_entry_polled_ir'],old_raw_IR=target['retained_raw'],old_polled_IR=target['retained_polled'],definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,old_internal_helpers_byte_exact=True,all_other_raw_module_bytes_unchanged_by_exact_inverse=True,raw_module_preservation=rawproof,polled_module_preservation=pollproof,single_target_poll_instrumentation=True,old_unsupported_heads=olderrors,new_unsupported_heads=expectederrors,State_size=1200,State_align=16,State_type_closure_sha256=STATE,old_poll_coverage=base.coverage(opf),new_poll_coverage=base.coverage(pf),optimized_guard_audit=d(audit),lowering_stats=d(stats),external_guest_references=sorted(refs),all_direct_refs_closed=True,native_neighbors_full_bytes_and_relocations_exact=equal,native_resolved_read_equivalent_neighbors=equivalent,native_neighbors_preserved_total=127,native_all_readonly_reference_proof=pr['certificate'],native_all_readonly_references_preserved=True,remaining_unsupported=remaining,remaining_nonNM_error_sites=partial['remaining_nonNM_error_sites']if remaining else [],partial_refresh_certificate=d(partialp)if remaining else None,whole_original_FDE_supported=not remaining)
  save(a.out/f'shard-{n:05d}.json',dict(passed=True,selected=False,**row));rows.append(row);print('SAVED-OBJECT-VERIFIED',n,flush=True)
  del old,oldp,fresh,single,raw,polled,expected,of,opf,ff,cf,pf
  gc.collect()
 assert[i for i in range(4660)if objects[i]!=parent['objects'][i]]==INDICES;save(a.out/'object-manifest.json',objects)
 headers={name:d(pp.parent/name)for name in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
 for x in headers.values():hold(x['path'])
 for p,h in held.items():assert sha(p)==h,p
 result=dict(passed=True,selected=False,parent_manifest=d(pp),retained_census=d(cp),qualification_gates=gates,compiled_inventory=d(ip),all_readonly_native_qualification=d(a.native_proof),partial_refresh_certificate=d(partialp),partial_refresh_indices=[1572],all_target_functions_fully_supported=False,object_manifest=d(a.out/'object-manifest.json'),target_objects=rows,replaced_indices=INDICES,guest_objects=4660,trace_heads=595548,other4652_object_descriptors_exact=True,all_four_generated_headers_unchanged=True,headers=headers,no_host_source_changes=True,no_header_outputs_created=True,State_size=1200,State_align=16,producer=d(Path(__file__)),frozen_producer=d(a.out/'executed-assembler.py'),held_inputs=held,lift_or_compile_performed=False,actual_large_candidate_functions_executed_in_fixture=False,original_game_execution=False,limits='Eight saved IL2CPP body candidates only.1572 retains one explicitly mapped FCCMP_D error. All other seven refreshed bodies decode without unsupported instructions; all127 neighboring raw/polled bodies and every non-target native constant read are preserved. Sparse8 entries and actual original game integration are separate. No complete TMP function fixture, visible frame or gameplay claim.')
 save(a.out/'acceptance.json',result);print(json.dumps(d(a.out/'acceptance.json')),flush=True)
if __name__=='__main__':main()
