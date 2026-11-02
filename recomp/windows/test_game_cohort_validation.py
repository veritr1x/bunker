"""Exercise actual Python/PowerShell cohort guards only; never compile/run a game."""
from pathlib import Path
import argparse,ast,copy,hashlib,json,subprocess

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--derived-proof',type=Path,required=True);a=p.parse_args()
 here=Path(__file__).resolve().parent;out=a.out.resolve();out.mkdir(exist_ok=False)
 python=here/'test_game_bootstrap.py';powershell=here/'game_bootstrap_build.ps1'
 w=here.parent/'work';v1=w/'game17-polled-cohort1/acceptance.json';v2=a.derived_proof.resolve()
 sources={str(x):sha(x)for x in(python,powershell,Path(__file__))}
 tree=ast.parse(python.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_cooperative_contract')
 env={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(python),'exec'),env);validate=env[fn.name]
 base={1:json.loads(v1.read_text()),2:json.loads(v2.read_text())};descriptors={1:dict(acceptance_path=str(v1),acceptance_sha256=sha(v1)),2:dict(acceptance_path=str(v2),acceptance_sha256=sha(v2))}
 assert base[2]['contract']['version']==2
 cases=[]
 def case(name,version,passed=False,*ops):cases.append(dict(name=name,version=version,passed=passed,ops=list(ops)))
 def change(root,path,value):return dict(root=root,path=path,value=value)
 zero='0'*64
 case('v1-original',1,True);case('v1-explicit-version',1,True,change('proof',['contract','version'],1));case('v2-qualified-sparse',2,True)
 for version in(1,2):
  prefix=f'v{version}-'
  for name,path,value in [('heads',['trace_heads'],456683),('unique',['unique_definitions'],False),('missing',['missing_direct_targets'],[0x825a60c4]),('instrument',['contract','poll_instrument_sha256'],zero),('array-instrument',['contract','poll_instrument_sha256'],[]),('target',['contract','target'],'x86_64-linux-gnu'),('version',['contract','version'],3),('boolean-version',['contract','version'],True),('null-version',['contract','version'],None)]:case(prefix+name,version,False,change('proof',path,value))
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
 results=[]
 for c in cases:
  data={'proof':copy.deepcopy(base[c['version']]),'descriptor':dict(descriptors[c['version']]),'objects':copy.deepcopy(base[c['version']]['objects'])}
  for op in c['ops']:
   target=data[op['root']]
   for key in op['path'][:-1]:target=target[key]
   if 'swap'in op:
    i,j=op['swap'];target[i],target[j]=target[j],target[i]
   elif op.get('pop'):target.pop()
   else:target[op['path'][-1]]=op['value']
  try:version=validate(data['proof'],data['descriptor'],data['objects']);passed=True
  except(AssertionError,KeyError,TypeError,IndexError):passed=False;version=None
  assert passed==c['passed'],(c['name'],passed)
  results.append(dict(name=c['name'],passed=passed,version=version))
 (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');(out/'python-results.json').write_text(json.dumps(results,indent=2)+'\n')
 tampered=out/'tampered-proof.json';tampered.write_bytes(v2.read_bytes()+b'\n');assert sha(tampered)!=descriptors[2]['acceptance_sha256']
 def windows(path):return subprocess.check_output(['wslpath','-w',str(Path(path).resolve())],text=True).strip()
 # PowerShell's own AST extracts the exact production function; no duplicate predicate.
 driver=r'''param([string]$Source,[string]$Original,[string]$Derived,[string]$Cases,[string]$Tampered,[string]$Output)
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
$results=@()
foreach($case in (Get-Content -Raw -LiteralPath $Cases|ConvertFrom-Json)){
 $v=[int]$case.version;$data=@{proof=($raw[$v]|ConvertFrom-Json);descriptor=[pscustomobject]@{acceptance_path=$paths[$v];acceptance_sha256=$hashes[$v]};objects=($raw[$v]|ConvertFrom-Json).objects}
 foreach($op in $case.ops){
  $target=$data[$op.root]
  for($i=0;$i -lt $op.path.Count-1;$i++){$k=$op.path[$i];if($k -is [long] -or $k -is [int]){$target=$target[[int]$k]}else{$target=$target.$k}}
  if($null -ne $op.swap){$i=[int]$op.swap[0];$j=[int]$op.swap[1];$saved=$target[$i];$target[$i]=$target[$j];$target[$j]=$saved}
  elseif($op.pop){$data[$op.root]=@($target[0..($target.Count-2)])}
  else{$k=$op.path[-1];if($k -is [long] -or $k -is [int]){$target[[int]$k]=$op.value}else{$target|Add-Member -Force -NotePropertyName $k -NotePropertyValue $op.value}}
 }
 $ok=$false;$message='';$version=$null
 try{$version=Game-ValidatePollContract $data.proof $data.descriptor $data.objects;$ok=$true}catch{$message=$_.Exception.Message}
 if($ok -ne $case.passed){throw "Unexpected production guard result: $($case.name) success=$ok message=$message"}
 $results+=@{name=$case.name;passed=$ok;version=$version;message=$message}
}
[IO.File]::WriteAllText($Output,($results|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
# Run the actual complete acceptance-loading/hash/contract/plan guard as well.
foreach($name in @('Game-Path','Game-Hash')){$fn=$ast.FindAll({param($n)$n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true);if($fn.Count -ne 1){throw 'Production IO function missing'};. ([ScriptBlock]::Create($fn[0].Extent.Text))}
$text=Get-Content -Raw -LiteralPath $Source;$begin=$text.IndexOf('$taskPollCohort=$taskInput.cooperative_poll_cohort');$end=$text.IndexOf("if((Game-Hash (Join-Path `$taskBuild 'libz-inflate.a'))")
if($begin -lt 0 -or $end -le $begin){throw 'Actual production cohort guard boundaries missing'}
$guard=[ScriptBlock]::Create($text.Substring($begin,$end-$begin));$io=@();$EnableCollectorDelivery=$true
foreach($v in @(1,2)){
 $taskInput=[pscustomobject]@{objects=($raw[$v]|ConvertFrom-Json).objects;cooperative_poll_cohort=[pscustomobject]@{acceptance_path=$paths[$v];acceptance_sha256=$hashes[$v]}}
 & $guard
 $io+=@{name="v$v-complete-production-guard";passed=$true}
}
$taskInput=[pscustomobject]@{objects=($raw[2]|ConvertFrom-Json).objects;cooperative_poll_cohort=[pscustomobject]@{acceptance_path=$Tampered;acceptance_sha256=$hashes[2]}}
$rejected=$false;try{& $guard}catch{if($_.Exception.Message -ne 'Cooperative cohort acceptance differs'){throw};$rejected=$true}
if(-not $rejected){throw 'Production hash guard accepted altered proof bytes'}
$io+=@{name='v2-altered-proof-bytes';passed=$false}
[IO.File]::WriteAllText(($Output+'.io.json'),($io|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
Write-Output "POWERSHELL-COHORT-GUARD-PASS $($results.Count)"
'''
 (out/'exercise.ps1').write_text(driver)
 command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',windows(out/'exercise.ps1'),'-Source',windows(powershell),'-Original',windows(v1),'-Derived',windows(v2),'-Cases',windows(out/'cases.json'),'-Tampered',windows(tampered),'-Output',windows(out/'powershell-results.json')]
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
 evidence={str(x):sha(x)for x in out.iterdir()if x.is_file()}
 receipt=dict(passed=True,scope='actual extracted Python/PowerShell validator predicates and static guard placement only; no compiler/native game/guest execution',cases_per_language=len(cases),positive_cases=sum(c['passed']for c in cases),negative_cases=sum(not c['passed']for c in cases),owned_sources=sources,input_pins={str(x):sha(x)for x in(v1,v2,plan)},commands=[command],evidence=evidence)
 (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('COHORT-VALIDATOR-PASS',len(cases),sha(out/'acceptance.json'),flush=True)

if __name__=='__main__':main()
