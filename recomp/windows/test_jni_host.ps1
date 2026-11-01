param(
    [Parameter(Mandatory = $true)][string]$JniHeader,
    [string]$BuildDirectory = (Join-Path $PSScriptRoot '..\work\windows-jni'),
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$LibMainDirectory,
    [string]$LibMainLibrary,
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $BuildDirectory | Out-Null
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
Copy-Item -LiteralPath $JniHeader -Destination (Join-Path $taskBuild 'jni.h')
$taskCommon = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-I$taskRemill\include", "-I$PSScriptRoot", "-I$taskBuild")
$taskRuntime = Join-Path $PSScriptRoot '..\whole\runtime.cpp'
$taskHost = Join-Path $PSScriptRoot 'jni_host.cpp'
$taskTest = Join-Path $taskBuild 'test-jni-host.exe'
& $Cxx @taskCommon (Join-Path $PSScriptRoot 'jni_host_test.cpp') $taskHost $taskRuntime '-static' '-latomic' '-o' $taskTest
if ($LASTEXITCODE -ne 0) { throw 'JNI host compilation failed.' }
& $taskTest
if ($LASTEXITCODE -ne 0) { throw 'JNI host checks failed.' }
$taskContextTest = Join-Path $taskBuild 'test-android-context.exe'
& $Cxx @taskCommon (Join-Path $PSScriptRoot 'android_context_test.cpp') (Join-Path $PSScriptRoot 'android_context.cpp') $taskHost $taskRuntime '-static' '-latomic' '-o' $taskContextTest
if ($LASTEXITCODE -ne 0) { throw 'Android context catalog compilation failed.' }
& $taskContextTest
if ($LASTEXITCODE -ne 0) { throw 'Android context catalog checks failed.' }
if ($LibMainDirectory) {
    if (-not $LibMainLibrary) { throw 'LibMainLibrary is required with LibMainDirectory.' }
    $taskMainDirectory = (Resolve-Path -LiteralPath $LibMainDirectory).ProviderPath
    $taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskMainDirectory 'manifest.json') | ConvertFrom-Json
    if ($taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.base -ne 0x40000000 -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count) { throw 'Incomplete or wrong-target libmain manifest.' }
    $taskImage = Join-Path $taskBuild 'libmain.so'
    Copy-Item -LiteralPath $LibMainLibrary -Destination $taskImage
    $taskLoader = Join-Path $taskBuild 'elfload.o'
    & $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
    if ($LASTEXITCODE -ne 0) { throw 'Windows data loader compilation failed.' }
    $taskArguments = $taskCommon + @("-I$taskMainDirectory", "-DLIBMAIN_IMAGE=`"$($taskImage.Replace('\', '/'))`"",
        (Join-Path $PSScriptRoot 'libmain_test.cpp'), $taskHost, $taskRuntime, $taskLoader)
    foreach ($taskObject in $taskManifest.objects) { $taskArguments += Join-Path $taskMainDirectory (Split-Path -Leaf $taskObject) }
    $taskGate = Join-Path $taskBuild 'bunker-libmain-x86_64.exe'
    $taskArguments += @('-static', '-latomic', '-o', $taskGate)
    & $Cxx @taskArguments
    if ($LASTEXITCODE -ne 0) { throw 'Real libmain Windows gate compilation failed.' }
    & $taskGate
    if ($LASTEXITCODE -ne 0) { throw 'Real libmain JNI_OnLoad gate failed.' }
    Write-Output $taskGate
}
