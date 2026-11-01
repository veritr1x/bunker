param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-combined-modules'))
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskMeta=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'combined_inputs.json')|ConvertFrom-Json
$taskRecord=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'combined_build_record.json')|ConvertFrom-Json
$taskLog=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'combined-run.log')
$taskChecks=0
function Check([bool]$ok,[string]$why){$script:taskChecks++;if(-not $ok){throw $why}}
Check ($taskRecord.status -eq 'native link passed' -and $taskRecord.run_exit_code -eq 0) 'Actual combined run did not pass.'
Check ($taskMeta.host_commit -like '1942e24*') 'Unexpected host source cohort.'
Check ($taskMeta.modules.Count -eq 2 -and $taskMeta.objects.Count -eq 3548) 'Wrong module/object cohort.'
Check ($taskMeta.union_trace_count -eq 453342 -and $taskMeta.missing_direct_guest_targets.Count -eq 0) 'Wrong union trace ownership/closure.'
foreach($entry in @(@('Unity',417),@('IL2CPP',9))){
 $taskName=$entry[0];$taskCount=$entry[1]
 Check (([regex]::Matches($taskLog,"(?m)^$taskName constructor ")).Count -eq $taskCount) "$taskName constructor count differs."
 Check (([regex]::Matches($taskLog,"(?m)^$taskName finalizer ")).Count -eq 2) "$taskName finalizer count differs."
}
Check ($taskLog.Contains('actual destructor once') -and $taskLog.Contains('/data/app/bunker/lib/arm64/libil2cpp.so')) 'Actual helper/string gate absent.'
Check ($taskLog.Contains('COMBINED bounded gate passed:417+9')) 'Final bounded proof marker absent.'
Check ((Get-FileHash (Join-Path $taskBuild 'bunker-combined-modules.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -eq $taskRecord.executable_sha256) 'Executable differs from recorded run.'
$taskExe=Join-Path $taskBuild 'bunker-combined-modules.exe'
$taskBadDir=Join-Path $taskBuild 'negative-native';[System.IO.Directory]::CreateDirectory($taskBadDir)|Out-Null
foreach($taskName in @('libunity.so','libil2cpp.so')){[System.IO.File]::WriteAllText((Join-Path $taskBadDir $taskName),'invalid original ELF')}
$taskBadApk=Join-Path $taskBuild 'negative.apk';[System.IO.File]::WriteAllText($taskBadApk,'invalid original APK')
$taskApk=$taskMeta.apk -replace '^/mnt/c/','C:/'
$taskResults=@()
foreach($taskCase in @(
 @{name='usage';args=@();exit=2;message='Usage:'},
 @{name='wrong-module';args=@($taskBadDir,$taskApk,(Join-Path $taskBuild 'negative-data'));exit=1;message='original input SHA256 differs'},
 @{name='wrong-apk';args=@((Join-Path $taskBuild 'native'),$taskBadApk,(Join-Path $taskBuild 'negative-data'));exit=1;message='original input SHA256 differs'}
)){
 $taskPrior=$ErrorActionPreference;$ErrorActionPreference='Continue'
 $taskArguments=$taskCase.args;$taskOutput=(& $taskExe @taskArguments 2>&1|Out-String);$taskExit=$LASTEXITCODE;$ErrorActionPreference=$taskPrior
 [System.IO.File]::WriteAllText((Join-Path $taskBuild ($taskCase.name+'.log')),$taskOutput)
 Check ($taskExit -eq $taskCase.exit -and $taskOutput.Contains($taskCase.message)) "Negative $($taskCase.name) did not reject truthfully."
 Check (-not $taskOutput.Contains('Unity constructor ')) "Negative $($taskCase.name) reached guest constructors."
 $taskResults+=@{name=$taskCase.name;exit=$taskExit}
}
$taskResult=@{status='passed';checks=$taskChecks;negative_cases=$taskResults;executable_sha256=$taskRecord.executable_sha256;host_commit=$taskMeta.host_commit}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'combined-test-result.json'),($taskResult|ConvertTo-Json -Depth 6),[System.Text.UTF8Encoding]::new($false))
Write-Output "$taskChecks combined lifecycle/source/input checks passed; no IL2CPP API bodies invoked."
