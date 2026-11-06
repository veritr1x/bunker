"""Build the twelve exact original Unity switch entries, unselected.

Default is a read-only dry run. Execution builds one sparse object, preserving
all 4,658 selected objects. Selection and real-game execution belong elsewhere.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,copy,hashlib,json,re,shutil,subprocess,traceback

W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
PARENT='239b08f32857c10ca74a911077544e803a51d1149c2902e8c2ab0d1aa1916123'
BOUNDARY='70cd411005108ed4309b2a3953f9d767d856a7f107f2cd8dfb6098f16c5cdff7'
BASE='dabb79975775ccb4f075adf7b931113af2045e3c601f8b178410ee4e90f4dd17'
PRODUCER='f5dab6b938c37869462762a4d807c5a902bdb8b86f0235564a51b3518a7cde6d'
TOOLS='968e994489732dad02e501e0f10396cff5029e58794a7956de0ff7afc4b068d0'
SSHLL='0619487932d06e0b7f540d15d5957fc5d8a4ffbc2ba5e209b7d8f17f42094b42'
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def d(p):
 p=Path(p);return dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def pin(p,h):assert sha(p)==h,p;return read(p)
def verify_objects(rows):
 def verify(r):assert sha(r['path'])==r['sha256'],r['path'];return True
 with ThreadPoolExecutor(max_workers=2)as pool:assert all(pool.map(verify,rows))

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'unity-701078-switch-entry-packet1');ap.add_argument('--native-out',type=Path,default=L/'unity-701078-switch-entry-candidate1');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 pp=W/'windows-first-frame-sshll-crash1/overlay.json';bp=W/'runtime16-unresolved-boundary1/acceptance.json';basep=W/'neg4s1-il2cpp-entry-preparation1/plan.json';producer=basep.with_name('build_candidate.py');tp=W/'sshll-toolchain1/tools-ready.json';qp=W/'sshll-qualification1/acceptance.json'
 parent=pin(pp,PARENT);boundary=pin(bp,BOUNDARY);base=pin(basep,BASE);assert sha(producer)==PRODUCER;tools=pin(tp,TOOLS);qualification=pin(qp,SSHLL)
 assert boundary['passed']and boundary['FDE']==['0x701068d8','0x70107f10']and qualification['passed']
 assert all(r['unsupported_calls']==0 and r['indirect_jump_calls']==3 for r in boundary['retained_IR'].values())
 heads=list(map(lambda h:int(h,0),boundary['missing_heads']));assert len(heads)==12 and heads==sorted(set(heads))and all(0x701068d8<h<0x70107f10 and h%4==0 for h in heads)
 tablep=Path(boundary['tables']['path']);tables=pin(tablep,boundary['tables']['sha256']);rows=[r for t in tables['tables']for r in t['rows']];assert len(rows)==16 and sorted({int(r['target'],0)for r in rows})==heads and all(not r['selected']for r in rows)
 assert len(parent['objects'])==4658 and parent['trace_heads']==595528 and parent['objects'][301]['sha256']=='333b419d038f445af856561e4139ced45025433a0f23c5d904fc1fb53c4456c0'
 header=Path(parent['trace_header']['path']);assert sha(header)==parent['trace_header']['sha256'];old=header.read_bytes();oldlines=old.splitlines(keepends=True)
 decl=re.compile(rb'extern "C" Memory \*sub_([0-9a-f]+)\(State &,addr_t,Memory \*\);\n');row=re.compile(rb'  \{0x([0-9a-f]+),sub_([0-9a-f]+)\},\n')
 oldheads=[int(m[1],16)for line in oldlines if(m:=decl.fullmatch(line))];oldrows=[int(m[1],16)for line in oldlines if(m:=row.fullmatch(line))];assert oldheads==oldrows==sorted(set(oldheads))and len(oldheads)==595528 and not set(oldheads)&set(heads)
 other_headers={n:d(pp.parent/n)for n in ['game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
 if not a.execute:print(json.dumps(dict(dry_run=True,new_heads=list(map(hex,heads)),objects_to_build=1,old_objects_preserved=4658,proposed_objects=4659,proposed_heads=595540)));return
 assert not a.out.exists()and not a.native_out.exists();a.out.mkdir();prep=a.out/'preparation';prep.mkdir();shutil.copyfile(__file__,prep/'executed-builder.py')
 held={str(p):sha(p)for p in [pp,bp,basep,producer,tp,qp,tablep,header,Path(__file__)]};held.update({r['path']:r['sha256']for r in other_headers.values()})
 try:
  print('VERIFY-OLD-OBJECTS-PRE',len(parent['objects']),flush=True);verify_objects(parent['objects'])
  def emit(name,values):
   p=prep/name;p.write_text(''.join(hex(v)+'\n'for v in values));return d(p)
  p=copy.deepcopy(base);p['all_heads']=emit('all-heads.txt',sorted(oldheads+heads));cursor=0
  for m in p['modules']:
   values=sorted([h for h in oldheads if m['base']<=h<m['base']+0x10000000]+(heads if m['name']=='unity'else []));m.update(heads=emit(m['name']+'-heads.txt',values),head_count=len(values),shards=(len(values)+127)//128,global_object_start=cursor);cursor+=m['shards']
  assert sum(m['head_count']for m in p['modules'])==595540
  for k in ['lifter','semantics']:assert sha(tools[k]['path'])==tools[k]['sha256'];p[k]=tools[k]
  p['semantics_SHA256']=p['semantics']['sha256'];save(prep/'compatible-cache-catalog.json',dict(source_plans={},sealed_caches={}));heldproducer=prep/'build_candidate.py';shutil.copyfile(producer,heldproducer);assert sha(heldproducer)==PRODUCER
  p.update(status='Exactly12 original Unity guarded switch targets; one unselected sparse object.',expected_fixed_heads=595540,expected_fixed_objects=cursor,old_selected_objects=4658,compatible_cache_catalog=d(prep/'compatible-cache-catalog.json'),qualification_jobs=[dict(module='unity',name='unity-table-cases',entries=emit('entries.txt',heads),head_count=12)],qualification_output=str(a.native_out),toolchain_qualification=d(qp),current_isolated_integer_toolchain_build=d(tp),selection_parent_overlay=d(pp),original_indirect_entry_audit=dict(boundary=d(bp),tables=d(tablep)),authorization_scope='Only twelve exact targets from three guarded tables; no automatic expansion, old object replacement, full host build or game.',sparse_scope=dict(actual_objects_to_build=1,actual_entries_to_build=12,parent_selected_objects=4658,parent_selected_heads=595528,proposed_append_object_index=4658,proposed_selected_objects_after_append=4659,proposed_selected_heads_after_append=595540,old_selected_objects_preserved=4658,existing_selected_objects_replaced=0,all_selected_native_objects_replaced=False,no_automatic_entry_expansion=True),producer_schema_disclosure='Inherited full-partition/legacy new_indirect_heads fields are hypothetical and not used by qualification mode; exact one-job twelve-entry sparse_scope is authoritative.',producer=d(heldproducer),preparer=d(Path(__file__)))
  save(prep/'plan.json',p);command=[str(L/'tools/bin/python'),str(heldproducer),'--plan',str(prep/'plan.json'),'--plan-sha256',sha(prep/'plan.json'),'--producer-sha256',PRODUCER,'--mode','qualification','--execute'];save(prep/'launch.json',dict(argv=command));subprocess.run(command,check=True)
  rp=prep/'qualification-result.json';q=read(rp);assert q['built']and len(q['results'])==1 and q['plan']==d(prep/'plan.json');r=q['results'][0]
  assert r['heads']==list(map(hex,heads))and not r['unsupported_heads']and r['State']==dict(bytes=1200,align=16,type_closure_sha256=STATE)and r['all_references_closed_against_fixed_inventory']
  assert set(map(lambda h:int(h,0),r['native_references']))<=set(oldheads+heads)
  for n in ['object','raw_ir','polled_ir','lowering_stats','optimized_guard_audit']:assert sha(r[n]['path'])==r[n]['sha256']
  result=[];added=[];di=ri=0
  for line in oldlines:
   dm=decl.fullmatch(line);rm=row.fullmatch(line)
   if dm:
    while di<len(heads)and heads[di]<int(dm[1],16):
     v=f'extern "C" Memory *sub_{heads[di]:x}(State &,addr_t,Memory *);\n'.encode();result.append(v);added.append(v);di+=1
   if rm:
    while ri<len(heads)and heads[ri]<int(rm[1],16):
     v=f'  {{0x{heads[ri]:x},sub_{heads[ri]:x}}},\n'.encode();result.append(v);added.append(v);ri+=1
   result.append(line)
  assert di==ri==12 and len(added)==24;inverse=b''.join(v for v in result if v not in set(added));assert inverse==old
  (a.out/'game_traces.h').write_bytes(b''.join(result));(a.out/'objects').mkdir();obj=a.out/'objects/unity-table-cases.o';shutil.copyfile(r['object']['path'],obj);save(a.out/'object-manifest.json',parent['objects']+[d(obj)])
  save(a.out/'trace-header-inverse.json',dict(passed=True,parent=d(header),candidate=d(a.out/'game_traces.h'),added_lines=[v.decode()for v in added],added_line_count=24,whole_file_inverse_sha256=hashlib.sha256(inverse).hexdigest()))
  component=a.out/'component_entries.h';component.write_text('#pragma once\n#include "runtime.h"\n'+''.join(f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*);\n'for h in heads)+'namespace bunker::unity_701078_switch_entries {\ninline const recomp::Trace kAddedTraces[] = {\n'+''.join(f'  {{0x{h:x},sub_{h:x}}},\n'for h in heads)+'};\n}\n')
  print('VERIFY-OLD-OBJECTS-POST',len(parent['objects']),flush=True);verify_objects(parent['objects'])
  for path,digest in held.items():assert sha(path)==digest,path
  packet=dict(passed=True,selected=False,scope='Exact twelve original Unity guarded table entries; static sparse code generation only.',parent_manifest=d(pp),original_static_boundary=d(bp),tables=d(tablep),qualification=d(rp),producer=d(Path(__file__)),nonleaf_codegen_producer=d(heldproducer),plan=d(prep/'plan.json'),toolchain_build=d(tp),semantic_qualification=d(qp),candidate_object=d(obj),object_manifest=d(a.out/'object-manifest.json'),trace_header=d(a.out/'game_traces.h'),trace_header_inverse=d(a.out/'trace-header-inverse.json'),component_trace_header=d(component),other_three_generated_headers=other_headers,parent_objects=4658,proposed_objects=4659,append_index=4658,parent_heads=595528,proposed_heads=595540,added_heads=r['heads'],State=r['State'],Memory64=True,raw_IR=r['raw_ir'],polled_IR=r['polled_ir'],optimized_guard_audit=r['optimized_guard_audit'],lowering_stats=r['lowering_stats'],external_original_guest_references=r['native_references'],finite_execution_qualification_pending=True,checks=dict(old_object_descriptors_exact_prefix=True,all4658_old_objects_physically_hashed_pre_and_post=True,old_header_exact_inverse=True,other_three_generated_headers_exact=True,no_unsupported_instructions=True,closed_original_guest_references=True,preinliner_GuestCall_and_poll_audit_passed=True),limits='No existing source/object changed. Only12 heads/24 header lines proposed. Finite original branch/successor qualification separate; no whole outer FDE, original startup, frame or gameplay claim.')
  save(a.out/'acceptance.json',packet);print('UNITY-SWITCH-STATIC-PACKET',json.dumps(d(a.out/'acceptance.json')),flush=True)
 except BaseException as ex:save(a.out/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),held_inputs=held));raise
if __name__=='__main__':main()
