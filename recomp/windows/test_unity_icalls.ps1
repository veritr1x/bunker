param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-unity-icalls'))
$ErrorActionPreference='Stop';$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskMeta=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'icall_inputs.json')|ConvertFrom-Json
$taskRecord=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'icall_build_record.json')|ConvertFrom-Json
$taskLog=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'icall-run.log');$taskChecks=0
function Check([bool]$ok,[string]$why){$script:taskChecks++;if(-not $ok){throw $why}}
Check ($taskRecord.status -eq 'native link passed' -and $taskRecord.run_exit_code -eq 0) 'Actual registration-only run failed.'
Check ($taskMeta.host_commit -like '1942e24*' -and $taskMeta.registration_base_gate.commit -eq '574235f') 'Frozen baseline differs.'
Check ($taskMeta.objects.Count -eq 3548 -and $taskMeta.union_trace_count -eq 453342 -and $taskMeta.missing_direct_guest_targets.Count -eq 0) 'Original object/trace ownership differs.'
foreach($entry in @(@('Unity',417),@('IL2CPP',9))){
 $taskName=$entry[0];$taskCount=$entry[1]
 Check (([regex]::Matches($taskLog,"(?m)^$taskName constructor ")).Count -eq $taskCount) "$taskName constructors differ."
 Check (([regex]::Matches($taskLog,"(?m)^$taskName finalizer ")).Count -eq 2) "$taskName finalizers differ."
}
Check ($taskLog.Contains('Original APIloader passed:dlopen1,dlsym222,dlerror444,9 constructors,refcount1,222 actual slots')) 'Original APIloader prefix missing.'
Check ($taskLog.Contains('owned NativeString destructor once')) 'Actual owned NativeString cleanup missing.'
Check (([regex]::Matches($taskLog,'Original startup queue count=0 active=0 dirty=0')).Count -eq 3) 'Real empty queue snapshots missing.'
Check (([regex]::Matches($taskLog,'JNI-cache snapshot entries=0')).Count -eq 5) 'JNI cleanup closures missing.'
Check ([regex]::IsMatch($taskLog,'ICALL preconditions observers=[0-9a-fx]+/[0-9a-fx]+/0 map=0x879a5b78/0/0 init=0 gc=0/0')) 'Actual pristine preconditions differ.'
Check (([regex]::Matches($taskLog,'(?m)^ICALL register ')).Count -eq 1987) 'Actual AddInternalCall count differs.'
Check (([regex]::Matches($taskLog,'OLD_UNSUPPORTED_BODY_NOT_CALLED')).Count -eq 3) 'Stored unsupported native body boundary missing.'
Check ($taskLog.Contains('ICALL registration/lookup passed:1987 exact original name/target pairs,1987 actual resolve_icall results')) 'Original registration/lookup verification missing.'
Check (([regex]::Matches($taskLog,'(?m)^ICALL actual __cxa_atexit callback=0x8257cdc0 object=0x879a5b70 dso=0x8740c790 LR=0x820ccca0')).Count -eq 1) 'Actual map destructor registration ownership differs.'
Check (([regex]::Matches($taskLog,'(?m)^ICALL actual registered destructor begin callback=0x8257cdc0 object=0x879a5b70 dso=0x8740c790 filter=0x8740c790')).Count -eq 1) 'Actual map destructor/filter invocation differs.'
Check (([regex]::Matches($taskLog,'(?m)^ICALL actual registered destructor complete once; owned blocks freed=')).Count -eq 1) 'Actual map allocation cleanup missing/repeated.'
Check ($taskLog.Contains('Real guest384764 closed IL2CPP and erased node') -and $taskLog.Contains('Actual JNI_OnUnload7043ab34 returned while IL2CPP remained live/refcount1')) 'Real supported teardown route missing.'
Check ($taskLog.Contains('ORIGINAL ICALLS bounded gate passed:417+9')) 'Final registration-only proof missing.'
Check ($taskLog.Contains('no init/config/GC/managed/RegisterModules/native-target execution')) 'Bounded execution exclusions missing.'
$taskExe=Join-Path $taskBuild 'bunker-unity-icalls.exe'
Check ((Get-FileHash -LiteralPath $taskExe -Algorithm SHA256).Hash.ToLowerInvariant() -eq $taskRecord.executable_sha256) 'Executable differs from recorded run.'
$taskOld=$taskMeta.registration_base_gate.directory -replace '^/mnt/c/','C:/'
Check ((Get-FileHash -LiteralPath (Join-Path $taskOld 'bunker-unity-api-loader.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -eq $taskMeta.registration_base_gate.executable_sha256) 'Prior executable changed.'
Check ((Get-FileHash -LiteralPath (Join-Path $taskOld 'api_loader_inputs.json') -Algorithm SHA256).Hash.ToLowerInvariant() -eq $taskMeta.registration_base_gate.inputs_sha256) 'Prior input metadata changed.'
$taskInventory=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'audit\icall-registration.json')|ConvertFrom-Json
$taskActual=[regex]::Matches($taskLog,'(?m)^ICALL register (\d+) name=(.*?) literal=(0x[0-9a-f]+) native=(0x[0-9a-f]+) wrapper=(0x[0-9a-f]+) stored-only')
for($taskI=0;$taskI -lt 1987;$taskI++){
 $taskRow=$taskInventory.resolved[$taskI];$taskMatch=$taskActual[$taskI]
 Check ([int]$taskMatch.Groups[1].Value -eq $taskI+1 -and $taskMatch.Groups[2].Value -ceq $taskRow.name -and [Convert]::ToUInt64($taskMatch.Groups[3].Value.Substring(2),16) -eq 1879048192+$taskRow.name_rva -and [Convert]::ToUInt64($taskMatch.Groups[4].Value.Substring(2),16) -eq $taskRow.native_guest -and [Convert]::ToUInt64($taskMatch.Groups[5].Value.Substring(2),16) -eq 1879048192+$taskRow.wrapper) "Actual registration journal row $taskI differs from original proof."
}
$taskBadDir=Join-Path $taskBuild 'negative-native';[System.IO.Directory]::CreateDirectory($taskBadDir)|Out-Null
foreach($taskName in @('libunity.so','libil2cpp.so')){[System.IO.File]::WriteAllText((Join-Path $taskBadDir $taskName),'invalid original ELF')}
$taskBadApk=Join-Path $taskBuild 'negative.apk';[System.IO.File]::WriteAllText($taskBadApk,'invalid original APK');$taskApk=$taskMeta.apk -replace '^/mnt/c/','C:/'
$taskResults=@()
foreach($taskCase in @(
 @{name='self-test';args=@('--self-test');exit=0;message='ICALL isolated precondition checks8 passed'},
 @{name='usage';args=@();exit=2;message='Usage:'},
 @{name='wrong-module';args=@($taskBadDir,$taskApk,(Join-Path $taskBuild 'negative-data'));exit=1;message='original input SHA256 differs'},
 @{name='wrong-apk';args=@((Join-Path $taskBuild 'native'),$taskBadApk,(Join-Path $taskBuild 'negative-data'));exit=1;message='original input SHA256 differs'}
)){
 $taskPrior=$ErrorActionPreference;$ErrorActionPreference='Continue';$taskArguments=$taskCase.args;$taskOutput=(& $taskExe @taskArguments 2>&1|Out-String);$taskExit=$LASTEXITCODE;$ErrorActionPreference=$taskPrior
 [System.IO.File]::WriteAllText((Join-Path $taskBuild ($taskCase.name+'.log')),$taskOutput)
 Check ($taskExit -eq $taskCase.exit -and $taskOutput.Contains($taskCase.message)) "Isolated/negative $($taskCase.name) differs."
 Check (-not $taskOutput.Contains('Unity constructor ')) "Isolated/negative $($taskCase.name) executed constructors."
 $taskResults+=@{name=$taskCase.name;exit=$taskExit}
}
$taskResult=@{status='passed';checks=$taskChecks;negative_cases=$taskResults;executable_sha256=$taskRecord.executable_sha256;host_commit=$taskMeta.host_commit;registration_count=1987;lookup_count=1987;stored_unsupported_native_targets=3;map_destructor_calls=1}
[System.IO.File]::WriteAllText((Join-Path $taskBuild 'icall-test-result.json'),($taskResult|ConvertTo-Json -Depth 6),[System.Text.UTF8Encoding]::new($false))
Write-Output "$taskChecks actual registration/source/lifecycle/negative checks passed;1987 native pointers were never invoked."
