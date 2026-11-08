"""Isolated real original Unity638 constructor/frame/shutdown component."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent
WORK=HERE.parent/'work'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--generic-build',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 out=args.out.resolve();out.mkdir(parents=True,exist_ok=False);base=args.generic_build.resolve();held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=60):
  argv=list(map(str,argv));commands.append({'stage':label,'argv':argv});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 def bound(d):p=Path(d['path']);assert sha(p)==d['sha256'];pin(p);return p
 try:
  acceptance=base/'acceptance.json';q=json.loads(acceptance.read_text());assert q['passed'];pin(acceptance)
  assert sha(acceptance)=='94947e3c07780377bc642f10c3ec34def986bf8370435ecbb399d304c24d0c1e'
  source=out/'source';shutil.copytree(base/'source',source)
  for n in('android_choreographer_original_test.cpp','test_android_choreographer_original.py'):shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  for name,digest in q['production_sources'].items():assert sha(HERE.parent/name)==digest==sha(source/name)
  # Verify the entire frozen generic include/source snapshot before reusing
  # its native objects; the new integration TU is compiled separately below.
  for name,digest in q['source_snapshot'].items():assert sha(base/'source'/name)==digest
  profile=WORK/'unity-choreographer-component-preparation1/component-profile.json';pin(profile);assert sha(profile)=='82b4144472d9345721dd5c87589b1fb5380c59c20e7ce19272b805e3e5d6d25e'
  p=json.loads(profile.read_text());assert len(p['class_initializers'])==24
  closure_path=WORK/'unity-choreographer-component-closure2/acceptance.json';pin(closure_path);assert sha(closure_path)=='46a25756e7cc9fba19908a14f63328a74f74692093dcd76eb562f24754e99297'
  closure=json.loads(closure_path.read_text());helpers=bound(closure['object']);helper_header=bound(closure['header']);unity=bound(closure['actual_original_ELF'])
  packet_path=WORK/'unity-choreographer-entry-packet1/acceptance.json';pin(packet_path);packet=json.loads(packet_path.read_text());assert packet['passed']
  entry_object=bound(packet['candidate_object']);entry_header=WORK/'unity-choreographer-entry-packet1/component_entries.h';pin(entry_header)
  guest=bound(q['focus']['guest']);manifest_path=bound(q['focus']['manifest']);manifest=json.loads(manifest_path.read_text());translated=manifest_path.parent
  for item in manifest['objects']:pin(item)
  generic_header=translated/'traces.h';pin(generic_header);shutil.copyfile(generic_header,out/'ndk_traces.h')
  rows=[]
  for header in(generic_header,helper_header,entry_header):rows+=re.findall(r'\{(0x[0-9a-fA-F]+),\s*(sub_[0-9a-fA-F]+)\}',header.read_text())
  assert len(rows)==len(set(address for address,_ in rows))==len(manifest['traces'])+638
  (out/'traces.h').write_text('#pragma once\n#define kTraces kNdkOnlyTraces\n#include "ndk_traces.h"\n#undef kTraces\n#include "'+wp(helper_header)+'"\n#include "'+wp(entry_header)+'"\nstatic const recomp::Trace kTraces[]={\n'+''.join('{'+address+','+symbol+'},\n'for address,symbol in rows)+'};\n')
  (out/'original_profile.h').write_text('#pragma once\nstatic const addr_t kOriginalInitializers[]={'+','.join(i['initializer']for i in p['class_initializers'])+'};\n')
  shutil.copyfile(base/'sample.h',out/'sample.h');pin(base/'sample.h')
  compiler=Path('/mnt/c/mingw64/bin/g++.exe');pin(compiler)
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(WORK/'remill-src/include'),'-I'+wp(out),'-I'+wp(source/'windows'),'-I'+wp(source/'whole'),'-I'+wp(translated),'-I'+wp(WORK/'zlib-native/zlib-1.3.2')]
  names=['jni_host','jni_interface_proxy','android_choreographer','pthread_host','signal_host','libc','android_context','windows_android_id','windows_display_service','android_assets','apk_assets','thread_priority','android_process','runtime']
  objects=[]
  for name in names:
   obj=base/(name+'.o');assert obj.is_file();pin(obj);objects.append(obj)
  for relative in('windows/filesystem.cpp','windows/logging.cpp','windows/growdown_memory.cpp','whole/cooperative_poll.cpp','whole/format.cpp'):
   def freeze(path):
    path=path.resolve();relative=path.relative_to(HERE.parent.resolve());target=source/relative;pin(path)
    if target.exists():assert sha(target)==sha(path);return
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for include in re.findall(r'^\s*#\s*include\s*"([^"]+)"',path.read_text(errors='replace'),re.M):
     candidate=(path.parent/include).resolve()
     if candidate.is_file()and candidate.is_relative_to(HERE.parent.resolve()):freeze(candidate)
   freeze(HERE.parent/relative)
   f=source/relative;assert sha(f)==sha(HERE.parent/relative);pin(HERE.parent/relative);obj=out/(f.stem+'.o');run([compiler,*flags,'-c',wp(f),'-o',wp(obj)],'compile-'+f.stem);objects.append(obj)
  loader=base/'elfload.o';pin(loader);backend=WORK/'zlib-native/libz-inflate.a';pin(backend)
  exe=out/'original638.exe';result=out/'result.txt'
  defines=['-DCHOREOGRAPHER_LIBRARY="'+wp(guest)+'"','-DCHOREOGRAPHER_RESULT="'+wp(out/'unused-generic.txt')+'"','-DORIGINAL_UNITY_LIBRARY="'+wp(unity)+'"','-DORIGINAL_RESULT_FILE="'+wp(result)+'"']
  run([compiler,*flags,*defines,'-Wall','-Wextra','-Werror',wp(source/'windows/android_choreographer_original_test.cpp'),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),wp(helpers),wp(entry_object),wp(backend),'-static','-pthread','-latomic','-ladvapi32','-luser32','-lgdi32','-o',wp(exe)],'build-original638')
  run([exe],'actual-original638',45);text=result.read_text();assert 'ORIGINAL638-PASS'in text
  for file,digest in held.items():assert sha(file)==digest,file
  receipt={'passed':True,'production_sources':q['production_sources'],'generic_qualification':desc(acceptance),'original_profile':desc(profile),'helper_closure':desc(closure_path),'entry_packet':desc(packet_path),'trace_count':len(rows),'original_trace_count':638,'actual_original_ELF':desc(unity),'actual_result':text,'stdout':desc(out/'actual-original638.log'),'executable':desc(exe),'fixture_sources':{n:sha(source/'windows'/n)for n in('android_choreographer_original_test.cpp','test_android_choreographer_original.py')},'held_inputs':held,'commands':commands,'limits':'Isolated original638 component with24 selected original class initializers and TEST-only VM pointer seed. Real original constructor, queued handler/frame native dispatch and nondeleting destructor; not full original JNI_OnLoad/Unity/ART initialization or first rendered frame.'}
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('ORIGINAL638-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps({'passed':False,'error':str(error),'traceback':traceback.format_exc(),'held_inputs':held,'commands':commands},indent=2)+'\n');raise
if __name__=='__main__':main()
