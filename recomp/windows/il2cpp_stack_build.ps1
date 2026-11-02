param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskInput=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'il2cpp_stack_inputs.json')|ConvertFrom-Json
if($taskInput.status -ne 'prepared' -or $taskInput.trace_count -ne 393781 -or $taskInput.remaining_unsupported -ne 189){throw 'Incomplete stack gate input proof'}
function Stack-Path([string]$path){if($path.StartsWith('/mnt/c/')){return 'C:\'+$path.Substring(7).Replace('/','\')}return $path}
function Stack-Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
foreach($taskGroup in @(@{root=(Join-Path $taskBuild 'sources');values=$taskInput.source_sha256},@{root=$taskBuild;values=$taskInput.frozen_support_sha256},@{root=$taskBuild;values=$taskInput.headers_sha256})){
 foreach($taskProperty in $taskGroup.values.PSObject.Properties){if((Stack-Hash (Join-Path $taskGroup.root $taskProperty.Name)) -ne $taskProperty.Value){throw "Frozen source/support differs: $($taskProperty.Name)"}}
}
$taskBaseline=Stack-Path $taskInput.baseline
foreach($taskObject in $taskInput.objects){if((Stack-Hash (Join-Path $taskBaseline $taskObject.path)) -ne $taskObject.sha256){throw "Accepted object differs: $($taskObject.path)"}}
$taskSource=Join-Path $taskBuild 'sources\recomp'
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild",'-Wa,-mbig-obj')
$taskHarness=Join-Path $taskBuild 'il2cpp-stack.o';$taskLoader=Join-Path $taskBuild 'elfload.o';$taskExe=Join-Path $taskBuild 'il2cpp-stack.exe'
& $Cxx @taskCommon '-c' (Join-Path $taskSource 'windows\il2cpp_stack.cpp') '-o' $taskHarness
if($LASTEXITCODE){throw 'Stack harness compile failed'}
& $Cc '-O2' '-c' (Join-Path $taskSource 'fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Stack ELF data loader compile failed'}
$taskArgs=$taskCommon+@("-I$taskBuild\zlib",'-static',$taskHarness,$taskLoader)
foreach($taskName in @('filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp','signal_host.cpp','semaphore_host.cpp')){$taskArgs+=Join-Path $taskSource ('windows\'+$taskName)}
$taskGrowdownSource=Join-Path $taskSource 'windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($taskName in @('runtime.cpp','format.cpp')){$taskArgs+=Join-Path $taskSource ('whole\'+$taskName)}
foreach($taskObject in $taskInput.objects){$taskArgs+=Join-Path $taskBaseline $taskObject.path}
$taskArgs+=@((Join-Path $taskBuild 'zlib\libz-inflate.a'),'-latomic','-lbcrypt','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'il2cpp-stack-link.rsp'
$taskEscaped=foreach($taskArgument in $taskArgs){'"'+$taskArgument.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE){throw 'Actual stack helper native link failed'}
$taskRecord=[ordered]@{status='native link passed';inputs_sha256=(Stack-Hash (Join-Path $taskBuild 'il2cpp_stack_inputs.json'));executable_sha256=(Stack-Hash $taskExe);response_sha256=(Stack-Hash $taskResponse);host_commit=$taskInput.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1);gate=$taskInput.gate}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'il2cpp_stack_build.json'),($taskRecord|ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
Write-Output $taskExe
