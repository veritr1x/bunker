param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'game_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or $taskInput.union_trace_count -ne 456684 -or $taskInput.objects.Count -ne 3575){throw 'Incomplete final dual-engine input proof'}
function Game-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Game-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
foreach($taskGroup in @(@{root=(Join-Path $taskBuild 'sources');values=$taskInput.source_sha256},@{root=$taskBuild;values=$taskInput.frozen_support_sha256},@{root=$taskBuild;values=$taskInput.generated_header_sha256})){
 foreach($taskProperty in $taskGroup.values.PSObject.Properties){if((Game-Hash (Join-Path $taskGroup.root $taskProperty.Name)) -ne $taskProperty.Value){throw "Frozen source/support differs: $($taskProperty.Name)"}}
}
foreach($taskObject in $taskInput.objects){if((Game-Hash (Game-Path $taskObject.path)) -ne $taskObject.sha256){throw "Accepted object differs: $($taskObject.path)"}}
if((Game-Hash (Join-Path $taskBuild 'libz-inflate.a')) -ne $taskInput.zlib_sha256){throw 'Frozen zlib backend differs'}
$taskSource=Join-Path $taskBuild 'sources\recomp'
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild","-I$taskBuild\zlib-include","-I$taskBuild\angle-include",'-Wa,-mbig-obj')
$taskHarness=Join-Path $taskBuild 'game-bootstrap.o';$taskLoader=Join-Path $taskBuild 'elfload.o';$taskExe=Join-Path $taskBuild 'bunker-game-bootstrap.exe'
& $Cxx @taskCommon '-c' (Join-Path $taskSource 'windows\game_bootstrap.cpp') '-o' $taskHarness
if($LASTEXITCODE){throw 'Game bootstrap harness compile failed'}
& $Cc '-O2' '-c' (Join-Path $taskSource 'fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Game ELF data loader compile failed'}
$taskArgs=$taskCommon+@('-static',$taskHarness,$taskLoader)
foreach($taskName in @('jni_host.cpp','java_native_libraries.cpp','android_context.cpp','windows_android_id.cpp','jni_interface_proxy.cpp','android_asset_pack_wrapper.cpp','android_shared_preferences.cpp','windows_shared_preferences.cpp','android_internal_storage.cpp','android_obb_storage.cpp','android_assets.cpp','apk_assets.cpp','native_window.cpp','unity_lifecycle.cpp','signal_host.cpp','semaphore_host.cpp','nonlocal_jmp.cpp','audio_volume.cpp','audio_volume_session.cpp','egl_host.cpp','gl_host.cpp','filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
$taskGrowdownSource=Join-Path $taskSource 'windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($taskName in @('runtime.cpp','format.cpp')){$taskArgs+=Join-Path $taskSource ('whole\'+$taskName)}
foreach($taskObject in $taskInput.objects){$taskArgs+=Game-Path $taskObject.path}
$taskArgs+=@((Join-Path $taskBuild 'libz-inflate.a'),'-Wl,--wrap=sub_825b0544','-latomic','-lbcrypt','-luser32','-lgdi32','-lole32','-luuid','-ladvapi32','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'game-bootstrap-link.rsp'
$taskEscaped=foreach($taskArgument in $taskArgs){'"'+$taskArgument.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE){throw 'Dual-engine natural-frame native link failed'}
$taskRecord=[ordered]@{status='native link passed';inputs_sha256=(Game-Hash (Join-Path $taskBuild 'game_inputs.json'));executable_sha256=(Game-Hash $taskExe);response_sha256=(Game-Hash $taskResponse);host_commit=$taskInput.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1);trace_count=$taskInput.union_trace_count;objects=$taskInput.objects.Count}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'game_build.json'),($taskRecord|ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
Write-Output $taskExe
