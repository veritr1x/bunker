param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-asset-java'),[string]$ContextDirectory=(Join-Path $PSScriptRoot '..\work\windows-context'),[string]$Apk=(Join-Path $PSScriptRoot '..\work\windows-files\base.apk'),[string]$ZlibDirectory=(Join-Path $PSScriptRoot '..\work\zlib-native'),[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop';$taskBuild=(Resolve-Path $BuildDirectory).ProviderPath;$taskContext=(Resolve-Path $ContextDirectory).ProviderPath;$taskApk=(Resolve-Path $Apk).ProviderPath
$taskManifest=Get-Content -Raw (Join-Path $taskContext 'guest\manifest.json')|ConvertFrom-Json
if($taskManifest.base -ne 0x73000000 -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count){throw 'Incomplete NDK asset caller fixture'}
$taskLoader=Join-Path $taskBuild 'elfload.o'; & $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader;if($LASTEXITCODE){throw 'Loader failed'}
$taskArgs=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$PSScriptRoot\..\work\remill-src\include","-I$taskContext\guest","-I$taskBuild","-I$ZlibDirectory\zlib-1.3.2","-DASSET_CONTEXT_IMAGE=`"$($taskContext.Replace('\','/'))/context.so`"",(Join-Path $PSScriptRoot 'asset_java_test.cpp'),(Join-Path $PSScriptRoot 'android_assets.cpp'),(Join-Path $PSScriptRoot 'apk_assets.cpp'),(Join-Path $PSScriptRoot 'jni_host.cpp'),(Join-Path $PSScriptRoot '..\whole\runtime.cpp'),$taskLoader)
foreach($taskObject in $taskManifest.objects){$taskArgs+=Join-Path $taskContext "guest\$(Split-Path -Leaf $taskObject)"}
$taskExe=Join-Path $taskBuild 'test-asset-java.exe';$taskArgs+=@((Join-Path $ZlibDirectory 'libz-inflate.a'),'-static','-latomic','-o',$taskExe)
& $Cxx @taskArgs;if($LASTEXITCODE){throw 'Asset Java gate compilation failed'}
& $taskExe $taskApk (Join-Path $taskBuild 'streams.apk');if($LASTEXITCODE){throw 'Asset Java gate failed'}
