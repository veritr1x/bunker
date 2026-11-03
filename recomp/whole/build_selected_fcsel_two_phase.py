"""FCSEL proposal-only preflight, saved-proposal verification, then gated compilation.

No mode selects a cohort or executes guest/native game code. A HOLD cannot be
skipped: every selected target must pass the same qualified whole-body proof.
"""
import argparse,concurrent.futures,difflib,hashlib,importlib.util,json,re,shutil,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_SHA='e3f3debd8a7ca636ed85a942d48fbccf58a45d619242ce50df293cef6a535bbf'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
basepath=HERE/'base.py'
if not basepath.exists():basepath=HERE/'build_selected_fcsel_batch.py'
assert sha(basepath)==BASE_SHA
B=load(basepath,'frozen_batch_base')
W,L,T=B.W,B.L,B.TOOL

def checked_checker(path,expected,qualification,qual_sha):
 assert sha(path)==expected and sha(qualification)==qual_sha and read(qualification)['passed'];return B.load_checker(path)
def fixed_ok(plan):
 for p,h in plan['fixed_inputs'].items():assert sha(p)==h,p
 for n,h in B.TOOL_SHA.items():assert sha(T/n)==h
 assert sha(B.POLL)==B.POLL_SHA

def run_all(items,jobs,worker,progress,label):
 started=time.time();results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=jobs)as pool:
  queue=iter(items);pending={pool.submit(worker,next(queue))for _ in range(min(jobs,len(items)))}
  while pending:
   done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    r=f.result();results.append(r);save(progress,{'phase':label,'completed':len(results),'planned':len(items),'elapsed_seconds':time.time()-started,'results':sorted(results,key=lambda x:x['index'])})
    if len(results)%25==0 or not r.get('passed',False):print(label,len(results),'/',len(items),r['index'],r.get('target_holds',r.get('hold_reason','')),flush=True)
    row=next(queue,None)
    if row is not None:pending.add(pool.submit(worker,row))
 return sorted(results,key=lambda x:x['index'])

def compare_targets(c,row,meta,fresh,folder):
 folder.mkdir(parents=True,exist_ok=False);ff=c.extract_functions(fresh);assert {int(f['head'],16)for f in row['functions']}<=set(ff)<={int(h,16)for h in meta['all_heads']};assert B.state_layout(fresh)==B.STATE_SHA
 kw={'old_attributes':meta['attributes'],'new_attributes':c.parse_attributes(fresh),'old_metadata':meta['metadata'],'new_metadata':c.parse_metadata(fresh),'old_types':meta['types'],'new_types':c.parse_types(fresh)};results={}
 for f in row['functions']:
  h=int(f['head'],16);oldpath=Path(meta['target_bodies'][f['head']]['path']);assert sha(oldpath)==meta['target_bodies'][f['head']]['sha256'];old=oldpath.read_text();new=ff[h]
  result=c.verify_body(old,new,sites=f['sites'],**kw);rec={'passed':result.passed,'head':f['head'],'site_count':len(f['sites']),'hold_reason':result.hold_reason,'proof':result.proof,'old_body_path':str(oldpath),'old_body_sha256':sha(oldpath),'fresh_body_sha256':hashlib.sha256(new.encode()).hexdigest()}
  if result.passed:
   assert not B.SHAPE.search(result.mapped_body);mapped=folder/f'{h:x}.mapped.ll';mapped.write_text(result.mapped_body);rec.update(mapped_body_path=str(mapped),mapped_body_sha256=sha(mapped))
  else:
   actual=folder/f'{h:x}.fresh.ll';actual.write_text(new);diff=folder/f'{h:x}.diff';diff.write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='current-selected-body',tofile='fresh-proposal')));rec.update(fresh_body_path=str(actual),diff_path=str(diff),diff_sha256=sha(diff))
  results[f['head']]=rec
 return results

def make_plan(a):
 assert a.manifest and a.checker and a.checker_qualification and a.native_out
 assert sha(a.manifest)==a.manifest_sha;manifest=read(a.manifest);assert manifest['passed']and manifest['affected_objects']==len(manifest['objects'])and not manifest.get('unattributed_shapes')
 assert manifest['affected_functions']==sum(len(r['functions'])for r in manifest['objects']);assert manifest['legacy_copies']==sum(len(f['sites'])for r in manifest['objects']for f in r['functions'])
 checked_checker(a.checker,a.checker_sha,a.checker_qualification,a.checker_qualification_sha)
 O=a.out.resolve();N=a.native_out.resolve();assert not O.exists()and not N.exists()and str(O).startswith(str(W)+'/')and str(N).startswith(str(L)+'/');O.mkdir()
 for src,dst in[(Path(__file__),O/'producer.py'),(basepath,O/'base.py'),(a.checker,O/'checker.py')]:shutil.copy2(src,dst)
 parent=Path(manifest['selected_input']);assert sha(parent)==manifest['selected_input_sha256'];game=read(parent);assert len(game['objects'])==3576
 for r in manifest['objects']:
  assert {k:r['selected_object'][k]for k in('path','sha256')}=={k:game['objects'][r['index']][k]for k in('path','sha256')}
  assert Path(r['raw_ir']).stat().st_size==r['raw_ir_bytes']
  for f in r['functions']:assert f['sites']and all(s['original_opcode_candidates']and s['width']in(32,64)for s in f['sites'])
 fixed={str(a.manifest.resolve()):a.manifest_sha,str(parent):manifest['selected_input_sha256'],str(O/'producer.py'):sha(O/'producer.py'),str(O/'base.py'):BASE_SHA,str(O/'checker.py'):a.checker_sha,str(a.checker_qualification.resolve()):a.checker_qualification_sha,str(B.POLL):B.POLL_SHA}
 for n,h in B.TOOL_SHA.items():assert sha(T/n)==h;fixed[str(T/n)]=h
 assert sha(B.POLL)==B.POLL_SHA
 for p,h in[(W/'fcsel-positive2/acceptance.json','b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b'),(W/'st2-qualification1/qualification1/acceptance.json','28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed'),(W/'st2-preparation1/compiled-semantic-proof.json','70c0e7ecedf707a43b968bd2bdf48419951d31e96781ca6cf842c98449063938')]:assert sha(p)==h;fixed[str(p)]=h
 selected=parent.parent/'game_traces.h';fixed[str(selected)]=sha(selected);assert len({int(h,16)for h in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',selected.read_text())})==456689
 recipes={}
 for name,d in[('Unity',L/'whole-unity-fmla-fmul-indexed'),('IL2CPP',L/'whole-il2cpp-current')]:
  mp=d/'manifest.json';m=read(mp);image=d/'executable.bin';fixed[str(mp)]=sha(mp);fixed[str(image)]=sha(image);recipes[name]={'manifest':str(mp),'image_start':m['image_start'],'bytes_file':str(image),'trace_heads':m['traces']}
 tools={n:str(Path(shutil.which(n)).resolve())for n in['clang-18','llvm-nm-18','llvm-objdump-18']}
 for p in tools.values():fixed[p]=sha(p)
 caches=[];incompatible_caches=[]
 for R in a.reuse_root or[W/'selected-fcsel-batch3',W/'selected-fcsel-batch2']:
  p=R/'plan.json'
  if not p.exists():continue
  q=read(p)
  if q['manifest_sha256']!=a.manifest_sha:
   incompatible_caches.append({'root':str(R),'plan':str(p),'plan_sha256':sha(p),'manifest_sha256':q['manifest_sha256'],'reason':'incompatible manifest; cache excluded, no provenance fallback'});continue
  assert all(q['fixed_inputs'].get(str(T/n))==h for n,h in B.TOOL_SHA.items());assert all(q['fixed_inputs'].get(p)==fixed[p]for r in recipes.values()for p in[r['manifest'],r['bytes_file']]);fixed[str(p)]=sha(p);caches.append({'root':str(R),'plan':str(p),'plan_sha256':sha(p),'native_out':q['native_out']})
 total=sum(r['raw_ir_bytes']for r in manifest['objects']);estimate=int(total*4.2+2**30);assert shutil.disk_usage(N.parent).free>estimate
 plan={'passed':True,'phase_kind':'proposal-only-preflight; no COFF/splice/admission','manifest_path':str(a.manifest.resolve()),'manifest_sha256':a.manifest_sha,'out':str(O),'native_out':str(N),'jobs':a.jobs,'producer_sha256':sha(O/'producer.py'),'checker_path':str(O/'checker.py'),'checker_sha256':a.checker_sha,'checker_qualification_path':str(a.checker_qualification.resolve()),'checker_qualification_sha256':a.checker_qualification_sha,'fixed_inputs':fixed,'recipes':recipes,'tools':tools,'reuse_roots':caches,'incompatible_reuse_roots':incompatible_caches,'objects':len(manifest['objects']),'functions':manifest['affected_functions'],'copies':manifest['legacy_copies'],'proposal_policy':'Reuse newest exact-tool/input cached fresh proposal only if current qualified checker accepts ALL flagged targets; otherwise propose ALL existing current-module heads (max128) solely for LLVM IPO context. Never splice unselected context; its identities are diagnostic, not admission. No older-pair fallback.','compile_gate':'Separate verification receipt must prove all objects/targets/sites complete and PASS; PhaseA never instruments/compiles/splices. Verify-only reads saved snapshots, never relifts or rereads current full IR.','affected_raw_bytes':total,'estimated_scratch_bytes':estimate,'estimated_proposal_minutes':[5,35],'free_native_bytes':shutil.disk_usage(N.parent).free}
 save(O/'plan.json',plan);print('TWO-PHASE-PLAN',sha(O/'plan.json'),plan['objects'],plan['functions'],plan['copies'],'estimatedGiB',round(estimate/2**30,2),flush=True)

def propose(a,plan,manifest):
 O=a.out.resolve();N=Path(plan['native_out']);P=O/'preflight';assert not P.exists()and not N.exists();P.mkdir();N.mkdir();c=B.load_checker(plan['checker_path']);heads={}
 for name,r in plan['recipes'].items():f=N/(name.lower()+'-heads.txt');f.write_text(''.join(hex(h)+'\n'for h in r['trace_heads']));heads[name]=f
 def worker(row):
  i=row['index'];D=N/f'object-{i:05}';D.mkdir();E=P/f'object-{i:05}';E.mkdir();stage='source';commands=[]
  try:
   data=Path(row['raw_ir']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['raw_ir_sha256'];old=data.decode();del data;of=c.extract_functions(old);assert 0<len(of)<=128 and B.state_layout(old)==B.STATE_SHA;assert len(B.SHAPE.findall(old))==sum(len(f['sites'])for f in row['functions']);bodies={}
   for f in row['functions']:
    h=int(f['head'],16);capture=Path(f['captured_body_path']);assert sha(capture)==f['captured_body_sha256']and capture.read_text()==of[h];p=E/f'{h:x}.old.ll';p.write_text(of[h]);bodies[f['head']]={'path':str(p),'sha256':sha(p)}
   meta={'index':i,'old_raw_sha256':row['raw_ir_sha256'],'all_heads':list(map(hex,sorted(of))),'attributes':c.parse_attributes(old),'metadata':c.parse_metadata(old),'types':c.parse_types(old),'unsupported_heads':B.errors(of),'target_bodies':bodies,'State_type_closure_sha256':B.STATE_SHA};save(E/'old-context.json',meta);old_heads=set(of);del old,of
   chosen=None;cache_attempt=None
   for root in plan['reuse_roots']:
    fp=Path(root['native_out'])/f'object-{i:05}/fresh.ll'
    if not fp.exists():continue
    stage='cached-target-verification';text=fp.read_text();cache_attempt={'fresh_path':str(fp),'fresh_sha256':sha(fp),'old_plan':root['plan'],'old_plan_sha256':root['plan_sha256'],'all_targets_passed':False}
    try:
     attempt=compare_targets(c,row,meta,text,E/'cached-check');cache_attempt.update(target_results=attempt,all_targets_passed=all(r['passed']for r in attempt.values()))
    except Exception as cache_error:cache_attempt.update(hold_reason=str(cache_error),traceback=traceback.format_exc())
    if cache_attempt['all_targets_passed']:shutil.copy2(fp,D/'fresh.ll');chosen='exact-input-cache'
    break
   if chosen is None:
    stage='full-context-proposal';entry=D/'entries.txt';entry.write_text(''.join(hex(h)+'\n'for h in sorted(old_heads)));r=plan['recipes'][row['module']];cmd=list(map(str,[T/'remill-lift','--arch','aarch64','--os','linux','--semantics_dir',T,'--bytes_file',r['bytes_file'],'--address',r['image_start'],'--entry_addresses_file',entry,'--trace_heads_file',heads[row['module']],'--ir_out',D/'fresh.ll']));commands.append(cmd)
    with(E/'lift.log').open('w')as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert set(c.extract_functions((D/'fresh.ll').read_text()))==old_heads;chosen='full-old-module-proposal-context'
   stage='all-target-diagnostics';fresh=(D/'fresh.ll').read_text();targets=compare_targets(c,row,meta,fresh,E/'target-diagnostics');holds=sum(not r['passed']for r in targets.values());result={'passed':holds==0,'proposal_generated':True,'index':i,'stage':'PROPOSAL ONLY','source_kind':chosen,'fresh_module':str(D/'fresh.ll'),'fresh_module_sha256':sha(D/'fresh.ll'),'old_context_path':str(E/'old-context.json'),'old_context_sha256':sha(E/'old-context.json'),'targets':targets,'target_holds':holds,'context_heads_proposed':len(c.extract_functions(fresh)),'unselected_context_admitted':False,'COFF_compiled':False,'module_spliced':False,'cached_attempt':cache_attempt,'commands':commands}
  except Exception as e:
   available=(D/'fresh.ll').exists()and(E/'old-context.json').exists();result={'passed':False,'proposal_generated':available,'index':i,'stage':stage,'hold_reason':str(e),'traceback':traceback.format_exc(),'commands':commands,'target_holds':len(row['functions'])}
   if available:result.update(fresh_module=str(D/'fresh.ll'),fresh_module_sha256=sha(D/'fresh.ll'),old_context_path=str(E/'old-context.json'),old_context_sha256=sha(E/'old-context.json'))
  save(E/'proposal.json',result);return{'index':i,'passed':result['passed'],'proposal_generated':result['proposal_generated'],'target_holds':result['target_holds'],'receipt':str(E/'proposal.json'),'receipt_sha256':sha(E/'proposal.json')}
 results=run_all(manifest['objects'],plan['jobs'],worker,P/'progress.json','PROPOSALS');complete=len(results)==plan['objects']and all(r['proposal_generated']for r in results);result={'passed':complete and all(r['passed']for r in results),'phase':'PROPOSAL-ONLY','all_objects_diagnosed':len(results)==plan['objects'],'all_proposals_generated':complete,'admission_performed':False,'compiled_objects':0,'plan_sha256':a.plan_sha,'manifest_sha256':plan['manifest_sha256'],'objects':results,'target_holds':sum(r['target_holds']for r in results),'fixed_inputs':plan['fixed_inputs']};fixed_ok(plan);save(P/'acceptance.json',result);print('PROPOSAL-PREFLIGHT-COMPLETE',sha(P/'acceptance.json'),'HOLD',result['target_holds'],flush=True)

def verify(a,plan,manifest):
 O=a.out.resolve();P=O/'preflight/acceptance.json';assert P.exists();q=read(P);assert q['all_proposals_generated']and q['all_objects_diagnosed']and q['manifest_sha256']==plan['manifest_sha256'];V=a.verification_out.resolve();assert not V.exists()and str(V).startswith(str(O)+'/');V.mkdir();c=checked_checker(a.checker,a.checker_sha,a.checker_qualification,a.checker_qualification_sha);shutil.copy2(a.checker,V/'checker.py')
 rows={r['index']:r for r in manifest['objects']};sources={r['index']:r for r in q['objects']};assert set(rows)==set(sources)
 def worker(row):
  i=row['index'];E=V/f'object-{i:05}';E.mkdir()
  try:
   r=sources[i];assert sha(r['receipt'])==r['receipt_sha256'];p=read(r['receipt']);assert p['proposal_generated'];assert sha(p['old_context_path'])==p['old_context_sha256']and sha(p['fresh_module'])==p['fresh_module_sha256'];meta=read(p['old_context_path']);targets=compare_targets(c,row,meta,Path(p['fresh_module']).read_text(),E/'targets');ok=all(r['passed']for r in targets.values());result={'passed':ok,'index':i,'targets':targets,'target_holds':sum(not r['passed']for r in targets.values()),'proposal_receipt':r['receipt'],'proposal_receipt_sha256':r['receipt_sha256'],'old_context_path':p['old_context_path'],'old_context_sha256':p['old_context_sha256'],'fresh_module':p['fresh_module'],'fresh_module_sha256':p['fresh_module_sha256']}
  except Exception as e:result={'passed':False,'index':i,'target_holds':len(row['functions']),'hold_reason':str(e),'traceback':traceback.format_exc()}
  save(E/'verification.json',result);return{'index':i,'passed':result['passed'],'target_holds':result['target_holds'],'receipt':str(E/'verification.json'),'receipt_sha256':sha(E/'verification.json')}
 results=run_all(manifest['objects'],plan['jobs'],worker,V/'progress.json','VERIFY');result={'passed':len(results)==plan['objects']and all(r['passed']for r in results),'phase':'ALL-TARGET-VERIFICATION-ONLY','plan_sha256':a.plan_sha,'manifest_sha256':plan['manifest_sha256'],'preflight_path':str(P),'preflight_sha256':sha(P),'checker_path':str(V/'checker.py'),'checker_sha256':a.checker_sha,'checker_qualification_path':str(a.checker_qualification.resolve()),'checker_qualification_sha256':a.checker_qualification_sha,'objects':results,'functions':plan['functions'],'sites':plan['copies'],'target_holds':sum(r['target_holds']for r in results),'no_relift':True,'no_current_raw_rescan':True,'compiled_objects':0};save(V/'acceptance.json',result);print('ALL-TARGET-VERIFICATION',result['passed'],sha(V/'acceptance.json'),flush=True)

def compile_batch(a,plan,manifest):
 assert a.verification and a.verification_sha and sha(a.verification)==a.verification_sha;v=read(a.verification);assert v['passed']and v['phase']=='ALL-TARGET-VERIFICATION-ONLY'and v['plan_sha256']==a.plan_sha and v['manifest_sha256']==plan['manifest_sha256']and v['functions']==plan['functions']and v['sites']==plan['copies']and v['target_holds']==0
 assert sha(v['preflight_path'])==v['preflight_sha256'];c=checked_checker(v['checker_path'],v['checker_sha256'],v['checker_qualification_path'],v['checker_qualification_sha256']);records={r['index']:r for r in v['objects']};assert set(records)=={r['index']for r in manifest['objects']}and all(r['passed']for r in records.values())
 # Check the complete actual per-object proof vector before any compilation,
 # rather than trusting only aggregate counters in its pinned receipt.
 for row in manifest['objects']:
  rr=records[row['index']];assert sha(rr['receipt'])==rr['receipt_sha256'];vv=read(rr['receipt']);assert vv['passed']and vv['target_holds']==0 and set(vv['targets'])=={f['head']for f in row['functions']}
  for f in row['functions']:
   pp=vv['targets'][f['head']];assert pp['passed']and pp['site_count']==len(f['sites'])and sha(pp['mapped_body_path'])==pp['mapped_body_sha256']
 # All guards above run before any poll/compiler subprocess or output object.
 O=a.out.resolve();C=a.compile_out.resolve();N=Path(plan['native_out'])/'compiled1';assert not C.exists()and not N.exists()and str(C).startswith(str(O)+'/');C.mkdir();(C/'objects').mkdir();N.mkdir();game=read(read(plan['manifest_path'])['selected_input']);selected=Path(read(plan['manifest_path'])['selected_input']).parent/'game_traces.h';heads={int(h,16)for h in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',selected.read_text())};assert len(heads)==456689
 def worker(row):
  i=row['index'];D=N/f'object-{i:05}';D.mkdir();R=C/f'object-{i:05}.json';commands=[]
  def run(cmd,label):
   cmd=list(map(str,cmd));commands.append(cmd)
   with(D/(label+'.log')).open('w')as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  try:
   rr=records[i];assert sha(rr['receipt'])==rr['receipt_sha256'];vv=read(rr['receipt']);assert vv['passed']and set(vv['targets'])=={f['head']for f in row['functions']};assert sha(vv['old_context_path'])==vv['old_context_sha256'];meta=read(vv['old_context_path']);data=Path(row['raw_ir']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['raw_ir_sha256'];old=data.decode();del data;of=c.extract_functions(old);assert set(of)=={int(h,16)for h in meta['all_heads']};assert c.parse_attributes(old)==meta['attributes']and c.parse_types(old)==meta['types']and c.parse_metadata(old)==meta['metadata'];kw={'old_attributes':meta['attributes'],'new_attributes':meta['attributes'],'old_metadata':meta['metadata'],'new_metadata':meta['metadata'],'old_types':meta['types'],'new_types':meta['types']};results={}
   for f in row['functions']:
    h=int(f['head'],16);proof=vv['targets'][f['head']];assert proof['passed']and sha(proof['mapped_body_path'])==proof['mapped_body_sha256'];oldbody=Path(proof['old_body_path']).read_text();assert oldbody==of[h]and sha(proof['old_body_path'])==proof['old_body_sha256'];r=c.verify_body(of[h],Path(proof['mapped_body_path']).read_text(),sites=f['sites'],**kw);assert r.passed,r.hold_reason;results[h]=r
   candidate,splice=c.splice_verified(old,results);cf=c.extract_functions(candidate);assert not B.SHAPE.search(candidate)and B.errors(cf)==B.errors(of)and B.state_layout(candidate)==B.STATE_SHA;old_errors=B.errors(of);old_hashes={h:B.digest(s)for h,s in of.items()};new_hashes={h:B.digest(s)for h,s in cf.items()};targets=set(results);raw=D/'replacement.raw.ll';raw.write_text(candidate);del old,of,cf,candidate
   run([B.POLL,raw,D/'replacement.polled.ll'],'poll');op=B.selected_polled(row);data=Path(op['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==op['sha256'];oldp=c.extract_functions(data.decode());del data;newtext=(D/'replacement.polled.ll').read_text();newp=c.extract_functions(newtext);assert set(oldp)==set(newp)and all(oldp[h]==newp[h]for h in oldp if h not in targets)and B.errors(newp)==old_errors;cov,oldcov=B.coverage(newp),B.coverage(oldp);assert B.state_layout(newtext)==B.STATE_SHA;del oldp,newp,newtext
   clang=plan['tools']['clang-18'];nm=plan['tools']['llvm-nm-18'];dump=plan['tools']['llvm-objdump-18'];run([clang,'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',D/'replacement.polled.ll','-o',D/'replacement.o'],'compile');symbols=subprocess.check_output([nm,'--format=posix','--extern-only',str(D/'replacement.o')],text=True);(D/'symbols.txt').write_text(symbols);defs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M));refs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M));assert defs==sorted(old_hashes)and not(set(refs)-heads);assert sha(row['selected_object']['path'])==row['selected_object']['sha256'];before=B.native_projection(dump,row['selected_object']['path']);after=B.native_projection(dump,D/'replacement.o');assert set(before)==set(after)==set(old_hashes);changed={h for h in before if before[h]!=after[h]};assert changed<=targets,('unaffected native differences',list(map(hex,changed-targets)));obj=C/'objects'/f'shard-{i:05}.o';shutil.copy2(D/'replacement.o',obj)
   result={'passed':True,'index':i,'module':row['module'],'object':{'path':str(obj),'sha256':sha(obj)},'old_object':row['selected_object'],'raw_ir':{'path':str(raw),'sha256':sha(raw)},'polled_ir':{'path':str(D/'replacement.polled.ll'),'sha256':sha(D/'replacement.polled.ll')},'old_raw_sha256':row['raw_ir_sha256'],'old_polled_ir':op,'changed_heads':list(map(hex,sorted(targets))),'definition_count':len(defs),'unchanged_raw_polled_native_functions':len(defs)-len(targets),'splice_proof':splice,'all_poll_coverage':cov,'old_poll_coverage':oldcov,'old_errors':old_errors,'new_errors':old_errors,'legacy_copies_removed':sum(len(f['sites'])for f in row['functions']),'remaining_legacy_shape_count':0,'native_changed_heads':list(map(hex,sorted(changed))),'direct_guest_targets':refs,'missing_direct_targets':[],'native_function_projections':{'old':{hex(h):p for h,p in before.items()},'new':{hex(h):p for h,p in after.items()}},'old_body_sha256':{hex(h):p for h,p in old_hashes.items()},'new_body_sha256':{hex(h):p for h,p in new_hashes.items()},'verification_receipt':rr,'commands':commands,'artifacts':{str(p):sha(p)for p in D.iterdir()if p.is_file()}}
  except Exception as e:result={'passed':False,'index':i,'hold_reason':str(e),'traceback':traceback.format_exc(),'commands':commands}
  save(R,result);return{'index':i,'passed':result['passed'],'receipt':str(R),'receipt_sha256':sha(R),'object':result.get('object'),'hold_reason':result.get('hold_reason')}
 results=run_all(manifest['objects'],plan['jobs'],worker,C/'progress.json','COMPILE');fixed_ok(plan);result={'passed':len(results)==plan['objects']and all(r['passed']for r in results),'phase':'COMPILED-CANDIDATE-VECTOR; NOT SELECTED','plan_sha256':a.plan_sha,'manifest_sha256':plan['manifest_sha256'],'verification_path':str(a.verification.resolve()),'verification_sha256':a.verification_sha,'objects':results,'functions':plan['functions'],'legacy_copies_removed':plan['copies'],'no_game_execution':True,'fixed_inputs':plan['fixed_inputs']};save(C/'acceptance.json',result);print('COMPILED-VECTOR',result['passed'],sha(C/'acceptance.json'),flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['plan','propose','verify','compile'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--native-out',type=Path);p.add_argument('--jobs',type=int,default=4)
 for n in['manifest','checker','checker-qualification','verification','verification-out','compile-out']:p.add_argument('--'+n,type=Path)
 for n in['manifest-sha','checker-sha','checker-qualification-sha','plan-sha','verification-sha']:p.add_argument('--'+n)
 p.add_argument('--reuse-root',type=Path,action='append');a=p.parse_args();assert 1<=a.jobs<=4
 if a.phase=='plan':make_plan(a);return
 O=a.out.resolve();assert a.plan_sha and sha(O/'plan.json')==a.plan_sha;plan=read(O/'plan.json');assert sha(__file__)==plan['producer_sha256']and BASE_SHA==sha(basepath);fixed_ok(plan);manifest=read(plan['manifest_path'])
 if a.phase=='propose':propose(a,plan,manifest)
 elif a.phase=='verify':assert a.verification_out and a.checker and a.checker_qualification;verify(a,plan,manifest)
 else:assert a.compile_out;compile_batch(a,plan,manifest)
if __name__=='__main__':main()
