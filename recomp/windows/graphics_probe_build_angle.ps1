param([int]$Jobs=6,[switch]$GenerateOnly)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\angle-native'))
$taskSource=Join-Path $taskRoot 'src'
$taskGn=Join-Path $taskRoot 'tools\mingw64\bin\gn.exe'
$taskOldPath=$env:PATH;$taskOldCc=$env:CC;$taskOldCxx=$env:CXX
try{
  $env:PATH='C:\mingw64\bin;'+$env:PATH;$env:CC='gcc';$env:CXX='g++'
  python (Join-Path $PSScriptRoot 'graphics_probe_patch_angle.py')
  if($LASTEXITCODE){throw 'ANGLE patch preparation failed'}
  Push-Location -LiteralPath $taskSource
  try{
    python build/util/lastchange.py -o build/util/LASTCHANGE
    if($LASTEXITCODE){throw 'Chromium build timestamp generation failed'}
    python src/commit_id.py gen src/common/angle_commit.h
    if($LASTEXITCODE){throw 'ANGLE commit metadata generation failed'}
    $taskArguments=@'
target_cpu="x64"
is_debug=false
is_clang=false
is_component_build=true
angle_build_all=false
angle_build_tests=false
angle_enable_abseil=false
angle_enable_cl=false
angle_enable_metal=false
angle_enable_d3d9=false
angle_enable_d3d11=false
angle_enable_gl=false
angle_enable_vulkan=true
angle_enable_swiftshader=false
angle_has_astc_encoder=true
angle_shared_libvulkan=true
angle_use_custom_libvulkan=false
angle_enable_vulkan_validation_layers=false
angle_enable_vulkan_api_dump_layer=false
chrome_pgo_phase=0
use_custom_libcxx=false
use_libcxx_modules=false
use_lld=false
use_siso=false
use_sysroot=false
win_enable_cfg_guards=false
treat_warnings_as_errors=false
'@
    New-Item -ItemType Directory -Force -Path out\BunkerVulkanAstc | Out-Null
    $taskArguments | Set-Content -LiteralPath out\BunkerVulkanAstc\args.gn -Encoding utf8
    & $taskGn gen out/BunkerVulkanAstc --threads=1
    if($LASTEXITCODE){throw 'ANGLE GN generation failed'}
    if(-not $GenerateOnly){
      & C:\mingw64\bin\ninja.exe -C out/BunkerVulkanAstc "-j$Jobs" libEGL libGLESv2
      if($LASTEXITCODE){throw 'ANGLE native build failed'}
    }
  }finally{Pop-Location}
}finally{$env:PATH=$taskOldPath;$env:CC=$taskOldCc;$env:CXX=$taskOldCxx}
