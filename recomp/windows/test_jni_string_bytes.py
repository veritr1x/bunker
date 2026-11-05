"""Actual installed JDK24 oracle and genuine NDK JNI String-byte qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('jni_string_bytes_guest.c','jni_string_bytes_test.cpp','jni_string_bytes_oracle.java','jni_string_bytes.md','test_jni_string_bytes.py')
PRODUCTION=('windows/jni_host.cpp','windows/jni_host.h','windows/jni_string_codec_detail.h')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def hp(s):return Path('/mnt/'+s[0].lower()+'/'+s[3:].replace('\\','/'))if re.match(r'^[A-Za-z]:[\\/]',s)else Path(s)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in('ndk','lift','semantics-dir','support-source','out','jdk-reference'):p.add_argument('--'+key,type=Path,required=True)
 p.add_argument('--jdk-reference-sha256',required=True);p.add_argument('--windows-only',action='store_true');a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';commands=[];held={};platforms={}
 def pin(f):held[str(Path(f).resolve())]=sha(f)
 def wp(f):return subprocess.check_output(['wslpath','-m',str(Path(f).resolve())],text=True).strip()
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(label=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  assert sha(a.jdk_reference)==a.jdk_reference_sha256;ref=json.loads(a.jdk_reference.read_bytes());assert ref['passed']is True and ref['JDK_runtime_version'].startswith('24.') and ref['decode_vectors']==71 and ref['encode_vectors']==47;pin(a.jdk_reference)
  for key in('java','javac','release','source','class','records'):
   path=hp(ref[key]['path']);assert sha(path)==ref[key]['sha256'];pin(path)
  assert sha(HERE/'jni_string_bytes_oracle.java')==ref['source']['sha256'];records=hp(ref['records']['path'])
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
  for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  for n in PRODUCTION:pin(a.support_source/n);assert sha(source/n)==sha(a.support_source/n)
  baseline=a.support_source/'work/windows-first-frame-jni-byte-array1/sources/recomp/windows';binding=dict(passed=True,scope='Baseline/candidate source binding only; functional named-profile qualification below',baseline_sources={n:desc(baseline/n)for n in('jni_host.cpp','jni_host.h')},production_sources={n:sha(source/n)for n in PRODUCTION},unchanged_jni_header=sha(source/'windows/jni_host.h')==sha(baseline/'jni_host.h'),JDK_reference=desc(a.jdk_reference));assert binding['unchanged_jni_header'];(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'string-bytes.so'
  run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/jni_string_bytes_guest.c','-o',guest],'compile-NDK-JNIEnv-caller')
  for windows in([True]if a.windows_only else[True,False]):
   label='windows'if windows else'linux';build=out/label;build.mkdir();translated=build/'guest';path=wp if windows else str
   run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x77000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],'lift-'+label)
   manifest=json.loads((translated/'manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
   cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'/usr/bin/clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'/usr/bin/clang++-18';pin(cc);pin(cxx);loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],'compile-loader-'+label)
   flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',path(a.support_source/'work/remill-src/include'),'-I'+path(translated),f'-DSTRING_BYTES_IMAGE="{path(guest)}"'];objects=[]
   for relative in('windows/jni_host.cpp','whole/runtime.cpp','windows/jni_string_bytes_test.cpp'):
    obj=build/(Path(relative).stem+'.o');extra=['-Wall','-Wextra','-Werror']if relative.endswith('jni_string_bytes_test.cpp')else[];run([cxx,*flags,*extra,'-c',path(source/relative),'-o',path(obj)],'compile-'+label+'-'+obj.stem);objects.append(obj)
   exe=build/('string-bytes.exe'if windows else'string-bytes');run([cxx,*map(path,objects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(exe)],'link-'+label);run([exe,path(records)],'actual-NDK-'+label)
   text=(out/('actual-NDK-'+label+'.log')).read_text();m=re.fullmatch(r'JNI-STRING-BYTES-PASS checks=(\d+) NDK_calls=(\d+) decode_vectors=71 encode_vectors=47 forms=3 State=1200 Memory64=1\s*',text);assert m,text[-3000:]
   platforms[label]=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=2,JNI_forms=['direct','V','A'],decode_vectors=71,encode_vectors=47,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/('actual-NDK-'+label+'.log')));(out/'progress.json').write_text(json.dumps(platforms,indent=2)+'\n')
  for f,h in held.items():assert sha(f)==h,f
  result=dict(passed=True,production_sources={n:sha(source/n)for n in PRODUCTION},owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),JDK_reference=desc(a.jdk_reference),oracle_records=desc(records),NDK_caller=desc(guest),platforms=platforms,commands=commands,held_inputs=held,controls=['exact71decode/47encodevectors on all3JNIforms','UTF8 ordinary NUL/supplementary and malformed-prefix grouping','UTF16 BOM/endian/odd/unpaired-surrogate profile','ASCII/Latin1 replacement and case/aliases','null and invalid syntax/empty Java exceptions','valid outsideprofile Shift_JIS native guard, not fabricated Java fallback','initialized String kind/class/UTF16 JNI reads','returned byte-array class/content and independent lifetime','local frame promotion/weak retirement','generic old constructor factory smoke','1200State/16alignment/SIMD128/highcell/Memory64'],limits='Actual installed JDK24.0.1 named malformed-replacement profile for six mandatory charsets and tested aliases; not ART equivalence or allJDK charsets. ActualNDK JNI direct/V/A callingABI, not an ART runtime. Syntactically valid outsideprofile names fail natively; null/invalidnames match JDK categories. No full historical JNI campaign, fullhost build/link, game, observer, or production source edits by test controller.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('JNI-STRING-BYTES-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,platforms=platforms,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
