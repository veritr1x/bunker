"""Actual NDK lookup/cache/ReflectionHelper native-proxy protocol component."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(p)],text=True).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse-compiled',type=Path);args=ap.parse_args();o=args.out;o.mkdir(exist_ok=False);s=o/'source';packet=W/'reflection-helper-source-preparation1/production-sources2.json';assert sha(packet)=='e47e49bfc6e97b1805d1153f30a78675d65c7c05325513ed8dfc55aec846d9db';p=json.loads(packet.read_text());production=p['production_sources'];commands=[];reused=[]
 needed={'windows/jni_host.cpp','windows/reflection_helper.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','fastaes/elfload.c','windows/reflection_helper_guest.c','windows/reflection_helper_test.cpp','windows/test_reflection_helper.py'}|set(production)
 for folder in ['windows','whole','fastaes']:
  (s/folder).mkdir(parents=True)
  for f in(HERE.parent/folder).iterdir():
   if f.is_file()and(f.suffix in('.h','.inc')or folder+'/'+f.name in needed):shutil.copyfile(f,s/folder/f.name)
 for n,h in production.items():assert sha(s/n)==h==sha(HERE.parent/n)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(o/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(o/(label+'.log')).open('w')as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 core=W/'jni-field-four-qualification3';prior=json.loads((core/'acceptance.json').read_text());assert sha(core/'acceptance.json')=='46c2e9e9690ccf69fdc03e066b4e688f41ba3fc939738edfce0fd1f1915199b1';assert prior['passed'];assert desc(core/'guest/manifest.json')==prior['focus']['manifest'];assert desc(core/'field-four.so')==prior['focus']['guest'];cm=json.loads((core/'guest/manifest.json').read_text())
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');tool=W/'fp-numeric-minmax-preparation1/toolchains/14f6409b2d88fbde-6dd3ed0e502e37b9';guest=o/'reflection-helper.so'
 if args.reuse_compiled:
  old=args.reuse_compiled;assert sha(old/'source/windows/reflection_helper_guest.c')==sha(s/'windows/reflection_helper_guest.c');shutil.copyfile(old/'reflection-helper.so',guest);shutil.copytree(old/'guest',o/'guest');reused+=[desc(old/'commands.json'),desc(old/'guest/manifest.json'),desc(old/'reflection-helper.so')]
 else:
  run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',s/'windows/reflection_helper_guest.c','-o',guest],'compile-NDK')
  run([sys.executable,HERE.parent/'whole/compile.py',guest,'--out',o/'guest','--base','0x61000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate-NDK')
 m=json.loads((o/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
 (o/'all_traces.h').write_text((core/'guest/traces.h').read_text().replace('kTraces','kCoreTraces').replace('kInitializers','kCoreInitializers')+(o/'guest/traces.h').read_text().replace('kTraces','kHelperTraces').replace('kInitializers','kHelperInitializers'))
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(o),'-DREFLECTION_CORE_LIBRARY="'+wp(core/'field-four.so')+'"','-DREFLECTION_HELPER_LIBRARY="'+wp(guest)+'"'];objects=[]
 for n in ['windows/jni_host.cpp','windows/reflection_helper.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','windows/reflection_helper_test.cpp']:
  obj=o/(Path(n).stem+'.o')
  if args.reuse_compiled and not n.endswith('reflection_helper_test.cpp'):
   assert sha(args.reuse_compiled/'source'/n)==sha(s/n)
   for header in(s/'windows').glob('*.h'):
    previous=args.reuse_compiled/'source/windows'/header.name
    if previous.exists():assert sha(previous)==sha(header)
   obj=args.reuse_compiled/obj.name;reused.append(desc(obj))
  else:run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if n.endswith('reflection_helper_test.cpp')else[]),'-c',wp(s/n),'-o',wp(obj)],'compile-'+obj.stem)
  objects.append(obj)
 loader=o/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',wp(s/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');exe=o/'reflection-helper.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,map(Path,cm['objects'])),*map(wp,map(Path,m['objects'])),'-static','-pthread','-latomic','-o',wp(exe)],'link');run([exe],'actual-NDK-Windows')
 text=(o/'actual-NDK-Windows.log').read_text();match=re.search(r'REFLECTION-HELPER-PASS checks=(\d+) actual_NDK_calls=(\d+) native_invokes=9 native_logs=2 native_finalizes=0 epoch=1 cache_collision=1 State=1200 Memory64=8 MethodArguments=32',text);assert match
 for n,h in production.items():assert sha(HERE.parent/n)==h
 result=dict(passed=True,production_source_manifest=desc(packet),production_sources=production,reused_compiled_inputs=reused,reused_core_qualification=desc(core/'acceptance.json'),focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),native_invokes=9,native_logs=2,native_finalizes=0,lookup_forms=4,factory_forms=3,cache_collision=True,epoch_suppression=True,core_traces=len(cm['traces']),new_traces=len(m['traces']),objects=len(cm['objects'])+len(m['objects']),guest=desc(guest),manifest=desc(o/'guest/manifest.json'),stdout=desc(o/'actual-NDK-Windows.log'),executable=desc(exe)),source_snapshot={str(f.relative_to(s)):sha(f)for f in s.rglob('*')if f.is_file()},commands=commands,limits='TEST-owned exact catalog subset and actual compiled NDK callback entries registered under real ReflectionHelper ABI. No fabricated original native addresses or helper results, whole APK bytecode/ART/JNI_OnLoad/Unity native callback execution, Java GC/finalize timing, unsupported interface/default/boxing profile or first-frame claim. Explicit Java finalize handler not invoked; absence of eager C++ native finalize is tested. Actual original integration remains separate.')
 (o/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(desc(o/'acceptance.json')),flush=True)
if __name__=='__main__':main()
