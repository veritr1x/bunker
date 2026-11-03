param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe',[switch]$EnableCollectorDelivery)
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'game_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or -not (($taskInput.union_trace_count -eq 456684 -and $taskInput.objects.Count -eq 3575) -or ($taskInput.union_trace_count -eq 456689 -and $taskInput.objects.Count -eq 3576 -and $null -ne $taskInput.cooperative_poll_cohort))){throw 'Incomplete final dual-engine input proof'}
function Game-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Game-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Game-ValidatePollContract($proof,$descriptor,$objects,$parentProof=$null,$grandparentProof=$null){
 if(-not (($proof.trace_heads -eq 456684 -and $proof.objects.Count -eq 3575 -and $objects.Count -eq 3575) -or ($proof.trace_heads -eq 456689 -and $proof.objects.Count -eq 3576 -and $objects.Count -eq 3576)) -or $proof.unique_definitions -isnot [bool] -or -not $proof.unique_definitions -or $proof.PSObject.Properties.Name -notcontains 'missing_direct_targets' -or $null -eq $proof.missing_direct_targets -or $proof.missing_direct_targets.Count -ne 0){throw 'Incomplete cooperative cohort'}
 for($index=0;$index -lt $objects.Count;$index++){if($proof.objects[$index].path -cne $objects[$index].path -or $proof.objects[$index].sha256 -cne $objects[$index].sha256){throw "Cooperative cohort object selection differs at $index"}}
 $contract=$proof.contract;$version=1
 if($contract.PSObject.Properties.Name -contains 'version'){if($contract.version -isnot [int] -and $contract.version -isnot [long]){throw 'Unknown cooperative contract version'};$version=$contract.version}
 if($version -ne 1 -and $version -ne 2 -and $version -ne 3 -and $version -ne 4){throw 'Unknown cooperative contract version'}
 if(($version -eq 4 -and ($proof.trace_heads -ne 456689 -or $objects.Count -ne 3576)) -or ($version -ne 4 -and ($proof.trace_heads -ne 456684 -or $objects.Count -ne 3575))){throw 'Cooperative contract version/shape differs'}
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
 }else{
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
 }
 return $version
}
function Game-LoadPollParent($proof){
 if(($proof.contract.version -isnot [int] -and $proof.contract.version -isnot [long]) -or ($proof.contract.version -ne 3 -and $proof.contract.version -ne 4)){return $null}
 $contract=$proof.contract;$version=$contract.version
 $anchors=@{3=@('7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549','9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95');4=@('68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67','4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb')}
 if($contract.parent_acceptance_sha256 -isnot [string] -or $contract.parent_acceptance_sha256 -cne $anchors[[int]$version][0] -or $contract.parent_input_plan_sha256 -isnot [string] -or $contract.parent_input_plan_sha256 -cne $anchors[[int]$version][1]){throw "v$version parent anchors differ"}
 foreach($key in @('parent_acceptance_path','parent_input_plan_path')){if($contract.$key -isnot [string] -or [string]::IsNullOrEmpty($contract.$key)){throw "v$version parent path is absent"}}
 if((Game-Hash (Game-Path $contract.parent_acceptance_path)) -cne $contract.parent_acceptance_sha256){throw "v$version parent proof file differs"}
 $parent=Get-Content -Raw -LiteralPath (Game-Path $contract.parent_acceptance_path)|ConvertFrom-Json
 if((Game-Hash (Game-Path $contract.parent_input_plan_path)) -cne $contract.parent_input_plan_sha256){throw "v$version parent plan file differs"}
 return $parent
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
 $taskParentProof=Game-LoadPollParent $taskPollProof
 $taskGrandparentProof=$null;if($taskPollProof.contract.version -eq 4){$taskGrandparentProof=Game-LoadPollParent $taskParentProof}
 $taskPollVersion=Game-ValidatePollContract $taskPollProof $taskPollCohort $taskInput.objects $taskParentProof $taskGrandparentProof
 if($taskInput.union_trace_count -ne $taskPollProof.trace_heads){throw 'Manifest/cohort head count differs'}
 if(($taskPollVersion -eq 2 -or $taskPollVersion -eq 3 -or $taskPollVersion -eq 4) -and (Game-Hash (Game-Path $taskPollProof.contract.input_plan_path)) -cne $taskPollProof.contract.input_plan_sha256){throw 'Sparse cooperative plan file differs'}
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
