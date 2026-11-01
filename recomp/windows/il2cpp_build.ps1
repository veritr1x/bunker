param(
  [Parameter(Mandatory=$true)][string]$BuildDirectory,
  [string]$Apk,
  [string]$StorageDirectory,
  [string]$Remill=(Join-Path $PSScriptRoot '..\work\remill-src'),
  [string]$ZlibDirectory=(Join-Path $PSScriptRoot '..\work\zlib-native'),
  [string]$Cxx='g++.exe',
  [string]$Cc='gcc.exe',
  [string[]]$OverlayMetadata=@(),
  [switch]$GcSignalInit,
  [switch]$Run,
  [switch]$CompileOnly
)
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill=(Resolve-Path -LiteralPath $Remill).ProviderPath
$taskZlib=(Resolve-Path -LiteralPath $ZlibDirectory).ProviderPath
$taskManifest=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'il2cpp_link.json')|ConvertFrom-Json
if(-not $taskManifest.complete -or $taskManifest.base -ne 2147483648 -or $taskManifest.constructors.Count -ne 9){throw 'Actual IL2CPP snapshot/lifecycle metadata is incomplete.'}
$taskLibrary=Join-Path $taskBuild 'native\libil2cpp.so'
if((Get-FileHash -Algorithm SHA256 -LiteralPath $taskLibrary).Hash.ToLowerInvariant() -ne $taskManifest.sha256){throw 'Original IL2CPP hash differs from verified snapshot.'}
# Freeze host provider source before the long link; other agents can continue
# owning their live files without changing this diagnostic executable's inputs.
$taskOverlayRecords=@()
$taskObjects=@($taskManifest.objects)
$taskRemaining=[System.Collections.Generic.HashSet[uint64]]::new()
foreach($taskEntry in $taskManifest.unsupported_traces){[void]$taskRemaining.Add([uint64]$taskEntry)}
foreach($taskMetadata in $OverlayMetadata){
  $taskOverlay=Get-Content -Raw -LiteralPath $taskMetadata|ConvertFrom-Json
  if($taskOverlay.status -ne 'validated' -or $taskOverlay.original_manifest_sha256 -ne $taskManifest.original_manifest_sha256 -or
     -not $taskOverlay.state_layout.equal -or $taskOverlay.new_definitions.Count -or $taskOverlay.deleted_definitions.Count -or
     $taskOverlay.missing_direct_targets.Count -or $taskOverlay.duplicate_outside_definitions.Count){throw 'Overlay ownership/closure/State-layout validation is incomplete.'}
  $taskOld=@($taskObjects|Where-Object{$_.path -eq $taskOverlay.replaces})
  if($taskOld.Count -ne 1 -or $taskOld[0].sha256 -ne $taskOverlay.original_object_sha256){throw 'Overlay does not replace exactly its validated original object.'}
  $taskObjects=@($taskObjects|Where-Object{$_.path -ne $taskOverlay.replaces})+@($taskOverlay.object)
  foreach($taskEntry in $taskOverlay.original_definitions){[void]$taskRemaining.Remove([uint64]$taskEntry)}
  foreach($taskEntry in $taskOverlay.unsupported_traces){[void]$taskRemaining.Add([uint64]$taskEntry)}
  $taskOverlayRecords+=@{metadata_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskMetadata).Hash.ToLowerInvariant();validation=$taskOverlay}
}
$taskSnapshot=Join-Path $taskBuild $(if($taskOverlayRecords.Count){'overlay-sources'}else{'sources'})
foreach($taskDirectory in @('windows','whole','fastaes')){[System.IO.Directory]::CreateDirectory((Join-Path $taskSnapshot $taskDirectory))|Out-Null}
$taskSources=@('il2cpp_bootstrap.cpp','filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp','signal_host.cpp','semaphore_host.cpp')
foreach($taskName in $taskSources){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskName) -Destination (Join-Path $taskSnapshot ('windows\'+$taskName))}
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.h'|ForEach-Object{Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $taskSnapshot ('windows\'+$_.Name))}
$taskWhole=Join-Path $PSScriptRoot '..\whole'
foreach($taskName in @('runtime.cpp','format.cpp')){Copy-Item -LiteralPath (Join-Path $taskWhole $taskName) -Destination (Join-Path $taskSnapshot ('whole\'+$taskName))}
Get-ChildItem -LiteralPath $taskWhole -Filter '*.h'|ForEach-Object{Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $taskSnapshot ('whole\'+$_.Name))}
foreach($taskName in @('elfload.c','elfload.h','elf64.h')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('..\fastaes\'+$taskName)) -Destination (Join-Path $taskSnapshot ('fastaes\'+$taskName))}
$taskSourceHashes=@{}
Get-ChildItem -LiteralPath $taskSnapshot -File -Recurse|ForEach-Object{$taskSourceHashes[$_.FullName.Substring($taskSnapshot.Length+1)]=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()}
$taskRecord=[ordered]@{status='host inputs frozen';source_sha256=$taskManifest.sha256;original_manifest_sha256=$taskManifest.original_manifest_sha256;original_toolchain=$taskManifest.toolchain;source_hashes=$taskSourceHashes;cxx_version=(& $Cxx --version|Select-Object -First 1);trace_header_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild 'il2cpp_traces.h')).Hash.ToLowerInvariant();runtime_state_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskRemill 'include\remill\Arch\AArch64\Runtime\State.h')).Hash.ToLowerInvariant()}
$taskRecord['overlays']=$taskOverlayRecords
$taskRecord['remaining_unsupported_traces']=@($taskRemaining|Sort-Object)
$taskRecordPath=Join-Path $taskBuild $(if($taskOverlayRecords.Count){'il2cpp_overlay_build_record.json'}else{'il2cpp_build_record.json'})
function Save-Il2cppRecord{[System.IO.File]::WriteAllText($taskRecordPath,($taskRecord|ConvertTo-Json -Depth 15),[System.Text.UTF8Encoding]::new($false))}
Save-Il2cppRecord
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-DIL2CPP_OVERLAY_COUNT=$($taskOverlayRecords.Count)","-DIL2CPP_REMAINING_UNSUPPORTED=$($taskRemaining.Count)","-I$taskRemill\include","-I$taskBuild",'-Wa,-mbig-obj')
$taskHarness=Join-Path $taskBuild 'il2cpp-bootstrap.o'
& $Cxx @taskCommon '-c' (Join-Path $taskSnapshot 'windows\il2cpp_bootstrap.cpp') '-o' $taskHarness
if($LASTEXITCODE -ne 0){$taskRecord.status='harness compile failed';Save-Il2cppRecord;throw 'IL2CPP harness compilation failed.'}
if($CompileOnly){$taskRecord.status='compile-only passed';Save-Il2cppRecord;Write-Output 'IL2CPP harness compile-only passed; guest code not executed.';return}
$taskIndex=0
foreach($taskObject in $taskObjects){
  $taskPath=Join-Path $taskBuild $taskObject.path
  if((Get-FileHash -Algorithm SHA256 -LiteralPath $taskPath).Hash.ToLowerInvariant() -ne $taskObject.sha256){throw "IL2CPP copied COFF shard differs: $taskPath"}
  $taskIndex++
  if($taskIndex%512 -eq 0){Write-Output "Verified $taskIndex/$($taskManifest.objects.Count) IL2CPP objects before link"}
}
$taskLoader=Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $taskSnapshot 'fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE -ne 0){$taskRecord.status='data loader compile failed';Save-Il2cppRecord;throw 'IL2CPP data loader compile failed.'}
$taskArguments=$taskCommon+@("-I$taskZlib\zlib-1.3.2",'-static',$taskHarness,$taskLoader)
foreach($taskName in $taskSources|Where-Object{$_ -ne 'il2cpp_bootstrap.cpp'}){$taskArguments+=Join-Path $taskSnapshot ('windows\'+$taskName)}
foreach($taskName in @('runtime.cpp','format.cpp')){$taskArguments+=Join-Path $taskSnapshot ('whole\'+$taskName)}
foreach($taskObject in $taskObjects){$taskArguments+=Join-Path $taskBuild $taskObject.path}
$taskExecutable=Join-Path $taskBuild $(if($taskOverlayRecords.Count){'bunker-il2cpp-overlay.exe'}else{'bunker-il2cpp-bootstrap.exe'})
$taskArguments+=@((Join-Path $taskZlib 'libz-inflate.a'),'-latomic','-lbcrypt','-o',$taskExecutable)
$taskResponse=Join-Path $taskBuild 'il2cpp-link.rsp'
$taskEscaped=foreach($taskArgument in $taskArguments){'"'+$taskArgument.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE -ne 0){$taskRecord.status='native link failed';Save-Il2cppRecord;throw 'Actual IL2CPP native link failed.'}
$taskRecord.status='native link passed';$taskRecord['executable_sha256']=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskExecutable).Hash.ToLowerInvariant();Save-Il2cppRecord
Write-Output $taskExecutable
if($Run){
  if(-not $Apk){throw '-Apk required for actual IL2CPP execution.'}
  $taskApk=(Resolve-Path -LiteralPath $Apk).ProviderPath
  if((Get-FileHash -Algorithm SHA256 -LiteralPath $taskApk).Hash.ToLowerInvariant() -ne $taskManifest.apk_sha256){throw 'Original APK differs from verified metadata.'}
  if(-not $StorageDirectory){$StorageDirectory=Join-Path $taskBuild 'data'}
  [System.IO.Directory]::CreateDirectory($StorageDirectory)|Out-Null
  $taskStorage=(Resolve-Path -LiteralPath $StorageDirectory).ProviderPath
  $taskRunArguments=@($taskLibrary,$taskApk,$taskStorage)
  if($GcSignalInit){$taskRunArguments+='--gc-signal-init'}
  & $taskExecutable @taskRunArguments 2>&1|Tee-Object -FilePath (Join-Path $taskBuild $(if($taskOverlayRecords.Count){'il2cpp-overlay-last-run.log'}else{'il2cpp-last-run.log'}))
  $taskRecord['run_exit_code']=$LASTEXITCODE;$taskRecord['gc_signal_init_requested']=[bool]$GcSignalInit;Save-Il2cppRecord
  if($LASTEXITCODE -ne 0){throw "Actual IL2CPP gate stopped with exit $LASTEXITCODE; inspect preserved first-blocker log."}
}
