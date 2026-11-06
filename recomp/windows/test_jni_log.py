"""Qualify the host-Throwable diagnostic path through real NDK direct/V/A calls."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
ROOT=Path(__file__).resolve().parent.parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';held={};commands=[]
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/(label+'.log')).write_bytes(r.stdout)
  if r.returncode:raise RuntimeError(label+' failed; inspect preserved log')
  return r.stdout.decode(errors='replace')
 try:
  units=['windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/jni_log_test.cpp'];todo=units+['windows/jni_log_guest.c','windows/test_jni_log.py','windows/jni_host_test.cpp','fastaes/elfload.c'];seen=set()
  while todo:
   name=todo.pop();p=(ROOT/name).resolve();name=str(p.relative_to(ROOT))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);held[str(p)]=sha(p)
   for inc in re.findall(r'^\s*#include\s*"([^\"]+)"',p.read_text(errors='replace'),re.M):
    child=(p.parent/inc).resolve()
    if child.is_file()and child.is_relative_to(ROOT):todo.append(str(child.relative_to(ROOT)))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe');tool=W/'integer-popcount8b-preparation1/toolchains/f967bf3b57f889d7-469903ec4d84cbd3'
  for p in [ndk,cxx,cc,tool/'remill-lift',tool/'aarch64.bc',ROOT/'whole/compile.py']:held[str(p)]=sha(p)
  guest=out/'jni-log.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'windows/jni_log_guest.c','-o',guest],'compile-NDK')
  run([sys.executable,ROOT/'whole/compile.py',guest,'--out',out/'guest','--base','0x64000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK');m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'guest'),'-DLOG_GUEST="'+wp(guest)+'"'];objects=[]
  for n in units:
   obj=out/(Path(n).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('jni_log_test.cpp')else[]),'-c',wp(source/n),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=out/'jni-log.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-o',wp(exe)],'link')
  text=run([exe],'actual-log');match=re.search(r'JNI-LOG-PASS checks=(\d+) NDK_calls=(\d+) actual_virtual_overrides=(\d+)',text);assert match;checks,calls,overrides=map(int,match.groups());assert calls==24 and overrides==3
  header=W/'asset-pack-wrapper2/jni.h';held[str(header)]=sha(header);shutil.copyfile(header,out/'jni.h');core=out/'jni-core.exe';run([cxx,*flags,'-I'+wp(out),wp(source/'windows/jni_host_test.cpp'),*map(wp,objects[:3]),'-static','-pthread','-latomic','-o',wp(core)],'link-existing-core');text=run([core],'actual-existing-core');assert 'JNI host:'in text and 'checks passed'in text
  assert all(sha(p)==h for p,h in held.items())
  result=dict(passed=True,production_sources={'windows/jni_host.cpp':sha(source/'windows/jni_host.cpp')},source_snapshot={str(p.relative_to(source)):sha(p)for p in sorted(source.rglob('*'))if p.is_file()},checks=checks,actual_NDK_calls=calls,actual_virtual_overrides=overrides,existing_core_passed=True,guest=desc(guest),executable=desc(exe),logs={n:desc(out/(n+'.log'))for n in ['actual-log','actual-existing-core']},held_inputs=held,scope='Actual initialized host Throwable diagnostics with no captured Java frames, causes or suppressed exceptions. Null/UnknownHost, virtual localized text, direct/V/A ABI, reference lifetime and explicit unsupported states. No full Java Throwable interpreter, original CheckException execution or game-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(desc(out/'acceptance.json')),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
