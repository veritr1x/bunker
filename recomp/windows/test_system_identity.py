"""Focused real NDK direct/V/A System.identityHashCode qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(p)],text=True).strip()
def main():
 a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);o=a.parse_args().out;o.mkdir(exist_ok=False);s=o/'source';commands=[]
 for folder in ['windows','whole','fastaes']:
  (s/folder).mkdir(parents=True)
  for p in(HERE.parent/folder).iterdir():
   if p.is_file()and(p.suffix in('.h','.inc')or p.name in ['jni_host.cpp','runtime.cpp','cooperative_poll.cpp','elfload.c','system_identity_guest.c','system_identity_test.cpp','test_system_identity.py']):shutil.copyfile(p,s/folder/p.name)
 production={'windows/jni_host.cpp':'5ffb32ff90269b450e70a42558bc5dca585bb3d34ad04c185ae6241121a0c148','windows/jni_host.h':'f3c388af6040842b94d54224e66809700907b0deac4fc0f5c46490afc8521af7'}
 for n,h in production.items():assert sha(s/n)==h==sha(HERE.parent/n)
 def run(args,name):
  args=list(map(str,args));commands.append(dict(stage=name,argv=args));(o/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',name,flush=True)
  with(o/(name+'.log')).open('w')as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');tool=W/'fp-numeric-minmax-preparation1/toolchains/14f6409b2d88fbde-6dd3ed0e502e37b9';guest=o/'identity.so'
 run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',s/'windows/system_identity_guest.c','-o',guest],'compile-NDK')
 run([sys.executable,HERE.parent/'whole/compile.py',guest,'--out',o/'guest','--base','0x5f000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK');m=json.loads((o/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(o/'guest'),'-DIDENTITY_LIBRARY="'+wp(guest)+'"'];objects=[]
 for n in ['windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/system_identity_test.cpp']:
  obj=o/(Path(n).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('system_identity_test.cpp')else[]),'-c',wp(s/n),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
 loader=o/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(s/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=o/'identity.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,map(Path,m['objects'])),'-static','-pthread','-latomic','-o',wp(exe)],'link');run([exe],'actual-NDK-Windows')
 text=(o/'actual-NDK-Windows.log').read_text();match=re.search(r'SYSTEM-IDENTITY-PASS checks=(\d+) actual_NDK_calls=(\d+) forms=3 State=1200 Memory64=8 override_calls=1',text);assert match
 for n,h in production.items():assert sha(HERE.parent/n)==h
 result=dict(passed=True,production_sources=production,focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),forms=3,traces=len(m['traces']),objects=len(m['objects']),guest=desc(guest),manifest=desc(o/'guest/manifest.json'),stdout=desc(o/'actual-NDK-Windows.log'),executable=desc(exe)),source_snapshot={str(p.relative_to(s)):sha(p)for p in s.rglob('*')if p.is_file()},commands=commands,limits='Actual NDK JNI caller contracts direct/V/A with null, reference aliases/lifetimes/threading, strings/arrays/class identities and override bypass. No exact cross-JVM numeric hash, noncollision guarantee, ART execution or game/visible-frame claim. Native environment preservation is qualified separately by capture component.')
 (o/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(desc(o/'acceptance.json')),flush=True)
if __name__=='__main__':main()
