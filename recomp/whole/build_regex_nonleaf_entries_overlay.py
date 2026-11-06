"""Build the exact 58 original RegexInterpreter.Go table entries, unselected.

Run in the retained WSL tools environment. Default is a read-only dry run.
Only the pinned sparse pre-inliner nonleaf producer is executed: one new object,
no old shard regeneration, replacement, full host build, or game execution.
"""
from pathlib import Path
import argparse, copy, hashlib, json, re, shutil, subprocess, traceback

W=Path('/mnt/c/GitRepos/bunker/recomp/work')
L=Path('/home/user/bunker-recomp/recomp/work')
PARENT='71ae305452fbc7a3436ff825e79cdf5c0b4fbbe78da810a8ca3ca4cec0f17de6'
BOUNDARY='3d4bd2f04a004e02d77003786883a41df0333ed0bc1bfca8666e66cbfbd4b002'
BASE_PLAN='dabb79975775ccb4f075adf7b931113af2045e3c601f8b178410ee4e90f4dd17'
PRODUCER='f5dab6b938c37869462762a4d807c5a902bdb8b86f0235564a51b3518a7cde6d'
PAIR='d24e0a81215b8c636da04505b220f37ab5b8491ef78cecc6b071ee22aabbabcf'
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def d(p):
 p=Path(p);return dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_bytes())
def save(p,v):
 assert not p.exists(),p
 p.write_text(json.dumps(v,indent=2)+'\n')
def pin(p,digest):
 assert sha(p)==digest,p
 return read(p)

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--out',type=Path,default=W/'regex-nonleaf-entry-packet1')
 ap.add_argument('--native-out',type=Path,default=L/'regex-nonleaf-entry-candidate1')
 ap.add_argument('--execute',action='store_true')
 a=ap.parse_args()
 parent_path=W/'windows-first-frame-entropy-device1/overlay.json'
 boundary_path=W/'runtime9-unresolved-boundary1/acceptance.json'
 base_path=W/'neg4s1-il2cpp-entry-preparation1/plan.json'
 producer_path=base_path.with_name('build_candidate.py')
 pair_path=W/'integer-popcount8b-preparation1/build1/acceptance.json'
 parent=pin(parent_path,PARENT);boundary=pin(boundary_path,BOUNDARY)
 base=pin(base_path,BASE_PLAN);assert sha(producer_path)==PRODUCER;pair=pin(pair_path,PAIR)
 assert boundary['passed'] and boundary['FDE']==['0x84315734','0x84316890']
 assert boundary['retained_target_unsupported_calls']==0
 heads=[int(h,0) for h in boundary['missing_heads']]
 assert len(heads)==58 and heads==sorted(set(heads))
 assert all(0x84315734<h<0x84316890 and h%4==0 for h in heads)
 table_path=Path(boundary['tables']['path']);tables=pin(table_path,boundary['tables']['sha256'])
 rows=[r for t in tables['tables'] for r in t['rows']]
 assert len(rows)==83 and sorted({int(r['target'],0) for r in rows})==heads
 assert all(not r['selected'] for r in rows)
 assert len(parent['objects'])==4657 and parent['trace_heads']==595470
 assert parent['objects'][3814]['sha256']==boundary['current_selected_object']['sha256']
 header=Path(parent['trace_header']['path']);assert sha(header)==parent['trace_header']['sha256']
 old=header.read_bytes()
 decl=re.compile(rb'extern "C" Memory \*sub_([0-9a-f]+)\(State &,addr_t,Memory \*\);\n')
 row=re.compile(rb'  \{0x([0-9a-f]+),sub_([0-9a-f]+)\},\n')
 oldlines=old.splitlines(keepends=True)
 oldheads=[int(m[1],16) for line in oldlines if(m:=decl.fullmatch(line))]
 oldrows=[int(m[1],16) for line in oldlines if(m:=row.fullmatch(line))]
 assert oldheads==oldrows==sorted(set(oldheads)) and len(oldheads)==595470
 assert not set(oldheads)&set(heads)
 # This unrelated preexisting untracked tool is provenance only; never write it.
 fmod=Path(__file__).with_name('build_unity_fmod_nonleaf_entries_overlay.py')
 assert sha(fmod)=='40f852fa45f180956200afa835d9a21ca250409bec621f46ff3fd6511651e4e0'
 if not a.execute:
  print(json.dumps(dict(dry_run=True,heads=list(map(hex,heads)),objects_to_build=1,
   old_objects_preserved=4657,proposed_objects=4658,proposed_heads=595528,
   parent=d(parent_path),boundary=d(boundary_path),out=str(a.out),native_out=str(a.native_out))))
  return
 assert not a.out.exists() and not a.native_out.exists()
 a.out.mkdir();prep=a.out/'preparation';prep.mkdir()
 shutil.copyfile(__file__,prep/'executed-builder.py')
 original_pins={str(p):sha(p) for p in (parent_path,boundary_path,base_path,producer_path,pair_path,table_path,header,fmod,Path(__file__))}
 try:
  def emit(name,values):
   p=prep/name;p.write_text(''.join(hex(v)+'\n' for v in values));return d(p)
  p=copy.deepcopy(base);p['all_heads']=emit('all-heads.txt',sorted(oldheads+heads))
  cursor=0
  for m in p['modules']:
   values=sorted([h for h in oldheads if m['base']<=h<m['base']+0x10000000]+(heads if m['name']=='il2cpp' else []))
   m.update(heads=emit(m['name']+'-heads.txt',values),head_count=len(values),shards=(len(values)+127)//128,global_object_start=cursor)
   cursor+=m['shards']
  assert sum(m['head_count'] for m in p['modules'])==595528
  tool=Path(pair['toolchain_dir'])
  p['lifter']=d(tool/'remill-lift');p['semantics']=d(tool/'aarch64.bc')
  assert p['lifter']['sha256']==pair['toolchain']['remill-lift'] and p['semantics']['sha256']==pair['toolchain']['aarch64.bc']
  p['semantics_SHA256']=p['semantics']['sha256']
  save(prep/'compatible-cache-catalog.json',dict(source_plans={},sealed_caches={}))
  held_producer=prep/'build_candidate.py';shutil.copyfile(producer_path,held_producer)
  assert sha(held_producer)==PRODUCER
  p.update(status='Exactly58 RegexInterpreter.Go guarded table entries, one unselected sparse object.',
   expected_fixed_heads=595528,expected_fixed_objects=cursor,old_selected_objects=4657,
   compatible_cache_catalog=d(prep/'compatible-cache-catalog.json'),
   qualification_jobs=[dict(module='il2cpp',name='regex-table-cases',entries=emit('entries.txt',heads),head_count=58)],
   qualification_output=str(a.native_out),toolchain_qualification=d(W/'vector-cnt8b-qualification1/acceptance.json'),
   current_isolated_integer_toolchain_build=d(pair_path),selection_parent_overlay=d(parent_path),
   original_indirect_entry_audit=dict(boundary=d(boundary_path),tables=d(table_path)),
   authorization_scope='Only the58 exact guarded rows targets; no automatic closure expansion, full build, game, or old object changes.',
   sparse_scope=dict(actual_objects_to_build=1,actual_entries_to_build=58,parent_selected_objects=4657,
    parent_selected_heads=595470,proposed_append_object_index=4657,proposed_selected_objects_after_append=4658,
    proposed_selected_heads_after_append=595528,old_selected_objects_preserved=4657,existing_selected_objects_replaced=0,
    all_selected_native_objects_replaced=False,no_automatic_entry_expansion=True),
   producer_schema_disclosure='Inherited full-partition fields are hypothetical only; mode is qualification with exactly one58-entry job. No full partition is built.',
   producer=d(held_producer),preparer=d(Path(__file__)))
  save(prep/'plan.json',p)
  command=[str(L/'tools/bin/python'),str(held_producer),'--plan',str(prep/'plan.json'),
   '--plan-sha256',sha(prep/'plan.json'),'--producer-sha256',PRODUCER,'--mode','qualification','--execute']
  save(prep/'launch.json',dict(argv=command))
  subprocess.run(command,check=True)
  result_path=prep/'qualification-result.json'
  q=read(result_path)
  assert q['built'] and len(q['results'])==1 and q['plan']==d(prep/'plan.json')
  r=q['results'][0]
  assert r['heads']==list(map(hex,heads)) and not r['unsupported_heads']
  assert r['State']==dict(bytes=1200,align=16,type_closure_sha256=STATE)
  assert r['all_references_closed_against_fixed_inventory']
  assert set(map(lambda h:int(h,0),r['native_references']))<=set(oldheads)
  for name in ('object','raw_ir','polled_ir','lowering_stats','optimized_guard_audit'):
   assert sha(r[name]['path'])==r[name]['sha256']
  result=[];added=[];di=ri=0
  for line in oldlines:
   dm=decl.fullmatch(line);rm=row.fullmatch(line)
   if dm:
    while di<len(heads) and heads[di]<int(dm[1],16):
     v=f'extern "C" Memory *sub_{heads[di]:x}(State &,addr_t,Memory *);\n'.encode();result.append(v);added.append(v);di+=1
   if rm:
    while ri<len(heads) and heads[ri]<int(rm[1],16):
     v=f'  {{0x{heads[ri]:x},sub_{heads[ri]:x}}},\n'.encode();result.append(v);added.append(v);ri+=1
   result.append(line)
  assert di==ri==58 and len(added)==116
  inverse=b''.join(v for v in result if v not in set(added));assert inverse==old
  (a.out/'game_traces.h').write_bytes(b''.join(result))
  (a.out/'objects').mkdir();obj=a.out/'objects/regex-table-cases.o';shutil.copyfile(r['object']['path'],obj)
  save(a.out/'object-manifest.json',parent['objects']+[d(obj)])
  save(a.out/'trace-header-inverse.json',dict(passed=True,parent=d(header),candidate=d(a.out/'game_traces.h'),
   added_lines=[v.decode() for v in added],added_line_count=116,whole_file_inverse_sha256=hashlib.sha256(inverse).hexdigest()))
  component=a.out/'component_entries.h'
  component.write_text('#pragma once\n#include "runtime.h"\n'+''.join(f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*);\n' for h in heads)+
   'namespace bunker::regex_nonleaf_entries {\ninline const recomp::Trace kAddedTraces[] = {\n'+''.join(f'  {{0x{h:x},sub_{h:x}}},\n' for h in heads)+'};\n}\n')
  for path,digest in original_pins.items():assert sha(path)==digest,path
  packet=dict(passed=True,selected=False,scope='Exact58 original RegexInterpreter.Go guarded table entries; static sparse codegen only.',
   parent_manifest=d(parent_path),original_static_boundary=d(boundary_path),tables=d(table_path),qualification=d(result_path),
   producer=d(Path(__file__)),nonleaf_codegen_producer=d(held_producer),plan=d(prep/'plan.json'),toolchain_build=d(pair_path),
   candidate_object=d(obj),object_manifest=d(a.out/'object-manifest.json'),trace_header=d(a.out/'game_traces.h'),
   trace_header_inverse=d(a.out/'trace-header-inverse.json'),component_trace_header=d(component),
   parent_objects=4657,proposed_objects=4658,append_index=4657,parent_heads=595470,proposed_heads=595528,
   added_heads=r['heads'],State=r['State'],Memory64=True,raw_IR=r['raw_ir'],polled_IR=r['polled_ir'],
   optimized_guard_audit=r['optimized_guard_audit'],lowering_stats=r['lowering_stats'],
   external_original_guest_references=r['native_references'],finite_execution_qualification_pending=True,
   checks=dict(old_object_descriptors_exact_prefix=True,old_header_exact_inverse=True,no_unsupported_instructions=True,
    closed_original_guest_references=True,preinliner_GuestCall_and_poll_audit_passed=True,untracked_FMOD_tool_preserved=True),
   limits='No existing source/object changed. Only58 head entries and116 header lines proposed. Real helper/delegate behavior retained. Finite execution qualification separate; no complete regex, game, or first-frame claim.')
  save(a.out/'acceptance.json',packet);print('REGEX-STATIC-PACKET',json.dumps(d(a.out/'acceptance.json')),flush=True)
 except BaseException as e:
  save(a.out/'failure.json',dict(passed=False,error=str(e),traceback=traceback.format_exc(),original_pins=original_pins))
  raise

if __name__=='__main__':main()
