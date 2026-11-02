param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'il2cpp_save_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or $taskInput.trace_count -ne 393781 -or $taskInput.remaining_unsupported -ne 189){throw 'Incomplete save gate input proof'}
function Save-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Save-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
foreach($taskGroup in @(@{root=(Join-Path $taskBuild 'sources');values=$taskInput.source_sha256},@{root=$taskBuild;values=$taskInput.frozen_support_sha256},@{root=$taskBuild;values=$taskInput.headers_sha256})){
 foreach($taskProperty in $taskGroup.values.PSObject.Properties){if((Save-Hash (Join-Path $taskGroup.root $taskProperty.Name)) -ne $taskProperty.Value){throw "Frozen source/support differs: $($taskProperty.Name)"}}
}
$taskBaseline=Save-Path $taskInput.baseline
foreach($taskObject in $taskInput.objects){if((Save-Hash (Join-Path $taskBaseline $taskObject.path)) -ne $taskObject.sha256){throw "Accepted object differs: $($taskObject.path)"}}
$taskSource=Join-Path $taskBuild 'sources\recomp'
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild",'-Wa,-mbig-obj')
$taskHarness=Join-Path $taskBuild 'il2cpp-save.o';$taskLoader=Join-Path $taskBuild 'elfload.o';$taskExe=Join-Path $taskBuild 'il2cpp-save.exe'
& $Cxx @taskCommon '-c' (Join-Path $taskSource 'windows\il2cpp_save.cpp') '-o' $taskHarness
if($LASTEXITCODE){throw 'Save harness compile failed'}
& $Cc '-O2' '-c' (Join-Path $taskSource 'fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Save ELF data loader compile failed'}
$taskArgs=$taskCommon+@("-I$taskBuild\zlib",'-static',$taskHarness,$taskLoader)
foreach($taskName in @('filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp','signal_host.cpp','semaphore_host.cpp','nonlocal_jmp.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
$taskGrowdownSource=Join-Path $taskSource 'windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($taskName in @('runtime.cpp','format.cpp')){$taskArgs+=Join-Path $taskSource ('whole\'+$taskName)}
foreach($taskObject in $taskInput.objects){$taskArgs+=Join-Path $taskBaseline $taskObject.path}
foreach($taskObject in $taskInput.fixture.objects){$taskPath=Save-Path $taskObject.path;if((Save-Hash $taskPath) -ne $taskObject.sha256){throw 'Strict NDK object changed'};$taskArgs+=$taskPath}
$taskArgs+=@((Join-Path $taskBuild 'zlib\libz-inflate.a'),'-latomic','-lbcrypt','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'il2cpp-save-link.rsp'
$taskEscaped=foreach($taskArgument in $taskArgs){'"'+$taskArgument.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE){throw 'Actual save helper native link failed'}
$taskRecord=[ordered]@{status='native link passed';inputs_sha256=(Save-Hash (Join-Path $taskBuild 'il2cpp_save_inputs.json'));executable_sha256=(Save-Hash $taskExe);response_sha256=(Save-Hash $taskResponse);host_commit=$taskInput.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1);gate=$taskInput.gate}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'il2cpp_save_build.json'),($taskRecord|ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
Write-Output $taskExe
