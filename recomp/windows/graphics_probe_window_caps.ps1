param([string]$Cxx='C:\mingw64\bin\g++.exe')
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskOutput=Join-Path $taskRoot 'work\graphics-probe-window-caps'
$taskAngle=Join-Path $taskRoot 'work\angle-native'
$taskInclude=Join-Path $taskRoot 'work\remill-src\include'
New-Item -ItemType Directory -Force -Path $taskOutput|Out-Null
$taskBase=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',$taskInclude,('-I'+(Join-Path $taskAngle 'src\include')),('-I'+(Join-Path $taskAngle 'src\third_party\vulkan-headers\src\include')))
$taskObjects=@()
foreach($taskSource in @('graphics_probe_window_caps.cpp','native_window.cpp','jni_host.cpp','..\whole\runtime.cpp')){
  $taskFile=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $taskSource))
  $taskObject=Join-Path $taskOutput (([IO.Path]::GetFileNameWithoutExtension($taskFile))+'.o')
  $taskStrict=@();if($taskSource -in @('graphics_probe_window_caps.cpp','native_window.cpp')){$taskStrict=@('-Wall','-Wextra','-Werror')}
  & $Cxx @taskBase @taskStrict '-c' $taskFile '-o' $taskObject
  if($LASTEXITCODE){throw "Window capability probe compile failed:$taskSource"}
  $taskObjects+=$taskObject
}
$taskExe=Join-Path $taskOutput 'test.exe'
& $Cxx '-static' '-municode' @taskObjects '-pthread' '-latomic' '-luser32' '-o' $taskExe
if($LASTEXITCODE){throw 'Window capability probe link failed'}
$taskProcess=Start-Process -FilePath $taskExe -ArgumentList ('"'+(Join-Path $taskAngle 'bundle\bin')+'"') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'result.json') -RedirectStandardError (Join-Path $taskOutput 'stderr.log')
if(-not $taskProcess.WaitForExit(60000)){$taskProcess.Kill();$taskProcess.WaitForExit();throw 'Window capability probe timed out'}
$taskProcess.WaitForExit()
Get-Content -Raw (Join-Path $taskOutput 'result.json')
if($taskProcess.ExitCode){throw "Actual HWND scaling capability probe failed exit$($taskProcess.ExitCode)"}
