"""Execute real NDK constructor/JNI_OnLoad and direct/V/A Java loader callers."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('java_native_loader.h','java_native_loader.cpp','java_native_loader_guest.c','java_native_loader_test.cpp','test_java_native_loader.py','java_native_loader.md')
PRODUCTION=('windows/java_native_loader.h','windows/java_native_loader.cpp')
SUPPORT=('windows/jni_host.h','windows/jni_host.cpp','windows/jni_string_codec_detail.h','windows/module_registry.h','windows/module_registry.cpp','windows/java_native_libraries.h','windows/java_native_libraries.cpp','whole/runtime.h','whole/runtime.cpp')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in('ndk','lift','semantics-dir','remill','support-source','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--windows-only',action='store_true');a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';held={};commands=[];results={}
 def pin(f):held[str(Path(f).resolve())]=sha(f)
 def wp(f):return subprocess.check_output(['wslpath','-m',str(Path(f).resolve())],text=True).strip()
 def run(argv,label):
  argv=list(map(str,argv));commands.append({'label':label,'argv':argv});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  for folder in('windows','whole','fastaes'):
   (source/folder).mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,source/folder/f.name)
  for n in OWN:pin(HERE/n);shutil.copyfile(HERE/n,source/'windows'/n)
  for n in SUPPORT:pin(a.support_source/n);assert sha(source/n)==sha(a.support_source/n)
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc')
  libraries=[]
  for name,extra,base in [('original',[],0x77000000),('absent',['-DNO_ONLOAD'],0x78000000)]:
   so=out/(name+'.so');run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-fno-jump-tables','-Wall','-Wextra','-Werror',*extra,source/'windows/java_native_loader_guest.c','-o',so],'compile-NDK-'+name);libraries.append((name,so,base))
  for windows in([True]if a.windows_only else[True,False]):
   label='windows'if windows else'linux';build=out/label;build.mkdir();path=wp if windows else str;manifests=[];decl=[];rows=[];objects=[]
   for name,so,base in libraries:
    guest=build/name;run([sys.executable,source/'whole/compile.py',so,'--out',guest,'--base',hex(base),'--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],'lift-'+label+'-'+name)
    m=json.loads((guest/'manifest.json').read_bytes());assert not m['unsupported_traces']and not m['unresolved_direct_targets'];assert len(m['initializers'])==1 and len(m['finalizers'])==1
    text=(guest/'traces.h').read_text();decl.extend(re.findall(r'extern "C" Memory \*[^;]+;',text));rows.extend(re.findall(r'  \{0x[0-9a-f]+, sub_[0-9a-f]+\},',text));objects.extend(map(Path,m['objects']));manifests.append(m)
   assert len(rows)==sum(len(m['traces'])for m in manifests)
   (build/'native_loader_traces.h').write_text('\n'.join(decl)+'\nstatic const recomp::Trace kLoaderTraces[]={\n'+'\n'.join(rows)+'\n};\n')
   cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';pin(Path(cc)if windows else Path('/usr/bin/'+cc));pin(Path(cxx)if windows else Path('/usr/bin/'+cxx))
   elfload=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(elfload)],'compile-elfload-'+label)
   flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.remill/'include'),'-I'+path(build),f'-DNATIVE_LOADER_IMAGE="{path(libraries[0][1])}"',f'-DNATIVE_LOADER_NOENTRY_IMAGE="{path(libraries[1][1])}"'];compiled=[]
   for relative in('windows/java_native_loader.cpp','windows/java_native_libraries.cpp','windows/jni_host.cpp','windows/module_registry.cpp','whole/runtime.cpp','windows/java_native_loader_test.cpp'):
    obj=build/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith(('java_native_loader.cpp','java_native_loader_test.cpp'))else[];run([cxx,*flags,*strict,'-c',path(source/relative),'-o',path(obj)],'compile-'+label+'-'+obj.stem);compiled.append(obj)
   exe=build/('native-loader.exe'if windows else'native-loader');run([cxx,*map(path,compiled),path(elfload),*map(path,objects),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)],'link-'+label);run([exe],'actual-NDK-'+label)
   log=out/('actual-NDK-'+label+'.log');text=log.read_text();m=re.fullmatch(r'JAVA-NATIVE-LOADER-PASS checks=(\d+) NDK_calls=(\d+) constructors_and_OnLoad=actual State=1200 Memory64=1\s*',text);assert m,text[-3000:]
   results[label]={'exit_code':0,'checks':int(m[1]),'actual_NDK_calls':int(m[2]),'traces':sum(len(x['traces'])for x in manifests),'objects':len(objects),'unsupported':[],'unresolved':[],'executable':desc(exe),'stdout':desc(log),'guest_manifests':[desc(build/name/'manifest.json')for name,_,_ in libraries]};(out/'progress.json').write_text(json.dumps(results,indent=2)+'\n')
  for f,h in held.items():assert sha(f)==h,f
  receipt={'passed':True,'production_sources':{n:sha(source/n)for n in PRODUCTION},'owned_sources':{'windows/'+n:sha(source/'windows'/n)for n in OWN},'support_sources':{n:sha(source/n)for n in SUPPORT},'platforms':results,'JNI_OnLoad_version_policy':{'accepted_constants':[0x10002,0x10004,0x10006],'executed_successful_versions':[0x10006],'executed_failed_versions':[-1,0x10001],'adoption_1_1_rejected':True,'limit':'No change to JavaVM GetEnv policy; 1.2 and1.4 acceptance is primary-source/static, not an actual NDK execution claim.'},'NDK_libraries':{name:desc(so)for name,so,_ in libraries},'commands':commands,'held_inputs':held,'controls':['real NDK constructor and GetEnv/OnLoad calls','real no-OnLoad ELF','JNI direct/V/A instance boolean callers','adopt existing exact live handle without reopening or OnLoad replay','same-export wrong-handle rejection and no-ref/no-dlerror-mutating query','actual JNI_OnLoad1.1 rejected and failure cached without finalization; completed1.1 adoption rejects before valid1.6','cached normal and bad-version outcomes','same-thread recursive OnLoad and concurrent attached JNI callers','closed catalog unknown/unregistered names fail with severity6 diagnostics','receiver/application loader identity and wrong-loader rejection','preexisting and original OnLoad Throwable preservation','revocation retains active native registrations/images','State1200/SIMD128/highcell/opaqueMemory64 forwarding'],'limits':['Not ART or full Android linker/class-loader conformance.','Multiple declared module fixtures deliberately share original NDK function addresses to exercise independent handle identity and cache ownership; this is not a claim of separately mapped ELF generations.','Actual constructor/OnLoad and JNI method bodies execute translated original NDK code; host hook only controls recursive/concurrent scheduling.','Library paths are closed explicit profiles; no portable native loading/ARM execution or namespace fallback.','No original game/full-host link or historical JNI campaign.']}
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('JAVA-NATIVE-LOADER-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps({'passed':False,'error':str(e),'traceback':traceback.format_exc(),'commands':commands,'held_inputs':held,'platforms':results},indent=2)+'\n');raise
if __name__=='__main__':main()
