"""Focused real NDK backed Field and four Java argument qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(p)],text=True).strip()
def main():
 a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--reuse-guest',type=Path);args=a.parse_args();o=args.out;o.mkdir(exist_ok=False);s=o/'source';commands=[]
 for folder in ['windows','whole','fastaes']:
  (s/folder).mkdir(parents=True)
  for p in(HERE.parent/folder).iterdir():
   if p.is_file()and(p.suffix in('.h','.inc')or p.name in ['jni_host.cpp','runtime.cpp','cooperative_poll.cpp','elfload.c','jni_field_four_guest.c','jni_field_four_test.cpp','test_jni_field_four.py']):shutil.copyfile(p,s/folder/p.name)
 production={'windows/jni_host.cpp':'95e6a7570c9767395506644d00c14207c3f8eb5ea0046137c51ceac8ce099fc1','windows/jni_host.h':'442b276ffcc1a5ad5c3ba01fd32e5dc39884d3bb804b29fe83a632019a61c06f'}
 for n,h in production.items():assert sha(s/n)==h==sha(HERE.parent/n)
 def run(args,name):
  args=list(map(str,args));commands.append(dict(stage=name,argv=args));(o/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',name,flush=True)
  with(o/(name+'.log')).open('w')as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');tool=W/'fp-numeric-minmax-preparation1/toolchains/14f6409b2d88fbde-6dd3ed0e502e37b9';guest=o/'field-four.so'
 reused=None
 if args.reuse_guest:
  old=args.reuse_guest;receipt=json.loads((old/'acceptance.json').read_text());assert receipt['passed'] and sha(old/'source/windows/jni_field_four_guest.c')==sha(s/'windows/jni_field_four_guest.c')
  assert desc(old/'guest/manifest.json')==receipt['focus']['manifest'] and desc(old/'field-four.so')==receipt['focus']['guest']
  shutil.copyfile(old/'field-four.so',guest);shutil.copytree(old/'guest',o/'guest');reused=desc(old/'acceptance.json')
 else:
  run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',s/'windows/jni_field_four_guest.c','-o',guest],'compile-NDK')
  run([sys.executable,HERE.parent/'whole/compile.py',guest,'--out',o/'guest','--base','0x60000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK')
 m=json.loads((o/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(o/'guest'),'-DFIELD_FOUR_LIBRARY="'+wp(guest)+'"'];objects=[]
 for n in ['windows/jni_host.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/jni_field_four_test.cpp']:
  obj=o/(Path(n).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('jni_field_four_test.cpp')else[]),'-c',wp(s/n),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
 loader=o/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(s/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=o/'field-four.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,map(Path,m['objects'])),'-static','-pthread','-latomic','-o',wp(exe)],'link');run([exe],'actual-NDK-Windows')
 text=(o/'actual-NDK-Windows.log').read_text();match=re.search(r'JNI-FIELD-FOUR-PASS checks=(\d+) actual_NDK_calls=(\d+) callbacks=(\d+) forms=4 State=1200 Memory64=8 MethodArguments=32',text);assert match
 for n,h in production.items():assert sha(HERE.parent/n)==h
 result=dict(passed=True,production_sources=production,reused_guest_qualification=reused,focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),callbacks=int(match[3]),forms=4,traces=len(m['traces']),objects=len(m['objects']),guest=desc(guest),manifest=desc(o/'guest/manifest.json'),stdout=desc(o/'actual-NDK-Windows.log'),executable=desc(exe)),source_snapshot={str(p.relative_to(s)):sha(p)for p in s.rglob('*')if p.is_file()},commands=commands,limits='Actual NDK Field8/12/getters/inherited/static ownership and null/invalid/pending controls; four Java args direct/V/A/GP-spilledV high64 references/longs and jvalue-padding canaries; old three Java argument regression/rejectfive. Invalid JNI errors are Host failclosed profile, not ART/JDK equivalence. No original game or visible-frame claim.')
 (o/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(desc(o/'acceptance.json')),flush=True)
if __name__=='__main__':main()
