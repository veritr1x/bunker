param([string]$Cxx='C:\mingw64\bin\g++.exe')
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\angle-native'))
$taskBuild=Join-Path $taskRoot 'src\out\BunkerVulkanAstc'
$taskDlls=Join-Path $taskRoot 'bundle\bin'
$taskOutput=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\graphics-probe-pinned-astc'))
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskOracle=Join-Path $taskBuild 'obj\third_party\astc-encoder\astcenc'
$taskObjects=@(Get-ChildItem -LiteralPath $taskOracle -File -Filter '*.o' | Sort-Object Name | Select-Object -ExpandProperty FullName)
if($taskObjects.Count -ne 22){throw "Expected22 official astcenc oracle objects; found$($taskObjects.Count)"}
$taskExe=Join-Path $taskOutput 'graphics-probe-astc.exe'
& $Cxx '-std=c++17' '-O2' '-Wall' '-Wextra' '-Werror' '-static' '-municode' "-I$taskRoot\src\third_party\astc-encoder\src\Source" (Join-Path $PSScriptRoot 'graphics_probe_astc.cpp') @taskObjects '-o' $taskExe
if($LASTEXITCODE){throw 'ASTC native acceptance probe compilation failed'}
$taskResult=Join-Path $taskOutput 'result.json'
$taskProcess=Start-Process -FilePath $taskExe -ArgumentList ('"'+$taskDlls+'"') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskResult -RedirectStandardError (Join-Path $taskOutput 'stderr.log')
if(-not $taskProcess.WaitForExit(60000)){$taskProcess.Kill();$taskProcess.WaitForExit();throw 'ASTC native probe timed out after60seconds'}
$taskProcess.WaitForExit()
$taskFiles=@($taskExe,(Join-Path $PSScriptRoot 'graphics_probe_astc.cpp'),(Join-Path $PSScriptRoot 'graphics_probe.cpp'),(Join-Path $taskDlls 'libEGL.dll'),(Join-Path $taskDlls 'libGLESv2.dll'))+$taskObjects
$taskEvidence=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');exit_code=$taskProcess.ExitCode;diagnostic_only=$true;source_setup=(Get-Content -Raw (Join-Path $taskRoot 'prepare-provenance.json')|ConvertFrom-Json);bundle_provenance=(Get-Content -Raw (Join-Path $taskRoot 'bundle\provenance.json')|ConvertFrom-Json);profile_patch=(Get-Content -Raw (Join-Path $taskRoot 'profile-patch.json')|ConvertFrom-Json);files=@($taskFiles|ForEach-Object { $taskItem=Get-Item -LiteralPath $_;[ordered]@{path=$taskItem.FullName;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$taskItem.Length}})}
$taskEvidence|ConvertTo-Json -Depth 20|Set-Content -LiteralPath (Join-Path $taskOutput 'provenance.json') -Encoding utf8
Get-Content -Raw -LiteralPath $taskResult
if($taskProcess.ExitCode){throw "ASTC capability acceptance failed exit$($taskProcess.ExitCode); see preserved evidence"}
