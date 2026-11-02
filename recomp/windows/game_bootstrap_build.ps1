param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe',[switch]$EnableCollectorDelivery)
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'game_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or $taskInput.union_trace_count -ne 456684 -or $taskInput.objects.Count -ne 3575){throw 'Incomplete final dual-engine input proof'}
function Game-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Game-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Game-ValidatePollContract($proof,$descriptor,$objects){
 if($proof.trace_heads -ne 456684 -or $proof.objects.Count -ne 3575 -or $objects.Count -ne 3575 -or $proof.unique_definitions -isnot [bool] -or -not $proof.unique_definitions -or $proof.PSObject.Properties.Name -notcontains 'missing_direct_targets' -or $null -eq $proof.missing_direct_targets -or $proof.missing_direct_targets.Count -ne 0){throw 'Incomplete cooperative cohort'}
 for($index=0;$index -lt $objects.Count;$index++){if($proof.objects[$index].path -cne $objects[$index].path -or $proof.objects[$index].sha256 -cne $objects[$index].sha256){throw "Cooperative cohort object selection differs at $index"}}
 $contract=$proof.contract;$version=1
 if($contract.PSObject.Properties.Name -contains 'version'){if($contract.version -isnot [int] -and $contract.version -isnot [long]){throw 'Unknown cooperative contract version'};$version=$contract.version}
 if($version -ne 1 -and $version -ne 2){throw 'Unknown cooperative contract version'}
 if($contract.poll_instrument_sha256 -isnot [string] -or $contract.poll_instrument_sha256 -cne '716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa' -or $contract.target -isnot [string] -or $contract.target -cne 'x86_64-w64-windows-gnu'){throw 'Unqualified cooperative instrumentation profile'}
 if($version -eq 1){
  if($contract.input_plan_sha256 -isnot [string] -or $contract.input_plan_sha256 -cne '14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9' -or $contract.no_relift -isnot [bool] -or -not $contract.no_relift -or $contract.source_ir_and_semantics_preserved -isnot [bool] -or -not $contract.source_ir_and_semantics_preserved){throw 'Unqualified original cooperative contract'}
 }else{
  if($descriptor.acceptance_sha256 -isnot [string] -or $descriptor.acceptance_sha256 -cne '7ce11b6bfd936334be8b7e8c7fe7691435830f818392a9a21d9f499120662549'){throw 'Unqualified sparse cooperative proof hash'}
  $required=@{profile='qualified-sparse-prefetch-v2';input_plan_sha256='9152d0cbf46a20aa86ee33cc48de63a1dece3647efe015b0aaed872c7e36bd95';base_input_plan_sha256='14e68811df426a9ce6488e1d724eed76cb5d6c95f95d9b4c70ead64ada87fea9';base_cohort_acceptance_sha256='0a5e6b164855d7c745962ec744d2e7bf1c7209a679065cc117c0575446d9687d';sparse_overlay_sha256='7fdc6f8b2e6eef9f5bafc9a4c5168318bf092ae1ec7e8988b44cd4b60b4dee7f';prefetch_fixture_acceptance_sha256='e387dc78d1f3c2d21999b8e105916faa1c53f86e67084cc31ffa6aebbddb71fc';prefetch_lifter_sha256='7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126';prefetch_semantics_sha256='c5f0d94e6b234f5f0f376eeb999bc9bfbaee62d654381751c3080e5c621ac3b5';old_polled_object_sha256='f1dfc4ccd067c68f509bd067766deff504d225bd17754742035ec86c849e2ee6';new_polled_object_sha256='e8ed4af6efde5f9df1d73905baf5f1f934931ded38327a1f36110b9dfe100358'}
  foreach($key in $required.Keys){if($contract.$key -isnot [string] -or $contract.$key -cne $required[$key]){throw "Unqualified sparse cooperative provenance: $key"}}
  if($contract.no_relift -isnot [bool] -or $contract.no_relift -or $contract.source_ir_and_semantics_preserved -isnot [bool] -or $contract.source_ir_and_semantics_preserved){throw 'Sparse cooperative contract must disclose changed source/semantics'}
  foreach($entry in @(@{key='qualified_sparse_relifts';value=1},@{key='replaced_object_index';value=1553},@{key='unchanged_objects';value=3574})){$value=$contract.($entry.key);if(($value -isnot [int] -and $value -isnot [long]) -or $value -ne $entry.value){throw "Sparse cooperative replacement scope differs: $($entry.key)"}}
  if($proof.objects[1553].sha256 -cne $required.new_polled_object_sha256){throw 'Sparse cooperative replacement object differs'}
  if($contract.input_plan_path -isnot [string] -or [string]::IsNullOrEmpty($contract.input_plan_path)){throw 'Sparse cooperative plan path is absent'}
 }
 return $version
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
 $taskPollVersion=Game-ValidatePollContract $taskPollProof $taskPollCohort $taskInput.objects
 if($taskPollVersion -eq 2 -and (Game-Hash (Game-Path $taskPollProof.contract.input_plan_path)) -cne $taskPollProof.contract.input_plan_sha256){throw 'Sparse cooperative plan file differs'}
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
foreach($taskName in @('jni_host.cpp','java_native_libraries.cpp','android_context.cpp','windows_android_id.cpp','jni_interface_proxy.cpp','android_asset_pack_wrapper.cpp','android_shared_preferences.cpp','windows_shared_preferences.cpp','android_internal_storage.cpp','android_obb_storage.cpp','android_assets.cpp','apk_assets.cpp','native_window.cpp','unity_lifecycle.cpp','signal_host.cpp','semaphore_host.cpp','nonlocal_jmp.cpp','audio_volume.cpp','audio_volume_session.cpp','egl_host.cpp','gl_host.cpp','filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
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
