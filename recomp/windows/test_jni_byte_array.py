"""Focused actual NDK JNI-byte-array callers on Windows and Linux; not ART."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('jni_byte_array_guest.c','jni_byte_array_test.cpp','jni_byte_array.md','test_jni_byte_array.py')
PRODUCTION=('windows/jni_host.cpp','windows/jni_host.h')
SLOTS=[171,176,184,192,200,208]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','support-source','out','source-proof'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--source-proof-sha256',required=True);p.add_argument('--windows-only',action='store_true');a=p.parse_args()
 out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';commands=[];held={};platforms={}
 def pin(path):held[str(Path(path).resolve())]=sha(path)
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(label=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  assert sha(a.source_proof)==a.source_proof_sha256;proof=json.loads(a.source_proof.read_bytes());assert proof['passed']is True;pin(a.source_proof)
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
  for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  for n in PRODUCTION:pin(a.support_source/n);assert sha(source/n)==sha(a.support_source/n)
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc')
  guest=out/'byte-array.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-fno-jump-tables',source/'windows/jni_byte_array_guest.c','-o',guest],'compile-NDK-JNIEnv-caller')
  for windows in([True]if a.windows_only else[True,False]):
   label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
   run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x76000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],'lift-'+label)
   manifest=json.loads((translated/'manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
   cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'/usr/bin/clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'/usr/bin/clang++-18';pin(cc);pin(cxx);loader=build/'elfload.o'
   run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],'compile-loader-'+label)
   flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.support_source/'work/remill-src/include'),'-I'+path(translated),f'-DBYTE_ARRAY_IMAGE="{path(guest)}"'];objects=[]
   for relative in('windows/jni_host.cpp','whole/runtime.cpp','windows/jni_byte_array_test.cpp'):
    obj=build/(Path(relative).stem+'.o');extra=['-Wall','-Wextra','-Werror']if relative.endswith('jni_byte_array_test.cpp')else[]
    run([cxx,*flags,*extra,'-c',path(source/relative),'-o',path(obj)],'compile-'+label+'-'+obj.stem);objects.append(obj)
   exe=build/('byte-array.exe'if windows else'byte-array');run([cxx,*map(path,objects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)],'link-'+label)
   run([exe],'actual-NDK-'+label);text=(out/('actual-NDK-'+label+'.log')).read_text();match=re.fullmatch(r'JNI-BYTE-ARRAY-PASS checks=(\d+) NDK_calls=(\d+) slots=6 State=1200 align=16 Memory64=1\s*',text);assert match,text[-2500:]
   platforms[label]=dict(exit_code=0,checks=int(match[1]),actual_NDK_calls=int(match[2]),APIs=6,JNI_slots=SLOTS,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/('actual-NDK-'+label+'.log')))
   (out/'progress.json').write_text(json.dumps(platforms,indent=2)+'\n')
  for f,h in held.items():assert sha(f)==h,f
  result=dict(passed=True,production_sources={n:sha(source/n)for n in PRODUCTION},owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_proof=desc(a.source_proof),platforms=platforms,NDK_caller=desc(guest),commands=commands,held_inputs=held,controls=['negative/zero/256byte allocation and zero initialization','all256 signedbyte bit patterns','exact region bounds and destination staging/canaries','always-copy isCopy byte and independent leases','mode0 copy/free,mode1 copy/retain,mode2 discard/free','wrong array/type/mode/stale pointer host-policy guards','Release cleanup preserves existing pending Throwable identity','Object/Cloneable/Serializable but not Object[] primitive identity','typed [B method/field and [[B nested reference arrays','local/global/weak/frame/attached-thread reference ownership and lease lifetime','ordinary elements copy release on another attached thread using globalref is allowed','foreign JNIEnv defensive host-boundary rejection','existing reference-array store/read smoke control','actual State1200/align16 SIMD128/highcell/opaqueMemory64'],limits='Actual NDK-compiled JNIEnv vtable callers linked only to this checked host, not ART or a Java runtime conformance oracle. Negative-size/bounds/wrong-type/lease-misuse checks are explicit defensive host policy; foreignJNIEnv is tested directly at the host boundary, not through an invented ART outcome. Valid release cleanup while pending preserves Throwable identity. Ordinary elements copies do not acquire an invented same-thread restriction. Region buffers are nonNULL even length0. No ordinary New/Get/region calls while pending are used as an ART claim. actual_NDK_calls counts executed translated caller invocations (byte_shape invokes multiple JNI slots). Same fixture on both hosts; no full historical JNI campaign, original game, observer, source promotion, or production link.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('JNI-BYTE-ARRAY-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held,platforms=platforms),indent=2)+'\n');raise
if __name__=='__main__':main()
