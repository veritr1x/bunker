param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe'
)
$ErrorActionPreference = 'Stop'
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskRuntime = Join-Path $PSScriptRoot '..\whole\runtime.cpp'
$taskCommon = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-I$taskRemill\include", "-I$PSScriptRoot", "-I$taskBuild")
$taskUnit = Join-Path $taskBuild 'test-module-registry.exe'
& $Cxx @taskCommon (Join-Path $PSScriptRoot 'module_registry_test.cpp') (Join-Path $PSScriptRoot 'module_registry.cpp') $taskRuntime '-static' '-latomic' '-o' $taskUnit
if ($LASTEXITCODE -ne 0) { throw 'Module registry compilation failed.' }
& $taskUnit
if ($LASTEXITCODE -ne 0) { throw 'Module registry unit tests failed.' }
$taskLoader = Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if ($LASTEXITCODE -ne 0) { throw 'ELF data loader compilation failed.' }
$taskArguments = $taskCommon + @("-DLIBMAIN_IMAGE=`"$($taskBuild.Replace('\', '/'))/libmain.so`"",
    "-DSYNTHETIC_UNITY_IMAGE=`"$($taskBuild.Replace('\', '/'))/synthetic-unity.so`"",
    (Join-Path $PSScriptRoot 'loader_test.cpp'), (Join-Path $PSScriptRoot 'jni_host.cpp'),
    (Join-Path $PSScriptRoot 'module_registry.cpp'), $taskRuntime, $taskLoader)
foreach ($taskName in @('main', 'unity')) {
    $taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBuild "$taskName\manifest.json") | ConvertFrom-Json
    if ($taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count) { throw 'Incomplete or wrong-target loader input manifest.' }
    foreach ($taskObject in $taskManifest.objects) { $taskArguments += Join-Path $taskBuild "$taskName\$(Split-Path -Leaf $taskObject)" }
}
$taskExecutable = Join-Path $taskBuild 'bunker-loader-x86_64.exe'
$taskArguments += @('-static', '-latomic', '-o', $taskExecutable)
& $Cxx @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Native loader gate compilation failed.' }
foreach ($taskScenario in @('success', 'missing-symbol')) {
    & $taskExecutable $taskScenario
    if ($LASTEXITCODE -ne 0) { throw "Native loader positive gate failed: $taskScenario" }
}
foreach ($taskScenario in @('missing-module', 'bad-version')) {
    $taskErrorFile = Join-Path $taskBuild "$taskScenario.stderr.txt"
    & $taskExecutable $taskScenario 2> $taskErrorFile
    if ($LASTEXITCODE -eq 0) { throw "Native loader negative gate unexpectedly succeeded: $taskScenario" }
    $taskError = Get-Content -Raw -LiteralPath $taskErrorFile
    $taskExpected = if ($taskScenario -eq 'bad-version') { 'Unsupported VM version' } else { 'Unable to load library' }
    if (-not $taskError.Contains($taskExpected)) { throw "Native loader negative gate lacked diagnostic: $taskScenario" }
    Write-Output "Native loader negative gate passed: $taskScenario"
}
Write-Output $taskExecutable
$global:LASTEXITCODE = 0 # Expected negative subprocess statuses were checked above.
