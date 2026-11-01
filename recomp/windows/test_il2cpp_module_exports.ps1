param(
  [Parameter(Mandatory=$true)][string]$BuildDirectory,
  [Parameter(Mandatory=$true)][string]$Apk,
  [string]$StorageDirectory
)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskApk=(Resolve-Path -LiteralPath $Apk).ProviderPath
$taskExe=Join-Path $taskBuild 'bunker-il2cpp-module-exports.exe'
$taskRecord=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'il2cpp_module_exports_build_record.json')|ConvertFrom-Json
if($taskRecord.status -ne 'native link passed' -or (Get-FileHash -Algorithm SHA256 -LiteralPath $taskExe).Hash.ToLowerInvariant() -ne $taskRecord.executable_sha256){throw 'New module-profile executable is not the recorded successful native link.'}
if(-not $StorageDirectory){$StorageDirectory=Join-Path $taskBuild 'module-exports-test-data'}
[System.IO.Directory]::CreateDirectory($StorageDirectory)|Out-Null
$taskStorage=(Resolve-Path -LiteralPath $StorageDirectory).ProviderPath
$taskOriginal=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'il2cpp-final-audit.json')|ConvertFrom-Json
function Test-Il2cppOriginalArtifacts{
  foreach($taskProperty in $taskOriginal.actual_artifact_hashes.PSObject.Properties){
    if((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild $taskProperty.Name)).Hash.ToLowerInvariant() -ne $taskProperty.Value){throw "Prior IL2CPP artifact changed: $($taskProperty.Name)"}
  }
}
Test-Il2cppOriginalArtifacts
$taskResults=@()
foreach($taskMode in @('module-exports','default','gc-signal-init')){
  $taskArguments=@((Join-Path $taskBuild 'native\libil2cpp.so'),$taskApk,$taskStorage)
  if($taskMode -eq 'module-exports'){$taskArguments+='--module-load-exports'}
  if($taskMode -eq 'gc-signal-init'){$taskArguments+='--gc-signal-init'}
  $taskOutput=(& $taskExe @taskArguments 2>&1|Out-String)
  $taskExit=$LASTEXITCODE
  [System.IO.File]::WriteAllText((Join-Path $taskBuild ('il2cpp-module-exports-'+$taskMode+'.log')),$taskOutput,[System.Text.UTF8Encoding]::new($false))
  if($taskExit -ne 0){throw "IL2CPP $taskMode gate failed with exit $taskExit; see its preserved log."}
  $taskConstructors=[regex]::Matches($taskOutput,'IL2CPP (?:module )?constructor \d+/9 guest=').Count
  $taskFinalizers=[regex]::Matches($taskOutput,'IL2CPP (?:module finalizer \d+/2|finalizer) guest=').Count
  if($taskConstructors -ne 9 -or $taskFinalizers -ne 2){throw "IL2CPP $taskMode lifecycle count differs: $taskConstructors/$taskFinalizers"}
  if($taskMode -eq 'module-exports'){
    if($taskOutput -notmatch '222 exact Unity-requested export lookups,repeat alias load/refcount2,nonfinal close passed' -or
       $taskOutput -notmatch 'stale handle rejected,reopen without reset rejected' -or
       $taskOutput -match 'calling actual parameterless GC signal initializer'){throw 'Module export-only evidence is incomplete or includes unwanted GC setup.'}
  }elseif($taskMode -eq 'gc-signal-init'){
    if($taskOutput -notmatch 'real GC signal initialization passed:30/24'){throw 'Existing actual GC signal-initializer regression did not pass.'}
  }elseif($taskOutput -match 'calling actual parameterless GC signal initializer'){throw 'Default mode unexpectedly entered GC signal setup.'}
  $taskResults+=@{mode=$taskMode;exit_code=$taskExit;constructors=$taskConstructors;finalizers=$taskFinalizers;log_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild ('il2cpp-module-exports-'+$taskMode+'.log'))).Hash.ToLowerInvariant()}
  Write-Output "IL2CPP $taskMode passed: actual 9 constructors/2 finalizers, exit 0."
}
Test-Il2cppOriginalArtifacts
$taskResult=[ordered]@{executable_sha256=$taskRecord.executable_sha256;profiles=$taskResults;prior_artifacts_unchanged=$true;resolved_exports=222;original_manifest_sha256=$taskRecord.original_manifest_sha256;remaining_unsupported_traces=$taskRecord.remaining_unsupported_traces.Count;il2cpp_init_or_managed_code_invoked=$false}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'il2cpp-module-exports-tests.json'),($taskResult|ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
Write-Output 'New module profile and existing default/GC-signal-init regressions passed; no il2cpp_init/managed/collector execution.'
