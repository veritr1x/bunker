"""Exercise the actual v16 Python/PowerShell guards; never build or run a game.

One parsed base and reversible compact mutations avoid reparsing the complete
fourteen-generation ancestry for each case. Historical negative cases are
retained as evidence and covered by an exact old-source inverse, not replayed.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

MISSING = object()


def sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2)+'\n')


def windows(path):
    return subprocess.check_output(['wslpath', '-w', str(Path(path).resolve())], text=True).strip()


def source_inverse(proof, sources, parent, historical):
    assert proof['passed'] is True
    assert proof['base_commit'] == 'a15fc1c16752eb4e6549c8db12bb2fe49af216e1'
    assert proof['old_v1_through_v15_branch_bodies_byte_exact'] is True
    assert proof['historical_driver_sha256'] == sha(historical)
    expected = {'windows/test_game_bootstrap.py', 'windows/game_bootstrap_build.ps1'}
    assert set(proof['files']) == expected
    result = {}
    for name, row in proof['files'].items():
        data = sources[name].read_bytes()
        assert row['exact_whole_file_inverse'] is True and sha(sources[name]) == row['new_sha256']
        assert row['old_sha256'] == parent['source_sha256']['recomp/'+name]
        for op in sorted(row['operations'], key=lambda x:x['new_offset'], reverse=True):
            pos = op['new_offset']; old = bytes.fromhex(op['old_hex']); new = bytes.fromhex(op['new_hex'])
            assert type(pos) is int and pos >= 0 and data[pos:pos+len(new)] == new
            data = data[:pos]+old+data[pos+len(new):]
        assert hashlib.sha256(data).hexdigest() == row['old_sha256']
        result[name] = dict(old_sha256=row['old_sha256'], new_sha256=row['new_sha256'],
                            exact_whole_file_inverse=True)
    return result


def make_cases(base):
    cases = []
    def op(root, path, value):
        return dict(root=root, path=path, value=value)
    def case(name, *ops, version=16, passed=False):
        cases.append(dict(name=name, version=version, passed=passed, ops=list(ops)))
    def field(name, value):
        return op('proof', ['contract', name], value)
    zero = '0'*64
    case('v16-actual-qualified-cohort', passed=True)
    for version in range(1,16):
        case(f'v{version}-actual-historical-positive', version=version, passed=True)
        case(f'v{version}-cannot-claim-v16', field('version',16), version=version)
    contract = base[16]['contract']
    for name in ('input_plan_sha256','parent_acceptance_sha256','parent_input_plan_sha256',
                 'parent_inputs_sha256','additive_candidate_sha256',
                 'original_unwind_fixture_acceptance_sha256','independent_candidate_fixture_peer_sha256',
                 'original_indirect_audit_sha256','lifter_sha256','semantics_sha256',
                 'poll_instrument_sha256','new_polled_object_sha256',
                 'metadata_count_header_sha256','metadata_count_projection_sha256'):
        assert re.fullmatch('[0-9a-f]{64}', contract[name])
        for label, wrong in (('wrong',zero),('array',[]),('uppercase',contract[name].upper())):
            case(f'v16-pin-{name}-{label}', field(name,wrong))
    for name in ('added_object_index','added_objects','preserved_objects','added_trace_count',
                 'parent_trace_heads','parent_unsupported_count','actual_unsupported_total',
                 'inherited_vector_replacements','parent_module_unsupported_count',
                 'actual_module_unsupported_count'):
        expected = contract[name]; assert type(expected) is int
        for label, wrong in (('wrong',expected+1),('boolean',True),('string',str(expected)),('null',None)):
            case(f'v16-count-{name}-{label}', field(name,wrong))
    for name in ('existing_objects_preserved','no_global_semantics_refresh','no_relift',
                 'source_ir_and_semantics_preserved','production_signal_delivery_enabled'):
        expected = contract[name]; assert type(expected) is bool
        case('v16-policy-'+name, field(name,not expected))
        case('v16-policy-type-'+name, field(name,int(expected)))
    for name, wrong in (('profile','unqualified'),('target','x86_64-linux-gnu'),('optimization','-O0'),
                        ('version',15),('version',True),('version','16'),('version',None),
                        ('input_plan_path',None),('parent_acceptance_path',''),('parent_input_plan_path',[])):
        case('v16-provenance-'+name+'-'+repr(wrong), field(name,wrong))
    for wrong in (zero, [], None):
        case('v16-descriptor-'+repr(wrong),op('descriptor',['acceptance_sha256'],wrong))
    heads = contract['added_trace_heads']; assert len(heads) == 27
    for label, wrong in (('reverse',heads[::-1]),('short',heads[:-1]),('duplicate',heads+[heads[-1]]),
                        ('integer',[int(x,0)for x in heads]),('wrong',heads[:-1]+['0x82625f88']),('null',None)):
        case('v16-heads-'+label, field('added_trace_heads',wrong))
    for name in ('inherited_error_instruction_PCs','inherited_error_advanced_PCs'):
        current = contract[name]; assert len(current) == 2
        for label, wrong in (('reverse',current[::-1]),('short',current[:1]),('numeric',[int(x,0)for x in current]),
                            ('new',current[:1]+['0x82625d80'])):
            case('v16-error-sites-'+name+'-'+label,field(name,wrong))
    case('v16-error-instruction-bytes',field('inherited_error_instruction_bytes','80108079'))
    case('v16-error-bytes-type',field('inherited_error_instruction_bytes',[]))
    for name in ('added_unsupported_heads',):
        current = contract[name]; assert len(current) == 22
        for label, wrong in (('empty',[]),('short',current[:-1]),('reverse',current[::-1]),
                            ('duplicate',current+[current[-1]]),('wrong',current[:-1]+[0x82625f08])):
            case('v16-contract-'+name+'-'+label,field(name,wrong))
    for name in ('unsupported_heads','added_unsupported_heads'):
        current = base[16][name]
        for label, wrong in (('short',current[:-1]),('reverse',current[::-1]),('empty',[])):
            case('v16-proof-'+name+'-'+label,op('proof',[name],wrong))
    case('v16-proof-unsupported-same-valued-float',
         op('proof',['unsupported_heads',0],float(base[16]['unsupported_heads'][0])))
    for wrong in (1453,1432,True,'1454'):
        case('v16-proof-unsupported-total-'+repr(wrong),op('proof',['actual_unsupported_total'],wrong))
    for name, wrong in (('trace_heads',456706),('trace_heads',True),('trace_heads','456733'),
                        ('unique_definitions',False),('unique_definitions',1),
                        ('missing_direct_targets',[0x82625f08])):
        case('v16-shape-'+name+'-'+repr(wrong),op('proof',[name],wrong))
    case('v16-shape-trace-heads-same-valued-float',op('proof',['trace_heads'],456733.0))
    for index in (0,129,1572,3577,3578):
        case(f'v16-object-{index}-hash-both-tables',op('proof',['objects',index,'sha256'],zero),
             op('objects',[index,'sha256'],zero))
    for wrong in ('',None,[]):
        case('v16-new-object-path-'+repr(wrong),op('proof',['objects',3578,'path'],wrong),
             op('objects',[3578,'path'],wrong))
    for root, path in (('objects',[]),('proof',['objects'])):
        case('v16-object-list-short-'+root,dict(root=root,path=path,action='drop_last'))
    case('v16-order-both-tables',dict(root='objects',path=[],action='swap',indices=[3577,3578]),
         dict(root='proof',path=['objects'],action='swap',indices=[3577,3578]))
    case('v16-self-consistent-history-rewrite',op('proof',['objects',1572,'sha256'],zero),
         op('objects',[1572,'sha256'],zero),op('ancestors',[0,'objects',1572,'sha256'],zero))
    case('v16-ancestry-absent',op('ancestors',[],None))
    case('v16-ancestry-short',dict(root='ancestors',path=[],action='drop_last'))
    case('v16-ancestry-order',dict(root='ancestors',path=[],action='swap',indices=[0,1]))
    for depth in range(14):
        case('v16-ancestor-missing-'+str(depth),op('ancestors',[depth],None))
        case('v16-ancestor-version-'+str(depth),op('ancestors',[depth,'contract','version'],1))
    assert len({c['name']for c in cases}) == len(cases)
    return cases


def mutate(data, operations):
    undo = []
    for op in operations:
        owner = data; key = op['root']
        for item in op['path']:
            owner = owner[key]; key = item
        old = owner.get(key,MISSING) if isinstance(owner,dict) else owner[key]
        undo.append((owner,key,old))
        if op.get('action') == 'swap':
            value = list(old); i,j = op['indices']; value[i],value[j] = value[j],value[i]
        elif op.get('action') == 'drop_last':
            value = old[:-1]
        else:
            value = copy.deepcopy(op['value'])
        owner[key] = value
    return undo


PS_DRIVER = r'''param([string]$Source,[string]$Payload,[string]$Output)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
$tokens=$null;$parseErrors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Production PowerShell parse failed'}
foreach($name in @('Game-ValidatePollContract','Game-Path','Game-Hash','Game-LoadPollParent','Game-LoadPollAncestors')){
 $nodes=$ast.FindAll({param($n)$n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 if($nodes.Count -ne 1){throw "Production function missing/duplicated: $name"}
 . ([ScriptBlock]::Create($nodes[0].Extent.Text))
}
$payloadData=Get-Content -Raw -LiteralPath $Payload|ConvertFrom-Json
$base=@{};$descriptors=@{};$objects=@{}
foreach($entry in $payloadData.proofs){
 $v=[int]$entry.version;$raw=Get-Content -Raw -LiteralPath (Game-Path $entry.path)
 if((Game-Hash (Game-Path $entry.path)) -cne $entry.sha256){throw 'Proof input changed'}
 $base[$v]=$raw|ConvertFrom-Json;$objects[$v]=($raw|ConvertFrom-Json).objects
 $descriptors[$v]=[pscustomobject]@{acceptance_path=$entry.path;acceptance_sha256=$entry.sha256}
}
$results=@()
foreach($case in $payloadData.cases){
 $v=[int]$case.version;$chain=$null
 if($v -ge 6){$chain=@();for($depth=$v-1;$depth -ge 2;$depth--){$chain+=,$base[$depth]}}
 $data=@{proof=$base[$v];objects=$objects[$v];descriptor=$descriptors[$v];ancestors=$chain}
 $undo=[Collections.Generic.List[object]]::new()
 foreach($op in $case.ops){
  $owner=$data;$key=$op.root
  foreach($item in $op.path){if($key -is [int] -or $key -is [long]){$owner=$owner[[int]$key]}else{$owner=$owner.$key};$key=$item}
  $exists=$true
  if($key -is [int] -or $key -is [long]){$old=$owner[[int]$key]}
  elseif($owner -is [Collections.IDictionary]){$exists=$owner.Contains($key);$old=$owner[$key]}
  else{$exists=$owner.PSObject.Properties.Name -contains $key;$old=$owner.$key}
  $undo.Add(@{owner=$owner;key=$key;value=$old;exists=$exists})
  if($op.action -eq 'swap'){$replacement=@($old);$i=[int]$op.indices[0];$j=[int]$op.indices[1];$saved=$replacement[$i];$replacement[$i]=$replacement[$j];$replacement[$j]=$saved}
  elseif($op.action -eq 'drop_last'){$replacement=@($old[0..($old.Count-2)])}
  else{$replacement=$op.value}
  if($key -is [int] -or $key -is [long]){$owner[[int]$key]=$replacement}
  elseif($owner -is [Collections.IDictionary]){$owner[$key]=$replacement}
  else{$owner|Add-Member -Force -NotePropertyName $key -NotePropertyValue $replacement}
 }
 $ok=$false;$version=$null;$message=''
 try{
  $parent=$null;$grand=$null;$great=$null
  if($v -in @(3,4,5)){$parent=$base[$v-1]};if($v -in @(4,5)){$grand=$base[$v-2]};if($v -eq 5){$great=$base[2]}
  $version=Game-ValidatePollContract $data.proof $data.descriptor $data.objects $parent $grand $great $data.ancestors;$ok=$true
 }catch{$message=$_.Exception.Message}
 for($i=$undo.Count-1;$i -ge 0;$i--){
  $item=$undo[$i]
  if($item.key -is [int] -or $item.key -is [long]){$item.owner[[int]$item.key]=$item.value}
  elseif($item.owner -is [Collections.IDictionary]){if($item.exists){$item.owner[$item.key]=$item.value}else{$item.owner.Remove($item.key)}}
  elseif($item.exists){$item.owner|Add-Member -Force -NotePropertyName $item.key -NotePropertyValue $item.value}
  else{$item.owner.PSObject.Properties.Remove($item.key)}
 }
 if($ok -ne $case.passed){throw "Unexpected guard result: $($case.name), success=$ok, message=$message"}
 $results+=@{name=$case.name;passed=$ok;version=$version}
}
$proof=$base[16];$io=@();$EnableCollectorDelivery=$true
$text=Get-Content -Raw -LiteralPath $Source
$begin=$text.IndexOf('$taskPollCohort=$taskInput.cooperative_poll_cohort')
$end=$text.IndexOf("if((Game-Hash (Join-Path `$taskBuild 'libz-inflate.a'))")
if($begin -lt 0 -or $end -le $begin){throw 'Production cohort IO guard boundaries absent'}
$guard=[ScriptBlock]::Create($text.Substring($begin,$end-$begin))
$taskInput=[pscustomobject]@{union_trace_count=$proof.trace_heads;objects=$proof.objects;cooperative_poll_cohort=$descriptors[16]}
& $guard
$io+=@{name='v16-complete-production-IO-guard';passed=$true}
foreach($case in $payloadData.io_cases){
 $ok=$false;$message=''
 try{
  if($case.kind -eq 'parent'){
   $q=Get-Content -Raw -LiteralPath (Game-Path $descriptors[16].acceptance_path)|ConvertFrom-Json
   $q.contract.($case.field)=$case.path;$null=Game-LoadPollAncestors $q
  }elseif($case.kind -eq 'plan'){
   $taskPollVersion=16;$taskPollProof=Get-Content -Raw -LiteralPath (Game-Path $descriptors[16].acceptance_path)|ConvertFrom-Json
   $taskPollProof.contract.input_plan_path=$case.path
   $planNodes=$ast.FindAll({param($n)$n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.Contains("throw 'Sparse cooperative plan file differs'")},$true)
   $planNode=$planNodes|Sort-Object {$_.Extent.Text.Length}|Select-Object -First 1
   if($null -eq $planNode){throw 'Production plan IO guard absent'}
   & ([ScriptBlock]::Create($planNode.Extent.Text))
  }else{
   $taskInput.cooperative_poll_cohort=[pscustomobject]@{acceptance_path=$case.path;acceptance_sha256=$descriptors[16].acceptance_sha256}
   & $guard
  };$ok=$true
 }catch{$message=$_.Exception.Message}
 if($ok -or $message -cne $case.message){throw "IO guard mismatch: $($case.name): $message"}
 $io+=@{name=$case.name;passed=$false}
}
[IO.File]::WriteAllText($Output,(@{cases=$results;io=$io}|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('out','derived-proof','guard-source-proof','historical-acceptance'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--derived-proof-sha256', required=True)
    ap.add_argument('--guard-source-proof-sha256', required=True)
    args = ap.parse_args(); out = args.out.resolve(); out.mkdir(exist_ok=False)
    here = Path(__file__).resolve().parent; work = here.parent/'work'
    python = here/'test_game_bootstrap.py'; powershell = here/'game_bootstrap_build.ps1'
    historical = here/'test_game_cohort_validation.py'
    sources = {'windows/'+p.name:p for p in (python,powershell)}
    source_pins = {str(p):sha(p)for p in (python,powershell,historical,Path(__file__))}
    proofpath = args.derived_proof.resolve(); guardpath = args.guard_source_proof.resolve()
    assert sha(proofpath) == args.derived_proof_sha256 and sha(guardpath) == args.guard_source_proof_sha256
    proof = json.loads(proofpath.read_text()); assert proof['passed'] is True and proof['contract']['version'] == 16
    parent_manifest = work/'windows-first-frame-phdr1/game_inputs.json'
    inverse = source_inverse(json.loads(guardpath.read_text()),sources,json.loads(parent_manifest.read_text()),historical)
    history = json.loads(args.historical_acceptance.read_text()); assert history['passed'] is True
    history_cases = next(Path(p)for p in history['evidence'] if Path(p).name == 'cases.json')
    assert sha(history_cases) == history['evidence'][str(history_cases)]
    historical_payload = json.loads(history_cases.read_text())
    assert len(historical_payload) == history['generated_cases_per_language']
    for name, row in inverse.items():
        oldhash = next(v for p,v in history['owned_sources'].items()if Path(p).name == Path(name).name)
        assert oldhash == row['old_sha256']
    tree = ast.parse(python.read_text()); names = {'sha','load_cooperative_parent','load_cooperative_ancestors','validate_cooperative_contract'}
    functions = [n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in names]
    assert {n.name for n in functions} == names
    env = dict(re=re,hashlib=hashlib,json=json,pathlib=__import__('pathlib'))
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(python),'exec'),env)
    base = {16:proof}; paths = {16:proofpath}; current = proof
    for version in range(15,1,-1):
        path = Path(current['contract']['parent_acceptance_path']); assert sha(path) == current['contract']['parent_acceptance_sha256']
        current = json.loads(path.read_text()); assert current['contract']['version'] == version
        base[version] = current; paths[version] = path
    paths[1] = work/'game17-polled-cohort1/acceptance.json'; base[1] = json.loads(paths[1].read_text())
    descriptors = {v:dict(acceptance_path=str(p),acceptance_sha256=sha(p))for v,p in paths.items()}
    pins = {str(p):sha(p)for p in list(paths.values())+[guardpath,args.historical_acceptance,history_cases,parent_manifest]}
    for v,q in base.items():
        if v >= 2:
            plan = Path(q['contract']['input_plan_path']); assert sha(plan) == q['contract']['input_plan_sha256']; pins[str(plan)] = sha(plan)
    cases = make_cases(base); save(out/'cases.json',cases)
    data = {v:dict(proof=q,objects=copy.deepcopy(q['objects']),descriptor=descriptors[v],
                  ancestors=[base[x]for x in range(v-1,1,-1)]if v>=6 else None)for v,q in base.items()}
    results = []
    for case in cases:
        v = case['version']; d = data[v]; undo = mutate(d,case['ops']); error = None
        try:
            version = env['validate_cooperative_contract'](d['proof'],d['descriptor'],d['objects'],
                base[v-1]if v in(3,4,5)else None,base[v-2]if v in(4,5)else None,base[2]if v==5 else None,d['ancestors'])
            ok = True
        except (AssertionError,KeyError,TypeError,IndexError,AttributeError) as caught:
            error = repr(caught); ok = False; version = None
        finally:
            for owner,key,old in reversed(undo):
                if old is MISSING:
                    del owner[key]
                else:
                    owner[key] = old
        assert ok == case['passed'],(case['name'],ok,error)
        results.append(dict(name=case['name'],passed=ok,version=version))
    save(out/'python-results.json',results)
    io = []; contract = proof['contract']; io_cases = []
    for field, kind, message in (('parent_acceptance_path','parent','v16 parent proof file differs'),
                                 ('parent_input_plan_path','parent','v16 parent plan file differs'),
                                 ('input_plan_path','plan','sparse cooperative plan file differs')):
        original = Path(contract[field]); altered = out/('tampered-'+field+'.json'); altered.write_bytes(original.read_bytes()+b'\n')
        q = copy.deepcopy(proof); q['contract'][field] = str(altered)
        try:
            if kind == 'parent':
                env['load_cooperative_ancestors'](q)
            else:
                nodes = [n for n in ast.walk(tree)if isinstance(n,ast.If)and any(isinstance(b,ast.Assert)and
                    isinstance(b.msg,ast.Constant)and b.msg.value=='sparse cooperative plan file differs'for b in n.body)]
                assert len(nodes) == 1
                exec(compile(ast.Module(body=nodes,type_ignores=[]),str(python),'exec'),dict(env,version=16,proof=q,expected={}))
        except AssertionError as caught:
            assert str(caught) == message,str(caught)
        else:
            raise AssertionError('Actual source IO guard accepted '+field)
        label = 'v16-tampered-'+field; io.append(dict(name=label,passed=False))
        io_cases.append(dict(name=label,kind=kind,field=field,path=str(altered),message=message[0].upper()+message[1:]if kind=='plan'else message))
    altered = out/'tampered-acceptance.json'; altered.write_bytes(proofpath.read_bytes()+b'\n')
    io_cases.append(dict(name='v16-tampered-acceptance',kind='acceptance',path=str(altered),message='Cooperative cohort acceptance differs'))
    # A plan mutation changes no production artifact; it specifically checks the
    # real source loader's byte hash before any compiler or process action.
    payload = dict(proofs=[dict(version=v,path=str(paths[v]),sha256=sha(paths[v]))for v in sorted(paths)],
                   cases=cases,io_cases=io_cases)
    save(out/'payload.json',payload); (out/'exercise.ps1').write_text(PS_DRIVER)
    command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',windows(out/'exercise.ps1'),
               '-Source',windows(powershell),'-Payload',windows(out/'payload.json'),'-Output',windows(out/'powershell-results.json')]
    with (out/'powershell.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    ps = json.loads((out/'powershell-results.json').read_text())
    assert ps['cases'] == results
    assert {x['name']:x['passed']for x in ps['io']} == {
        'v16-complete-production-IO-guard':True,**{x['name']:False for x in io_cases}}
    text = powershell.read_text(); pytext = python.read_text()
    assert text.index('$taskPollVersion=Game-ValidatePollContract') < text.index('& $Cxx @taskCommon')
    assert text.index('Cooperative cohort acceptance differs') < text.index('$taskPollVersion=Game-ValidatePollContract')
    assert pytext.index('version=validate_cooperative_contract') < pytext.index('if a.verify_only:') < pytext.index('storage.mkdir()')
    assert all(sha(p)==digest for p,digest in {**pins,**source_pins}.items())
    save(out/'python-io-results.json',io)
    evidence = {str(p):sha(p)for p in out.iterdir()if p.is_file()}
    receipt = dict(passed=True,scope='Actual extracted v16 metadata guards and source IO only; no native/game execution',
        cases_per_language=len(cases),positive_cases=sum(c['passed']for c in cases),negative_cases=sum(not c['passed']for c in cases),
        actual_ancestor_count=14,source_inverse=inverse,historical_case_payload_sha256=sha(history_cases),
        historical_cases_preserved=len(historical_payload),historical_negative_cases_rerun=0,
        actual_parent_and_new_plan_IO_subguards=True,derived_proof=dict(path=str(proofpath),sha256=sha(proofpath)),
        guard_source_proof=dict(path=str(guardpath),sha256=sha(guardpath)),owned_sources=source_pins,
        input_pins=pins,commands=[command],evidence=evidence)
    save(out/'acceptance.json',receipt)
    print('ACCEPTANCE',sha(out/'acceptance.json'),flush=True)


if __name__ == '__main__':
    main()
