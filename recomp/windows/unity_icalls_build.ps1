param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-unity-icalls'),
 [string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe',[switch]$Run,[switch]$CompileOnly)
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskMeta=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'icall_inputs.json')|ConvertFrom-Json
if($taskMeta.status -ne 'prepared' -or $taskMeta.host_commit -notlike '1942e24*' -or $taskMeta.registration_base_gate.commit -ne '574235f' -or $taskMeta.icall_profile.expected_count -ne 1987){throw 'Wrong frozen registration-only lineage.'}
function Native-Path([string]$p){if($p -match '^/mnt/([a-z])/(.*)$'){return $Matches[1].ToUpper()+':\'+$Matches[2].Replace('/','\')};if($p.StartsWith('/')){return (& wsl.exe -e wslpath -w $p).Trim()};return $p}
function Verify-Hash([string]$p,[string]$sha){if((Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() -ne $sha){throw "Frozen input changed: $p"}}
foreach($property in $taskMeta.source_hashes.PSObject.Properties){Verify-Hash (Join-Path $taskBuild ('sources\'+$property.Name)) $property.Value}
foreach($property in $taskMeta.registration_preparation_hashes.PSObject.Properties){Verify-Hash (Join-Path $taskBuild ('sources\windows\'+$property.Name)) $property.Value}
foreach($property in $taskMeta.remill_header_hashes.PSObject.Properties){Verify-Hash (Join-Path $taskBuild ('remill-include\'+$property.Name)) $property.Value}
foreach($property in $taskMeta.input_hashes.PSObject.Properties){Verify-Hash (Native-Path $property.Name) $property.Value}
foreach($module in $taskMeta.modules){Verify-Hash (Native-Path $module.data) $module.sha256}
Verify-Hash (Native-Path $taskMeta.apk) $taskMeta.apk_sha256
Verify-Hash (Native-Path $taskMeta.zlib_backend) $taskMeta.zlib_sha256
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild","-I$taskBuild\zlib-include",'-Wa,-mbig-obj')
$taskRecord=[ordered]@{status='frozen inputs verified';inputs_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild 'icall_inputs.json')).Hash.ToLowerInvariant();host_commit=$taskMeta.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1)}
$taskGenerated=@{}
foreach($taskName in @('combined_traces.h','combined_metadata.h','unity_bootstrap_data.h','il2cpp_data.h','il2cpp_module_exports.h','icall_inventory.h')){
 $taskGenerated[$taskName]=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild $taskName)).Hash.ToLowerInvariant()
 foreach($property in $taskMeta.input_hashes.PSObject.Properties){if(($property.Name -split '/')[-1] -eq $taskName){Verify-Hash (Join-Path $taskBuild $taskName) $property.Value}}
}
$taskRecord['generated_header_sha256']=$taskGenerated;$taskRecordPath=Join-Path $taskBuild 'icall_build_record.json'
function Save-Record{[System.IO.File]::WriteAllText($taskRecordPath,($taskRecord|ConvertTo-Json -Depth 15),[System.Text.UTF8Encoding]::new($false))}
Save-Record
& $Cxx @taskCommon '-c' (Join-Path $taskBuild 'sources\windows\unity_icalls.cpp') '-o' (Join-Path $taskBuild 'icall-harness.o')
if($LASTEXITCODE){$taskRecord.status='harness compile failed';Save-Record;throw 'Registration harness compile failed.'}
if($CompileOnly){$taskRecord.status='compile-only passed';Save-Record;return}
$taskIndex=0
foreach($object in $taskMeta.objects){Verify-Hash (Native-Path $object.path) $object.sha256;$taskIndex++;if($taskIndex%512 -eq 0){Write-Output "Verified $taskIndex/$($taskMeta.objects.Count) original guest COFF objects"}}
& $Cc '-O2' '-c' (Join-Path $taskBuild 'sources\fastaes\elfload.c') '-o' (Join-Path $taskBuild 'icall-elfload.o')
if($LASTEXITCODE){throw 'Frozen original ELF loader compile failed.'}
$taskArgs=$taskCommon+@('-static',(Join-Path $taskBuild 'icall-harness.o'),(Join-Path $taskBuild 'icall-elfload.o'))
foreach($name in @('jni_host','android_context','android_assets','apk_assets','java_native_libraries','filesystem','module_registry','pthread_host','libc','logging','zlib_host','signal_host','semaphore_host')){$taskArgs+=Join-Path $taskBuild ("sources\windows\$name.cpp")}
$taskGrowdownSource=Join-Path $taskBuild 'sources\windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($name in @('runtime','format')){$taskArgs+=Join-Path $taskBuild ("sources\whole\$name.cpp")}
foreach($object in $taskMeta.objects){$taskArgs+=Native-Path $object.path}
$taskExe=Join-Path $taskBuild 'bunker-unity-icalls.exe'
$taskArgs+=@((Native-Path $taskMeta.zlib_backend),'-latomic','-lbcrypt','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'icall-link.rsp';$taskEscaped=foreach($arg in $taskArgs){'"'+$arg.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskEscaped,[System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if($LASTEXITCODE){$taskRecord.status='native link failed';Save-Record;throw 'Registration-only native link failed.'}
$taskRecord.status='native link passed';$taskRecord['executable_sha256']=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskExe).Hash.ToLowerInvariant();Save-Record
if($Run){
 $taskStorage=Join-Path $taskBuild 'data';[System.IO.Directory]::CreateDirectory($taskStorage)|Out-Null
 & $taskExe (Join-Path $taskBuild 'native') (Native-Path $taskMeta.apk) $taskStorage 2>&1|Tee-Object -FilePath (Join-Path $taskBuild 'icall-run.log')
 $taskExit=$LASTEXITCODE;$taskRecord['run_exit_code']=$taskExit;Save-Record
 if($taskExit){throw "Registration diagnostic stopped with exit $taskExit; exact first failure preserved."}
}
