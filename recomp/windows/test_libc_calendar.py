"""Actual selected-NDK calendar oracle and Windows Bionic-ABI qualification."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
ZONES=('UTC0','IST-5:30','EST5EDT,M3.2.0/2,M11.1.0/2','AEST-10AEDT-11,M10.1.0/2,M4.1.0/3')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p))
def native_negatives(exe,out,commands):
 negatives=[]
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def quote(s):return "'"+s.replace("'","''")+"'"
 for kind in('fault-read','fault-write'):
  stdout=out/('negative-'+kind+'.stdout');stderr=out/('negative-'+kind+'.stderr')
  command='$p=Start-Process -FilePath '+quote(wp(exe))+' -ArgumentList '+quote(kind)+' -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput '+quote(wp(stdout))+' -RedirectStandardError '+quote(wp(stderr))+'; if ($null -eq $p.ExitCode) { throw "No native exit code" }; Write-Output $p.ExitCode'
  argv=['powershell.exe','-NoProfile','-NonInteractive','-Command',command];commands.append(dict(label='negative-'+kind,argv=argv))
  code=int(subprocess.check_output(argv,text=True).strip());assert code==-1073741819,code
  negatives.append(dict(kind=kind,native_Windows_exit_code=code,Windows_exception_hex='0xc0000005',actual_library_invalid_pointer_fault=True,stdout=desc(stdout),stderr=desc(stderr)))
 return negatives
def reference(a):
 out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);commands=[]
 def run(argv,label,env=None):
  commands.append(dict(label=label,argv=list(map(str,argv)),TZ=env.get('TZ')if env else None));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
 try:
  src=HERE/'libc_calendar_ref.c';frozen=out/src.name;shutil.copyfile(src,frozen);source_sha=sha(src)
  cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';exe=out/'calendar-reference';qemu=a.qemu
  run([cc,'-O1','-static','-fno-builtin','-fno-emulated-tls',frozen,'-o',exe],'compile-NDK-static')
  rows=[]
  for i,zone in enumerate(ZONES):
   env=dict(os.environ,TZ=zone);label=f'Bionic-zone{i}';run([qemu,exe],label,env);text=(out/(label+'.log')).read_text();lines=text.splitlines()
   assert lines.count('ABI|8|56|8|20|40|48')==1;mk=[x.split('|')for x in lines if x.startswith('MK|')];assert len(mk)==26
   records={x[1]:dict(timestamp=int(x[2]),errno=int(x[3]),tm=x[4].split(','))for x in mk};diff=next(x for x in lines if x.startswith('DIFF|')).split('|');assert diff[1:3]==['1','1']
   formatting=[x for x in lines if x.startswith('FCASE|')];assert len(formatting)==25
   rows.append(dict(TZ=zone,records=records,shared=next(x for x in lines if x.startswith('SHARED|')),gmtime=next(x for x in lines if x.startswith('GM|')),localtime=next(x for x in lines if x.startswith('LOCAL|')),format_records=[x for x in lines if x.startswith('FMT|')],formatting_cases=formatting,difftime=diff[1:],stdout=desc(out/(label+'.log'))))
  run([qemu,exe,'null'],'Bionic-null',dict(os.environ,TZ='UTC0'))
  assert sha(src)==source_sha and sha(frozen)==source_sha
  record_path=out/'records.json';record_path.write_text(json.dumps(rows,indent=2)+'\n')
  result=dict(passed=True,kind='Actual selected NDK static Bionic process-local-TZ reference; not Windows provider qualification',reference_source=desc(frozen),original_source_sha256=source_sha,compiler=desc(cc),qemu=desc(qemu),binary=desc(exe),records=desc(record_path),profiles=list(ZONES),mktime_records=104,null_stdout=desc(out/'Bionic-null.log'),ABI=dict(time_t_bytes=8,time_t_signed=True,tm_bytes=56,tm_align=8,tm_year_offset=20,gmtoff_offset=40,zone_offset=48),commands=commands,limits='No global Windows timezone changes, no glibc proxy, no game execution. Normalized pointer values compared by zone contents, not process addresses. Actual errno/padding/fold/gap/hints recorded without imposing generic POSIX policy.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CALENDAR-REFERENCE',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
def windows(a):
 out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(label=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  assert a.reference and sha(a.reference)==a.reference_sha256;ref=json.loads(a.reference.read_bytes());assert ref['passed']is True and ref['mktime_records']==104;pin(a.reference)
  records=json.loads(Path(ref['records']['path']).read_bytes());assert sha(ref['records']['path'])==ref['records']['sha256'];pin(ref['records']['path'])
  assert sha(HERE/'libc_calendar_ref.c')==ref['original_source_sha256']
  case_source=(HERE/'libc_calendar_ref.c').read_text().split('static const char*patterns[]')[0]
  inputs={m[1]:[int(x.strip())for x in m[2].split(',')]for m in re.finditer(r'\{"([^\"]+)",([^}]+)\}',case_source)};assert len(inputs)==26
  lines=[]
  for i,profile in enumerate(records):
   for label,item in profile['records'].items():
    if label in('year_low','year_high'):continue
    t=inputs[label];assert len(t)==8
    lines.append('|'.join(map(str,[i,label,*t,item['timestamp'],item['errno'],*item['tm']])))
  assert len(lines)==96;oracle=out/'native-oracle.tsv';oracle.write_text('\n'.join(lines)+'\n')
  patterns=json.loads('['+re.search(r'patterns\[\]=\{([^}]+)\}',(HERE/'libc_calendar_ref.c').read_text())[1]+']');format_lines=[]
  for i,profile in enumerate(records):
   for line in profile['formatting_cases']:
    _,stamp,k,n,error,value=line.split('|');format_lines.append('|'.join([str(i),stamp,patterns[int(k)].encode().hex(),n,error,value]))
  assert len(format_lines)==100;format_oracle=out/'native-formats.tsv';format_oracle.write_text('\n'.join(format_lines)+'\n')
  own=('libc_calendar_ref.c','libc_calendar_guest.c','libc_calendar_test.cpp','test_libc_calendar.py');production=('windows/libc.cpp','windows/libc_calendar_detail.h')
  for directory in('windows','whole','fastaes'):
   target=source/directory;target.mkdir(parents=True)
   for p in(a.support_source/directory).iterdir():
    if p.is_file()and p.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(p,target/p.name)
  for n in own:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  for n in production:pin(a.support_source/n);assert sha(source/n)==sha(a.support_source/n)
  if a.source_proof:assert sha(a.source_proof)==a.source_proof_sha256 and json.loads(a.source_proof.read_bytes())['passed']is True;pin(a.source_proof)
  old_header=sha(a.support_source/'windows/libc.h');ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc')
  for tool in('/usr/bin/clang-18','/mnt/c/mingw64/bin/g++.exe','/mnt/c/mingw64/bin/gcc.exe'):pin(tool)
  guest=out/'calendar.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/libc_calendar_guest.c','-o',guest],'compile-NDK-caller')
  translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x5b000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-actual-NDK')
  manifest=json.loads((translated/'manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include')];objects=[]
  for n in('windows/libc.cpp','whole/runtime.cpp'):
   obj=out/(Path(n).stem+'.o');run([cxx,*flags,'-c',wp(source/n),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  obj=out/'calendar-test.o';run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+wp(translated),f'-DCALENDAR_LIBRARY="{wp(guest)}"','-c',wp(source/'windows/libc_calendar_test.cpp'),'-o',wp(obj)],'strict-compile-test')
  exe=out/'calendar-test.exe';run([cxx,wp(obj),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows')
  run([exe,wp(oracle),wp(format_oracle)],'actual-Windows-calendar');text=(out/'actual-Windows-calendar.log').read_text();m=re.fullmatch(r'CALENDAR-PASS checks=(\d+) oracle_MK=96 NDK_calls=26 APIs=8 Bionic_tm=56 actual_host_zone=1\s*',text);assert m,text[-2500:]
  negatives=native_negatives(exe,out,commands)
  for p,h in held.items():assert sha(p)==h,p
  assert sha(a.support_source/'windows/libc.h')==old_header
  result=dict(passed=True,production_sources={n:sha(source/n)for n in production},test_sources={'windows/'+n:sha(source/'windows'/n)for n in own},unchanged_LibC_header_sha256=old_header,source_proof=desc(a.source_proof)if a.source_proof else None,Bionic_reference=desc(a.reference),oracle=desc(oracle),format_oracle=desc(format_oracle),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),native_oracle_mktime_records=96,native_format_records=100,actual_NDK_calls=26,APIs=8,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],negative_controls=negatives,executable=desc(exe),stdout=desc(out/'actual-Windows-calendar.log'))),held_inputs=held,commands=commands,limits='Actual selected static Bionic reference with process-localPOSIX TZ, no glibc proxy or Windows machineTZ changes. Full96 local-range records compared on controlled year-rule seam;8 beyondWindowsyearrange native records retained as explicit exclusion/error controls. ActualNDK8API direct/indirect callbacks target unchanged compile.py leaf fixture, not production game/cohort. No native pointer-value equality acrossprocesses; zonecontents and lifetime checked. Library invalid-pointer controls terminate with actual access violation, not fabricated kernelEFAULT.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CALENDAR-QUALIFICATION',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
def finalize_existing(a):
 out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);stage=a.reuse_host_stage.resolve();commands=[]
 try:
  failed=json.loads((stage/'failure.json').read_bytes());assert failed['passed']is False and failed['error']=='5'
  assert failed['commands'][-1]['label']=='negative-fault-read' and failed['commands'][-2]['label']=='actual-Windows-calendar'
  controller=HERE/'test_libc_calendar.py';old_controller=stage/'source/windows/test_libc_calendar.py';old_key=str(controller.resolve());assert sha(old_controller)==failed['held_inputs'][old_key]
  for p,h in failed['held_inputs'].items():
   if p!=old_key:assert sha(p)==h,p
  production=('windows/libc.cpp','windows/libc_calendar_detail.h');own=('libc_calendar_ref.c','libc_calendar_guest.c','libc_calendar_test.cpp','test_libc_calendar.py')
  for n in production:assert sha(stage/'source'/n)==sha(a.support_source/n)
  for n in own:
   if n!='test_libc_calendar.py':assert sha(stage/'source/windows'/n)==sha(HERE/n)
  assert sha(a.source_proof)==a.source_proof_sha256 and json.loads(a.source_proof.read_bytes())['passed']is True
  assert sha(a.reference)==a.reference_sha256 and json.loads(a.reference.read_bytes())['passed']is True
  text=(stage/'actual-Windows-calendar.log').read_text();m=re.fullmatch(r'CALENDAR-PASS checks=(\d+) oracle_MK=96 NDK_calls=26 APIs=8 Bionic_tm=56 actual_host_zone=1\s*',text);assert m,text
  manifest=json.loads((stage/'guest/manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  negatives=native_negatives(stage/'calendar-test.exe',out,commands)
  artifact_names=('calendar-test.exe','calendar.so','native-oracle.tsv','native-formats.tsv','actual-Windows-calendar.log','strict-compile-test.log','compile-libc.log','compile-runtime.log','link-Windows.log','guest/manifest.json','failure.json','commands.json')
  artifacts={n:desc(stage/n)for n in artifact_names}
  result=dict(passed=True,production_sources={n:sha(stage/'source'/n)for n in production},test_sources={'windows/'+n:sha(HERE/n)for n in own},unchanged_LibC_header_sha256=sha(stage/'source/windows/libc.h'),source_proof=desc(a.source_proof),Bionic_reference=desc(a.reference),oracle=desc(stage/'native-oracle.tsv'),format_oracle=desc(stage/'native-formats.tsv'),positive_stage=dict(path=str(stage),status='All positive native-oracle and actual NDK tests passed; collection failed only because WSL truncated Windows access-violation status to5',frozen_original_controller=desc(old_controller),artifacts=artifacts,actual_positive_commands=failed['commands']),finalizing_controller=desc(controller),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),native_oracle_mktime_records=96,native_format_records=100,actual_NDK_calls=26,APIs=8,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],negative_controls=negatives,executable=desc(stage/'calendar-test.exe'),stdout=desc(stage/'actual-Windows-calendar.log'))),commands=commands,limits='Positive stage executed with its frozen original controller; no claim positive tests executed after controller collection fix. Same verified stage EXE used for two fresh native Windows Process.ExitCode negative controls. Only current controller differs from prior held input; all implementation, caller, native reference, C++ tests, tools and sourceproof bytes remain equal. Original WSLstatus5 failure preserved.96 local-year records plus100formats compared against actual selectedBionic;8 out-of-host-range records explicitly excluded/failclosed. No Windows machineTZ changes, glibc proxy, production game/build/cohort or stale-source exception for code under test.')
  (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CALENDAR-QUALIFICATION',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['reference','windows'],required=True);p.add_argument('--ndk',type=Path,required=True);p.add_argument('--qemu',type=Path);p.add_argument('--out',type=Path,required=True)
 for key in('reference','lift','semantics-dir','support-source','source-proof','reuse-host-stage'):p.add_argument('--'+key,type=Path)
 p.add_argument('--reference-sha256');p.add_argument('--source-proof-sha256');a=p.parse_args();return reference(a)if a.mode=='reference'else(finalize_existing(a)if a.reuse_host_stage else windows(a))
if __name__=='__main__':main()
