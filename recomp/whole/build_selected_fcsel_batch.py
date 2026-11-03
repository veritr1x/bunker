"""Plan/produce a strictly verified selected-IR FCSEL batch. Never selects or runs a game."""
import argparse,concurrent.futures,hashlib,importlib.util,json,re,shutil,struct,subprocess,sys,time,traceback
from pathlib import Path
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
L=Path('/home/user/bunker-recomp/recomp/work')
TOOL=W/'st2-preparation1/toolchains/a6adf76c0c6f57ae-1c8ac0b879632f7c'
TOOL_SHA={'remill-lift':'a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa','aarch64.bc':'1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658'}
POLL=W/'poll-admission3/poll-instrument'
POLL_SHA='716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa'
STATE_SHA='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
SHAPE=re.compile(r'  (%[A-Za-z0-9_.]+) = inttoptr i64 (%[A-Za-z0-9_.]+) to ptr\n  (%[A-Za-z0-9_.]+) = load i(32|64), ptr \1, align 1\n  store i\4 \3, ptr (%[A-Za-z0-9_.]+), align 1')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def errors(fs):return sorted(hex(h)for h,b in fs.items()if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',b))
def state_layout(t):
 types=dict(re.findall(r'^(%[-A-Za-z$._0-9]+) = type (.*)$',t,re.M));seen=set();pending=['%struct.State']
 while pending:
  x=pending.pop()
  if x in seen:continue
  seen.add(x);pending.extend(re.findall(r'%[-A-Za-z$._0-9]+',types[x]))
 return digest('\n'.join(x+' = type '+types[x]for x in sorted(seen))+'\n')
def coverage(fs):
 result={}
 for h,b in fs.items():
  req=len(re.findall(r'call i32 @__bunker_guest_poll_requested\(',b));sites=re.findall(r'call void @__bunker_guest_poll_slow\(ptr [^,]+, i64 (\d+), i64 (\d+), i64 ([^,)]+)\)',b)
  assert req==len(sites)>=1 and all(int(s[0])==h for s in sites)and[int(s[1])for s in sites]==list(range(len(sites))),hex(h)
  result[hex(h)]={'entry':1,'cycle':len(sites)-1,'total':len(sites)}
 return result

def load_checker(p):
 spec=importlib.util.spec_from_file_location('frozen_fcsel_checker',p);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def selected_polled(row):
 i=row['index'];base=W/f'game17-polled-cohort1/shard-{i:05}.json';r=read(base)
 if r['object']['path']==row['selected_object']['path']and r['object']['sha256']==row['selected_object']['sha256']:
  return {'path':r['instrument_command'][2],'sha256':r['instrumented_ir_sha256']}
 q=read(row['producer_receipt']);raw_parent=Path(row['raw_ir']).parent
 if 'polled_ir'in q:return q['polled_ir']
 artifacts=q['artifacts'];found=[{'path':p,'sha256':h}for p,h in artifacts.items()if Path(p).parent==raw_parent and Path(p).name in('candidate-polled.ll','five.polled.ll')]
 assert len(found)==1,(i,found);return found[0]

def native_projection(dump,obj):
 text=subprocess.check_output([str(dump),'-dr',str(obj)],text=True);result={}
 for m in re.finditer(r'(?m)^[0-9a-f]+ <(sub_[0-9a-f]+)>:\n(.*?)(?=^[0-9a-f]+ <|\Z)',text,re.S):
  code=''.join(''.join(z.split())for z in re.findall(r'^\s+[0-9a-f]+:\s+((?:[0-9a-f]{2} )+)',m[2],re.M));relocations=re.findall(r'(IMAGE_REL_AMD64_\S+\s+\S+)',m[2]);result[int(m[1][4:],16)]={'code_sha256':digest(code),'relocations':relocations,'bytes':len(code)//2}
 return result

def discover_context(targets, module_heads, recipe, image):
 """Conservative original direct-CFG closure, bounded to existing module heads.

 This only supplies proposal optimizer context. Strict body/identity proofs still
 decide admission; unknown indirect targets are never invented or admitted.
 """
 base=recipe['image_start'];global_heads=set(recipe['trace_heads']);ranges=recipe['executable_ranges'];pending=list(sorted(targets));done=set();edges={};counts={}
 def signed(value,bits):return value-(1<<bits)if value>>(bits-1)else value
 while pending:
  root=pending.pop()
  if root in done:continue
  done.add(root);assert len(done)<=len(module_heads)<=128
  todo=[root];visited=set();dependencies=set()
  def reach(pc):
   if pc in module_heads and pc!=root:dependencies.add(pc)
   elif pc in global_heads and pc!=root:return
   else:todo.append(pc)
  while todo:
   pc=todo.pop()
   if pc in visited:continue
   assert len(visited)<100000,'original context discovery instruction budget exceeded'
   if not any(lo<=pc<hi for lo,hi in ranges):continue
   assert pc%4==0 and 0<=pc-base<=len(image)-4
   visited.add(pc);word=struct.unpack_from('<I',image,pc-base)[0]
   if word&0x7c000000==0x14000000:
    reach(pc+signed(word&0x3ffffff,26)*4)
    if word&0x80000000:reach(pc+4)
   elif word&0xff000010==0x54000000 or word&0x7e000000==0x34000000:
    reach(pc+signed((word>>5)&0x7ffff,19)*4);reach(pc+4)
   elif word&0x7e000000==0x36000000:
    reach(pc+signed((word>>5)&0x3fff,14)*4);reach(pc+4)
   elif word&0xfffffc1f in(0xd65f0000,0xd61f0000):pass
   elif word&0xfffffc1f==0xd63f0000:reach(pc+4)
   else:reach(pc+4)
  edges[hex(root)]=list(map(hex,sorted(dependencies)));counts[hex(root)]=len(visited);pending.extend(sorted(dependencies-done))
 return done,{'method':'Original B/BL/conditional direct CFG; foreign selected trace boundaries stop; unresolved BR/RET stop; existing current module heads only; no new heads or fallback', 'target_heads':list(map(hex,sorted(targets))),'proposal_heads':list(map(hex,sorted(done))),'context_only_heads':list(map(hex,sorted(done-set(targets)))),'direct_edges':edges,'visited_instruction_counts':counts,'maximum_existing_definitions':128,'maximum_visited_instructions_per_node':100000}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in('manifest','checker','checker-qualification','out','native-out'):p.add_argument('--'+key,type=Path,required=True)
 for key in('manifest-sha','checker-sha','checker-qualification-sha'):p.add_argument('--'+key,required=True)
 p.add_argument('--jobs',type=int,default=4);p.add_argument('--execute',action='store_true');p.add_argument('--plan-sha');a=p.parse_args();assert 1<=a.jobs<=4
 O=a.out.resolve();N=a.native_out.resolve();assert str(O).startswith(str(W)+'/')and str(N).startswith(str(L)+'/')and O!=N
 assert sha(a.manifest)==a.manifest_sha and sha(a.checker)==a.checker_sha and sha(a.checker_qualification)==a.checker_qualification_sha
 manifest=read(a.manifest);assert manifest['passed']and manifest['read_only'];groups=manifest['objects'];assert len(groups)==manifest['affected_objects'];assert len({r['index']for r in groups})==len(groups)
 assert sum(len(r['functions'])for r in groups)==manifest['affected_functions'];assert sum(len(f['sites'])for r in groups for f in r['functions'])==manifest['legacy_copies'];assert not manifest.get('unattributed_shapes')
 parent=Path(manifest['selected_input']);assert sha(parent)==manifest['selected_input_sha256'];game=read(parent);assert len(game['objects'])==3576
 for r in groups:
  assert {k:r['selected_object'][k]for k in('path','sha256')}=={k:game['objects'][r['index']][k]for k in('path','sha256')};assert r['functions'] and all(f['sites']for f in r['functions'])
  for f in r['functions']:
   assert all(s.get('original_opcode_candidates')and s['width']in(32,64)for s in f['sites']);assert Path(f['captured_body_path']).is_file()
 fixed={str(a.manifest.resolve()):a.manifest_sha,str(a.checker.resolve()):a.checker_sha,str(a.checker_qualification.resolve()):a.checker_qualification_sha,str(parent):manifest['selected_input_sha256'],str(Path(__file__).resolve()):sha(__file__),str(POLL):POLL_SHA}
 for name,h in TOOL_SHA.items():assert sha(TOOL/name)==h;fixed[str(TOOL/name)]=h
 assert sha(POLL)==POLL_SHA
 context_dry=W/'fcsel-context-dry-check1/result.json';assert sha(context_dry)=='72553a083ec1c8564ddb502fc1b4bd8d4f016b74bd9e376cea0e470621b0c9d2';dry=read(context_dry);assert dry['checker_sha256']==a.checker_sha
 assert all(r['passed']for label in('7-current','11-closure25')for r in dry['results'][label].values());fixed[str(context_dry)]=sha(context_dry)
 qualifications=[(W/'fcsel-positive2/acceptance.json','b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b'),(W/'st2-qualification1/qualification1/acceptance.json','28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed'),(W/'st2-preparation1/compiled-semantic-proof.json','70c0e7ecedf707a43b968bd2bdf48419951d31e96781ca6cf842c98449063938')]
 for q,h in qualifications:assert sha(q)==h;fixed[str(q)]=h
 clang=Path(shutil.which('clang-18')).resolve();nm=Path(shutil.which('llvm-nm-18')).resolve();dump=Path(shutil.which('llvm-objdump-18')).resolve()
 for x in[clang,nm,dump]:fixed[str(x)]=sha(x)
 selected=parent.parent/'game_traces.h';fixed[str(selected)]=sha(selected);heads={int(x,16)for x in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',selected.read_text())};assert len(heads)==456689
 recipes={}
 for name,base in [('Unity',L/'whole-unity-fmla-fmul-indexed'),('IL2CPP',L/'whole-il2cpp-current')]:
  mp=base/'manifest.json';m=read(mp);image=base/'executable.bin';assert m['traces']and set(m['traces'])<=heads
  recipes[name]={'manifest':str(mp),'manifest_sha256':sha(mp),'bytes_file':str(image),'bytes_sha256':sha(image),'image_start':m['image_start'],'trace_heads':m['traces'],'executable_ranges':m['executable_ranges'],'trace_heads_count':len(m['traces'])};fixed[str(mp)]=recipes[name]['manifest_sha256'];fixed[str(image)]=recipes[name]['bytes_sha256']
 # Recipe whitelist is intentionally narrow. Any other producer requires review.
 assert {r['producer']for r in groups}<={'unity_base','il2cpp_base','unity-st2-object-overlay1','unity-display-fcsel-overlay1'}
 total=sum(r['raw_ir_bytes']for r in groups);assert all(Path(r['raw_ir']).stat().st_size==r['raw_ir_bytes']for r in groups)
 if not a.execute:
  assert not O.exists()and not N.exists();O.mkdir();estimated=int(total*3.3+2**30);free=shutil.disk_usage(N.parent).free
  plan={'passed':True,'stage':'PREPARED ONLY; explicit root review required before --execute','manifest_path':str(a.manifest.resolve()),'manifest_sha256':a.manifest_sha,'checker_path':str(a.checker.resolve()),'checker_sha256':a.checker_sha,'checker_qualification_path':str(a.checker_qualification.resolve()),'checker_qualification_sha256':a.checker_qualification_sha,'out':str(O),'native_out':str(N),'jobs':a.jobs,'affected_objects':len(groups),'affected_functions':manifest['affected_functions'],'legacy_copies':manifest['legacy_copies'],'module_counts':manifest['module_counts'],'affected_current_raw_bytes':total,'estimated_native_output_bytes':estimated,'native_free_bytes':free,'windows_free_bytes':shutil.disk_usage(O).free,'estimated_wall_minutes':[5,35],'recipe':recipes,'fixed_inputs':fixed,'limits':'Flagged-function fresh proposals with original direct-CFG in-module dependency context (max128 existing heads); only flagged functions splice. Old raw read once before proposal to recover exact current head/context. Current overlays are splice baselines; all context definitions require zero-owned-site identity. No game/cohort selection or automatic retries. Any checker/native/unattributed mismatch holds/stops the batch.'};assert free>estimated
  save(O/'plan.json',plan);shutil.copy2(__file__,O/'frozen-producer.py');shutil.copy2(a.checker,O/'frozen-checker.py');print('BATCH-PLAN',sha(O/'plan.json'),len(groups),manifest['affected_functions'],manifest['legacy_copies'],'rawGiB',round(total/2**30,3),'estimatedGiB',round(estimated/2**30,3),flush=True);return
 assert a.plan_sha and(O/'plan.json').exists()and sha(O/'plan.json')==a.plan_sha;plan=read(O/'plan.json');assert plan['fixed_inputs']==fixed and plan['out']==str(O)and plan['native_out']==str(N)and plan['jobs']==a.jobs;assert not N.exists()and not(O/'execution.json').exists()
 N.mkdir();(O/'objects').mkdir();(O/'receipts').mkdir();(O/'logs').mkdir();checker=load_checker(O/'frozen-checker.py');started=time.time()
 recipe_files={};context_images={}
 for name,recipe in recipes.items():
  f=N/(name.lower()+'-original-heads.txt');f.write_text(''.join(hex(h)+'\n'for h in recipe['trace_heads']));recipe_files[name]=f;context_images[name]=Path(recipe['bytes_file']).read_bytes()
 save(O/'execution.json',{'stage':'RUNNING','plan_sha256':a.plan_sha,'started_unix':started,'no_game_execution':True})
 def produce(row):
  i=row['index'];D=N/f'object-{i:05}';D.mkdir();R=O/'receipts'/f'object-{i:05}.json';commands=[];stage='start'
  def run(cmd,label):
   nonlocal stage
   stage=label;cmd=list(map(str,cmd));commands.append(cmd)
   with(O/'logs'/f'{i:05}-{label}.log').open('w')as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  try:
   stage='current-source-and-context';targets={int(f['head'],16):f for f in row['functions']};recipe=recipes[row['module']]
   # Exactly one full current raw read, now before proposal: immutable source,
   # all existing heads and original dependency context come from this same text.
   data=Path(row['raw_ir']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['raw_ir_sha256'];old=data.decode();del data;of=checker.extract_functions(old);assert set(targets)<=set(of);assert len(SHAPE.findall(old))==sum(len(f['sites'])for f in row['functions'])
   for h,f in targets.items():
    captured=Path(f['captured_body_path']).read_text();assert digest(captured)==f['captured_body_sha256']and captured==of[h]
   proposal_heads,context_discovery=discover_context(set(targets),set(of),recipe,context_images[row['module']]);save(D/'context-discovery.json',context_discovery)
   entry=D/'entries.txt';entry.write_text(''.join(hex(h)+'\n'for h in sorted(proposal_heads)))
   run([TOOL/'remill-lift','--arch','aarch64','--os','linux','--semantics_dir',TOOL,'--bytes_file',recipe['bytes_file'],'--address',recipe['image_start'],'--entry_addresses_file',entry,'--trace_heads_file',recipe_files[row['module']],'--ir_out',D/'fresh.ll'],'lift')
   stage='strict-target-and-context-verification';fresh=(D/'fresh.ll').read_text();ff=checker.extract_functions(fresh);assert set(ff)==proposal_heads;assert state_layout(old)==state_layout(fresh)==STATE_SHA
   kw={'old_attributes':checker.parse_attributes(old),'new_attributes':checker.parse_attributes(fresh),'old_metadata':checker.parse_metadata(old),'new_metadata':checker.parse_metadata(fresh),'old_types':checker.parse_types(old),'new_types':checker.parse_types(fresh)};results={};proofs={};context_proofs={}
   for h in sorted(proposal_heads):
    if h in targets:
     result=checker.verify_body(of[h],ff[h],sites=targets[h]['sites'],**kw);proofs[hex(h)]=result.proof
     if not result.passed:raise RuntimeError('CHECKER-HOLD '+hex(h)+' '+str(result.hold_reason))
     results[h]=result
    else:
     assert not SHAPE.search(of[h]),'unowned legacy FCSEL in proposal context'
     result=checker.verify_identity(of[h],ff[h],**kw);context_proofs[hex(h)]=result.proof
     if not result.passed:raise RuntimeError('CONTEXT-IDENTITY-HOLD '+hex(h)+' '+str(result.hold_reason))
   candidate,splice_proof=checker.splice_verified(old,results);cf=checker.extract_functions(candidate);assert set(cf)==set(of)and all(cf[h]==of[h]for h in of if h not in targets);assert errors(cf)==errors(of);assert not SHAPE.search(candidate)
   assert state_layout(candidate)==STATE_SHA
   raw=D/'replacement.raw.ll';raw.write_text(candidate);old_errors=errors(of);old_body_hashes={h:digest(b)for h,b in of.items()};new_body_hashes={h:digest(b)for h,b in cf.items()};del old,of,cf,candidate,fresh,ff
   run([POLL,raw,D/'replacement.polled.ll'],'poll')
   pp=selected_polled(row);op_data=Path(pp['path']).read_bytes();assert hashlib.sha256(op_data).hexdigest()==pp['sha256'];op=checker.extract_functions(op_data.decode());del op_data;np_text=(D/'replacement.polled.ll').read_text();nf=checker.extract_functions(np_text);assert set(nf)==set(op)and all(nf[h]==op[h]for h in op if h not in targets);assert errors(nf)==old_errors and state_layout(np_text)==STATE_SHA
   cov,old_cov=coverage(nf),coverage(op);del np_text,nf,op
   run([clang,'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',D/'replacement.polled.ll','-o',D/'replacement.o'],'compile')
   symbols=subprocess.check_output([str(nm),'--format=posix','--extern-only',str(D/'replacement.o')],text=True);(D/'symbols.txt').write_text(symbols);defs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M));refs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M));assert defs==sorted(old_body_hashes)and not(set(refs)-heads)
   assert sha(row['selected_object']['path'])==row['selected_object']['sha256'];before=native_projection(dump,row['selected_object']['path']);after=native_projection(dump,D/'replacement.o');assert set(before)==set(after)==set(old_body_hashes);native_changed=[h for h in before if before[h]!=after[h]];assert set(native_changed)<=set(targets),['UNEXPECTED-NATIVE',list(map(hex,set(native_changed)-set(targets)))]
   object_path=O/'objects'/f'shard-{i:05}.o';shutil.copy2(D/'replacement.o',object_path)
   receipt={'passed':True,'index':i,'module':row['module'],'old_object':row['selected_object'],'object':{'path':str(object_path),'sha256':sha(object_path)},'old_raw':{'path':row['raw_ir'],'sha256':row['raw_ir_sha256']},'raw_ir':{'path':str(raw),'sha256':sha(raw)},'polled_ir':{'path':str(D/'replacement.polled.ll'),'sha256':sha(D/'replacement.polled.ll')},'old_polled_ir':pp,'changed_heads':list(map(hex,sorted(targets))),'definition_count':len(defs),'unchanged_raw_polled_native_functions':len(defs)-len(targets),'old_errors':old_errors,'new_errors':old_errors,'legacy_copies_removed':sum(len(f['sites'])for f in row['functions']),'remaining_legacy_shape_count':0,'State_type_closure_sha256':STATE_SHA,'proofs':proofs,'optimization_context_discovery':context_discovery,'context_identity_proofs':context_proofs,'context_definitions_spliced':False,'splice_proof':splice_proof,'all_poll_coverage':cov,'old_poll_coverage':old_cov,'direct_guest_targets':refs,'missing_direct_targets':[],'native_changed_heads':list(map(hex,native_changed)),'native_function_projections':{'old':{hex(h):v for h,v in before.items()},'new':{hex(h):v for h,v in after.items()}},'old_body_sha256':{hex(h):v for h,v in old_body_hashes.items()},'new_body_sha256':{hex(h):v for h,v in new_body_hashes.items()},'commands':commands,'artifacts':{str(f):sha(f)for f in D.iterdir()if f.is_file()}}
   save(R,receipt);return{'index':i,'passed':True,'receipt':str(R),'receipt_sha256':sha(R),'object':receipt['object'],'changed_functions':len(targets),'removed_sites':receipt['legacy_copies_removed']}
  except Exception as error:
   save(R,{'passed':False,'index':i,'stage':stage,'hold_reason':str(error),'traceback':traceback.format_exc(),'commands':commands});return{'index':i,'passed':False,'receipt':str(R),'receipt_sha256':sha(R),'hold_reason':str(error)}
 completed=[];queue=iter(groups);stop=False
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs)as pool:
  pending={pool.submit(produce,next(queue))for _ in range(min(a.jobs,len(groups)))}
  while pending:
   done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    r=f.result();completed.append(r);stop=stop or not r['passed'];save(O/'progress.json',{'completed':len(completed),'planned':len(groups),'passed':sum(x['passed']for x in completed),'stopped_on_hold':stop,'elapsed_seconds':time.time()-started,'results':completed})
    if not r['passed']or len(completed)%25==0:print('BATCH-PROGRESS',len(completed),'/',len(groups),'PASS'if r['passed']else'HOLD',r['index'],r.get('hold_reason',''),flush=True)
   if not stop:
    for _ in range(len(done)):
     row=next(queue,None)
     if row is not None:pending.add(pool.submit(produce,row))
 success=len(completed)==len(groups)and all(r['passed']for r in completed)
 for pth,h in fixed.items():assert sha(pth)==h,pth
 result={'passed':success,'stage':'CANDIDATE ONLY; no cohort/game selection'if success else'HELD/INCOMPLETE; no automatic retry or partial success','plan_sha256':a.plan_sha,'manifest_sha256':a.manifest_sha,'planned_objects':len(groups),'completed_objects':len(completed),'replaced_objects':sum(r['passed']for r in completed),'changed_functions':sum(r.get('changed_functions',0)for r in completed),'legacy_copies_removed':sum(r.get('removed_sites',0)for r in completed),'results':sorted(completed,key=lambda x:x['index']),'fixed_inputs':fixed,'elapsed_seconds':time.time()-started,'limits':plan['limits']};save(O/'acceptance.json',result);print('BATCH-TERMINAL',success,sha(O/'acceptance.json'),flush=True)
 if not success:raise SystemExit(1)
if __name__=='__main__':main()
