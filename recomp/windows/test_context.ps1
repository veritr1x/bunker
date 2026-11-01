param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-context'),[string]$ApkMetadata=(Join-Path $PSScriptRoot '..\work\windows-files'),[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop';$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath;$taskApk=(Resolve-Path -LiteralPath $ApkMetadata).ProviderPath
$taskManifest=Get-Content -Raw (Join-Path $taskBuild 'guest\manifest.json')|ConvertFrom-Json
if($taskManifest.base -ne 0x73000000 -or $taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count){throw 'Incomplete Context fixture'}
$taskLoader=Join-Path $taskBuild 'elfload.o'; & $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Loader compilation failed'}
$taskArgs=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$PSScriptRoot\..\work\remill-src\include","-I$taskBuild\guest","-I$taskApk","-DCONTEXT_IMAGE=`"$($taskBuild.Replace('\','/'))/context.so`"",(Join-Path $PSScriptRoot 'context_intent_test.cpp'),(Join-Path $PSScriptRoot 'android_context.cpp'),(Join-Path $PSScriptRoot 'jni_host.cpp'),(Join-Path $PSScriptRoot '..\whole\runtime.cpp'),$taskLoader)
foreach($taskObject in $taskManifest.objects){$taskArgs+=Join-Path $taskBuild "guest\$(Split-Path -Leaf $taskObject)"}
$taskExe=Join-Path $taskBuild 'test-context.exe';$taskArgs+=@('-static','-latomic','-o',$taskExe)
& $Cxx @taskArgs;if($LASTEXITCODE){throw 'Context compilation failed'}
& $taskExe;if($LASTEXITCODE){throw 'Context checks failed'}
