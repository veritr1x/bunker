"""Splice exactly the eight approved stale IL2CPP scalar numeric MIN/MAX functions.

Default is read-only. Execution prepares eight unselected object candidates,
preserving all neighboring IR/native code, headers, and the selected inventory.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,traceback
W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
CENSUS='b9e29956fec6c5f8fca626315f6d48b77a5aa70a7f8628f9c352faa32a0fe20e'
TOOLS='50b1c6fbe959c443eb89f197365ec8ca0c8b58333f39db290632500460d03180'
FAMILY='19d724b9b523f4d446c9231da9aea5661cd1ceaca8969d7661037c1bc29cecc3'
DECODE='09e4e2b647485cfc90d38410cb7cff2fadbdf0c5190c4b1a3698cb789f3c41ed'
REUSE='d07c42d4b5fe9860e13da9ed95095cebda60d4557fda22764f888ef7572bc029'
PROBE='3e416efbcf2374cd5777369e103c3e6589ce49753d1e3cc9deb3522a52de593a'
PARENT='beb2c6cecab5afea86c14609ea05ed1c56758f005fc0d36df9e1f8e796eb4ff8'
BASE='37c2c4dfa49c285e545b7ed041ea07d20ee4b2c7bcb6e1026414eda199bc2e1b'
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def d(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def pin(r):assert sha(r['path'])==r['sha256'],r['path']
def remap_attrs(t,m):return re.sub(r' #(\d+)(?=[ {\n])',lambda x:' #'+m[x[1]],t)
def splice_polled_target(base,old,fresh,head):
 oldf=base.functions(old);freshf=base.functions(fresh);assert set(freshf)=={head}
 oa=base.attrs(old);fa=base.attrs(fresh);reverse={v:k for k,v in oa.items()};attrs={};extra_attrs=[];n=max(map(int,oa))+1
 for key,value in fa.items():
  if value not in reverse:reverse[value]=str(n);extra_attrs.append('attributes #'+str(n)+' = '+value+'\n');n+=1
  attrs[key]=reverse[value]
 body=remap_attrs(freshf[head],attrs);omd={int(x[1]):x[2]for x in re.finditer(r'^!(\d+) = (.*)$',old,re.M)};fmd={int(x[1]):x[2]for x in re.finditer(r'^!(\d+) = (.*)$',fresh,re.M)};offset=max(omd,default=-1)+1;mapping={str(k):str(k+offset)for k in fmd};mapmd=lambda t:re.sub(r'!(\d+)\b',lambda x:'!'+mapping[x[1]],t);body=mapmd(body);extra_md=['!'+str(k+offset)+' = '+mapmd(v)+'\n'for k,v in fmd.items()]
 ot=base.types(old);ft=base.types(fresh)
 for name in set(re.findall(r'%[-A-Za-z$._0-9]+',body))&set(ft):assert ot.get(name)==ft[name],name
 refs=set(re.findall(r'@([-A-Za-z$._0-9]+)',body));defined=set(re.findall(r'^define[^\n]*@([^ (]+)',old,re.M));decls={x[1]:x[0]for x in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',old,re.M)};freshdecls={x[1]:x[0]for x in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',fresh,re.M)};globals=set(re.findall(r'^@([^ =]+)',old,re.M));extra_decls=[]
 for name in sorted(refs-defined-set(decls)-globals):assert name in freshdecls,name;extra_decls.append(remap_attrs(freshdecls[name],attrs)+'\n')
 candidate=old.replace(oldf[head],body);onamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',old,re.M);fnamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',fresh,re.M);nb=na=None
 if fnamed:assert onamed;nb=onamed[0];na='!bunker.guest.call.lowering = !{'+onamed[1]+(', 'if onamed[1]else'')+mapmd(fnamed[1])+'}';candidate=candidate.replace(nb,na)
 suffix='\n'+''.join(extra_decls+extra_attrs+extra_md);candidate+=suffix;inverse=candidate[:-len(suffix)];inverse=inverse.replace(na,nb)if na else inverse;inverse=inverse.replace(body,oldf[head]);assert inverse==old
 return candidate,dict(whole_module_inverse_exact=True,old_numeric_metadata_definitions_preserved=True,new_metadata_records=len(extra_md),new_attributes=extra_attrs,new_declarations=extra_decls)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'il2cpp-numeric-minmax-overlay3');ap.add_argument('--native-out',type=Path,default=L/'il2cpp-numeric-minmax-overlay3');ap.add_argument('--reuse-native-plan',type=Path);ap.add_argument('--only-indices',help='Explicit unselected component of the eight approved indices.');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 cp=W/'il2cpp-numeric-minmax-preparation1/plan.json';tp=W/'frinta-toolchain1/tools-ready.json';fp=W/'fp-numeric-minmax-qualification1/acceptance.json';dp=W/'fp-numeric-minmax-decode2/acceptance.json';rp=W/'numeric-minmax-reuse-review1/acceptance.json';up=W/'runtime19-numeric-minmax-frontier1/acceptance.json'
 for p,h in [(cp,CENSUS),(tp,TOOLS),(fp,FAMILY),(dp,DECODE),(rp,REUSE),(up,PROBE)]:assert sha(p)==h and read(p)['passed']is True
 census=read(cp);tools=read(tp);pp=Path(census['parent_manifest']['path']);assert sha(pp)==PARENT;parent=read(pp);assert len(parent['objects'])==4660 and parent['trace_heads']==595548
 targets=census['targets'];assert[(r['head'],r['global_index'])for r in targets]==[('0x825c2c90',1572),('0x831b4ae8',2695),('0x835a4af4',2950),('0x83aa45e8',3251),('0x841e0654',3733),('0x841e4bc4',3734),('0x843aa9d4',3842),('0x849a7154',4168)]
 requested=sorted(int(v)for v in a.only_indices.split(','))if a.only_indices else [r['global_index']for r in targets]
 assert requested and len(requested)==len(set(requested))and set(requested)<={r['global_index']for r in targets}
 targets=[r for r in targets if r['global_index']in requested]
 if not a.execute:print(json.dumps(dict(dry_run=True,changed_heads=[r['head']for r in targets],replaced_object_indices=[1572,2695,2950,3251,3733,3734,3842,4168],objects=4660,heads=595548,unchanged_objects=4652,unchanged_headers=4)));return
 assert not a.out.exists()and not a.native_out.exists();a.out.mkdir();a.native_out.mkdir();shutil.copyfile(__file__,a.out/'executed-builder.py');commands=[];held={};results=[]
 def hold(p):p=Path(p);held[str(p)]=sha(p)
 def run(argv,label,folder):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(folder/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  helper=Path(__file__).with_name('build_unity_st2_constructor_overlay.py');assert sha(helper)==BASE;spec=importlib.util.spec_from_file_location('numeric_minmax_qualified_projection',helper);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
  for p in [Path(__file__),helper,cp,tp,fp,dp,rp,up,pp]:hold(p)
  partial_path=W/'numeric-minmax-fresh-followon1/acceptance.json';assert sha(partial_path)=='fd3cf28232a0aa7c25be5bd49cfdc8c0a4125d35b7382606785cbab087aab76e';partial=read(partial_path);hold(partial_path)
  assert partial['passed']and partial['global_index']==1572 and partial['remaining_unsupported']and len(partial['remaining_nonNM_error_sites'])==1 and partial['remaining_nonNM_error_sites'][0]['offending_PC']=='0x825c2dc8'
  for name in ['fresh_one_entry_raw_ir','pc_flow','pc_proof','original_bytes']:pin(partial[name]);hold(partial[name]['path'])
  reuse=None
  if a.reuse_native_plan:
   assert sha(a.reuse_native_plan)=='b6c2e69ac7acb400d284d012e6e2293f19a48cf63d63965ee00c33df92069fc5';reuse=read(a.reuse_native_plan);assert reuse['passed']and reuse['global_index']==3734 and reuse['target_head']=='0x841e4bc4';hold(a.reuse_native_plan)
   assert reuse['independent_native_equivalence']['sha256']=='d58ca081535ef9d38030e30397c9c25351f9e1d9ae40b2dff470ec44732f6bfe'
   for r in [*reuse['inputs'].values(),*reuse['artifacts'].values(),reuse['independent_native_equivalence']]:pin(r);hold(r['path'])
  producer=read(W/'neg4s1-il2cpp-entry-preparation1/plan.json')
  for k in ['poll','compiler','nm','llvm_opt','optimized_auditor']:pin(producer[k]);hold(producer[k]['path'])
  for k in ['lifter','semantics']:pin(tools[k]);hold(tools[k]['path'])
  header=Path(parent['trace_header']['path']);pin(parent['trace_header']);hold(header);heads=sorted({int(h,16)for h in re.findall(r'^extern "C" Memory \*sub_([0-9a-f]+)\(',header.read_text(),re.M)});assert len(heads)==595548
  headfile=a.native_out/'all-heads.txt';headfile.write_text(''.join(hex(h)+'\n'for h in heads));headers={n:d(pp.parent/n)for n in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
  for r in headers.values():hold(r['path'])
  new_objects=list(parent['objects'])
  for target in sorted(targets,key=lambda r:(r["global_index"]!=3734,r["global_index"])):
   head=int(target['head'],0);index=target['global_index'];out=a.out/('shard-'+str(index).zfill(5));native=a.native_out/out.name;out.mkdir();native.mkdir()
   assert parent['objects'][index]['path']==target['current_object']['path']and parent['objects'][index]['sha256']==target['current_object']['sha256']
   for r in [target['current_object'],target['retained_raw'],target['retained_polled'],target['original_bytes']]:pin(r);hold(r['path'])
   old_raw=Path(target['retained_raw']['path']);old_poll=Path(target['retained_polled']['path']);old_obj=Path(target['current_object']['path']);old=old_raw.read_text();oldp=old_poll.read_text();of=base.functions(old);opf=base.functions(oldp);old_errors=base.errors(of)
   assert len(of)==len(opf)==128 and set(of)==set(opf)and hex(head)in old_errors and of[head].count('@__remill_error(')==1 and base.state(old)==STATE
   image=Path(target['original_bytes']['path']);assert image.stat().st_size==target['fde_bytes']==int(target['fde_end_exclusive'],0)-head
   freshpath=native/'one-entry.raw.ll';stats=native/'lowering-stats.json'
   reuse_case=reuse is not None and index==3734
   if reuse_case:
    for name,r in reuse['artifacts'].items():shutil.copyfile(r['path'],native/name);assert sha(native/name)==r['sha256']
    save(out/'preserved-stage-reuse.json',dict(passed=True,reuse_plan=d(a.reuse_native_plan),completed_commands=reuse['completed_stage_commands'],stages_reexecuted=[],source_inputs_pinned=True))
   else:run([tools['lifter']['path'],'--arch','aarch64','--os','linux','--semantics_dir',str(Path(tools['semantics']['path']).parent),'--bytes_file',image,'--address',str(head),'--entry_address',str(head),'--trace_heads_file',headfile,'--guest_call_transfer=true','--guest_call_transfer_stats_out',stats,'--ir_out',freshpath],'one-entry-lift',out)
   fresh=freshpath.read_text();ff=base.functions(fresh);assert set(ff)=={head}and base.state(fresh)==STATE
   remaining=index==1572
   if remaining:assert ff==base.functions(Path(partial['fresh_one_entry_raw_ir']['path']).read_text())and ff[head].count('@__remill_error(')==1
   else:assert not base.errors(ff)
   lowering=read(stats);assert lowering['passed']and lowering['State_bytes']==1200 and lowering['SP_offset']==1040 and lowering['PC_offset']==1056
   oa=base.attrs(old);fa=base.attrs(fresh);reverse={v:k for k,v in oa.items()};mapping={};extra_attrs=[];next_attr=max(map(int,oa))+1
   for key,value in fa.items():
    if value not in reverse:reverse[value]=str(next_attr);extra_attrs.append('attributes #'+str(next_attr)+' = '+value+'\n');next_attr+=1
    mapping[key]=reverse[value]
   body=remap_attrs(ff[head],mapping);omd={int(x[1]):x[2]for x in re.finditer(r'^!(\d+) = (.*)$',old,re.M)};fmd={int(x[1]):x[2]for x in re.finditer(r'^!(\d+) = (.*)$',fresh,re.M)};offset=max(omd,default=-1)+1;mdmap={str(k):str(k+offset)for k in fmd};mapmd=lambda t:re.sub(r'!(\d+)\b',lambda x:'!'+mdmap[x[1]],t);body=mapmd(body);extra_md=['!'+str(k+offset)+' = '+mapmd(v)+'\n'for k,v in fmd.items()]
   ot=base.types(old);ft=base.types(fresh)
   for name in set(re.findall(r'%[-A-Za-z$._0-9]+',body))&set(ft):assert ot.get(name)==ft[name],name
   refs=set(re.findall(r'@([-A-Za-z$._0-9]+)',body));defined=set(re.findall(r'^define[^\n]*@([^ (]+)',old,re.M));decls={x[1]:x[0]for x in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',old,re.M)};fresh_decls={x[1]:x[0]for x in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',fresh,re.M)};globals=set(re.findall(r'^@([^ =]+)',old,re.M));extra_decls=[]
   for name in sorted(refs-defined-set(decls)-globals):assert name in fresh_decls,name;extra_decls.append(remap_attrs(fresh_decls[name],mapping)+'\n')
   assert all(int(n[4:],16)in heads for n in refs if n.startswith('sub_'))
   candidate=old.replace(of[head],body);onamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',old,re.M);fnamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',fresh,re.M);nb=na=None
   if fnamed:assert onamed;nb=onamed[0];na='!bunker.guest.call.lowering = !{'+onamed[1]+(', 'if onamed[1]else'')+mapmd(fnamed[1])+'}';candidate=candidate.replace(nb,na)
   suffix='\n'+''.join(extra_decls+extra_attrs+extra_md);candidate+=suffix;inverse=candidate[:-len(suffix)];inverse=inverse.replace(na,nb)if na else inverse;inverse=inverse.replace(body,of[head]);assert inverse==old
   cf=base.functions(candidate);expected_errors=sorted(h for h in old_errors if remaining or h!=hex(head));assert set(cf)==set(of)and all(cf[h]==of[h]for h in of if h!=head)and sorted(base.errors(cf))==expected_errors and base.state(candidate)==STATE
   rawpath=native/'candidate.raw.ll';polled=native/'candidate.polled.ll';singlepolled=native/'one-entry.polled.ll'
   if reuse_case:assert rawpath.read_text()==candidate
   else:rawpath.write_text(candidate);run([producer['poll']['path'],freshpath,singlepolled],'instrument-single-entry',out)
   polltext,pollproof=splice_polled_target(base,oldp,singlepolled.read_text(),head)
   if reuse_case:assert polled.read_text()==polltext
   else:polled.write_text(polltext)
   pf=base.functions(polltext);assert set(pf)==set(opf)and all(pf[h]==opf[h]for h in opf if h!=head)and sorted(base.errors(pf))==expected_errors and base.internal_functions(polltext)==base.internal_functions(oldp)
   optimized=native/'optimized.ll';audit=native/'optimized-guard-audit.json';obj=native/'candidate.polled.o'
   if not reuse_case:
    run([producer['llvm_opt']['path'],'-passes=verify','-disable-output',polled],'verify',out);run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-S','-emit-llvm',polled,'-o',optimized],'optimized-IR',out);run([producer['optimized_auditor']['path'],optimized,audit],'audit-guards',out);run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',polled,'-o',obj],'compile',out)
   audited=read(audit);assert audited['passed'];symbols=subprocess.check_output([producer['nm']['path'],'--format=posix','--extern-only',obj],text=True);definitions={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M)};direct={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M)};assert definitions==set(of)and direct<=set(heads)
   native_projections={}
   for label,path in [('old',old_obj),('candidate',obj)]:native_projections[label],asm,_=base.coff_projection('/usr/lib/llvm-18/bin/llvm-objdump',path);(out/(label+'-disassembly.txt')).write_text(asm)
   changed=[h for h in native_projections['old']if native_projections['old'][h]!=native_projections['candidate'][h]];equivalent=[];native_certificate=None
   if reuse_case:
    native_certificate=reuse['independent_native_equivalence'];proof=read(native_certificate['path']);assert proof['candidate_object']['sha256']==sha(obj)and proof['old_object']['sha256']==sha(old_obj);equivalent=[r['head']for r in proof['functions']if r['changed_fields']];assert len(equivalent)==27 and set(changed)=={hex(head)}|set(equivalent)
   else:assert changed==[hex(head)],changed
   for name,path in [('one-entry.raw.ll',freshpath),('one-entry.polled.ll',singlepolled),('candidate.raw.ll',rawpath),('candidate.polled.ll',polled),('candidate.polled.o',obj),('lowering-stats.json',stats),('optimized-guard-audit.json',audit)]:shutil.copyfile(path,out/name)
   new_objects[index]=d(out/'candidate.polled.o');row=dict(global_index=index,target_head=hex(head),original_FDE_end=target['fde_end_exclusive'],original_bytes=target['original_bytes'],old_object=d(old_obj),candidate_object=d(out/'candidate.polled.o'),raw_ir=d(out/'candidate.raw.ll'),polled_ir=d(out/'candidate.polled.ll'),one_entry_raw_ir=d(out/'one-entry.raw.ll'),old_raw_IR=d(old_raw),old_polled_IR=d(old_poll),definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,native_neighbors_full_bytes_and_relocations_exact=127,native_changed_symbols=changed,old_internal_helpers_byte_exact=True,all_other_raw_module_bytes_unchanged_by_exact_inverse=True,old_unsupported_heads=old_errors,new_unsupported_heads=expected_errors,added_declarations=extra_decls,added_attributes=extra_attrs,added_metadata_records=len(extra_md),named_metadata_only_appended=True,State_type_closure_sha256=STATE,State_size=1200,State_align=16,old_poll_coverage=base.coverage(opf),new_poll_coverage=base.coverage(pf),optimized_guard_audit=d(out/'optimized-guard-audit.json'),observed_guard_audit=audited,lowering_stats=d(out/'lowering-stats.json'),observed_lowering_stats=lowering,external_guest_references=sorted(direct),all_direct_refs_closed=True)
   row.update(one_entry_polled_ir=d(out/'one-entry.polled.ll'),single_target_poll_instrumentation=True,polled_module_preservation=pollproof)
   row.update(remaining_unsupported=remaining,remaining_nonNM_error_sites=partial['remaining_nonNM_error_sites']if remaining else [],partial_refresh_certificate=d(partial_path)if remaining else None,whole_original_FDE_supported=not remaining)
   row.update(native_neighbors_full_bytes_and_relocations_exact=127-len(equivalent),native_resolved_read_equivalent_neighbors=len(equivalent),native_neighbors_preserved_total=127,native_resolved_read_equivalent_heads=equivalent,native_resolved_read_equivalence=native_certificate,native_semantically_changed_symbols=[hex(head)],preserved_native_stage_reuse=d(a.reuse_native_plan)if reuse_case else None)
   save(out/'acceptance.json',dict(passed=True,selected=False,**row));results.append(row);print('NUMERIC-MINMAX-OBJECT-READY',json.dumps(dict(head=hex(head),object=row['candidate_object'],polled=row['polled_ir'])),flush=True)
  changed=[i for i in range(4660)if new_objects[i]!=parent['objects'][i]];assert changed==requested;save(a.out/'object-manifest.json',new_objects)
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,selected=False,component_original_function_qualification_pending=True,parent_manifest=d(pp),retained_census=d(cp),toolchain=d(tp),primitive_family_qualification=d(fp),decoder_qualification=d(dp),compiled_semantic_reuse=d(rp),bounded_current_tool_probe=d(up),producer=d(Path(__file__)),frozen_producer=d(a.out/'executed-builder.py'),object_manifest=d(a.out/'object-manifest.json'),target_objects=sorted(results,key=lambda r:r["global_index"]),replaced_indices=changed,changed_heads=[r['head']for r in targets],guest_objects=4660,trace_heads=595548,other4652_object_descriptors_exact=True,all_four_generated_headers_unchanged=True,headers=headers,no_header_outputs_created=True,no_host_source_changes=True,original_instruction_bytes_unchanged=True,State_size=1200,State_align=16,held_inputs=held,commands=commands,limits='Only eight censused original IL2CPP numeric MIN/MAX-truncated FDE bodies replaced. All127 neighbors in each affected module raw/polled/native contexts preserved; unrelated existing unsupported heads remain explicit. Finite original-function gates and actual host build/peer admission separate. No original startup, frame or gameplay claim.')
  save(a.out/'acceptance.json',result);print('NUMERIC-MINMAX-BATCH-CANDIDATE',json.dumps(d(a.out/'acceptance.json')),flush=True)
 except BaseException as ex:save(a.out/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands,completed_objects=results));raise
if __name__=='__main__':main()
