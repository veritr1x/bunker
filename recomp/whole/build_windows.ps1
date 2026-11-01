param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [Parameter(Mandatory = $true)][string]$Library,
    [ValidateSet('fastaes', 'fixture', 'semantics')][string]$Program = 'fastaes',
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe'
)
$ErrorActionPreference = 'Stop'
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskLibrary = (Resolve-Path -LiteralPath $Library).ProviderPath.Replace('\', '/')
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'manifest.json') | ConvertFrom-Json
if ($taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count) {
    throw 'Build requires complete Windows-target objects from whole/compile.py.'
}
$taskLoader = Join-Path $taskBuild 'elfload-win.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if ($LASTEXITCODE -ne 0) { throw 'Windows ELF data-loader compilation failed.' }
$taskSource = switch ($Program) {
    'fastaes' { 'fastaes_test.cpp' }
    'fixture' { 'fixture_test.cpp' }
    'semantics' { 'semantic_test.cpp' }
}
$taskDefine = switch ($Program) {
    'fastaes' { "-DLIB=`"$taskLibrary`"" }
    'fixture' { "-DFIXTURE_LIB=`"$taskLibrary`"" }
    'semantics' { "-DSEMANTIC_LIB=`"$taskLibrary`"" }
}
$taskExecutable = Join-Path $taskBuild "bunker-$Program-x86_64.exe"
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', $taskDefine,
    "-I$taskRemill\include", "-I$PSScriptRoot", "-I$PSScriptRoot\..\fastaes", "-I$taskBuild",
    (Join-Path $PSScriptRoot $taskSource), (Join-Path $PSScriptRoot 'runtime.cpp'), $taskLoader)
foreach ($taskObject in $taskManifest.objects) {
    $taskArguments += Join-Path $taskBuild (Split-Path -Leaf $taskObject)
}
$taskArguments += @('-static', '-latomic', '-o', $taskExecutable)
& $Cxx @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Windows executable build failed.' }
Write-Output $taskExecutable
