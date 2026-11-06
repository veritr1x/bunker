"""Splice exactly the two censused original FRINTA-truncated Unity functions.

Default is read-only. Execution replaces two unselected object candidates,
preserving all neighboring IR/native code, headers, and the selected inventory.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,traceback
W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
CENSUS='4ddaddc979a2f4d5309c5e3c96d7d64acf35d00492aee6862e8f6aa8c6a40d56'
TOOLS='50b1c6fbe959c443eb89f197365ec8ca0c8b58333f39db290632500460d03180'
FAMILY='aeb6e436dc2d073102ff503213208208eae462260e6c4a3a109d9c9cf879f442'
DECODE='ce5c3ad788e2379d5505afba61636f2a99aa1cc2e606b6b2277b9a0ae5d708f4'
PARENT='d41d151d302c58298240ac11c3486d31220d2783df3214233460bf1e58c4c6aa'
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
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'frinta-retained-overlay2');ap.add_argument('--native-out',type=Path,default=L/'frinta-retained-overlay2');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 cp=W/'frinta-retained-census1/acceptance.json';tp=W/'frinta-toolchain1/tools-ready.json';fp=W/'frinta-family-qualification2/acceptance.json';dp=W/'frinta-decode-qualification1/acceptance.json'
 for p,h in [(cp,CENSUS),(tp,TOOLS),(fp,FAMILY),(dp,DECODE)]:assert sha(p)==h and read(p)['passed']is True
 census=read(cp);tools=read(tp);pp=Path(census['parent_manifest']['path']);assert sha(pp)==PARENT;parent=read(pp);assert len(parent['objects'])==4660 and parent['trace_heads']==595548
 targets=census['targets'];assert[(r['head'],r['global_index'])for r in targets]==[('0x7042dee4',166),('0x70828b78',289)]
 if not a.execute:print(json.dumps(dict(dry_run=True,changed_heads=[r['head']for r in targets],replaced_object_indices=[166,289],objects=4660,heads=595548,unchanged_objects=4658,unchanged_headers=4)));return
 assert not a.out.exists()and not a.native_out.exists();a.out.mkdir();a.native_out.mkdir();shutil.copyfile(__file__,a.out/'executed-builder.py');commands=[];held={};results=[]
 def hold(p):p=Path(p);held[str(p)]=sha(p)
 def run(argv,label,folder):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(folder/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  helper=Path(__file__).with_name('build_unity_st2_constructor_overlay.py');assert sha(helper)==BASE;spec=importlib.util.spec_from_file_location('frinta_qualified_projection',helper);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
  for p in [Path(__file__),helper,cp,tp,fp,dp,pp]:hold(p)
  producer=read(W/'neg4s1-il2cpp-entry-preparation1/plan.json')
  for k in ['poll','compiler','nm','llvm_opt','optimized_auditor']:pin(producer[k]);hold(producer[k]['path'])
  for k in ['lifter','semantics']:pin(tools[k]);hold(tools[k]['path'])
  header=Path(parent['trace_header']['path']);pin(parent['trace_header']);hold(header);heads=sorted({int(h,16)for h in re.findall(r'^extern "C" Memory \*sub_([0-9a-f]+)\(',header.read_text(),re.M)});assert len(heads)==595548
  headfile=a.native_out/'all-heads.txt';headfile.write_text(''.join(hex(h)+'\n'for h in heads));headers={n:d(pp.parent/n)for n in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
  for r in headers.values():hold(r['path'])
  new_objects=list(parent['objects'])
  for target in targets:
   head=int(target['head'],0);index=target['global_index'];out=a.out/('shard-'+str(index).zfill(5));native=a.native_out/out.name;out.mkdir();native.mkdir()
   assert parent['objects'][index]['path']==target['current_object']['path']and parent['objects'][index]['sha256']==target['current_object']['sha256']
   for r in [target['current_object'],target['retained_raw'],target['retained_polled'],target['original_bytes']]:pin(r);hold(r['path'])
   old_raw=Path(target['retained_raw']['path']);old_poll=Path(target['retained_polled']['path']);old_obj=Path(target['current_object']['path']);old=old_raw.read_text();oldp=old_poll.read_text();of=base.functions(old);opf=base.functions(oldp);old_errors=base.errors(of)
   assert len(of)==len(opf)==128 and set(of)==set(opf)and hex(head)in old_errors and of[head].count('@__remill_error(')==1 and base.state(old)==STATE
   image=Path(target['original_bytes']['path']);assert image.stat().st_size==target['fde_bytes']==int(target['fde_end_exclusive'],0)-head
   freshpath=native/'one-entry.raw.ll';stats=native/'lowering-stats.json'
   run([tools['lifter']['path'],'--arch','aarch64','--os','linux','--semantics_dir',str(Path(tools['semantics']['path']).parent),'--bytes_file',image,'--address',str(head),'--entry_address',str(head),'--trace_heads_file',headfile,'--guest_call_transfer=true','--guest_call_transfer_stats_out',stats,'--ir_out',freshpath],'one-entry-lift',out)
   fresh=freshpath.read_text();ff=base.functions(fresh);assert set(ff)=={head}and not base.errors(ff)and base.state(fresh)==STATE;lowering=read(stats);assert lowering['passed']and lowering['State_bytes']==1200 and lowering['SP_offset']==1040 and lowering['PC_offset']==1056
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
   cf=base.functions(candidate);expected_errors=sorted(h for h in old_errors if h!=hex(head));assert set(cf)==set(of)and all(cf[h]==of[h]for h in of if h!=head)and sorted(base.errors(cf))==expected_errors and base.state(candidate)==STATE
   rawpath=native/'candidate.raw.ll';polled=native/'candidate.polled.ll';singlepolled=native/'one-entry.polled.ll';rawpath.write_text(candidate);run([producer['poll']['path'],freshpath,singlepolled],'instrument-single-entry',out);polltext,pollproof=splice_polled_target(base,oldp,singlepolled.read_text(),head);polled.write_text(polltext);pf=base.functions(polltext);assert set(pf)==set(opf)and all(pf[h]==opf[h]for h in opf if h!=head)and sorted(base.errors(pf))==expected_errors and base.internal_functions(polltext)==base.internal_functions(oldp)
   run([producer['llvm_opt']['path'],'-passes=verify','-disable-output',polled],'verify',out);optimized=native/'optimized.ll';audit=native/'optimized-guard-audit.json';run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-S','-emit-llvm',polled,'-o',optimized],'optimized-IR',out);run([producer['optimized_auditor']['path'],optimized,audit],'audit-guards',out);audited=read(audit);assert audited['passed']
   obj=native/'candidate.polled.o';run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',polled,'-o',obj],'compile',out);symbols=subprocess.check_output([producer['nm']['path'],'--format=posix','--extern-only',obj],text=True);definitions={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M)};direct={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M)};assert definitions==set(of)and direct<=set(heads)
   native_projections={}
   for label,path in [('old',old_obj),('candidate',obj)]:native_projections[label],asm,_=base.coff_projection('/usr/lib/llvm-18/bin/llvm-objdump',path);(out/(label+'-disassembly.txt')).write_text(asm)
   changed=[h for h in native_projections['old']if native_projections['old'][h]!=native_projections['candidate'][h]];assert changed==[hex(head)],changed
   for name,path in [('one-entry.raw.ll',freshpath),('one-entry.polled.ll',singlepolled),('candidate.raw.ll',rawpath),('candidate.polled.ll',polled),('candidate.polled.o',obj),('lowering-stats.json',stats),('optimized-guard-audit.json',audit)]:shutil.copyfile(path,out/name)
   new_objects[index]=d(out/'candidate.polled.o');row=dict(global_index=index,target_head=hex(head),original_FDE_end=target['fde_end_exclusive'],original_bytes=target['original_bytes'],old_object=d(old_obj),candidate_object=d(out/'candidate.polled.o'),raw_ir=d(out/'candidate.raw.ll'),polled_ir=d(out/'candidate.polled.ll'),one_entry_raw_ir=d(out/'one-entry.raw.ll'),old_raw_IR=d(old_raw),old_polled_IR=d(old_poll),definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,native_neighbors_full_bytes_and_relocations_exact=127,native_changed_symbols=changed,old_internal_helpers_byte_exact=True,all_other_raw_module_bytes_unchanged_by_exact_inverse=True,old_unsupported_heads=old_errors,new_unsupported_heads=expected_errors,added_declarations=extra_decls,added_attributes=extra_attrs,added_metadata_records=len(extra_md),named_metadata_only_appended=True,State_type_closure_sha256=STATE,State_size=1200,State_align=16,old_poll_coverage=base.coverage(opf),new_poll_coverage=base.coverage(pf),optimized_guard_audit=d(out/'optimized-guard-audit.json'),observed_guard_audit=audited,lowering_stats=d(out/'lowering-stats.json'),observed_lowering_stats=lowering,external_guest_references=sorted(direct),all_direct_refs_closed=True)
   row.update(one_entry_polled_ir=d(out/'one-entry.polled.ll'),single_target_poll_instrumentation=True,polled_module_preservation=pollproof)
   save(out/'acceptance.json',dict(passed=True,selected=False,**row));results.append(row);print('FRINTA-OBJECT-READY',json.dumps(dict(head=hex(head),object=row['candidate_object'],polled=row['polled_ir'])),flush=True)
  changed=[i for i in range(4660)if new_objects[i]!=parent['objects'][i]];assert changed==[166,289];save(a.out/'object-manifest.json',new_objects)
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,selected=False,component_original_function_qualification_pending=True,parent_manifest=d(pp),retained_census=d(cp),toolchain=d(tp),primitive_family_qualification=d(fp),decoder_qualification=d(dp),producer=d(Path(__file__)),frozen_producer=d(a.out/'executed-builder.py'),object_manifest=d(a.out/'object-manifest.json'),target_objects=results,replaced_indices=changed,changed_heads=[r['head']for r in targets],guest_objects=4660,trace_heads=595548,other4658_object_descriptors_exact=True,all_four_generated_headers_unchanged=True,headers=headers,no_header_outputs_created=True,no_host_source_changes=True,original_instruction_bytes_unchanged=True,State_size=1200,State_align=16,held_inputs=held,commands=commands,limits='Only two censused original FRINTA-truncated FDE bodies replaced. All127 neighbors in each affected module raw/polled/native contexts preserved; unrelated existing unsupported heads remain explicit. Finite original-function gates and actual host build/peer admission separate. No original startup, frame or gameplay claim.')
  save(a.out/'acceptance.json',result);print('FRINTA-BATCH-CANDIDATE',json.dumps(d(a.out/'acceptance.json')),flush=True)
 except BaseException as ex:save(a.out/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands,completed_objects=results));raise
if __name__=='__main__':main()
