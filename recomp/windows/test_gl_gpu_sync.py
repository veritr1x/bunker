"""Actual native ANGLE sync lifecycle through typed NDK callers."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('gl_gpu_sync_guest.c','gl_gpu_sync_test.cpp','test_gl_gpu_sync.py')
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def names(root):
 cpp=(root/'windows/gl_host.cpp').read_text();draw=re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types',cpp,re.S);assert draw
 ds=re.findall(r'X\((gl\w+),',draw[1]);values=[];block=cpp[cpp.index('const char *const names[]='):cpp.index('std::string Hex(')]
 for m in re.finditer(r'#include "([^"]+)"|GL_DRAW_API\(DRAW_NAME\)|"(gl\w+)"',block):values+=re.findall(r'GL_[A-Z0-9_]+\((gl\w+),',(root/'windows'/m[1]).read_text())if m[1]else [m[2]]if m[2]else ds
 assert len(values)==len(set(values));return values
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--production-pins',type=Path,default=W/'gpu-sync-source-preparation1/production-sources1.json');a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  manifest=json.loads(a.production_pins.read_text());production=manifest['production_sources'];pin(a.production_pins);source=out/'source';required={'windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','fastaes/elfload.c'}
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for p in(HERE.parent/folder).iterdir():
    relative=folder+'/'+p.name
    if p.is_file()and(p.suffix in('.h','.inc','.py')or relative in required or p.name in OWN):shutil.copyfile(p,target/p.name)
  for name,h in production.items():assert sha(source/name)==h==sha(HERE.parent/name);pin(HERE.parent/name)
  for name in OWN:pin(HERE/name)
  base=W/'windows-first-frame-program-cache1/sources/recomp';old=names(base);new=names(source);assert new==old+['glFenceSync','glClientWaitSync','glDeleteSync'];pin(base/'windows/gl_host.cpp');(out/'gpu_sync_old_commands.h').write_text('#pragma once\nstatic const char*const kOldGpuSyncCommands[]={'+','.join(map(json.dumps,old))+'};\n')
  ndkroot=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64');ndk=ndkroot/'bin/aarch64-linux-android24-clang';tool=W/'fp-numeric-minmax-preparation1/toolchains/14f6409b2d88fbde-6dd3ed0e502e37b9';angle=W/'angle-native';dlls=angle/'bundle/bin';cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe')
  for p in(ndk,tool/'remill-lift',tool/'aarch64.bc',cxx,cc):pin(p)
  for root in(dlls,angle/'src/include'):
   for p in root.rglob('*'):
    if p.is_file():pin(p)
  for folder in('GLES2','GLES3','EGL','KHR'):
   for p in(ndkroot/'sysroot/usr/include'/folder).glob('*.h'):pin(p)
  (out/'source-binding.json').write_text(json.dumps(dict(production_sources=production,owned_sources={n:sha(source/'windows'/n)for n in OWN},baseline_commands=old,new_commands=new,source_pins_manifest=desc(a.production_pins)),indent=2)+'\n')
  guest=out/'gpu_sync.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'windows/gl_gpu_sync_guest.c','-o',guest],'compile-NDK')
  translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x5e000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK');m=json.loads((translated/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(translated),'-I'+wp(out),'-I'+wp(angle/'src/include'),'-DGL_GPU_SYNC_LIBRARY="'+wp(guest)+'"','-DGL_GPU_SYNC_DLL_DIRECTORY=L"'+wp(dlls)+'"','-DGL_GPU_SYNC_RESULT="'+wp(out/'result.txt')+'"'];objects=[]
  for name in('windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/gl_gpu_sync_test.cpp'):
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('gl_gpu_sync_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'gpu_sync.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,m['objects']),'-Wl,--wrap='+WRAP,'-Wl,--wrap=__imp_GetProcAddress','-static','-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(exe)],'link');run([exe],'actual-ANGLE',120)
  text=(out/'result.txt').read_text();match=re.search(r'GL-GPU-SYNC-PASS checks=(\d+) actual_NDK_calls=(\d+) installed_sync_calls=(\d+) APIs=3 forms=3 lifecycle=(\d+) completed_waits=(\d+) error_cases=(\d+) observed_waits=(\d+) independent_context_progress=1 State=1200 Memory64=1',text);assert match and 'NATIVE-CLIENT-WAIT'in(out/'actual-ANGLE.log').read_text()
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,scope='Actual ANGLE coreFenceSync/ClientWaitSync/DeleteSync typedNDK direct/volatilepointer/eglGetProcAddress lifecycle. Realopaquehandles/nativecompletion/GPUcommands, fulluint64timeoutsobserved bytransparentforwarder, nativeerrors/env/StateMemory and independentNONsharingcontextFlush progress duringpausedcompletedwait.',production_sources=production,production_source_manifest=desc(a.production_pins),owned_sources={n:sha(source/'windows'/n)for n in OWN},old_commands=old,new_commands=new,old_marker_prefix_exact=True,focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),installed_sync_calls=int(match[3]),APIs=3,forms=3,lifecycle_cases=int(match[4]),completed_waits=int(match[5]),error_cases=int(match[6]),observed_waits=int(match[7]),independent_context_progress=True,traces=len(m['traces']),objects=len(m['objects']),guest=desc(guest),manifest=desc(translated/'manifest.json'),executable=desc(exe),stdout=desc(out/'actual-ANGLE.log'),result=desc(out/'result.txt')),source_snapshot={str(p.relative_to(source)):sha(p)for p in source.rglob('*')if p.is_file()},held_inputs=held,commands=commands,limits='Driverhandles remain opaque; noassumptionhandle>32bits or fabricatedhighactualhandle. No fakestatus, timingnormalization, indefiniteunsafe wait, sameShareGroup parallelguarantee, extraquery/serverwaitguestexports or originalgameframe. NativeGetSynciv/IsSync are oracleonly. Testobserver records/forwardsactualdriver unchanged; no oldcampaign rerun.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('GL-GPU-SYNC-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
