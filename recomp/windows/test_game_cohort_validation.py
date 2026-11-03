"""Exercise actual Python/PowerShell cohort guards only; never compile/run a game."""
from pathlib import Path
import argparse,ast,copy,hashlib,json,subprocess

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--derived-proof',type=Path,required=True);p.add_argument('--sparse-proof',type=Path);p.add_argument('--additive-proof',type=Path);p.add_argument('--fcsel-proof',type=Path);p.add_argument('--fcsel-callers-proof',type=Path);p.add_argument('--st2-proof',type=Path);p.add_argument('--fcsel-batch-proof',type=Path);p.add_argument('--st2-constructor-proof',type=Path);a=p.parse_args()
 here=Path(__file__).resolve().parent;out=a.out.resolve();out.mkdir(exist_ok=False)
 python=here/'test_game_bootstrap.py';powershell=here/'game_bootstrap_build.ps1'
 w=here.parent/'work';v1=w/'game17-polled-cohort1/acceptance.json';v2=a.derived_proof.resolve()
 sources={str(x):sha(x)for x in(python,powershell,Path(__file__))}
 tree=ast.parse(python.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_cooperative_contract')
 env={'re':__import__('re'),'hashlib':hashlib,'pathlib':__import__('pathlib'),'json':json};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('sha','load_cooperative_parent','load_cooperative_ancestors','validate_cooperative_contract')],type_ignores=[]),str(python),'exec'),env);validate=env[fn.name]
 base={1:json.loads(v1.read_text()),2:json.loads(v2.read_text())};descriptors={1:dict(acceptance_path=str(v1),acceptance_sha256=sha(v1)),2:dict(acceptance_path=str(v2),acceptance_sha256=sha(v2))}
 assert base[2]['contract']['version']==2
 if a.sparse_proof:
  v3=a.sparse_proof.resolve();base[3]=json.loads(v3.read_text());descriptors[3]=dict(acceptance_path=str(v3),acceptance_sha256=sha(v3));assert base[3]['contract']['version']==3
 if a.additive_proof:
  assert a.sparse_proof,'additive proof requires the actual v3 parent'
  v4=a.additive_proof.resolve();base[4]=json.loads(v4.read_text());descriptors[4]=dict(acceptance_path=str(v4),acceptance_sha256=sha(v4));assert base[4]['contract']['version']==4
 if a.fcsel_proof:
  assert a.additive_proof,'FCSEL proof requires the actual v4 parent'
  v5=a.fcsel_proof.resolve();base[5]=json.loads(v5.read_text());descriptors[5]=dict(acceptance_path=str(v5),acceptance_sha256=sha(v5));assert base[5]['contract']['version']==5
 if a.fcsel_callers_proof:
  assert a.fcsel_proof,'FCSEL callers proof requires the actual v5 parent'
  v6=a.fcsel_callers_proof.resolve();base[6]=json.loads(v6.read_text());descriptors[6]=dict(acceptance_path=str(v6),acceptance_sha256=sha(v6));assert base[6]['contract']['version']==6
 if a.st2_proof:
  assert a.fcsel_callers_proof,'ST2 proof requires the actual v6 parent'
  v7=a.st2_proof.resolve();base[7]=json.loads(v7.read_text());descriptors[7]=dict(acceptance_path=str(v7),acceptance_sha256=sha(v7));assert base[7]['contract']['version']==7
 if a.fcsel_batch_proof:
  assert a.st2_proof,'FCSEL batch proof requires the actual v7 parent'
  v8=a.fcsel_batch_proof.resolve();base[8]=json.loads(v8.read_text());descriptors[8]=dict(acceptance_path=str(v8),acceptance_sha256=sha(v8));assert base[8]['contract']['version']==8
 if a.st2_constructor_proof:
  assert a.fcsel_batch_proof,'ST2 constructor proof requires the actual v8 parent'
  v9=a.st2_constructor_proof.resolve();base[9]=json.loads(v9.read_text());descriptors[9]=dict(acceptance_path=str(v9),acceptance_sha256=sha(v9));assert base[9]['contract']['version']==9
 initial_input_pins={str(file):sha(file)for file in [v1,v2]+([v3]if a.sparse_proof else[])+([v4]if a.additive_proof else[])+([v5]if a.fcsel_proof else[])+([v6]if a.fcsel_callers_proof else[])+([v7]if a.st2_proof else[])+([v8]if a.fcsel_batch_proof else[])+([v9]if a.st2_constructor_proof else[])+[Path(proof['contract']['input_plan_path'])for version,proof in base.items()if version>=2]}
 cases=[]
 def case(name,version,passed=False,*ops):cases.append(dict(name=name,version=version,passed=passed,ops=list(ops)))
 def change(root,path,value):return dict(root=root,path=path,value=value)
 zero='0'*64
 case('v1-original',1,True);case('v1-explicit-version',1,True,change('proof',['contract','version'],1));case('v2-qualified-sparse',2,True)
 for version in sorted(base):
  prefix=f'v{version}-'
  for name,path,value in [('heads',['trace_heads'],456683),('unique',['unique_definitions'],False),('missing',['missing_direct_targets'],[0x825a60c4]),('instrument',['contract','poll_instrument_sha256'],zero),('array-instrument',['contract','poll_instrument_sha256'],[]),('target',['contract','target'],'x86_64-linux-gnu'),('version',['contract','version'],10),('boolean-version',['contract','version'],True),('null-version',['contract','version'],None)]:case(prefix+name,version,False,change('proof',path,value))
  case(prefix+'order',version,False,dict(root='objects',path=[],swap=[0,1]))
  case(prefix+'object-hash',version,False,change('objects',[1553,'sha256'],zero))
  case(prefix+'object-count',version,False,dict(root='objects',path=[],pop=True))
 case('v1-plan',1,False,change('proof',['contract','input_plan_sha256'],zero))
 case('v1-relift-claim',1,False,change('proof',['contract','no_relift'],False))
 case('v1-source-claim',1,False,change('proof',['contract','source_ir_and_semantics_preserved'],False))
 for field in('input_plan_sha256','base_input_plan_sha256','base_cohort_acceptance_sha256','sparse_overlay_sha256','prefetch_fixture_acceptance_sha256','prefetch_lifter_sha256','prefetch_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
  case('v2-'+field,2,False,change('proof',['contract',field],zero))
 case('v2-acceptance-hash',2,False,change('descriptor',['acceptance_sha256'],zero))
 case('v2-profile',2,False,change('proof',['contract','profile'],'original'))
 case('v2-array-anchor',2,False,change('proof',['contract','base_input_plan_sha256'],[]))
 case('v2-relift-disclosure',2,False,change('proof',['contract','no_relift'],True))
 case('v2-source-disclosure',2,False,change('proof',['contract','source_ir_and_semantics_preserved'],True))
 case('v2-relift-count',2,False,change('proof',['contract','qualified_sparse_relifts'],2))
 case('v2-replaced-index',2,False,change('proof',['contract','replaced_object_index'],1554))
 case('v2-unchanged-count',2,False,change('proof',['contract','unchanged_objects'],3573))
 case('v2-plan-path',2,False,change('proof',['contract','input_plan_path'],None))
 case('v2-wrong-replacement-both-tables',2,False,change('proof',['objects',1553,'sha256'],zero),change('objects',[1553,'sha256'],zero))
 case('v3-missing-parent-on-v2',2,False,change('proof',['contract','version'],3))
 if a.sparse_proof:
  case('v3-qualified-single-sort',3,True)
  for field in('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','sparse_overlay_sha256','ext_fixture_acceptance_sha256','sort_fixture_acceptance_sha256','ext_lifter_sha256','ext_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
   case('v3-'+field,3,False,change('proof',['contract',field],zero))
  for field,value in [('profile','wrong'),('target_head','0x70255054'),('target_end_exclusive','0x70256040'),('optimization','-O0'),('optimization',[]),('no_relift',True),('source_ir_and_semantics_preserved',True),('no_global_semantics_refresh',False),('no_global_semantics_refresh',1),('production_signal_delivery_enabled',True),('production_signal_delivery_enabled',0),('incremental_sparse_relifts',2),('cumulative_qualified_sparse_relifts',1),('replaced_object_index',79),('unchanged_objects',3573),('cumulative_changed_indices',[1553,78]),('cumulative_changed_indices',[78]),('cumulative_changed_indices',[True,1553]),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:
   case('v3-'+field+'-'+repr(value),3,False,change('proof',['contract',field],value))
  for field in('incremental_sparse_relifts','cumulative_qualified_sparse_relifts','replaced_object_index','unchanged_objects'):
   for value in(True,'1',None,[]):case('v3-type-'+field+'-'+repr(value),3,False,change('proof',['contract',field],value))
  case('v3-acceptance-hash',3,False,change('descriptor',['acceptance_sha256'],zero))
  case('v3-parent-missing',3,False,change('parent',[],None))
  case('v3-parent-version',3,False,change('parent',['contract','version'],1))
  case('v3-parent-prefetch-index',3,False,change('parent',['objects',1553,'sha256'],zero))
  for index in(78,79,1553):case('v3-object-both-tables-'+str(index),3,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
 if a.additive_proof:
  case('v4-qualified-five-entry-addition',4,True)
  for field in('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','additive_candidate_sha256','prefix_fixture_acceptance_sha256','lifter_sha256','semantics_sha256','new_polled_object_sha256'):
   for value in(zero,[]):case('v4-'+field+'-'+repr(value),4,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('optimization','-O0'),('optimization',[]),('no_relift',True),('source_ir_and_semantics_preserved',True),('existing_objects_preserved',False),('no_global_semantics_refresh',False),('production_signal_delivery_enabled',True),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:
   case('v4-'+field+'-'+repr(value),4,False,change('proof',['contract',field],value))
  for field in('no_relift','source_ir_and_semantics_preserved','existing_objects_preserved','no_global_semantics_refresh','production_signal_delivery_enabled'):
   case('v4-bool-type-'+field,4,False,change('proof',['contract',field],0))
  for field,value in {'added_object_index':3575,'added_objects':1,'added_trace_count':5,'preserved_objects':3575,'inherited_cumulative_sparse_relifts':2}.items():
   for wrong in(value+1,True,str(value),None,[]):case('v4-count-'+field+'-'+repr(wrong),4,False,change('proof',['contract',field],wrong))
  heads=['0x70b5b488','0x70b5b4b0','0x70b5b4bc','0x70b5b648','0x70b5b674']
  for value in(heads[::-1],heads[:-1],heads+[heads[-1]],[int(x,16)for x in heads],heads[:-1]+['0x70b5b678'],None):case('v4-head-list-'+repr(value),4,False,change('proof',['contract','added_trace_heads'],value))
  for value in(456684,456690,'456689',True):case('v4-trace-shape-'+repr(value),4,False,change('proof',['trace_heads'],value))
  case('v4-acceptance-hash',4,False,change('descriptor',['acceptance_sha256'],zero))
  case('v4-parent-missing',4,False,change('parent',[],None))
  case('v4-parent-version',4,False,change('parent',['contract','version'],2))
  case('v4-grandparent-missing',4,False,change('grandparent',[],None))
  case('v4-grandparent-version',4,False,change('grandparent',['contract','version'],1))
  case('v4-grandparent-object',4,False,change('grandparent',['objects',1553,'sha256'],zero))
  for index in(0,78,1553,3574):case('v4-prefix-both-tables-'+str(index),4,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
  case('v4-parent-existing-object',4,False,change('parent',['objects',3574,'sha256'],zero))
  case('v4-new-object-both-tables',4,False,change('proof',['objects',3575,'sha256'],zero),change('objects',[3575,'sha256'],zero))
  case('v4-new-object-empty-path',4,False,change('proof',['objects',3575,'path'],''),change('objects',[3575,'path'],''))
  case('v4-new-object-reordered-both',4,False,dict(root='proof',path=['objects'],swap=[3574,3575]),dict(root='objects',path=[],swap=[3574,3575]))
  case('v4-extra-object-both',4,False,dict(root='proof',path=['objects'],append=dict(path='unexpected.o',sha256=zero)),dict(root='objects',path=[],append=dict(path='unexpected.o',sha256=zero)))
 if a.fcsel_proof:
  case('v5-qualified-single-fcsel-wrapper',5,True)
  for field in('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','sparse_overlay_sha256','fcsel_fixture_acceptance_sha256','fcsel_lifter_sha256','fcsel_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
   for value in(zero,[]):case('v5-'+field+'-'+repr(value),5,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('target_head','0x70abcbe0'),('target_end_exclusive','0x70acc1d4'),('optimization','-O0'),('optimization',[]),('no_relift',True),('source_ir_and_semantics_preserved',True),('no_global_semantics_refresh',False),('production_signal_delivery_enabled',True),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:
   case('v5-'+field+'-'+repr(value),5,False,change('proof',['contract',field],value))
  for field in('no_relift','source_ir_and_semantics_preserved','no_global_semantics_refresh','production_signal_delivery_enabled'):case('v5-policy-type-'+field,5,False,change('proof',['contract',field],0))
  for field,value in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':3,'replaced_object_index':459,'unchanged_objects':3575}.items():
   for wrong in(value+1,True,str(value),None,[]):case('v5-count-'+field+'-'+repr(wrong),5,False,change('proof',['contract',field],wrong))
  for value in([459,78,1553],[78,459],[78,459,1553,3575],[78,True,1553],None):case('v5-cumulative-indices-'+repr(value),5,False,change('proof',['contract','cumulative_changed_indices'],value))
  case('v5-acceptance-hash',5,False,change('descriptor',['acceptance_sha256'],zero))
  case('v5-parent-missing',5,False,change('parent',[],None));case('v5-parent-version',5,False,change('parent',['contract','version'],3))
  case('v5-grandparent-missing',5,False,change('grandparent',[],None));case('v5-grandparent-version',5,False,change('grandparent',['contract','version'],2))
  case('v5-great-grandparent-missing',5,False,change('greatgrandparent',[],None));case('v5-great-grandparent-version',5,False,change('greatgrandparent',['contract','version'],1))
  case('v5-parent-added-object',5,False,change('parent',['objects',3575,'sha256'],zero))
  for index in(0,78,458,460,1553,3575):case('v5-neighbor-both-tables-'+str(index),5,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
  case('v5-replacement-both-tables',5,False,change('proof',['objects',459,'sha256'],zero),change('objects',[459,'sha256'],zero))
  case('v5-parent-old-object',5,False,change('parent',['objects',459,'sha256'],zero))
  case('v5-reorder-both',5,False,dict(root='proof',path=['objects'],swap=[459,460]),dict(root='objects',path=[],swap=[459,460]))
  case('v5-extra-object-both',5,False,dict(root='proof',path=['objects'],append=dict(path='unexpected.o',sha256=zero)),dict(root='objects',path=[],append=dict(path='unexpected.o',sha256=zero)))
 if a.fcsel_callers_proof:
  case('v6-qualified-five-caller-definitions',6,True)
  for field in('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','sparse_overlay_sha256','fcsel_fixture_acceptance_sha256','fcsel_lifter_sha256','fcsel_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
   for value in(zero,[]):case('v6-'+field+'-'+repr(value),6,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('optimization','-O0'),('optimization',[]),('no_relift',True),('source_ir_and_semantics_preserved',True),('no_global_semantics_refresh',False),('production_signal_delivery_enabled',True),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:case('v6-'+field+'-'+repr(value),6,False,change('proof',['contract',field],value))
  for field in('no_relift','source_ir_and_semantics_preserved','no_global_semantics_refresh','production_signal_delivery_enabled'):case('v6-policy-type-'+field,6,False,change('proof',['contract',field],0))
  for field,value in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':4,'replaced_object_index':161,'unchanged_objects':3575,'changed_function_count':5,'unchanged_functions_in_shard':123}.items():
   for wrong in(value+1,True,str(value),None,[]):case('v6-count-'+field+'-'+repr(wrong),6,False,change('proof',['contract',field],wrong))
  for value in([161,78,459,1553],[78,161,459],[78,161,459,1553,3575],[78,True,459,1553],None):case('v6-cumulative-indices-'+repr(value),6,False,change('proof',['contract','cumulative_changed_indices'],value))
  heads=['0x7042377c','0x704238f4','0x70423908','0x70423918','0x70423928']
  for value in(heads[::-1],heads[:-1],heads+[heads[-1]],[int(h,0)for h in heads],heads[:-1]+['0x70423960'],None):case('v6-target-heads-'+repr(value),6,False,change('proof',['contract','target_heads'],value))
  case('v6-acceptance-hash',6,False,change('descriptor',['acceptance_sha256'],zero))
  case('v6-chain-missing',6,False,change('ancestors',[],None))
  case('v6-chain-short',6,False,dict(root='ancestors',path=[],pop=True))
  case('v6-chain-order',6,False,dict(root='ancestors',path=[],swap=[0,1]))
  for depth in range(4):
   case('v6-ancestor-missing-'+str(depth),6,False,change('ancestors',[depth],None))
   case('v6-ancestor-version-'+str(depth),6,False,change('ancestors',[depth,'contract','version'],1))
  case('v6-parent459-repair',6,False,change('ancestors',[0,'objects',459,'sha256'],zero))
  for index in(0,78,160,162,459,1553,3575):case('v6-neighbor-both-tables-'+str(index),6,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
  case('v6-replacement-both-tables',6,False,change('proof',['objects',161,'sha256'],zero),change('objects',[161,'sha256'],zero))
  case('v6-parent-old-object',6,False,change('ancestors',[0,'objects',161,'sha256'],zero))
  case('v6-reorder-both',6,False,dict(root='proof',path=['objects'],swap=[161,162]),dict(root='objects',path=[],swap=[161,162]))
  case('v6-extra-object-both',6,False,dict(root='proof',path=['objects'],append=dict(path='unexpected.o',sha256=zero)),dict(root='objects',path=[],append=dict(path='unexpected.o',sha256=zero)))
 if a.st2_proof:
  case('v7-qualified-original-st2-object',7,True)
  for field in ('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','sparse_overlay_sha256','st2_fixture_acceptance_sha256','original_fixture_acceptance_sha256','st2_lifter_sha256','st2_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
   for value in (zero,[]):case('v7-'+field+'-'+repr(value),7,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('target_head','0x707bb4bc'),('target_end_exclusive','0x707bb560'),('optimization','-O0'),('no_relift',True),('source_ir_and_semantics_preserved',True),('no_global_semantics_refresh',False),('production_signal_delivery_enabled',True),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:
   case('v7-'+field+'-'+repr(value),7,False,change('proof',['contract',field],value))
  for field in ('no_relift','source_ir_and_semantics_preserved','no_global_semantics_refresh','production_signal_delivery_enabled'):
   case('v7-bool-type-'+field,7,False,change('proof',['contract',field],0))
  for field,value in {'incremental_sparse_relifts':1,'cumulative_qualified_sparse_relifts':5,'replaced_object_index':270,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items():
   for wrong in (value+1,True,str(value),None,[]):case('v7-count-'+field+'-'+repr(wrong),7,False,change('proof',['contract',field],wrong))
  for value in ([78,161,459,1553],[78,161,270,459,1553][::-1],[78,161,270,459,1553,3575],[78,True,270,459,1553],None):case('v7-cumulative-set-'+repr(value),7,False,change('proof',['contract','cumulative_changed_indices'],value))
  case('v7-acceptance-hash',7,False,change('descriptor',['acceptance_sha256'],zero))
  case('v7-chain-missing',7,False,change('ancestors',[],None))
  case('v7-chain-short',7,False,dict(root='ancestors',path=[],pop=True))
  case('v7-chain-order',7,False,dict(root='ancestors',path=[],swap=[0,1]))
  for depth in range(5):
   case('v7-ancestor-missing-'+str(depth),7,False,change('ancestors',[depth],None))
   case('v7-ancestor-version-'+str(depth),7,False,change('ancestors',[depth,'contract','version'],1))
  for index in (0,78,161,269,271,459,1553,3575):case('v7-neighbor-both-tables-'+str(index),7,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
  case('v7-replacement-both-tables',7,False,change('proof',['objects',270,'sha256'],zero),change('objects',[270,'sha256'],zero))
  case('v7-parent-old-object',7,False,change('ancestors',[0,'objects',270,'sha256'],zero))
  case('v7-reorder-both',7,False,dict(root='proof',path=['objects'],swap=[270,271]),dict(root='objects',path=[],swap=[270,271]))
 if a.fcsel_batch_proof:
  case('v8-qualified-fcsel-vector-batch',8,True)
  for field in ('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','batch_acceptance_sha256','batch_manifest_sha256','checker_qualification_sha256','fcsel_fixture_acceptance_sha256','fcsel_lifter_sha256','fcsel_semantics_sha256','compiled_identity_sha256','condition_qualification_sha256','replacement_vector_sha256'):
   for value in (zero,[]):case('v8-'+field+'-'+repr(value),8,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('proof_mode','wrong'),('optimization','-O0'),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:case('v8-'+field,8,False,change('proof',['contract',field],value))
  for field,value in {'no_relift':True,'source_ir_and_semantics_preserved':False,'no_global_semantics_refresh':True,'production_signal_delivery_enabled':False,'non_fcsel_instructions_preserved':True,'all_replacements_qualified':True}.items():
   case('v8-policy-'+field,8,False,change('proof',['contract',field],not value));case('v8-policy-type-'+field,8,False,change('proof',['contract',field],int(value)))
  for field,value in {'replacement_count':556,'unchanged_objects':3020,'changed_function_count':2164,'legacy_fcsel_copy_count':5766}.items():
   for wrong in(value+1,True,str(value),None,[]):case('v8-count-'+field+'-'+repr(wrong),8,False,change('proof',['contract',field],wrong))
  case('v8-acceptance-hash',8,False,change('descriptor',['acceptance_sha256'],zero))
  case('v8-chain-missing',8,False,change('ancestors',[],None));case('v8-chain-short',8,False,dict(root='ancestors',path=[],pop=True));case('v8-chain-order',8,False,dict(root='ancestors',path=[],swap=[0,1]))
  for depth in range(6):
   case('v8-ancestor-missing-'+str(depth),8,False,change('ancestors',[depth],None));case('v8-ancestor-version-'+str(depth),8,False,change('ancestors',[depth,'contract','version'],1))
  vector=base[8]['contract']['replacement_vector'];first=vector[0];index=first['index'];unchanged=next(i for i in range(3576)if i not in {r['index']for r in vector})
  case('v8-vector-null',8,False,change('proof',['contract','replacement_vector'],None));case('v8-vector-dict',8,False,change('proof',['contract','replacement_vector'],{}))
  case('v8-vector-short',8,False,dict(root='proof',path=['contract','replacement_vector'],pop=True));case('v8-vector-extra',8,False,dict(root='proof',path=['contract','replacement_vector'],append=first))
  case('v8-vector-order',8,False,dict(root='proof',path=['contract','replacement_vector'],swap=[0,1]));case('v8-vector-duplicate',8,False,change('proof',['contract','replacement_vector',1],first))
  case('v8-vector-null-row',8,False,change('proof',['contract','replacement_vector',0],None));case('v8-vector-row-list',8,False,change('proof',['contract','replacement_vector',0],[]))
  case('v8-vector-extra-key',8,False,change('proof',['contract','replacement_vector',0],dict(first,extra='no')))
  for field in first:
   case('v8-vector-missing-'+field,8,False,change('proof',['contract','replacement_vector',0],{k:v for k,v in first.items()if k!=field}))
  for value in(-1,3576,True,str(index),None,[]):case('v8-vector-index-'+repr(value),8,False,change('proof',['contract','replacement_vector',0,'index'],value))
  for field in('old_path','new_path','old_sha256','new_sha256'):
   for value in(None,[], '',first[field]+'\t',first[field]+'\n',first[field]+'\r',first[field]+'\x00',first[field]+'\x7f',first[field]+'\x85',first[field]+'\ud800'):
    case('v8-vector-field-'+field+'-'+repr(value),8,False,change('proof',['contract','replacement_vector',0,field],value))
  for field in('old_sha256','new_sha256'):
   for value in('g'*64,'A'*64,'0'*63):case('v8-vector-sha-'+field+'-'+value,8,False,change('proof',['contract','replacement_vector',0,field],value))
  for field,wrong in [('sha256',zero),('path',first['new_path']+'-tamper')]:
   case('v8-new-'+field+'-both-tables',8,False,change('proof',['objects',index,field],wrong),change('objects',[index,field],wrong))
   # A self-consistent vector and two object tables still cannot change its pinned payload.
   key='new_sha256'if field=='sha256'else'new_path'
   ops=[change('proof',['contract','replacement_vector',0,key],wrong),change('proof',['objects',index,field],wrong),change('objects',[index,field],wrong)]
   case('v8-new-'+field+'-vector-and-both-tables',8,False,*ops)
   altered=copy.deepcopy(vector);altered[0][key]=wrong;payload=''.join(str(r['index'])+'\t'+r['old_path']+'\t'+r['old_sha256']+'\t'+r['new_path']+'\t'+r['new_sha256']+'\n'for r in altered)
   case('v8-new-'+field+'-self-rehashed-vector',8,False,*ops,change('proof',['contract','replacement_vector_sha256'],hashlib.sha256(payload.encode('utf-8')).hexdigest()))
   oldkey='old_sha256'if field=='sha256'else'old_path';case('v8-old-'+field+'-vector-and-parent',8,False,change('proof',['contract','replacement_vector',0,oldkey],wrong),change('ancestors',[0,'objects',index,field],wrong))
   case('v8-unchanged-'+field+'-both-tables',8,False,change('proof',['objects',unchanged,field],wrong),change('objects',[unchanged,field],wrong))
 if a.st2_constructor_proof:
  case('v9-qualified-st2-constructor',9,True)
  for field in ('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256','sparse_overlay_sha256','st2_fixture_acceptance_sha256','original_fixture_acceptance_sha256','st2_lifter_sha256','st2_semantics_sha256','old_polled_object_sha256','new_polled_object_sha256'):
   for value in (zero,[]):case('v9-'+field+'-'+repr(value),9,False,change('proof',['contract',field],value))
  for field,value in [('profile','wrong'),('target_head','0x70752174'),('target_end_exclusive','0x707521c0'),('optimization','-O0'),('no_relift',True),('source_ir_and_semantics_preserved',True),('no_global_semantics_refresh',False),('production_signal_delivery_enabled',True),('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])]:
   case('v9-'+field+'-'+repr(value),9,False,change('proof',['contract',field],value))
  for field in ('no_relift','source_ir_and_semantics_preserved','no_global_semantics_refresh','production_signal_delivery_enabled'):
   case('v9-bool-type-'+field,9,False,change('proof',['contract',field],0))
  for field,value in {'incremental_sparse_relifts':1,'inherited_vector_replacements':556,'replaced_object_index':249,'unchanged_objects':3575,'changed_function_count':1,'unchanged_functions_in_shard':127}.items():
   for wrong in (value+1,True,str(value),None,[]):case('v9-count-'+field+'-'+repr(wrong),9,False,change('proof',['contract',field],wrong))
  case('v9-acceptance-hash',9,False,change('descriptor',['acceptance_sha256'],zero))
  case('v9-chain-missing',9,False,change('ancestors',[],None))
  case('v9-chain-short',9,False,dict(root='ancestors',path=[],pop=True))
  case('v9-chain-order',9,False,dict(root='ancestors',path=[],swap=[0,1]))
  for depth in range(7):
   case('v9-ancestor-missing-'+str(depth),9,False,change('ancestors',[depth],None))
   case('v9-ancestor-version-'+str(depth),9,False,change('ancestors',[depth,'contract','version'],1))
  for index in (0,78,161,248,250,459,1553,3575):case('v9-neighbor-both-tables-'+str(index),9,False,change('proof',['objects',index,'sha256'],zero),change('objects',[index,'sha256'],zero))
  case('v9-replacement-both-tables',9,False,change('proof',['objects',249,'sha256'],zero),change('objects',[249,'sha256'],zero))
  case('v9-parent-old-object',9,False,change('ancestors',[0,'objects',249,'sha256'],zero))
  case('v9-reorder-both',9,False,dict(root='proof',path=['objects'],swap=[249,250]),dict(root='objects',path=[],swap=[249,250]))
 results=[]
 for c in cases:
  data={'proof':copy.deepcopy(base[c['version']]),'descriptor':dict(descriptors[c['version']]),'objects':copy.deepcopy(base[c['version']]['objects']),'parent':copy.deepcopy(base[c['version']-1])if c['version']in(3,4,5)else None,'grandparent':copy.deepcopy(base[c['version']-2])if c['version']in(4,5)else None,'greatgrandparent':copy.deepcopy(base[2])if c['version']==5 else None,'ancestors':copy.deepcopy([base[v]for v in range(c['version']-1,1,-1)])if c['version']in(6,7,8,9)else None}
  for op in c['ops']:
   target=data[op['root']]
   for key in op['path'][:-1]:target=target[key]
   if 'swap'in op or 'append'in op or op.get('pop'):
    if op['path']:target=target[op['path'][-1]]
    if 'swap'in op:i,j=op['swap'];target[i],target[j]=target[j],target[i]
    elif 'append'in op:target.append(op['append'])
    else:target.pop()
   elif not op['path']:data[op['root']]=op['value']
   else:target[op['path'][-1]]=op['value']
  try:version=validate(data['proof'],data['descriptor'],data['objects'],data['parent'],data['grandparent'],data['greatgrandparent'],data['ancestors']);passed=True
  except(AssertionError,KeyError,TypeError,IndexError):passed=False;version=None
  assert passed==c['passed'],(c['name'],passed)
  results.append(dict(name=c['name'],passed=passed,version=version))
 (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');(out/'python-results.json').write_text(json.dumps(results,indent=2)+'\n')
 python_io=[]
 if a.sparse_proof:
  parent_path=Path(base[3]['contract']['parent_acceptance_path']);parent_plan=Path(base[3]['contract']['parent_input_plan_path']);new_plan=Path(base[3]['contract']['input_plan_path'])
  tampered_parent=out/'tampered-parent.json';tampered_parent.write_bytes(parent_path.read_bytes()+b'\n')
  tampered_parent_plan=out/'tampered-parent-plan.json';tampered_parent_plan.write_bytes(parent_plan.read_bytes()+b'\n')
  tampered_v3_plan=out/'tampered-v3-plan.json';tampered_v3_plan.write_bytes(new_plan.read_bytes()+b'\n')
  parent=env['load_cooperative_parent'](base[3]);assert validate(base[3],descriptors[3],base[3]['objects'],parent)==3
  python_io.append(dict(name='v3-actual-parent-load-source-subguard',passed=True))
  for field,file,message in [('parent_acceptance_path',tampered_parent,'v3 parent proof file differs'),('parent_input_plan_path',tampered_parent_plan,'v3 parent plan file differs')]:
   q=copy.deepcopy(base[3]);q['contract'][field]=str(file)
   try:env['load_cooperative_parent'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual parent hash subguard accepted altered bytes')
   python_io.append(dict(name='v3-altered-'+field+'-source-subguard',passed=False))
  plan_guard=next(n for n in ast.walk(tree)if isinstance(n,ast.If)and ast.unparse(n.test)=='version in (2, 3, 4, 5, 6, 7, 8, 9)')
  q=copy.deepcopy(base[3]);q['contract']['input_plan_path']=str(tampered_v3_plan);scope=dict(env,version=3,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v3-altered-new-plan-source-subguard',passed=False))
 if a.additive_proof:
  c=base[4]['contract'];parent=env['load_cooperative_parent'](base[4]);grandparent=env['load_cooperative_parent'](parent)
  assert validate(base[4],descriptors[4],base[4]['objects'],parent,grandparent)==4
  python_io.append(dict(name='v4-actual-two-ancestor-load-source-subguard',passed=True))
  tampered_v4_parent=out/'tampered-v4-parent.json';tampered_v4_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v4_parent_plan=out/'tampered-v4-parent-plan.json';tampered_v4_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v4_plan=out/'tampered-v4-plan.json';tampered_v4_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v4_parent,'v4 parent proof file differs'),('parent_input_plan_path',tampered_v4_parent_plan,'v4 parent plan file differs')]:
   q=copy.deepcopy(base[4]);q['contract'][field]=str(file)
   try:env['load_cooperative_parent'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v4 parent hash subguard accepted altered bytes')
   python_io.append(dict(name='v4-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[4]);q['contract']['input_plan_path']=str(tampered_v4_plan);scope=dict(env,version=4,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v4 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v4-altered-new-plan-source-subguard',passed=False))
 if a.fcsel_proof:
  c=base[5]['contract'];parent=env['load_cooperative_parent'](base[5]);grandparent=env['load_cooperative_parent'](parent);great=env['load_cooperative_parent'](grandparent)
  assert validate(base[5],descriptors[5],base[5]['objects'],parent,grandparent,great)==5
  python_io.append(dict(name='v5-three-ancestor-load-source-subguard',passed=True))
  tampered_v5_parent=out/'tampered-v5-parent.json';tampered_v5_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v5_parent_plan=out/'tampered-v5-parent-plan.json';tampered_v5_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v5_plan=out/'tampered-v5-plan.json';tampered_v5_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v5_parent,'v5 parent proof file differs'),('parent_input_plan_path',tampered_v5_parent_plan,'v5 parent plan file differs')]:
   q=copy.deepcopy(base[5]);q['contract'][field]=str(file)
   try:env['load_cooperative_parent'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v5 parent hash subguard accepted altered bytes')
   python_io.append(dict(name='v5-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[5]);q['contract']['input_plan_path']=str(tampered_v5_plan);scope=dict(env,version=5,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v5 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v5-altered-new-plan-source-subguard',passed=False))
 if a.fcsel_callers_proof:
  c=base[6]['contract'];ancestors=env['load_cooperative_ancestors'](base[6]);assert validate(base[6],descriptors[6],base[6]['objects'],ancestor_chain=ancestors)==6
  python_io.append(dict(name='v6-four-ancestor-load-source-subguard',passed=True))
  tampered_v6_parent=out/'tampered-v6-parent.json';tampered_v6_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v6_parent_plan=out/'tampered-v6-parent-plan.json';tampered_v6_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v6_plan=out/'tampered-v6-plan.json';tampered_v6_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v6_parent,'v6 parent proof file differs'),('parent_input_plan_path',tampered_v6_parent_plan,'v6 parent plan file differs')]:
   q=copy.deepcopy(base[6]);q['contract'][field]=str(file)
   try:env['load_cooperative_ancestors'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v6 ancestor hash subguard accepted altered bytes')
   python_io.append(dict(name='v6-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[6]);q['contract']['input_plan_path']=str(tampered_v6_plan);scope=dict(env,version=6,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v6 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v6-altered-new-plan-source-subguard',passed=False))
 if a.st2_proof:
  c=base[7]['contract'];ancestors=env['load_cooperative_ancestors'](base[7]);assert validate(base[7],descriptors[7],base[7]['objects'],ancestor_chain=ancestors)==7
  python_io.append(dict(name='v7-five-ancestor-load-source-subguard',passed=True))
  tampered_v7_parent=out/'tampered-v7-parent.json';tampered_v7_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v7_parent_plan=out/'tampered-v7-parent-plan.json';tampered_v7_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v7_plan=out/'tampered-v7-plan.json';tampered_v7_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v7_parent,'v7 parent proof file differs'),('parent_input_plan_path',tampered_v7_parent_plan,'v7 parent plan file differs')]:
   q=copy.deepcopy(base[7]);q['contract'][field]=str(file)
   try:env['load_cooperative_ancestors'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v7 ancestor hash subguard accepted altered bytes')
   python_io.append(dict(name='v7-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[7]);q['contract']['input_plan_path']=str(tampered_v7_plan);scope=dict(env,version=7,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v7 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v7-altered-new-plan-source-subguard',passed=False))
 if a.fcsel_batch_proof:
  c=base[8]['contract'];ancestors=env['load_cooperative_ancestors'](base[8]);assert validate(base[8],descriptors[8],base[8]['objects'],ancestor_chain=ancestors)==8
  python_io.append(dict(name='v8-six-ancestor-load-source-subguard',passed=True))
  tampered_v8_parent=out/'tampered-v8-parent.json';tampered_v8_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v8_parent_plan=out/'tampered-v8-parent-plan.json';tampered_v8_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v8_plan=out/'tampered-v8-plan.json';tampered_v8_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v8_parent,'v8 parent proof file differs'),('parent_input_plan_path',tampered_v8_parent_plan,'v8 parent plan file differs')]:
   q=copy.deepcopy(base[8]);q['contract'][field]=str(file)
   try:env['load_cooperative_ancestors'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v8 ancestor hash subguard accepted altered bytes')
   python_io.append(dict(name='v8-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[8]);q['contract']['input_plan_path']=str(tampered_v8_plan);scope=dict(env,version=8,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v8 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v8-altered-new-plan-source-subguard',passed=False))
 if a.st2_constructor_proof:
  c=base[9]['contract'];ancestors=env['load_cooperative_ancestors'](base[9]);assert validate(base[9],descriptors[9],base[9]['objects'],ancestor_chain=ancestors)==9
  python_io.append(dict(name='v9-seven-ancestor-load-source-subguard',passed=True))
  tampered_v9_parent=out/'tampered-v9-parent.json';tampered_v9_parent.write_bytes(Path(c['parent_acceptance_path']).read_bytes()+b'\n')
  tampered_v9_parent_plan=out/'tampered-v9-parent-plan.json';tampered_v9_parent_plan.write_bytes(Path(c['parent_input_plan_path']).read_bytes()+b'\n')
  tampered_v9_plan=out/'tampered-v9-plan.json';tampered_v9_plan.write_bytes(Path(c['input_plan_path']).read_bytes()+b'\n')
  for field,file,message in [('parent_acceptance_path',tampered_v9_parent,'v9 parent proof file differs'),('parent_input_plan_path',tampered_v9_parent_plan,'v9 parent plan file differs')]:
   q=copy.deepcopy(base[9]);q['contract'][field]=str(file)
   try:env['load_cooperative_ancestors'](q)
   except AssertionError as error:assert str(error)==message
   else:raise AssertionError('actual v9 ancestor hash subguard accepted altered bytes')
   python_io.append(dict(name='v9-altered-'+field+'-source-subguard',passed=False))
  q=copy.deepcopy(base[9]);q['contract']['input_plan_path']=str(tampered_v9_plan);scope=dict(env,version=9,proof=q,expected={})
  try:exec(compile(ast.Module(body=[plan_guard],type_ignores=[]),str(python),'exec'),scope)
  except AssertionError as error:assert str(error)=='sparse cooperative plan file differs'
  else:raise AssertionError('actual v9 plan IO subguard accepted altered bytes')
  python_io.append(dict(name='v9-altered-new-plan-source-subguard',passed=False))
 (out/'python-io-results.json').write_text(json.dumps(python_io,indent=2)+'\n')
 tampered=out/'tampered-proof.json';tampered.write_bytes(v2.read_bytes()+b'\n');assert sha(tampered)!=descriptors[2]['acceptance_sha256']
 def windows(path):return subprocess.check_output(['wslpath','-w',str(Path(path).resolve())],text=True).strip()
 # PowerShell's own AST extracts the exact production function; no duplicate predicate.
 driver=r'''param([string]$Source,[string]$Original,[string]$Derived,[string]$Sparse,[string]$Additive,[string]$Fcsel,[string]$FcselCallers,[string]$St2,[string]$FcselBatch,[string]$St2Constructor,[string]$TamperedV9Parent,[string]$TamperedV9ParentPlan,[string]$TamperedV9Plan,[string]$TamperedV8Parent,[string]$TamperedV8ParentPlan,[string]$TamperedV8Plan,[string]$TamperedV7Parent,[string]$TamperedV7ParentPlan,[string]$TamperedV7Plan,[string]$TamperedV6Parent,[string]$TamperedV6ParentPlan,[string]$TamperedV6Plan,[string]$TamperedV5Parent,[string]$TamperedV5ParentPlan,[string]$TamperedV5Plan,[string]$TamperedV4Parent,[string]$TamperedV4ParentPlan,[string]$TamperedV4Plan,[string]$TamperedParent,[string]$TamperedParentPlan,[string]$TamperedV3Plan,[string]$Cases,[string]$Tampered,[string]$Output)
$ErrorActionPreference='Stop'
# WSL can inherit PowerShell7's PSModulePath when launching WindowsPowerShell5.
# Load its own real utility module explicitly; never replace Game-Hash.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
$tokens=$null;$parseErrors=$null;$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'PowerShell production parse failed'}
$definition=$ast.FindAll({param($n)$n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Game-ValidatePollContract'},$true)
if($definition.Count -ne 1){throw 'Production validator function missing/duplicated'}
. ([ScriptBlock]::Create($definition[0].Extent.Text))
$raw=@{1=(Get-Content -Raw -LiteralPath $Original);2=(Get-Content -Raw -LiteralPath $Derived)}
$paths=@{1=$Original;2=$Derived}
$hashes=@{1=(Get-FileHash -LiteralPath $Original -Algorithm SHA256).Hash.ToLowerInvariant();2=(Get-FileHash -LiteralPath $Derived -Algorithm SHA256).Hash.ToLowerInvariant()}
$versions=@(1,2)
if($Sparse){$raw[3]=Get-Content -Raw -LiteralPath $Sparse;$paths[3]=$Sparse;$hashes[3]=(Get-FileHash -LiteralPath $Sparse -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=3}
if($Additive){$raw[4]=Get-Content -Raw -LiteralPath $Additive;$paths[4]=$Additive;$hashes[4]=(Get-FileHash -LiteralPath $Additive -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=4}
if($Fcsel){$raw[5]=Get-Content -Raw -LiteralPath $Fcsel;$paths[5]=$Fcsel;$hashes[5]=(Get-FileHash -LiteralPath $Fcsel -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=5}
if($FcselCallers){$raw[6]=Get-Content -Raw -LiteralPath $FcselCallers;$paths[6]=$FcselCallers;$hashes[6]=(Get-FileHash -LiteralPath $FcselCallers -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=6}
if($St2){$raw[7]=Get-Content -Raw -LiteralPath $St2;$paths[7]=$St2;$hashes[7]=(Get-FileHash -LiteralPath $St2 -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=7}
if($FcselBatch){$raw[8]=Get-Content -Raw -LiteralPath $FcselBatch;$paths[8]=$FcselBatch;$hashes[8]=(Get-FileHash -LiteralPath $FcselBatch -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=8}
if($St2Constructor){$raw[9]=Get-Content -Raw -LiteralPath $St2Constructor;$paths[9]=$St2Constructor;$hashes[9]=(Get-FileHash -LiteralPath $St2Constructor -Algorithm SHA256).Hash.ToLowerInvariant();$versions+=9}
$results=@()
foreach($case in (Get-Content -Raw -LiteralPath $Cases|ConvertFrom-Json)){
 $v=[int]$case.version;$data=@{proof=($raw[$v]|ConvertFrom-Json);descriptor=[pscustomobject]@{acceptance_path=$paths[$v];acceptance_sha256=$hashes[$v]};objects=($raw[$v]|ConvertFrom-Json).objects;parent=$null;grandparent=$null;greatgrandparent=$null;ancestors=$null};if($v -eq 3 -or $v -eq 4 -or $v -eq 5){$data.parent=$raw[$v-1]|ConvertFrom-Json};if($v -eq 4 -or $v -eq 5){$data.grandparent=$raw[$v-2]|ConvertFrom-Json};if($v -eq 5){$data.greatgrandparent=$raw[2]|ConvertFrom-Json};if($v -eq 6 -or $v -eq 7 -or $v -eq 8 -or $v -eq 9){$data.ancestors=@();for($ancestor=$v-1;$ancestor -ge 2;$ancestor--){$data.ancestors+=,($raw[$ancestor]|ConvertFrom-Json)}}
 foreach($op in $case.ops){
  $target=$data[$op.root]
  for($i=0;$i -lt $op.path.Count-1;$i++){$k=$op.path[$i];if($k -is [long] -or $k -is [int]){$target=$target[[int]$k]}else{$target=$target.$k}}
  if($null -ne $op.swap -or $null -ne $op.append -or $op.pop){
   if($op.path.Count){$key=$op.path[-1];$collectionOwner=$target;if($key -is [long] -or $key -is [int]){$target=$target[[int]$key]}else{$target=$target.$key}}
   if($null -ne $op.swap){$i=[int]$op.swap[0];$j=[int]$op.swap[1];$saved=$target[$i];$target[$i]=$target[$j];$target[$j]=$saved}
   else{if($op.pop){$replacement=@($target[0..($target.Count-2)])}else{$replacement=@($target)+@($op.append)};if($op.path.Count){if($key -is [long] -or $key -is [int]){$collectionOwner[[int]$key]=$replacement}else{$collectionOwner|Add-Member -Force -NotePropertyName $key -NotePropertyValue $replacement}}else{$data[$op.root]=$replacement}}
  }
  elseif($op.path.Count -eq 0){$data[$op.root]=$op.value}
  else{$k=$op.path[-1];if($k -is [long] -or $k -is [int]){$target[[int]$k]=$op.value}else{$target|Add-Member -Force -NotePropertyName $k -NotePropertyValue $op.value}}
 }
 $ok=$false;$message='';$version=$null
 try{$version=Game-ValidatePollContract $data.proof $data.descriptor $data.objects $data.parent $data.grandparent $data.greatgrandparent $data.ancestors;$ok=$true}catch{$message=$_.Exception.Message}
 if($ok -ne $case.passed){throw "Unexpected production guard result: $($case.name) success=$ok message=$message"}
 $results+=@{name=$case.name;passed=$ok;version=$version;message=$message}
}
[IO.File]::WriteAllText($Output,($results|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
# Run the actual complete acceptance-loading/hash/contract/plan guard as well.
foreach($name in @('Game-Path','Game-Hash','Game-LoadPollParent','Game-LoadPollAncestors')){$fn=$ast.FindAll({param($n)$n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true);if($fn.Count -ne 1){throw 'Production IO function missing'};. ([ScriptBlock]::Create($fn[0].Extent.Text))}
$text=Get-Content -Raw -LiteralPath $Source;$begin=$text.IndexOf('$taskPollCohort=$taskInput.cooperative_poll_cohort');$end=$text.IndexOf("if((Game-Hash (Join-Path `$taskBuild 'libz-inflate.a'))")
if($begin -lt 0 -or $end -le $begin){throw 'Actual production cohort guard boundaries missing'}
$guard=[ScriptBlock]::Create($text.Substring($begin,$end-$begin));$io=@();$EnableCollectorDelivery=$true
foreach($v in $versions){
 $taskInput=[pscustomobject]@{union_trace_count=($raw[$v]|ConvertFrom-Json).trace_heads;objects=($raw[$v]|ConvertFrom-Json).objects;cooperative_poll_cohort=[pscustomobject]@{acceptance_path=$paths[$v];acceptance_sha256=$hashes[$v]}}
 & $guard
 $io+=@{name="v$v-complete-production-guard";passed=$true}
}
$taskInput=[pscustomobject]@{union_trace_count=($raw[2]|ConvertFrom-Json).trace_heads;objects=($raw[2]|ConvertFrom-Json).objects;cooperative_poll_cohort=[pscustomobject]@{acceptance_path=$Tampered;acceptance_sha256=$hashes[2]}}
$rejected=$false;try{& $guard}catch{if($_.Exception.Message -ne 'Cooperative cohort acceptance differs'){throw};$rejected=$true}
if(-not $rejected){throw 'Production hash guard accepted altered proof bytes'}
$io+=@{name='v2-altered-proof-bytes';passed=$false}
if($Sparse){
 $q=$raw[3]|ConvertFrom-Json;$q.contract.parent_acceptance_path=$TamperedParent;$rejected=$false
 try{$null=Game-LoadPollParent $q}catch{if($_.Exception.Message -ne 'v3 parent proof file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual parent proof IO subguard accepted altered bytes'};$io+=@{name='v3-altered-parent-proof-source-subguard';passed=$false}
 $q=$raw[3]|ConvertFrom-Json;$q.contract.parent_input_plan_path=$TamperedParentPlan;$rejected=$false
 try{$null=Game-LoadPollParent $q}catch{if($_.Exception.Message -ne 'v3 parent plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual parent plan IO subguard accepted altered bytes'};$io+=@{name='v3-altered-parent-plan-source-subguard';passed=$false}
 # Execute the actual final plan hash block independently, after the separate
 # complete v3 positive. No hash stub and no production file is changed.
 $planBegin=$text.IndexOf(' if(($taskPollVersion -eq 2 -or $taskPollVersion -eq 3 -or $taskPollVersion -eq 4 -or $taskPollVersion -eq 5 -or $taskPollVersion -eq 6 -or $taskPollVersion -eq 7 -or $taskPollVersion -eq 8 -or $taskPollVersion -eq 9) -and');$planEnd=$text.IndexOf("`n}",$planBegin)
 if($planBegin -lt 0 -or $planEnd -le $planBegin){throw 'Actual production plan subguard missing'}
 $planGuard=[ScriptBlock]::Create($text.Substring($planBegin,$planEnd-$planBegin));$taskPollVersion=3;$taskPollProof=$raw[3]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV3Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual new plan IO subguard accepted altered bytes'};$io+=@{name='v3-altered-new-plan-source-subguard';passed=$false}
}
if($Additive){
 $q=$raw[4]|ConvertFrom-Json;$parent=Game-LoadPollParent $q;$grandparent=Game-LoadPollParent $parent
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$Additive;acceptance_sha256=$hashes[4]}) $q.objects $parent $grandparent) -ne 4){throw 'Actual v4 ancestry positive failed'}
 $io+=@{name='v4-two-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV4Parent;message='v4 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV4ParentPlan;message='v4 parent plan file differs'})){
  $q=$raw[4]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollParent $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v4 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v4-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=4;$taskPollProof=$raw[4]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV4Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v4 new plan IO subguard accepted altered bytes'};$io+=@{name='v4-altered-new-plan-source-subguard';passed=$false}
}
if($Fcsel){
 $q=$raw[5]|ConvertFrom-Json;$parent=Game-LoadPollParent $q;$grandparent=Game-LoadPollParent $parent;$great=Game-LoadPollParent $grandparent
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$Fcsel;acceptance_sha256=$hashes[5]}) $q.objects $parent $grandparent $great) -ne 5){throw 'Actual v5 ancestry positive failed'}
 $io+=@{name='v5-three-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV5Parent;message='v5 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV5ParentPlan;message='v5 parent plan file differs'})){
  $q=$raw[5]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollParent $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v5 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v5-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=5;$taskPollProof=$raw[5]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV5Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v5 new plan IO subguard accepted altered bytes'};$io+=@{name='v5-altered-new-plan-source-subguard';passed=$false}
}
if($FcselCallers){
 $q=$raw[6]|ConvertFrom-Json;$ancestors=Game-LoadPollAncestors $q
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$FcselCallers;acceptance_sha256=$hashes[6]}) $q.objects $null $null $null $ancestors) -ne 6){throw 'Actual v6 ancestry positive failed'}
 $io+=@{name='v6-four-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV6Parent;message='v6 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV6ParentPlan;message='v6 parent plan file differs'})){
  $q=$raw[6]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollAncestors $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v6 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v6-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=6;$taskPollProof=$raw[6]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV6Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v6 new plan IO subguard accepted altered bytes'};$io+=@{name='v6-altered-new-plan-source-subguard';passed=$false}
}
if($St2){
 $q=$raw[7]|ConvertFrom-Json;$ancestors=Game-LoadPollAncestors $q
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$St2;acceptance_sha256=$hashes[7]}) $q.objects $null $null $null $ancestors) -ne 7){throw 'Actual v7 ancestry positive failed'}
 $io+=@{name='v7-five-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV7Parent;message='v7 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV7ParentPlan;message='v7 parent plan file differs'})){
  $q=$raw[7]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollAncestors $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v7 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v7-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=7;$taskPollProof=$raw[7]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV7Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v7 new plan IO subguard accepted altered bytes'};$io+=@{name='v7-altered-new-plan-source-subguard';passed=$false}
}
if($FcselBatch){
 $q=$raw[8]|ConvertFrom-Json;$ancestors=Game-LoadPollAncestors $q
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$FcselBatch;acceptance_sha256=$hashes[8]}) $q.objects $null $null $null $ancestors) -ne 8){throw 'Actual v8 ancestry positive failed'}
 $io+=@{name='v8-six-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV8Parent;message='v8 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV8ParentPlan;message='v8 parent plan file differs'})){
  $q=$raw[8]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollAncestors $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v8 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v8-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=8;$taskPollProof=$raw[8]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV8Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v8 new plan IO subguard accepted altered bytes'};$io+=@{name='v8-altered-new-plan-source-subguard';passed=$false}
}
if($St2Constructor){
 $q=$raw[9]|ConvertFrom-Json;$ancestors=Game-LoadPollAncestors $q
 if((Game-ValidatePollContract $q ([pscustomobject]@{acceptance_path=$St2Constructor;acceptance_sha256=$hashes[9]}) $q.objects $null $null $null $ancestors) -ne 9){throw 'Actual v9 ancestry positive failed'}
 $io+=@{name='v9-seven-ancestor-load-source-subguard';passed=$true}
 foreach($entry in @(@{key='parent_acceptance_path';file=$TamperedV9Parent;message='v9 parent proof file differs'},@{key='parent_input_plan_path';file=$TamperedV9ParentPlan;message='v9 parent plan file differs'})){
  $q=$raw[9]|ConvertFrom-Json;$q.contract.($entry.key)=$entry.file;$rejected=$false
  try{$null=Game-LoadPollAncestors $q}catch{if($_.Exception.Message -ne $entry.message){throw};$rejected=$true}
  if(-not $rejected){throw 'Actual v9 ancestor hash subguard accepted altered bytes'};$io+=@{name=('v9-altered-'+$entry.key+'-source-subguard');passed=$false}
 }
 $taskPollVersion=9;$taskPollProof=$raw[9]|ConvertFrom-Json;$taskPollProof.contract.input_plan_path=$TamperedV9Plan;$rejected=$false
 try{& $planGuard}catch{if($_.Exception.Message -ne 'Sparse cooperative plan file differs'){throw};$rejected=$true}
 if(-not $rejected){throw 'Actual v9 new plan IO subguard accepted altered bytes'};$io+=@{name='v9-altered-new-plan-source-subguard';passed=$false}
}
[IO.File]::WriteAllText(($Output+'.io.json'),($io|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
Write-Output "POWERSHELL-COHORT-GUARD-PASS $($results.Count)"
'''
 (out/'exercise.ps1').write_text(driver)
 command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',windows(out/'exercise.ps1'),'-Source',windows(powershell),'-Original',windows(v1),'-Derived',windows(v2),'-Cases',windows(out/'cases.json'),'-Tampered',windows(tampered),'-Output',windows(out/'powershell-results.json')]
 if a.sparse_proof:command+=['-Sparse',windows(v3),'-TamperedParent',windows(tampered_parent),'-TamperedParentPlan',windows(tampered_parent_plan),'-TamperedV3Plan',windows(tampered_v3_plan)]
 if a.additive_proof:command+=['-Additive',windows(v4),'-TamperedV4Parent',windows(tampered_v4_parent),'-TamperedV4ParentPlan',windows(tampered_v4_parent_plan),'-TamperedV4Plan',windows(tampered_v4_plan)]
 if a.fcsel_proof:command+=['-Fcsel',windows(v5),'-TamperedV5Parent',windows(tampered_v5_parent),'-TamperedV5ParentPlan',windows(tampered_v5_parent_plan),'-TamperedV5Plan',windows(tampered_v5_plan)]
 if a.fcsel_callers_proof:command+=['-FcselCallers',windows(v6),'-TamperedV6Parent',windows(tampered_v6_parent),'-TamperedV6ParentPlan',windows(tampered_v6_parent_plan),'-TamperedV6Plan',windows(tampered_v6_plan)]
 if a.st2_proof:command+=['-St2',windows(v7),'-TamperedV7Parent',windows(tampered_v7_parent),'-TamperedV7ParentPlan',windows(tampered_v7_parent_plan),'-TamperedV7Plan',windows(tampered_v7_plan)]
 if a.fcsel_batch_proof:command+=['-FcselBatch',windows(v8),'-TamperedV8Parent',windows(tampered_v8_parent),'-TamperedV8ParentPlan',windows(tampered_v8_parent_plan),'-TamperedV8Plan',windows(tampered_v8_plan)]
 if a.st2_constructor_proof:command+=['-St2Constructor',windows(v9),'-TamperedV9Parent',windows(tampered_v9_parent),'-TamperedV9ParentPlan',windows(tampered_v9_parent_plan),'-TamperedV9Plan',windows(tampered_v9_plan)]
 with(out/'powershell.log').open('w')as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
 ps_results=json.loads((out/'powershell-results.json').read_text());assert len(ps_results)==len(results)
 assert {x['name']:x['passed']for x in ps_results}=={x['name']:x['passed']for x in results}
 # Verify guard placement remains before compiler and runner process/storage actions.
 ps_text=powershell.read_text();py_text=python.read_text()
 assert ps_text.index('$taskPollVersion=Game-ValidatePollContract')<ps_text.index('& $Cxx @taskCommon')
 assert ps_text.index('Cooperative cohort acceptance differs')<ps_text.index('$taskPollVersion=Game-ValidatePollContract')
 assert ps_text.index("throw 'Sparse cooperative plan file differs'")<ps_text.index('& $Cxx @taskCommon')
 assert py_text.index('version=validate_cooperative_contract')<py_text.index('if a.verify_only:')<py_text.index('storage.mkdir()')<py_text.index('run=subprocess.run(command')
 # Actual proof/derived-plan bytes, not a synthetic positive descriptor.
 plan=Path(base[2]['contract']['input_plan_path']);assert sha(plan)==base[2]['contract']['input_plan_sha256']
 assert sha(v1)==descriptors[1]['acceptance_sha256'] and sha(v2)==descriptors[2]['acceptance_sha256']
 tampered_plan=out/'tampered-plan.json';tampered_plan.write_bytes(plan.read_bytes()+b'\n');assert sha(tampered_plan)!=base[2]['contract']['input_plan_sha256']
 assert all(sha(p)==h for p,h in sources.items())
 assert all(sha(p)==h for p,h in initial_input_pins.items())
 evidence={str(x):sha(x)for x in out.iterdir()if x.is_file()}
 receipt=dict(passed=True,scope='actual extracted Python/PowerShell validator predicates and static guard placement only; no compiler/native game/guest execution',cases_per_language=len(cases),positive_cases=sum(c['passed']for c in cases),negative_cases=sum(not c['passed']for c in cases),owned_sources=sources,input_pins=initial_input_pins,v3_actual_proof_executed=bool(a.sparse_proof),actual_parent_and_new_plan_source_IO_subguards=bool(a.sparse_proof),v3_placeholder_rejection_only=not bool(a.sparse_proof),v4_actual_proof_executed=bool(a.additive_proof),v4_placeholder_rejection_only=not bool(a.additive_proof),v5_actual_proof_executed=bool(a.fcsel_proof),v5_placeholder_rejection_only=not bool(a.fcsel_proof),v6_actual_proof_executed=bool(a.fcsel_callers_proof),v6_placeholder_rejection_only=not bool(a.fcsel_callers_proof),commands=[command],evidence=evidence)
 receipt.update(v7_actual_proof_executed=bool(a.st2_proof),v7_placeholder_rejection_only=not bool(a.st2_proof),v8_actual_proof_executed=bool(a.fcsel_batch_proof),v8_placeholder_rejection_only=not bool(a.fcsel_batch_proof),v9_actual_proof_executed=bool(a.st2_constructor_proof),v9_placeholder_rejection_only=not bool(a.st2_constructor_proof))
 (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('COHORT-VALIDATOR-PASS',len(cases),sha(out/'acceptance.json'),flush=True)

if __name__=='__main__':main()
