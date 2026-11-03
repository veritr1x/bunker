"""Exact attributed FCSEL transport repair, followed by separately gated compilation.

No relift, fresh-body-equivalence claim, PhaseA dependency or game execution.
"""
import argparse,concurrent.futures,hashlib,importlib.util,json,re,shutil,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_SHA='e3f3debd8a7ca636ed85a942d48fbccf58a45d619242ce50df293cef6a535bbf'
MODE='exact-attributed-fcsel-transport-v1'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
bp=HERE/'base.py'
if not bp.exists():bp=HERE/'build_selected_fcsel_batch.py'
assert sha(bp)==BASE_SHA
B=load(bp,'exact_transport_base');W,L=B.W,B.L

def validate_condition(path,expected,manifest_sha,manifest):
 assert sha(path)==expected;c=read(path);functions=manifest['affected_functions'];sites=manifest['legacy_copies'];assert c['passed']and c['manifest_sha256']==manifest_sha and c['functions']==functions and c['sites']==sites and c['evaluations']==sites*16 and c['unknown']==0
 wanted={}
 for row in manifest['objects']:
  for f in row['functions']:
   for site in f['sites']:
    key=(row['index'],int(f['head'],16),site['IR_offset']);assert key not in wanted;wanted[key]=(f['captured_body_sha256'],site)
 assert len(wanted)==sites
 expected_bodies={f['captured_body_path']:f['captured_body_sha256']for row in manifest['objects']for f in row['functions']};assert c['captured_body_pins']==expected_bodies
 def canonical(candidate):
  return (int(candidate['pc'],0)if isinstance(candidate['pc'],str)else candidate['pc'],int(candidate['word'],16)if isinstance(candidate['word'],str)else candidate['word'],*(int(candidate[n])for n in('width','rd','rn','rm','cond')))
 def condition(cond,nzcv):
  n,z,carry,v=(nzcv>>3)&1,(nzcv>>2)&1,(nzcv>>1)&1,nzcv&1
  if cond>=14:return True
  result=[z,carry,n,v,carry and not z,n==v,(n==v)and not z][cond>>1]
  return bool(not result if cond&1 else result)
 seen=set()
 for record in c['records']:
  key=(record['index'],int(record['head'],16),record['IR_offset']);assert key in wanted and key not in seen;seen.add(key);body_sha,site=wanted[key]
  assert record['passed']and record['body_sha256']==body_sha and record['evaluations']==16 and record['original_candidate_list_preserved']is True
  matching=record['matching_original_candidates'];nonmatching=record['nonmatching_original_candidates'];assert matching
  original=sorted(canonical(x)for x in site['original_opcode_candidates']);assert sorted(canonical(x)for x in matching+nonmatching)==original
  selected=record['selected_registers_by_NZCV'];truth=record['predicate_truth_table'];assert len(selected)==len(truth)==16 and all(x in(0,1,False,True)for x in truth)
  arms=[record['true_source_register'],record['false_source_register']];assert sorted(arms)==sorted(site['source_vector_registers'])and selected==[arms[0]if b else arms[1]for b in truth]
  freshness=record['flag_freshness'];assert all(freshness[k]is True for k in('same_basic_block','no_intervening_store','no_intervening_opaque_call','no_intervening_atomic'));assert freshness['current_instruction_PC_store_offset']<=freshness['first_flag_load_offset']<record['IR_offset']
  for candidate in matching:
   assert canonical(candidate)in original
   _,_,_,_,rn,rm,cond=canonical(candidate);expected_registers=[rn if condition(cond,flags)else rm for flags in range(16)]
   assert selected==expected_registers
 assert seen==set(wanted)
 return c

def check_fixed(plan):
 for p,h in plan['fixed_inputs'].items():assert sha(p)==h,p

def jobs(rows,count,worker,progress,label):
 started=time.time();results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=count)as pool:
  queue=iter(rows);pending={pool.submit(worker,next(queue))for _ in range(min(count,len(rows)))}
  while pending:
   done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    r=f.result();results.append(r);save(progress,{'phase':label,'completed':len(results),'planned':len(rows),'elapsed_seconds':time.time()-started,'results':sorted(results,key=lambda x:x['index'])})
    if len(results)%25==0 or not r['passed']:print(label,len(results),'/',len(rows),r['index'],r.get('hold_reason',r.get('holds',0)),flush=True)
    row=next(queue,None)
    if row is not None:pending.add(pool.submit(worker,row))
 return sorted(results,key=lambda x:x['index'])

def plan(a):
 assert a.manifest and a.checker and a.checker_qualification and a.condition_qualification and a.native_out
 assert sha(a.manifest)==a.manifest_sha;m=read(a.manifest);assert m['passed']and m['read_only']and len(m['objects'])==m['affected_objects'];assert sum(len(r['functions'])for r in m['objects'])==m['affected_functions'];assert sum(len(f['sites'])for r in m['objects']for f in r['functions'])==m['legacy_copies']
 assert sha(a.checker)==a.checker_sha and sha(a.checker_qualification)==a.checker_qualification_sha and read(a.checker_qualification)['passed'];c=B.load_checker(a.checker);assert hasattr(c,'build_transport_candidate')and hasattr(c,'verify_transport_body')
 condition=validate_condition(a.condition_qualification,a.condition_qualification_sha,a.manifest_sha,m)
 assert all(t['passed']for t in condition['selftests']);helper=Path(condition['executed_helper_path']);helper_sha=condition['executed_helper_sha256'];assert helper_sha==condition['helper_source_sha256']and sha(helper)==helper_sha;identity=condition['runtime_compare_identity_source'];assert sha(identity['path'])==identity['sha256']
 O=a.out.resolve();N=a.native_out.resolve();assert not O.exists()and not N.exists()and str(O).startswith(str(W)+'/')and str(N).startswith(str(L)+'/');O.mkdir()
 for source,dest in[(Path(__file__),O/'producer.py'),(bp,O/'base.py'),(a.checker,O/'checker.py'),(helper,O/'condition-helper.py')]:shutil.copy2(source,dest)
 parent=Path(m['selected_input']);assert sha(parent)==m['selected_input_sha256'];game=read(parent);assert len(game['objects'])==3576
 for r in m['objects']:
  assert {k:r['selected_object'][k]for k in('path','sha256')}=={k:game['objects'][r['index']][k]for k in('path','sha256')};assert Path(r['raw_ir']).stat().st_size==r['raw_ir_bytes']
  for f in r['functions']:assert f['sites']and all(s['width']in(32,64)and s['original_opcode_candidates']for s in f['sites'])
 fixed={str(a.manifest.resolve()):a.manifest_sha,str(parent):m['selected_input_sha256'],str(O/'producer.py'):sha(O/'producer.py'),str(O/'base.py'):BASE_SHA,str(O/'checker.py'):a.checker_sha,str(a.checker_qualification.resolve()):a.checker_qualification_sha,str(a.condition_qualification.resolve()):a.condition_qualification_sha,str(B.POLL):B.POLL_SHA}
 assert sha(B.POLL)==B.POLL_SHA
 fixed[str(O/'condition-helper.py')]=helper_sha;fixed[identity['path']]=identity['sha256']
 # Lifter/semantics receipts are ancestry only. Neither tool is invoked here.
 for path,h in[(W/'fcsel-positive2/acceptance.json','b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b'),(W/'fcsel-toolchain-build/compiled-semantic-proof.json','5aa404c19cde7cdec0745316fbc6cfaea0856cfdd357c26738307a390c445779')]:assert sha(path)==h;fixed[str(path)]=h
 tools={n:str(Path(shutil.which(n)).resolve())for n in['clang-18','llvm-nm-18','llvm-objdump-18']}
 for path in tools.values():fixed[path]=sha(path)
 header=parent.parent/'game_traces.h';fixed[str(header)]=sha(header);assert len({int(h,16)for h in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',header.read_text())})==456689
 total=sum(r['raw_ir_bytes']for r in m['objects']);estimate=int(total*2.5+2**30);assert shutil.disk_usage(N.parent).free>estimate
 q={'passed':True,'phase_kind':'exact local FCSEL transport proof then separate compiled vector','proof_mode':MODE,'no_relift':True,'fresh_body_equality_claimed':False,'manifest_path':str(a.manifest.resolve()),'manifest_sha256':a.manifest_sha,'out':str(O),'native_out':str(N),'jobs':a.jobs,'producer_sha256':sha(O/'producer.py'),'checker_path':str(O/'checker.py'),'checker_sha256':a.checker_sha,'checker_qualification_path':str(a.checker_qualification.resolve()),'checker_qualification_sha256':a.checker_qualification_sha,'condition_qualification_path':str(a.condition_qualification.resolve()),'condition_qualification_sha256':a.condition_qualification_sha,'condition_helper_path':str(O/'condition-helper.py'),'condition_helper_sha256':helper_sha,'runtime_compare_identity_source':identity,'functions':m['affected_functions'],'sites':m['legacy_copies'],'objects':len(m['objects']),'tools':tools,'fixed_inputs':fixed,'estimated_output_bytes':estimate,'rule':'Keep original inttoptr SSA unused. Replace only its attributed following load32 with same-SSA trunc carrier to i32, or load64 with same-SSA add carrier,0. All other bytes/names unchanged; exact inverse required.','limits':'No arbitrary fallback/skip. All target site proofs and all16-NZCV condition checks required before any compiler. Current unrelated functions, types, globals, declarations, attrs and metadata remain exact by splice inverse. No game or cohort selection.'};save(O/'plan.json',q);print('TRANSPORT-PLAN',sha(O/'plan.json'),q['objects'],q['functions'],q['sites'],flush=True)

def prove(a,p,m):
 O=a.out.resolve();P=O/'proofs';assert not P.exists();P.mkdir();c=B.load_checker(p['checker_path'])
 def worker(row):
  i=row['index'];E=P/f'object-{i:05}';E.mkdir();records={}
  try:
   for f in row['functions']:
    try:
     oldpath=Path(f['captured_body_path']);assert sha(oldpath)==f['captured_body_sha256'];old=oldpath.read_text();candidate=c.build_transport_candidate(old,sites=f['sites']);r=c.verify_transport_body(old,candidate,sites=f['sites']);assert r.passed,r.hold_reason;assert r.proof['proof_mode']==MODE and r.proof['fresh_body_equality_claimed']is False;assert not B.SHAPE.search(candidate)
     head=int(f['head'],16);body=E/f'{head:x}.ll';body.write_text(candidate);records[f['head']]={'passed':True,'site_count':len(f['sites']),'old_body_path':str(oldpath),'old_body_sha256':f['captured_body_sha256'],'candidate_body_path':str(body),'candidate_body_sha256':sha(body),'proof':r.proof}
    except Exception as target_error:records[f['head']]={'passed':False,'site_count':len(f['sites']),'hold_reason':str(target_error),'traceback':traceback.format_exc()}
   result={'passed':all(r['passed']for r in records.values()),'index':i,'proof_mode':MODE,'functions':records,'sites':sum(len(f['sites'])for f in row['functions']),'module_spliced':False,'compiled':False}
  except Exception as e:result={'passed':False,'index':i,'proof_mode':MODE,'functions':records,'hold_reason':str(e),'traceback':traceback.format_exc()}
  save(E/'proof.json',result);return{'index':i,'passed':result['passed'],'receipt':str(E/'proof.json'),'receipt_sha256':sha(E/'proof.json'),'holds':len(row['functions'])-sum(r['passed']for r in records.values())}
 rr=jobs(m['objects'],p['jobs'],worker,P/'progress.json','TRANSPORT-PROOF');check_fixed(p);q={'passed':len(rr)==p['objects']and all(r['passed']for r in rr),'proof_mode':MODE,'phase':'ALL-EXACT-TRANSPORT-PROOFS','plan_sha256':a.plan_sha,'manifest_sha256':p['manifest_sha256'],'condition_qualification_path':p['condition_qualification_path'],'condition_qualification_sha256':p['condition_qualification_sha256'],'functions':p['functions'],'sites':p['sites'],'objects':rr,'no_relift':True,'fresh_body_equality_claimed':False,'compiled_objects':0};save(P/'acceptance.json',q);print('ALL-TRANSPORT-PROOFS',q['passed'],sha(P/'acceptance.json'),flush=True)

def compile_vector(a,p,m):
 assert a.proof and a.proof_sha and sha(a.proof)==a.proof_sha;proof=read(a.proof);assert proof['passed']and proof['proof_mode']==MODE and proof['phase']=='ALL-EXACT-TRANSPORT-PROOFS'and proof['plan_sha256']==a.plan_sha and proof['manifest_sha256']==p['manifest_sha256']and proof['functions']==p['functions']and proof['sites']==p['sites']
 validate_condition(p['condition_qualification_path'],p['condition_qualification_sha256'],p['manifest_sha256'],m);records={r['index']:r for r in proof['objects']};assert set(records)=={r['index']for r in m['objects']}and all(r['passed']for r in records.values())
 for row in m['objects']:
  rr=records[row['index']];assert sha(rr['receipt'])==rr['receipt_sha256'];q=read(rr['receipt']);assert q['passed']and q['proof_mode']==MODE and set(q['functions'])=={f['head']for f in row['functions']}
  for f in row['functions']:
   r=q['functions'][f['head']];assert r['passed']and r['site_count']==len(f['sites'])and sha(r['candidate_body_path'])==r['candidate_body_sha256']and r['proof']['proof_mode']==MODE
 # Complete-vector and condition guards above precede output/IR-tool/compiler creation.
 O=a.out.resolve();C=O/'compiled';N=Path(p['native_out']);assert not C.exists()and not N.exists();C.mkdir();(C/'objects').mkdir();N.mkdir();c=B.load_checker(p['checker_path']);parent=Path(m['selected_input']);header=parent.parent/'game_traces.h';heads={int(h,16)for h in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',header.read_text())};assert len(heads)==456689
 def worker(row):
  i=row['index'];D=N/f'object-{i:05}';D.mkdir();R=C/f'object-{i:05}.json';commands=[]
  def run(cmd,label):
   cmd=list(map(str,cmd));commands.append(cmd)
   with(D/(label+'.log')).open('w')as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  try:
   rr=records[i];assert sha(rr['receipt'])==rr['receipt_sha256'];q=read(rr['receipt']);data=Path(row['raw_ir']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['raw_ir_sha256'];old=data.decode();del data;of=c.extract_functions(old);assert B.state_layout(old)==B.STATE_SHA and len(B.SHAPE.findall(old))==sum(len(f['sites'])for f in row['functions']);results={}
   for f in row['functions']:
    h=int(f['head'],16);r=q['functions'][f['head']];oldbody=Path(r['old_body_path']).read_text();assert oldbody==of[h]and sha(r['old_body_path'])==r['old_body_sha256']and sha(r['candidate_body_path'])==r['candidate_body_sha256'];v=c.verify_transport_body(of[h],Path(r['candidate_body_path']).read_text(),sites=f['sites']);assert v.passed,v.hold_reason;assert v.proof['proof_mode']==MODE;results[h]=v
   candidate,splice=c.splice_verified(old,results);cf=c.extract_functions(candidate);assert set(cf)==set(of)and all(cf[h]==of[h]for h in of if h not in results)and not B.SHAPE.search(candidate)and B.errors(cf)==B.errors(of);assert B.state_layout(candidate)==B.STATE_SHA;errors=B.errors(of);oldhash={h:B.digest(t)for h,t in of.items()};newhash={h:B.digest(t)for h,t in cf.items()};targets=set(results);raw=D/'replacement.raw.ll';raw.write_text(candidate);del old,of,cf,candidate
   run([B.POLL,raw,D/'replacement.polled.ll'],'poll');op=B.selected_polled(row);data=Path(op['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==op['sha256'];opf=c.extract_functions(data.decode());del data;newtext=(D/'replacement.polled.ll').read_text();nf=c.extract_functions(newtext);assert set(nf)==set(opf)and all(nf[h]==opf[h]for h in nf if h not in targets)and B.errors(nf)==errors and B.state_layout(newtext)==B.STATE_SHA;cov,ocov=B.coverage(nf),B.coverage(opf);del nf,opf,newtext
   run([p['tools']['clang-18'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',D/'replacement.polled.ll','-o',D/'replacement.o'],'compile');sym=subprocess.check_output([p['tools']['llvm-nm-18'],'--format=posix','--extern-only',str(D/'replacement.o')],text=True);(D/'symbols.txt').write_text(sym);defs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',sym,re.M));refs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',sym,re.M));assert defs==sorted(oldhash)and not(set(refs)-heads);assert sha(row['selected_object']['path'])==row['selected_object']['sha256'];before=B.native_projection(p['tools']['llvm-objdump-18'],row['selected_object']['path']);after=B.native_projection(p['tools']['llvm-objdump-18'],D/'replacement.o');assert set(before)==set(after)==set(oldhash);changed={h for h in before if before[h]!=after[h]};assert changed<=targets,('unaffected native differences',list(map(hex,changed-targets)));obj=C/'objects'/f'shard-{i:05}.o';shutil.copy2(D/'replacement.o',obj)
   result={'passed':True,'index':i,'module':row['module'],'proof_mode':MODE,'no_relift':True,'fresh_body_equality_claimed':False,'old_object':row['selected_object'],'object':{'path':str(obj),'sha256':sha(obj)},'old_raw_sha256':row['raw_ir_sha256'],'raw_ir':{'path':str(raw),'sha256':sha(raw)},'polled_ir':{'path':str(D/'replacement.polled.ll'),'sha256':sha(D/'replacement.polled.ll')},'old_polled_ir':op,'definition_count':len(defs),'changed_heads':list(map(hex,sorted(targets))),'unchanged_raw_polled_native_functions':len(defs)-len(targets),'old_errors':errors,'new_errors':errors,'legacy_copies_removed':sum(len(f['sites'])for f in row['functions']),'remaining_legacy_load_shape_count':0,'dead_inttoptr_SSA_retained':True,'splice_proof':splice,'transport_proofs':{hex(h):v.proof for h,v in results.items()},'all_poll_coverage':cov,'old_poll_coverage':ocov,'direct_guest_targets':refs,'missing_direct_targets':[],'native_changed_heads':list(map(hex,sorted(changed))),'native_function_projections':{'old':{hex(h):v for h,v in before.items()},'new':{hex(h):v for h,v in after.items()}},'old_body_sha256':{hex(h):v for h,v in oldhash.items()},'new_body_sha256':{hex(h):v for h,v in newhash.items()},'proof_receipt':rr,'commands':commands,'artifacts':{str(f):sha(f)for f in D.iterdir()if f.is_file()}}
  except Exception as e:result={'passed':False,'index':i,'proof_mode':MODE,'hold_reason':str(e),'traceback':traceback.format_exc(),'commands':commands}
  save(R,result);return{'index':i,'passed':result['passed'],'receipt':str(R),'receipt_sha256':sha(R),'object':result.get('object'),'hold_reason':result.get('hold_reason')}
 rr=jobs(m['objects'],p['jobs'],worker,C/'progress.json','TRANSPORT-COMPILE');check_fixed(p);q={'passed':len(rr)==p['objects']and all(r['passed']for r in rr),'proof_mode':MODE,'phase':'COMPILED-TRANSPORT-VECTOR; NOT SELECTED','plan_sha256':a.plan_sha,'manifest_sha256':p['manifest_sha256'],'proof_path':str(a.proof.resolve()),'proof_sha256':a.proof_sha,'condition_qualification_path':p['condition_qualification_path'],'condition_qualification_sha256':p['condition_qualification_sha256'],'functions':p['functions'],'legacy_copies_removed':p['sites'],'objects':rr,'no_relift':True,'fresh_body_equality_claimed':False,'lifter_invocations':0,'no_game_execution':True,'fixed_inputs':p['fixed_inputs']};save(C/'acceptance.json',q);print('TRANSPORT-VECTOR',q['passed'],sha(C/'acceptance.json'),flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['plan','prove','compile'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--native-out',type=Path);p.add_argument('--jobs',type=int,default=4)
 for n in['manifest','checker','checker-qualification','condition-qualification','proof']:p.add_argument('--'+n,type=Path)
 for n in['manifest-sha','checker-sha','checker-qualification-sha','condition-qualification-sha','plan-sha','proof-sha']:p.add_argument('--'+n)
 a=p.parse_args();assert 1<=a.jobs<=4
 if a.phase=='plan':plan(a);return
 O=a.out.resolve();assert a.plan_sha and sha(O/'plan.json')==a.plan_sha;q=read(O/'plan.json');assert sha(__file__)==q['producer_sha256'];check_fixed(q);m=read(q['manifest_path']);validate_condition(q['condition_qualification_path'],q['condition_qualification_sha256'],q['manifest_sha256'],m)
 if a.phase=='prove':prove(a,q,m)
 else:compile_vector(a,q,m)
if __name__=='__main__':main()
