param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe',[switch]$EnableCollectorDelivery)
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'game_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or -not (($taskInput.union_trace_count -eq 456684 -and $taskInput.objects.Count -eq 3575) -or ($taskInput.union_trace_count -eq 456689 -and $taskInput.objects.Count -eq 3576 -and $null -ne $taskInput.cooperative_poll_cohort))){throw 'Incomplete final dual-engine input proof'}
function Game-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Game-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Game-ValidatePollContract($proof,$descriptor,$objects,$parentProof=$null,$grandparentProof=$null,$greatGrandparentProof=$null,$ancestorProofs=$null){
 if(-not (($proof.trace_heads -eq 456684 -and $proof.objects.Count -eq 3575 -and $objects.Count -eq 3575) -or ($proof.trace_heads -eq 456689 -and $proof.objects.Count -eq 3576 -and $objects.Count -eq 3576)) -or $proof.unique_definitions -isnot [bool] -or -not $proof.unique_definitions -or $proof.PSObject.Properties.Name -notcontains 'missing_direct_targets' -or $null -eq $proof.missing_direct_targets -or $proof.missing_direct_targets.Count -ne 0){throw 'Incomplete cooperative cohort'}
 for($index=0;$index -lt $objects.Count;$index++){if($proof.objects[$index].path -cne $objects[$index].path -or $proof.objects[$index].sha256 -cne $objects[$index].sha256){throw "Cooperative cohort object selection differs at $index"}}
 $contract=$proof.contract;$version=1
 if($contract.PSObject.Properties.Name -contains 'version'){if($contract.version -isnot [int] -and $contract.version -isnot [long]){throw 'Unknown cooperative contract version'};$version=$contract.version}
 if($version -ne 1 -and $version -ne 2 -and $version -ne 3 -and $version -ne 4 -and $version -ne 5 -and $version -ne 6 -and $version -ne 7 -and $version -ne 8 -and $version -ne 9 -and $version -ne 10 -and $version -ne 11 -and $version -ne 12){throw 'Unknown cooperative contract version'}
 if((($version -eq 4 -or $version -eq 5 -or $version -eq 6 -or $version -eq 7 -or $version -eq 8 -or $version -eq 9 -or $version -eq 10 -or $version -eq 11 -or $version -eq 12) -and ($proof.trace_heads -ne 456689 -or $objects.Count -ne 3576)) -or ($version -ne 4 -and $version -ne 5 -and $version -ne 6 -and $version -ne 7 -and $version -ne 8 -and $version -ne 9 -and $version -ne 10 -and $version -ne 11 -and $version -ne 12 -and ($proof.trace_heads -ne 456684 -or $objects.Count -ne 3575))){throw 'Cooperative contract version/shape differs'}
 if($contract.poll_instrument_sha256 -isnot [string] -or $contract.poll_instrument_sha256 -cne '716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa' -or $contract.target -isnot [string] -or $contract.target -cne 'x86_64-w64-windows-gnu'){throw 'Unqualified cooperative instrumentation profile'}
 if($version -eq 1){
  if($contract.input_plan_sha256 -isnot [string] -or $contract.input_plan_sha256 -cne '14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9' -or $contract.no_relift -isnot [bool] -or -not $contract.no_relift -or $contract.source_ir_and_semantics_preserved -isnot [bool] -or -not $contract.source_ir_and_semantics_preserved){throw 'Unqualified original cooperative contract'}
 }elseif($version -eq 2){
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne '7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549'){throw 'Unqualified sparse cooperative proof hash'}
  $required=@{profile='qualified-sparse-prefetch-v2';input_plan_sha256='9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95';base_input_plan_sha256='14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9';base_cohort_acceptance_sha256='0a5e6b164855d7c745962ec744d2e7bf1c7209a679065cc117c0575446d9687d';sparse_overlay_sha256='7fdc6f8b2e6eef9f5bafc9a4c5168318bf092ae1ec7e8988b44cd4b60b4dee7f';prefetch_fixture_acceptance_sha256='e387dc78d1f3c2d21999b8e105916faa1c53f86e67084cc31ffa6aebbddb71fc';prefetch_lifter_sha256='7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126';prefetch_semantics_sha256='c5f0d94e6b234f5f0f376eeb999bc9bfbaee62d654381751c3080e5c621ac3b5';old_polled_object_sha256='f1dfc4ccd067c68f509bd067766deff504d225bd17754742035ec86c849e2ee6';new_polled_object_sha256='e8ed4af6efde5f9df1d73905baf5f1f934931ded38327a1f36110b9dfe100358'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified sparse cooperative provenance: $key"}}
  if($contract.no_relift -isnot [bool] -or $contract.no_relift -or $contract.source_ir_and_semantics_preserved -isnot [bool] -or $contract.source_ir_and_semantics_preserved){throw 'Sparse cooperative contract must disclose changed source/semantics'}
  foreach($entry in @(@{key='qualified_sparse_relifts';value=1},@{key='replaced_object_index';value=1553},@{key='unchanged_objects';value=3574})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "Sparse cooperative replacement scope differs: $($entry.key)"}}
  if($proof.objects[1553].sha256 -cne $required.new_polled_object_sha256){throw 'Sparse cooperative replacement object differs'}
  if($contract.input_plan_path -isnot [string] -or [string]::IsNullOrEmpty($contract.input_plan_path)){throw 'Sparse cooperative plan path is absent'}
 }elseif($version -eq 3){
  # Exact qualified one-sort repair over the pinned v2 parent; no global refresh.
  $acceptance='68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67'
  $required=@{profile='qualified-sparse-unity-ext-sort-v3';input_plan_sha256='4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb';parent_acceptance_sha256='7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549';parent_input_plan_sha256='9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95';sparse_overlay_sha256='9ad375fa793aa5ba92ee626abe6316f85a97d31379bd4d6fe34a7b80c267e343';ext_fixture_acceptance_sha256='b4412315ade9aef3bd02aeb1ea0610692cdd52113e2d46c2bd40498ab95acf24';sort_fixture_acceptance_sha256='be2afc2eb5b37e92b45eac72e8aebd5ab1640c8bb12d5060eb6a65acef81ba0f';ext_lifter_sha256='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e';ext_semantics_sha256='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a';old_polled_object_sha256='71e7e8bc2f79bb88be46c8c39e89dca57f41687ba0d110f6f70786fd1530726a';new_polled_object_sha256='f15e35212a7ea11597c885f990822018be23acf850080b84f919c114e3392327';target_head='0x70255e38';target_end_exclusive='0x7025603c';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v3 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v3 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v3 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v3 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v3 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='cumulative_qualified_sparse_relifts';value=2},@{key='replaced_object_index';value=78},@{key='unchanged_objects';value=3574})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v3 cooperative replacement scope differs: $($entry.key)"}}
  if($contract.cumulative_changed_indices -isnot [array] -or $contract.cumulative_changed_indices.Count -ne 2){throw 'v3 cumulative replacement set differs'}
  for($i=0;$i -lt 2;$i++){$value=$contract.cumulative_changed_indices[$i];if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne @(78,1553)[$i]){throw 'v3 cumulative replacement set differs'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v3 cooperative plan/parent path is absent'}}
  if($null -eq $parentProof -or ($parentProof.contract.version -isnot [int] -and $parentProof.contract.version -isnot [long]) -or $parentProof.contract.version -ne 2){throw 'v3 exact parent v2 proof is absent'}
  $parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  if((Game-ValidatePollContract $parentProof $parentDescriptor $parentProof.objects) -ne 2 -or $parentProof.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v3 parent contract/plan differs'}
  if($parentProof.objects[78].sha256 -cne $required.old_polled_object_sha256 -or $objects[78].sha256 -cne $required.new_polled_object_sha256){throw 'v3 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 78){continue};if($proof.objects[$index].path -cne $parentProof.objects[$index].path -or $proof.objects[$index].sha256 -cne $parentProof.objects[$index].sha256){throw "v3 changed a second parent object: $index"}}
 }elseif($version -eq 4){
  # Exact qualified additive entries over the pinned v3 parent; no old object refresh.
  $acceptance='5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3'
  $required=@{profile='qualified-additive-unity-vararg-v4';input_plan_sha256='57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae';parent_acceptance_sha256='68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67';parent_input_plan_sha256='4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb';additive_candidate_sha256='88e29cd4c8853af8a6f9111b8e56504db556b2ef2fa6eb31bc81f310b98e85f2';prefix_fixture_acceptance_sha256='ed69b5f9076507a58c57f95ef569172db08e5f94fc9a72215d03ac90d74574ee';lifter_sha256='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e';semantics_sha256='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a';new_polled_object_sha256='f2bd9a1606dfc26ccbfa02f331f708df94cab70fe24fcbffbc511ef6d1a181cc';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v4 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v4 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v4 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v4 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='existing_objects_preserved';value=$true},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v4 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='added_object_index';value=3575},@{key='added_objects';value=1},@{key='added_trace_count';value=5},@{key='preserved_objects';value=3575},@{key='inherited_cumulative_sparse_relifts';value=2})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v4 additive scope differs: $($entry.key)"}}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v4 trace count differs'}
  $heads=@('0x70b5b488','0x70b5b4b0','0x70b5b4bc','0x70b5b648','0x70b5b674')
  if($contract.added_trace_heads -isnot [array] -or $contract.added_trace_heads.Count -ne 5){throw 'v4 additive head set differs'}
  for($i=0;$i -lt 5;$i++){if($contract.added_trace_heads[$i] -isnot [string] -or $contract.added_trace_heads[$i] -cne $heads[$i]){throw 'v4 additive head set differs'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v4 cooperative plan/parent path is absent'}}
  if($null -eq $parentProof -or ($parentProof.contract.version -isnot [int] -and $parentProof.contract.version -isnot [long]) -or $parentProof.contract.version -ne 3){throw 'v4 exact parent v3 proof is absent'}
  $parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  if((Game-ValidatePollContract $parentProof $parentDescriptor $parentProof.objects $grandparentProof) -ne 3 -or $parentProof.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v4 parent contract/plan differs'}
  for($index=0;$index -lt 3575;$index++){if($proof.objects[$index].path -cne $parentProof.objects[$index].path -or $proof.objects[$index].sha256 -cne $parentProof.objects[$index].sha256){throw "v4 changed an existing parent object: $index"}}
  if($objects[3575].path -isnot [string] -or [string]::IsNullOrEmpty($objects[3575].path) -or $objects[3575].sha256 -cne $required.new_polled_object_sha256){throw 'v4 additive object differs'}
 }elseif($version -eq 5){
  # Exact qualified single-wrapper FCSEL repair over the pinned additive v4.
  $acceptance='9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14'
  $required=@{profile='qualified-sparse-unity-fcsel-refresh-v5';input_plan_sha256='6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9';parent_acceptance_sha256='5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3';parent_input_plan_sha256='57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae';sparse_overlay_sha256='8911f23e4fa017fda6148a1883b176bc841749f73c6e2d900e75dee92d4dd838';fcsel_fixture_acceptance_sha256='4a0af97c4130ee43c294addde6fba772f4ae792a7c24c7c050b5459864cc6cf7';fcsel_lifter_sha256='7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126';fcsel_semantics_sha256='316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3';old_polled_object_sha256='142b008353679001d265e7288cd2a37d16062b39eebf28f9cdfd246c6fa8d5c3';new_polled_object_sha256='61dac83d8cb59610d51924673888f4d4c4ab7ad3960d277717100cbde48215c2';target_head='0x70acc13c';target_end_exclusive='0x70acc1d0';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v5 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v5 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v5 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v5 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v5 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='cumulative_qualified_sparse_relifts';value=3},@{key='replaced_object_index';value=459},@{key='unchanged_objects';value=3575})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v5 cooperative replacement scope differs: $($entry.key)"}}
  if($contract.cumulative_changed_indices -isnot [array] -or $contract.cumulative_changed_indices.Count -ne 3){throw 'v5 cumulative replacement set differs'}
  for($i=0;$i -lt 3;$i++){$value=$contract.cumulative_changed_indices[$i];if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne @(78,459,1553)[$i]){throw 'v5 cumulative replacement set differs'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v5 cooperative plan/parent path is absent'}}
  if($null -eq $parentProof -or ($parentProof.contract.version -isnot [int] -and $parentProof.contract.version -isnot [long]) -or $parentProof.contract.version -ne 4){throw 'v5 exact parent v4 proof is absent'}
  $parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  if((Game-ValidatePollContract $parentProof $parentDescriptor $parentProof.objects $grandparentProof $greatGrandparentProof) -ne 4 -or $parentProof.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v5 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v5 trace count differs'}
  if($parentProof.objects[459].sha256 -cne $required.old_polled_object_sha256 -or $objects[459].sha256 -cne $required.new_polled_object_sha256){throw 'v5 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 459){continue};if($proof.objects[$index].path -cne $parentProof.objects[$index].path -or $proof.objects[$index].sha256 -cne $parentProof.objects[$index].sha256){throw "v5 changed a second parent object: $index"}}
 }elseif($version -eq 6){
  # Exact qualified five-definition caller repair over the pinned v5 cohort.
  $acceptance='1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893'
  $required=@{profile='qualified-sparse-unity-fcsel-callers-v6';input_plan_sha256='3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b';parent_acceptance_sha256='9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14';parent_input_plan_sha256='6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9';sparse_overlay_sha256='5af486e926556cfa0de9d1cfeb01db7ae8e7f73253a076c6fe0f92735d4248bc';fcsel_fixture_acceptance_sha256='5d7d768ad4332255d483f4c939fd2f9abde75c538a88ecb3ba474e85bc368ede';fcsel_lifter_sha256='7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126';fcsel_semantics_sha256='316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3';old_polled_object_sha256='ab19f24618b5fe9cda0ba6716bd47e2da87026de4427029e377056146cc916e1';new_polled_object_sha256='d33641796aa959871443201ac2f8ffccc067a19326a5ad0c1f8afe6a73e99e9e';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v6 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v6 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v6 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v6 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v6 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='cumulative_qualified_sparse_relifts';value=4},@{key='replaced_object_index';value=161},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=5},@{key='unchanged_functions_in_shard';value=123})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v6 cooperative replacement scope differs: $($entry.key)"}}
  if($contract.cumulative_changed_indices -isnot [array] -or $contract.cumulative_changed_indices.Count -ne 4){throw 'v6 cumulative replacement set differs'}
  for($i=0;$i -lt 4;$i++){$value=$contract.cumulative_changed_indices[$i];if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne @(78,161,459,1553)[$i]){throw 'v6 cumulative replacement set differs'}}
  $heads=@('0x7042377c','0x704238f4','0x70423908','0x70423918','0x70423928')
  if($contract.target_heads -isnot [array] -or $contract.target_heads.Count -ne 5){throw 'v6 exact changed definitions differ'}
  for($i=0;$i -lt 5;$i++){if($contract.target_heads[$i] -isnot [string] -or $contract.target_heads[$i] -cne $heads[$i]){throw 'v6 exact changed definitions differ'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v6 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 4 -or $ancestorProofs[0].contract.version -ne 5){throw 'v6 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $ancestorProofs[1] $ancestorProofs[2] $ancestorProofs[3]) -ne 5 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v6 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v6 trace count differs'}
  if($parent.objects[161].sha256 -cne $required.old_polled_object_sha256 -or $objects[161].sha256 -cne $required.new_polled_object_sha256){throw 'v6 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 161){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v6 changed a second parent object: $index"}}
 }elseif($version -eq 7){
  # Original object initialization with qualified ST2 multiple-structure stores.
  $acceptance='5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049'
  $required=@{profile='qualified-sparse-unity-st2-object-v7';input_plan_sha256='e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621';parent_acceptance_sha256='1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893';parent_input_plan_sha256='3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b';sparse_overlay_sha256='d3078449b770caa61630df63faff7dd6772a2733778e49bf556dbf6c8c0d88d3';st2_fixture_acceptance_sha256='28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed';original_fixture_acceptance_sha256='ad2aec850d93eb8cf1650c09636c3d7766f29f14c24cc79389882e2b484cf982';st2_lifter_sha256='a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa';st2_semantics_sha256='1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658';old_polled_object_sha256='5504d089df69da73b12002d7e84dc9e9ecc2cac88a8e0d79b7b12df7d1089d47';new_polled_object_sha256='910d1a15ce49da0b48e6f54abd879a5b544d624101763845105ad475008ca12b';target_head='0x707bb458';target_end_exclusive='0x707bb55c';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v7 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v7 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v7 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v7 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v7 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='cumulative_qualified_sparse_relifts';value=5},@{key='replaced_object_index';value=270},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=1},@{key='unchanged_functions_in_shard';value=127})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v7 cooperative replacement scope differs: $($entry.key)"}}
  if($contract.cumulative_changed_indices -isnot [array] -or $contract.cumulative_changed_indices.Count -ne 5){throw 'v7 cumulative replacement set differs'}
  for($i=0;$i -lt 5;$i++){$value=$contract.cumulative_changed_indices[$i];if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne @(78,161,270,459,1553)[$i]){throw 'v7 cumulative replacement set differs'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v7 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 5 -or $ancestorProofs[0].contract.version -ne 6){throw 'v7 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  $parentAncestors=@($ancestorProofs[1..4])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 6 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v7 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v7 trace count differs'}
  if($parent.objects[270].sha256 -cne $required.old_polled_object_sha256 -or $objects[270].sha256 -cne $required.new_polled_object_sha256){throw 'v7 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 270){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v7 changed a second parent object: $index"}}
 }elseif($version -eq 8){
  # Exact fully qualified vector batch; paths and hashes are one bound payload.
  $acceptance='4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569'
  $required=@{profile='qualified-fcsel-vector-batch-v8';input_plan_sha256='d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4';parent_acceptance_sha256='5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049';parent_input_plan_sha256='e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621';batch_acceptance_sha256='a790ab1e8cbfeb90b5c91b533ee161626e1a2ce10d3b730a87ee06c72060c09a';batch_manifest_sha256='faecdde9e83aa7fa9bbfe2a1264f5e914a6c9f3aa970431ef5d3807774dfd864';checker_qualification_sha256='09c13e1636abe9b566e7fc26ae6829f46a9c0126dce08cef16a6815152ba7ba5';fcsel_fixture_acceptance_sha256='b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b';fcsel_lifter_sha256='a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa';fcsel_semantics_sha256='1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658';compiled_identity_sha256='70c0e7ecedf707a43b968bd2bdf48419951d31e96781ca6cf842c98449063938';replacement_vector_sha256='a5c19e5bf534730f9e697d5d237a98f3f41ad324e4956109a56c92c96d19c70b';condition_qualification_sha256='cd99aa583e4121e4a2369b9348d4731914f103bc64c902166c7a3d9daf867b56';proof_mode='exact-attributed-fcsel-transport-v1';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v8 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v8 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v8 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v8 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$true},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false},@{key='non_fcsel_instructions_preserved';value=$true},@{key='all_replacements_qualified';value=$true})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v8 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='replacement_count';value=556},@{key='unchanged_objects';value=3020},@{key='changed_function_count';value=2164},@{key='legacy_fcsel_copy_count';value=5766})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw 'v8 cooperative replacement scope differs'}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v8 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 6 -or $ancestorProofs[0].contract.version -ne 7){throw 'v8 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256};$parentAncestors=@($ancestorProofs[1..5])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 7 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v8 parent contract/plan differs'}
  $vector=$contract.replacement_vector;if($vector -isnot [array] -or $vector.Count -ne 556){throw 'v8 replacement vector shape differs'}
  $payload=[Text.StringBuilder]::new();$changed=@{};$previous=-1
  foreach($row in $vector){
   $keys=@($row.PSObject.Properties.Name);if($row -isnot [pscustomobject] -or $keys.Count -ne 5){throw 'v8 replacement row shape differs'}
   foreach($key in @('index','old_path','old_sha256','new_path','new_sha256')){if($keys -cnotcontains $key){throw 'v8 replacement row shape differs'}}
   $index=$row.index;if(($index -isnot [int] -and $index -isnot [long]) -or $index -le $previous -or $index -ge 3576){throw 'v8 replacement indices differ'}
   foreach($key in @('old_path','new_path','old_sha256','new_sha256')){if($row.$key -isnot [string] -or [string]::IsNullOrEmpty($row.$key) -or $row.$key -cmatch '[\x00-\x1f\x7f-\x9f]'){throw 'v8 replacement descriptor encoding differs'}}
   foreach($key in @('old_sha256','new_sha256')){if($row.$key -cnotmatch '^[0-9a-f]{64}$'){throw 'v8 replacement descriptor hash differs'}}
   $null=$payload.Append($index.ToString([Globalization.CultureInfo]::InvariantCulture)).Append("`t").Append($row.old_path).Append("`t").Append($row.old_sha256).Append("`t").Append($row.new_path).Append("`t").Append($row.new_sha256).Append("`n");$previous=$index;$changed[[int]$index]=$true
   if($parent.objects[$index].path -cne $row.old_path -or $parent.objects[$index].sha256 -cne $row.old_sha256){throw 'v8 old replacement descriptor differs'}
   if($objects[$index].path -cne $row.new_path -or $objects[$index].sha256 -cne $row.new_sha256){throw 'v8 new replacement descriptor differs'}
  }
  $encoding=[Text.UTF8Encoding]::new($false,$true);$hasher=[System.Security.Cryptography.SHA256]::Create()
  try{$vectorHash=([BitConverter]::ToString($hasher.ComputeHash($encoding.GetBytes($payload.ToString())))).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose()}
  if($vectorHash -cne $required.replacement_vector_sha256){throw 'v8 replacement payload differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($changed.ContainsKey($index)){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v8 changed an unlisted parent object: $index"}}
 }elseif($version -eq 9){
  # One qualified ST2 constructor over the exact vector-repaired parent.
  $acceptance='9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea'
  $required=@{profile='qualified-sparse-unity-st2-constructor-v9';input_plan_sha256='d3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058';parent_acceptance_sha256='4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569';parent_input_plan_sha256='d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4';sparse_overlay_sha256='6791fa803510090f27a2b0d08a2f371fd9b8b2201bf555f14da2214f30d2ce4d';st2_fixture_acceptance_sha256='28851765bb44ca825859ae6bfec24b0fa23094624fe98112c55d828b3feed3ed';original_fixture_acceptance_sha256='6b6dbfb3d20b080b4f029c410a776d088a28dbe7e0f05c9a68b4c739b30f3597';st2_lifter_sha256='a6adf76c0c6f57ae2046bdfe9044fd553bb341979e734f7588fdedec5806fcaa';st2_semantics_sha256='1c8ac0b879632f7c8d7fc1dfaf455c1b91fdce985cb00d6829b7a314f1b32658';old_polled_object_sha256='963b56f892d06428753bad028ad396eb97eeaff9d9ee8770fc9c144e62aa5d48';new_polled_object_sha256='ad6b08dbcebe0d007c60a6ccc6a8b71f6a8be8a80693cec4fda0223fab53fe5e';target_head='0x707520c4';target_end_exclusive='0x707521bc';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v9 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v9 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v9 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v9 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v9 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='inherited_vector_replacements';value=556},@{key='replaced_object_index';value=249},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=1},@{key='unchanged_functions_in_shard';value=127})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v9 cooperative replacement scope differs: $($entry.key)"}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v9 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 7 -or $ancestorProofs[0].contract.version -ne 8){throw 'v9 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  $parentAncestors=@($ancestorProofs[1..6])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 8 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v9 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v9 trace count differs'}
  if($parent.objects[249].sha256 -cne $required.old_polled_object_sha256 -or $objects[249].sha256 -cne $required.new_polled_object_sha256){throw 'v9 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 249){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v9 changed a second parent object: $index"}}
 }elseif($version -eq 10){
  # One qualified fixed FCVTZU function over the exact vector-repaired parent.
  $acceptance='0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5'
  $required=@{profile='qualified-sparse-unity-fcvtzu-fixed-v10';input_plan_sha256='ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3';parent_acceptance_sha256='9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea';parent_input_plan_sha256='d3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058';sparse_overlay_sha256='303e3bfd8a245e354eff8c1a8219fe2e7f1cb3499823bafd8fa38675d1f0a1c8';fcvtzu_fixed_fixture_acceptance_sha256='73a166570129008d44061237cea546504534c0f6c79f59d4242ca17b4506e675';original_fixture_acceptance_sha256='87b27ab5a230225ee1de843392215c0a0a7d3136839a86dad21dace684514f7b';compiled_identity_sha256='2886ee6e5252abe176a99a2f0ae429fb6d8f89cfd2b869fc59e19c4de796cac9';fcvtzu_fixed_lifter_sha256='3d6beaa96e010c7b5424fba8960fe19eca3c261d6da164df08e4adadd75fbf88';fcvtzu_fixed_semantics_sha256='0d5c2c427b2f43d2f5b01db564e3141837c86df0afe79dee5c32ae48c3237409';old_polled_object_sha256='f30ae550a205c93624049b720eca1a88503cc6335744372340ca68162d07b418';new_polled_object_sha256='87149852496090c1c5084d79e024514c07da34c60974f537cfe3f4fdb655200f';target_head='0x70362a2c';target_end_exclusive='0x70362a8c';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v10 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v10 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v10 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v10 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v10 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='inherited_vector_replacements';value=556},@{key='replaced_object_index';value=123},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=1},@{key='unchanged_functions_in_shard';value=127})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v10 cooperative replacement scope differs: $($entry.key)"}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v10 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 8 -or $ancestorProofs[0].contract.version -ne 9){throw 'v10 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  $parentAncestors=@($ancestorProofs[1..7])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 9 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v10 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v10 trace count differs'}
  if($parent.objects[123].sha256 -cne $required.old_polled_object_sha256 -or $objects[123].sha256 -cne $required.new_polled_object_sha256){throw 'v10 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 123){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v10 changed a second parent object: $index"}}
 }elseif($version -eq 11){
  # One qualified ST3 definition; the original-prefix fixture is not a full-FDE run.
  $acceptance='64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e'
  $required=@{profile='qualified-sparse-unity-st3-store-v11';input_plan_sha256='57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93';parent_acceptance_sha256='0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5';parent_input_plan_sha256='ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3';sparse_overlay_sha256='1c832a98fbdd491c53038ca20779d36e8f47f6fde62a29d11d8546abb3293118';st3_fixture_acceptance_sha256='15404cfbfca518caa3393c428e9585d0456086232892ff95e75b73d6cfabfa98';original_block_fixture_acceptance_sha256='4f6bfd4533f5c04514e433fb6ddef2592823d403454f32aa17ff465589c68b25';compiled_identity_sha256='a2ab71354a31cd0fee124252d5310b760a5915875206458129a760f32a9c97b7';st3_lifter_sha256='8e5b529295a67f9387dbf1d1dcbed4e71aebcb741e11f09103a17899ee44df2c';st3_semantics_sha256='e289429a3da24b4dd08b4dcc1471572f06d940cb2958db8e66dd8554965c7b30';old_polled_object_sha256='be26cf4231b66f7f069f0aa8b95e2ec784b0ed97a6cfb864182215917162f577';new_polled_object_sha256='cddd5852024875161cef458b8b3d1e825721a32965ad79f66fc7157d92ab53b6';target_head='0x704fd850';target_end_exclusive='0x704fdb60';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v11 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v11 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v11 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v11 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v11 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='inherited_vector_replacements';value=556},@{key='replaced_object_index';value=200},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=1},@{key='unchanged_functions_in_shard';value=127})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v11 cooperative replacement scope differs: $($entry.key)"}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v11 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 9 -or $ancestorProofs[0].contract.version -ne 10){throw 'v11 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  $parentAncestors=@($ancestorProofs[1..8])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 10 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v11 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v11 trace count differs'}
  if($parent.objects[200].sha256 -cne $required.old_polled_object_sha256 -or $objects[200].sha256 -cne $required.new_polled_object_sha256){throw 'v11 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 200){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v11 changed a second parent object: $index"}}
 }else{
  # One qualified USHLL mask definition; the original-block fixture is not a full-FDE run.
  $acceptance='34a41fc3f8fa21e5df3d23d702d455e52805bfd21a6f33161b5176245d241601'
  $required=@{profile='qualified-sparse-unity-ushll-mask-v12';input_plan_sha256='0385129c17c6b2db060aa938127edf2993490b78b4adcbd551d24840fa006aea';parent_acceptance_sha256='64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e';parent_input_plan_sha256='57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93';sparse_overlay_sha256='03b57f5e4a16488f364975e9f79c406308454fafe46f5a47056a5f30caedeebf';ushll_fixture_acceptance_sha256='623082c62ae71210756c08a92eec56bf0e3e8b94cc07d6650818e855d0b41e9b';original_block_fixture_acceptance_sha256='be35d41e14bd385469ddb11778e1cb4ff2a22936765b658d83b4a0d7824fbecd';compiled_identity_sha256='d2918f90adb54fa2d720b9ca9a6e7c776fed66bb0fe58af54ad5065feb7899b8';ushll_lifter_sha256='8e5b529295a67f9387dbf1d1dcbed4e71aebcb741e11f09103a17899ee44df2c';ushll_semantics_sha256='e289429a3da24b4dd08b4dcc1471572f06d940cb2958db8e66dd8554965c7b30';old_polled_object_sha256='8d74124a34e0511ba0bbaf71d11c031290d9e8db431bdd228c5775b834ef2e42';new_polled_object_sha256='c28559fea099d8d2091ec876061345fd7b6aa80e6740745cf30586e9930ea5d5';target_head='0x702b3d34';target_end_exclusive='0x702b4034';optimization='-O2'}
  if($acceptance -cnotmatch '^[0-9a-f]{64}$'){throw 'v12 cooperative pins are not qualified'}
  foreach($key in $required.Keys){if($key.EndsWith('_sha256') -and $required[$key] -cnotmatch '^[0-9a-f]{64}$'){throw 'v12 cooperative pins are not qualified'}}
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne $acceptance){throw 'Unqualified v12 cooperative proof hash'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified v12 cooperative provenance: $key"}}
  foreach($entry in @(@{key='no_relift';value=$false},@{key='source_ir_and_semantics_preserved';value=$false},@{key='no_global_semantics_refresh';value=$true},@{key='production_signal_delivery_enabled';value=$false})){if($contract.($entry.key) -isnot [bool] -or $contract.($entry.key) -ne $entry.value){throw 'v12 cooperative policy disclosure differs'}}
  foreach($entry in @(@{key='incremental_sparse_relifts';value=1},@{key='inherited_vector_replacements';value=556},@{key='replaced_object_index';value=94},@{key='unchanged_objects';value=3575},@{key='changed_function_count';value=1},@{key='unchanged_functions_in_shard';value=127})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "v12 cooperative replacement scope differs: $($entry.key)"}}
  foreach($key in @('input_plan_path','parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw 'v12 cooperative plan/parent path is absent'}}
  if($ancestorProofs -isnot [array] -or $ancestorProofs.Count -ne 10 -or $ancestorProofs[0].contract.version -ne 11){throw 'v12 exact ancestor chain is absent'}
  $parent=$ancestorProofs[0];$parentDescriptor=[pscustomobject]@{acceptance_path=$contract.parent_acceptance_path;acceptance_sha256=$contract.parent_acceptance_sha256}
  $parentAncestors=@($ancestorProofs[1..9])
  if((Game-ValidatePollContract $parent $parentDescriptor $parent.objects $null $null $null $parentAncestors) -ne 11 -or $parent.contract.input_plan_sha256 -cne $contract.parent_input_plan_sha256){throw 'v12 parent contract/plan differs'}
  if(($proof.trace_heads -isnot [int] -and $proof.trace_heads -isnot [long]) -or $proof.trace_heads -ne 456689){throw 'v12 trace count differs'}
  if($parent.objects[94].sha256 -cne $required.old_polled_object_sha256 -or $objects[94].sha256 -cne $required.new_polled_object_sha256){throw 'v12 replacement object differs'}
  for($index=0;$index -lt $objects.Count;$index++){if($index -eq 94){continue};if($proof.objects[$index].path -cne $parent.objects[$index].path -or $proof.objects[$index].sha256 -cne $parent.objects[$index].sha256){throw "v12 changed a second parent object: $index"}}
 }
 return $version
}
function Game-LoadPollParent($proof){
 if(($proof.contract.version -isnot [int] -and $proof.contract.version -isnot [long]) -or ($proof.contract.version -ne 3 -and $proof.contract.version -ne 4 -and $proof.contract.version -ne 5 -and $proof.contract.version -ne 6 -and $proof.contract.version -ne 7 -and $proof.contract.version -ne 8 -and $proof.contract.version -ne 9 -and $proof.contract.version -ne 10 -and $proof.contract.version -ne 11 -and $proof.contract.version -ne 12)){return $null}
 $contract=$proof.contract;$version=$contract.version
 $anchors=@{3=@('7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95');4=@('68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67','4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb');5=@('5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3','57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae');6=@('9bf9e6bc5df6c932f552b81456559d28d6fa0d9c1cc1a65b3afa00deff9ade14','6bf5af7262febc4fa10ff452c06a938d3089504b8a136ab808f2ce52fe6dc3d9')}
 $anchors[7]=@('1df01bf6d53e33b0b34372306d48141e48b08d798f550136fed2ad651051a893','3b6023a4952b82c3bed4e60580e8f52232e4f0a71071dd05a0506fcc07a1690b')
 $anchors[8]=@('5803222e59da7de5fcb6fc1b3ca712ea3f899a60bf7e5e2bb4d4734d76ee3049','e15748779e6a48ade204a2e83b35848757cef91264ed136056ee403b421f7621')
 $anchors[9]=@('4b1ce5cd31a95f74677eda4099a605bf2b5a9621f8247fae48ad6afaf8113569','d1fe8968346692ed7151e7544271cebd4273970672961448bbf75b46f1fd22a4')
 $anchors[10]=@('9aba61275bad90b338aaaabebcad9bedd55bcef47144428e31da409cfb8566ea','d3fc6ef22d80cf1696d031585f0035b1ccd6a355c8dd9f5ab9efdf304dfe2058')
 $anchors[11]=@('0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5','ea3566b3a2c70facdbdb8e50ec3593b588aa70d1c14704dad9fde83e678edee3')
 $anchors[12]=@('64498bd829e9b92c7f4867a6fe3a1fc5a8a162c6b937a4cfdd23aa9404ae969e','57198d945823aa02a06101a5ac2490337680b5251527a62da07db5f789947d93')
 if($contract.parent_acceptance_sha256 -isnot [string] -or $contract.parent_acceptance_sha256 -cne $anchors[[int]$version][0] -or $contract.parent_input_plan_sha256 -isnot [string] -or $contract.parent_input_plan_sha256 -cne $anchors[[int]$version][1]){throw "v$version parent anchors differ"}
 foreach($key in @('parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw "v$version parent path is absent"}}
 if((Game-Hash (Game-Path $contract.parent_acceptance_path)) -cne $contract.parent_acceptance_sha256){throw "v$version parent proof file differs"}
 $parent=Get-Content -Raw -LiteralPath (Game-Path $contract.parent_acceptance_path)|ConvertFrom-Json
 if((Game-Hash (Game-Path $contract.parent_input_plan_path)) -cne $contract.parent_input_plan_sha256){throw "v$version parent plan file differs"}
 return $parent
}

function Game-LoadPollAncestors($proof){
 if(($proof.contract.version -isnot [int] -and $proof.contract.version -isnot [long]) -or ($proof.contract.version -ne 6 -and $proof.contract.version -ne 7 -and $proof.contract.version -ne 8 -and $proof.contract.version -ne 9 -and $proof.contract.version -ne 10 -and $proof.contract.version -ne 11 -and $proof.contract.version -ne 12)){throw 'Ancestor loading requires v6 through v12'}
 $result=@();$current=$proof
 for($version=$proof.contract.version-1;$version -ge 2;$version--){
  $parent=Game-LoadPollParent $current
  if($null -eq $parent -or ($parent.contract.version -isnot [int] -and $parent.contract.version -isnot [long]) -or $parent.contract.version -ne $version){throw 'v6 ancestor version differs'}
  $result+=,$parent;$current=$parent
 }
 return ,$result
}
foreach($taskGroup in @(@{root=(Join-Path $taskBuild 'sources');values=$taskInput.source_sha256},@{root=$taskBuild;values=$taskInput.frozen_support_sha256},@{root=$taskBuild;values=$taskInput.generated_header_sha256})){
 foreach($taskProperty in $taskGroup.values.PSObject.Properties){if((Game-Hash (Join-Path $taskGroup.root $taskProperty.Name)) -ne $taskProperty.Value){throw "Frozen source/support differs: $($taskProperty.Name)"}}
}
foreach($taskObject in $taskInput.objects){if((Game-Hash (Game-Path $taskObject.path)) -ne $taskObject.sha256){throw "Accepted object differs: $($taskObject.path)"}}
$taskPollCohort=$taskInput.cooperative_poll_cohort
if($EnableCollectorDelivery -and $null -eq $taskPollCohort){throw 'Original collector delivery requires the accepted fully cooperative cohort'}
if($null -ne $taskPollCohort){
 $taskPollProofPath=Game-Path $taskPollCohort.acceptance_path
 if((Game-Hash $taskPollProofPath) -ne $taskPollCohort.acceptance_sha256){throw 'Cooperative cohort acceptance differs'}
 $taskPollProof=Get-Content -Raw -LiteralPath $taskPollProofPath|ConvertFrom-Json
 if($taskPollProof.contract.version -eq 6 -or $taskPollProof.contract.version -eq 7 -or $taskPollProof.contract.version -eq 8 -or $taskPollProof.contract.version -eq 9 -or $taskPollProof.contract.version -eq 10 -or $taskPollProof.contract.version -eq 11 -or $taskPollProof.contract.version -eq 12){
  $taskAncestors=Game-LoadPollAncestors $taskPollProof
  $taskPollVersion=Game-ValidatePollContract $taskPollProof $taskPollCohort $taskInput.objects $null $null $null $taskAncestors
 }else{
  $taskParentProof=Game-LoadPollParent $taskPollProof
  $taskGrandparentProof=$null;if($taskPollProof.contract.version -eq 4 -or $taskPollProof.contract.version -eq 5){$taskGrandparentProof=Game-LoadPollParent $taskParentProof}
  $taskGreatGrandparentProof=$null;if($taskPollProof.contract.version -eq 5){$taskGreatGrandparentProof=Game-LoadPollParent $taskGrandparentProof}
  $taskPollVersion=Game-ValidatePollContract $taskPollProof $taskPollCohort $taskInput.objects $taskParentProof $taskGrandparentProof $taskGreatGrandparentProof
 }
 if($taskInput.union_trace_count -ne $taskPollProof.trace_heads){throw 'Manifest/cohort head count differs'}
 if(($taskPollVersion -eq 2 -or $taskPollVersion -eq 3 -or $taskPollVersion -eq 4 -or $taskPollVersion -eq 5 -or $taskPollVersion -eq 6 -or $taskPollVersion -eq 7 -or $taskPollVersion -eq 8 -or $taskPollVersion -eq 9 -or $taskPollVersion -eq 10 -or $taskPollVersion -eq 11 -or $taskPollVersion -eq 12) -and (Game-Hash (Game-Path $taskPollProof.contract.input_plan_path)) -cne $taskPollProof.contract.input_plan_sha256){throw 'Sparse cooperative plan file differs'}
}
if((Game-Hash (Join-Path $taskBuild 'libz-inflate.a')) -ne $taskInput.zlib_sha256){throw 'Frozen zlib backend differs'}
$taskSource=Join-Path $taskBuild 'sources\recomp'
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild","-I$taskBuild\zlib-include","-I$taskBuild\angle-include",'-Wa,-mbig-obj')
if($null -ne $taskPollCohort){$taskCommon+='-DBUNKER_GAME_COOPERATIVE_POLLS=1'}
if($EnableCollectorDelivery){$taskCommon+='-DBUNKER_GAME_COLLECTOR_DELIVERY=1'}
$taskHarness=Join-Path $taskBuild 'game-bootstrap.o';$taskLoader=Join-Path $taskBuild 'elfload.o';$taskExe=Join-Path $taskBuild 'bunker-game-bootstrap.exe'
& $Cxx @taskCommon '-c' (Join-Path $taskSource 'windows\game_bootstrap.cpp') '-o' $taskHarness
if($LASTEXITCODE){throw 'Game bootstrap harness compile failed'}
& $Cc '-O2' '-c' (Join-Path $taskSource 'fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Game ELF data loader compile failed'}
$taskArgs=$taskCommon+@('-static',$taskHarness,$taskLoader)
foreach($taskName in @('jni_host.cpp','java_native_libraries.cpp','android_context.cpp','windows_display_service.cpp','windows_android_id.cpp','jni_interface_proxy.cpp','android_asset_pack_wrapper.cpp','android_shared_preferences.cpp','windows_shared_preferences.cpp','android_internal_storage.cpp','android_obb_storage.cpp','android_assets.cpp','apk_assets.cpp','native_window.cpp','unity_lifecycle.cpp','signal_host.cpp','signal_sleep.cpp','signal_futex.cpp','thread_priority.cpp','android_process.cpp','thread_affinity.cpp','semaphore_host.cpp','nonlocal_jmp.cpp','audio_volume.cpp','audio_volume_session.cpp','egl_host.cpp','gl_host.cpp','filesystem.cpp','module_registry.cpp','module_registry_elf.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
$taskGrowdownSource=Join-Path $taskSource 'windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($taskName in @('runtime.cpp','format.cpp')){$taskArgs+=Join-Path $taskSource ('whole\'+$taskName)}
if($null -ne $taskPollCohort){$taskArgs+=Join-Path $taskSource 'whole\cooperative_poll.cpp'}
if($EnableCollectorDelivery){
 foreach($taskName in @('worker_signal_lifecycle.cpp','signal_delivery.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
 $taskArgs+=Join-Path $taskSource 'whole\signal_frame.cpp'
}
foreach($taskObject in $taskInput.objects){$taskArgs+=Game-Path $taskObject.path}
$taskArgs+=@((Join-Path $taskBuild 'libz-inflate.a'),'-Wl,--wrap=sub_825b0544','-latomic','-lbcrypt','-luser32','-lgdi32','-lole32','-luuid','-ladvapi32','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'game-bootstrap-link.rsp'
$taskEscaped=foreach($taskArgument in $taskArgs){'"'+$taskArgument.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE){throw 'Dual-engine natural-frame native link failed'}
$taskRecord=[ordered]@{status='native link passed';inputs_sha256=(Game-Hash (Join-Path $taskBuild 'game_inputs.json'));executable_sha256=(Game-Hash $taskExe);response_sha256=(Game-Hash $taskResponse);host_commit=$taskInput.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1);trace_count=$taskInput.union_trace_count;objects=$taskInput.objects.Count;collector_delivery_profile=if($EnableCollectorDelivery){'original-finalizer-single-condwait-v1'}else{$null}}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'game_build.json'),($taskRecord|ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
Write-Output $taskExe
