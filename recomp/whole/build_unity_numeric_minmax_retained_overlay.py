"""Prepare unselected clean normal-entry Unity NM refreshes, grouped per object.

No ISA, host or header changes. Every module is compiled once after its accepted
target bodies are spliced. Newly exposed unsupported bodies are retained intact
and recorded as held, rather than silently extending the instruction profile.
"""
from pathlib import Path
import argparse,gc,hashlib,importlib.util,json,re,shutil,subprocess,traceback
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(t):return hashlib.sha256(t.encode()).hexdigest()
def d(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'unity-nm-retained-overlay1');ap.add_argument('--native-out',type=Path,default=L/'unity-nm-retained-overlay1');ap.add_argument('--indices',required=True,help='Explicit object indices within the approved normal-entry131 scope.');ap.add_argument('--reuse-target-ir-plan',type=Path);ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 planp=W/'unity-nm-clean-plan1/plan.json';assert sha(planp)=='1916a774c7f3334af378b2642b0f3fc4e0e84a3198e71091588aa6619b2f49d8';plan=read(planp);groups=plan['first_proposed_scope']['grouped_current_modules'];assert len(groups)==62 and sum(len(g['candidate_heads'])for g in groups)==131
 wanted=sorted(int(n)for n in a.indices.split(','));assert wanted and len(wanted)==len(set(wanted))and set(wanted)<={g['global_index']for g in groups};groups=[g for g in groups if g['global_index']in wanted]
 if not a.execute:print(json.dumps(dict(dry_run=True,indices=wanted,heads=sum(len(g['candidate_heads'])for g in groups),scope='Only approved131 normal-entry bodies.')));return
 assert not a.out.exists()and not a.native_out.exists();a.out.mkdir();a.native_out.mkdir();shutil.copyfile(__file__,a.out/'executed-builder.py');held={};commands=[];modules=[];body_holds=[]
 def hold(p):p=Path(p);held[str(p)]=sha(p)
 def pin(r):assert sha(r['path'])==r['sha256'],r['path'];hold(r['path'])
 def run(argv,stage,folder):
  argv=list(map(str,argv));commands.append(dict(stage=stage,argv=argv));(a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',stage,flush=True)
  with(folder/(stage+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  helper=Path(__file__).with_name('build_unity_st2_constructor_overlay.py');assert sha(helper)=='37c2c4dfa49c285e545b7ed041ea07d20ee4b2c7bcb6e1026414eda199bc2e1b';base=load('unity_nm_projection',helper)
  splicep=Path(__file__).with_name('build_il2cpp_numeric_minmax_retained_overlay.py');assert sha(splicep)=='8d440dd121683ffcba2d66ccb58f80702b0b2998b6f6f2691dae018955884517';splice=load('unity_nm_frozen_splice',splicep)
  checkp=Path(__file__).with_name('coff_readonly_constant_preservation_pcmpeqd.py');assert sha(checkp)=='2490ce261cedb0564c3da6b1484e971095f40d9dfbf67d0eda8df004cdcce5f4';checker=load('unity_nm_all_readonly_checker',checkp)
  tools_path=W/'frinta-toolchain1/tools-ready.json';assert sha(tools_path)=='50b1c6fbe959c443eb89f197365ec8ca0c8b58333f39db290632500460d03180';tools=read(tools_path)
  reusep=W/'numeric-minmax-reuse-review1/acceptance.json';assert sha(reusep)=='d07c42d4b5fe9860e13da9ed95095cebda60d4557fda22764f888ef7572bc029'and read(reusep)['passed']
  checker_gate=W/'unity-nm-pcmpeqd-profile-qualification1/acceptance.json';assert sha(checker_gate)=='7563cadd7d9cb47ce924b8aca4fffac3282ccbf2723f99c14675956e8e36ddec'and read(checker_gate)['passed']
  pp=Path(plan['current_manifest']['path']);assert sha(pp)=='beb2c6cecab5afea86c14609ea05ed1c56758f005fc0d36df9e1f8e796eb4ff8';parent=read(pp);assert len(parent['objects'])==4660 and parent['trace_heads']==595548
  cp=Path(plan['sealed_census']['path']);pin(plan['sealed_census']);census=read(cp);elfr=next(r for r in census['original_ELFs']if r['path'].endswith('libunity.so'));pin(elfr)
  for p in [Path(__file__),planp,helper,splicep,checkp,tools_path,reusep,checker_gate,pp]:hold(p)
  reuse_ir={}
  if a.reuse_target_ir_plan:
   hold(a.reuse_target_ir_plan);reuse_plan=read(a.reuse_target_ir_plan);assert reuse_plan['prepared_only']and reuse_plan['toolchain']==d(tools_path)
   for r in reuse_plan['held_descriptors']:pin(r)
   reuse_ir={r['head']:r for r in reuse_plan['targets']}
  producer=read(W/'neg4s1-il2cpp-entry-preparation1/plan.json')
  for k in ['poll','compiler','nm','llvm_opt','optimized_auditor']:pin(producer[k])
  for k in ['lifter','semantics']:pin(tools[k])
  headers={name:d(pp.parent/name)for name in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
  for r in headers.values():pin(r)
  heads={int(h,16)for h in re.findall(r'^extern "C" Memory \*sub_([0-9a-f]+)\(',Path(parent['trace_header']['path']).read_text(),re.M)};assert len(heads)==595548
  headfile=a.native_out/'all-heads.txt';headfile.write_text(''.join(hex(h)+'\n'for h in sorted(heads)));objects=list(parent['objects'])
  with Path(elfr['path']).open('rb')as f:
   e=ELFFile(f);segments=[s for s in e.iter_segments()if s['p_type']=='PT_LOAD'];image=Path(elfr['path']).read_bytes()
  for group in groups:
   n=group['global_index'];out=a.out/f'shard-{n:05d}';native=a.native_out/out.name;out.mkdir();native.mkdir();source=group['current_module'];oldobj=source['current_object'];assert oldobj['sha256']==parent['objects'][n]['sha256']and oldobj['path']==parent['objects'][n]['path']
   for k in ['current_object','source_object','retained_raw','retained_polled']:pin(source[k])
   assert 'fresh_cache'in source or 'source_packet'in source
   for k in ['fresh_cache','source_packet']:
    if k in source:pin(source[k])
   old=Path(source['retained_raw']['path']).read_text();oldp=Path(source['retained_polled']['path']).read_text();of=base.functions(old);opf=base.functions(oldp);assert len(of)==len(opf)==128 and set(of)==set(opf)and base.state(old)==base.state(oldp)==STATE
   raw=old;polled=oldp;operations={'raw':[],'polled':[]};accepted=[];holds=[];target_rows=[]
   def splice_step(kind,current,fresh,h):
    ft=base.types(fresh);ot=base.types(current);referenced=set(re.findall(r'%[-A-Za-z$._0-9]+',base.functions(fresh)[h]));missing=sorted((referenced&set(ft))-set(ot));new_types=[]
    for name in missing:
     assert re.fullmatch(r'%struct\.(?:u?int|float)\d+v\d+_t',name),name
     shape=re.fullmatch(r'\{ \[(\d+) x (i\d+|float|double|half)\] \}',ft[name]);assert shape,(name,ft[name]);bits=int(shape[2][1:])if shape[2].startswith('i')else{'float':32,'double':64,'half':16}[shape[2]];assert int(shape[1])*bits in (64,128),(name,ft[name]);new_types.append(name+' = type '+ft[name]+'\n')
    extended=current+('\n'+''.join(new_types)if new_types else'');assert base.state(extended)==base.state(current)==STATE
    empty=re.search(r'^!bunker\.guest\.call\.lowering = !\{\}$',fresh,re.M);fresh_for_splice=fresh.replace(empty[0],'')if empty else fresh
    assert base.functions(fresh_for_splice)==base.functions(fresh)
    result,proof=splice.splice_polled_target(base,extended,fresh_for_splice,h);before=base.functions(current)[h];after=base.functions(result)[h];onamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{.*\}$',current,re.M);nnamed=re.search(r'^!bunker\.guest\.call\.lowering = !\{.*\}$',result,re.M);ob=onamed[0]if onamed else None;nb=nnamed[0]if nnamed else None
    if empty:assert nb==ob
    inverse=result.replace(after,before);inverse=inverse.replace(nb,ob)if nb!=ob else inverse;assert inverse.startswith(current);suffix=inverse[len(current):];assert result.endswith(suffix)and suffix
    operations[kind].append(dict(head=hex(h),before_module_sha256=digest(current),after_body_sha256=digest(after),suffix=suffix,old_named_metadata=ob,new_named_metadata=nb,empty_fresh_named_metadata_ignored=bool(empty),new_local_vector_wrapper_type_declarations=new_types,old_type_declarations_unchanged=True,State_closure_unchanged=True,step_inverse_exact=proof['whole_module_inverse_exact']))
    return result
   for span in group['candidate_original_spans']:
    h=int(span['head'],0);assert h==int(span['low'],0)and h in of and hex(h)in base.errors(of);end=int(span['high'],0);size=end-h;seg=next(s for s in segments if s['p_vaddr']<=h-0x70000000 and end-0x70000000<=s['p_vaddr']+s['p_filesz']);at=seg['p_offset']+h-0x70000000-seg['p_vaddr'];blob=image[at:at+size];assert len(blob)==span['bytes']==size
    td=out/hex(h);tn=native/hex(h);td.mkdir();tn.mkdir();binary=td/'original.bin';binary.write_bytes(blob);(td/'original-disassembly.txt').write_text(''.join(f'{i.address:08x} {bytes(i.bytes).hex()} {i.mnemonic} {i.op_str}\n'for i in Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN).disasm(blob,h)))
    freshp=tn/'fresh.raw.ll';statp=tn/'lowering-stats.json';single=tn/'fresh.polled.ll';reuse_case=reuse_ir.get(hex(h))
    if reuse_case:
     assert reuse_case['global_index']==n and reuse_case['original_bytes']['sha256']==sha(binary)
     for name,key in [('fresh.raw.ll','fresh_raw_IR'),('fresh.polled.ll','fresh_polled_IR'),('lowering-stats.json','lowering_stats')]:pin(reuse_case[key]);shutil.copyfile(reuse_case[key]['path'],tn/name)
     save(td/'prepared-target-IR-reuse.json',dict(prepared_only=True,reuse_plan=d(a.reuse_target_ir_plan),target=reuse_case,no_reexecuted_lift_or_poll=True))
    else:run([tools['lifter']['path'],'--arch','aarch64','--os','linux','--semantics_dir',Path(tools['semantics']['path']).parent,'--bytes_file',binary,'--address',h,'--entry_address',h,'--trace_heads_file',headfile,'--guest_call_transfer=true','--guest_call_transfer_stats_out',statp,'--ir_out',freshp],'lift',td)
    fresh=freshp.read_text();ff=base.functions(fresh);assert set(ff)=={h}and base.state(fresh)==STATE;stats=read(statp);assert stats['passed']and stats['State_bytes']==1200 and stats['SP_offset']==1040 and stats['PC_offset']==1056
    if base.errors(ff):
     row=dict(head=hex(h),global_index=n,held=True,selected=False,old_body_retained=True,fresh_IR=d(freshp),new_error_blocks=base.errors(ff),original_bytes=d(binary),original_disassembly=d(td/'original-disassembly.txt'),reason='Newly exposed unsupported instruction after NM repair; no ISA expansion authorized.');save(td/'held.json',row);holds.append(row);body_holds.append(row);print('BODY-HELD',hex(h),flush=True);continue
    if not reuse_case:run([producer['poll']['path'],freshp,single],'poll',td)
    single_text=single.read_text();assert not base.errors(base.functions(single_text))and base.state(single_text)==STATE
    raw=splice_step('raw',raw,fresh,h);polled=splice_step('polled',polled,single_text,h);accepted.append(h);target_rows.append(dict(head=hex(h),original_bytes=d(binary),fresh_raw_IR=d(freshp),fresh_polled_IR=d(single),lowering_stats=d(statp),no_unsupported=True))
   if not accepted:
    save(out/'acceptance.json',dict(passed=True,selected=False,no_replacement=True,all_targets_held=True,held_targets=holds));print('MODULE-HELD',n,flush=True);continue
   rf=base.functions(raw);pf=base.functions(polled);protected=set(of)-set(accepted);assert all(rf[h]==of[h]and pf[h]==opf[h]for h in protected)and set(rf)==set(of)==set(pf)and base.internal_functions(polled)==base.internal_functions(oldp)
   for kind,current,original,original_functions in [('raw',raw,old,of),('polled',polled,oldp,opf)]:
    for op in reversed(operations[kind]):
     assert current.endswith(op['suffix']);current=current[:-len(op['suffix'])];current=current.replace(op['new_named_metadata'],op['old_named_metadata'])if op['new_named_metadata']!=op['old_named_metadata']else current;h=int(op['head'],0);body=base.functions(current)[h];assert digest(body)==op['after_body_sha256'];current=current.replace(body,original_functions[h]);assert digest(current)==op['before_module_sha256']
    assert current==original
   oldmd={m[1]:m[0]for m in re.finditer(r'^!(\d+) = .*$',oldp,re.M)};newmd={m[1]:m[0]for m in re.finditer(r'^!(\d+) = .*$',polled,re.M)};assert all(newmd[k]==v for k,v in oldmd.items())
   expected=sorted(h for h in base.errors(of)if int(h,0)not in accepted);assert sorted(base.errors(rf))==sorted(base.errors(pf))==expected
   rawp=native/'candidate.raw.ll';polledp=native/'candidate.polled.ll';rawp.write_text(raw);polledp.write_text(polled);save(out/'module-inverse.json',dict(passed=True,raw_whole_module_inverse_exact=True,polled_whole_module_inverse_exact=True,old_numeric_metadata_definitions_preserved=True,operations=operations))
   optimized=native/'optimized.ll';audit=native/'optimized-guard-audit.json';obj=native/'candidate.polled.o';run([producer['llvm_opt']['path'],'-passes=verify','-disable-output',polledp],'verify',out);run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-S','-emit-llvm',polledp,'-o',optimized],'optimized-IR',out);run([producer['optimized_auditor']['path'],optimized,audit],'audit-guards',out);assert read(audit)['passed'];run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',polledp,'-o',obj],'compile-once',out)
   symbols=subprocess.check_output([producer['nm']['path'],'--format=posix','--extern-only',obj],text=True);defs={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M)};refs={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M)};assert defs==set(of)and refs<=heads
   asms={}
   for label,path in [('old',Path(oldobj['path'])),('candidate',obj)]:_,asm,_=base.coff_projection('/usr/lib/llvm-18/bin/llvm-objdump',path);(out/(label+'-disassembly.txt')).write_text(asm);asms[label]=asm
   proof=checker.prove_neighbors(oldobj['path'],obj,set(accepted),asms['old'],asms['candidate']);assert proof['passed']and proof['protected_functions']==128-len(accepted);proof.update(old_object=d(oldobj['path']),candidate_object=d(obj),checker=d(checkp));save(out/'native-preservation.json',proof)
   dest=out/'candidate.polled.o';shutil.copyfile(obj,dest);assert sha(dest)==sha(obj);objects[n]=d(dest);row=dict(passed=True,selected=False,global_index=n,proposed_heads=group['candidate_heads'],accepted_heads=list(map(hex,accepted)),held_targets=holds,old_object=d(oldobj['path']),candidate_object=d(dest),raw_IR=d(rawp),polled_IR=d(polledp),module_inverse=d(out/'module-inverse.json'),native_preservation=d(out/'native-preservation.json'),raw_neighbors_byte_exact=len(protected),polled_neighbors_byte_exact=len(protected),all_non_target_native_contexts_preserved=True,old_internal_helpers_byte_exact=True,old_numeric_metadata_definitions_preserved=True,State_size=1200,State_align=16,State_type_closure_sha256=STATE,old_poll_coverage=base.coverage(opf),new_poll_coverage=base.coverage(pf),optimized_guard_audit=d(audit),all_direct_guest_refs_closed=True,external_guest_references=sorted(refs),target_bodies=target_rows,compile_invocations=1)
   save(out/'acceptance.json',row);modules.append(row);print('UNITY-MODULE-READY',n,len(accepted),len(holds),flush=True);del old,oldp,raw,polled,of,opf,rf,pf;gc.collect()
  changed=[i for i in range(4660)if objects[i]!=parent['objects'][i]];assert changed==sorted(r['global_index']for r in modules);save(a.out/'object-manifest.json',objects)
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,selected=False,component_only=True,scope='Approved normal-entry Unity NM population only; unprocessed and held bodies are not qualified.',parent_manifest=d(pp),approved_static_plan=d(planp),requested_indices=wanted,requested_heads=sum(len(g['candidate_heads'])for g in groups),completed_modules=modules,held_bodies=body_holds,held_body_count=len(body_holds),repaired_heads=sum(len(r['accepted_heads'])for r in modules),replaced_indices=changed,object_manifest=d(a.out/'object-manifest.json'),guest_objects=4660,trace_heads=595548,headers=headers,all_four_generated_headers_unchanged=True,no_host_or_ISA_source_changes=True,other_object_descriptors_unchanged=4660-len(changed),source=d(Path(__file__)),executed_source=d(a.out/'executed-builder.py'),toolchain=d(tools_path),compiled_semantic_reuse=d(reusep),native_checker=d(checkp),native_checker_qualification=d(checker_gate),held_inputs=held,commands=commands,actual_original_function_execution=False,original_game_execution=False,limits='Static prepared candidates, not selected. No new ISA support, no complete131 qualification unless every body is explicitly covered. Other7interior/11mixed bodies excluded. No visible frame or gameplay claim.');save(a.out/'acceptance.json',result);print('UNITY-NM-COMPONENT',json.dumps(d(a.out/'acceptance.json')),flush=True)
 except BaseException as ex:
  save(a.out/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands,completed_modules=modules,held_bodies=body_holds));raise
if __name__=='__main__':main()
