"""Exact Unity scanner formats: actual static Bionic versus NDK Windows calls."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('libc_scan_profiles_cases.h','libc_scan_profiles_guest.c','libc_scan_profiles_ref.c','libc_scan_profiles_test.cpp','libc_scan_profiles.md','test_libc_scan_profiles.py')
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def records(path):
 lines=[s for s in Path(path).read_text().splitlines()if s.startswith('REC ')];assert lines and all(int(s.split()[1])==i for i,s in enumerate(lines));return lines
def digest(lines):return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','support-source','out'):ap.add_argument('--'+k,type=Path,required=True)
 ap.add_argument('--qemu',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static'));ap.add_argument('--reference-only',action='store_true');ap.add_argument('--reference',type=Path);ap.add_argument('--production-cpp-sha256');ap.add_argument('--production-header-sha256');a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
  for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.qemu)
  if a.reference:
   ref=json.loads(a.reference.read_text());assert ref['passed']is True and ref['actual_static_Bionic']is True
   for n in('libc_scan_profiles_cases.h','libc_scan_profiles_guest.c','libc_scan_profiles_ref.c'):assert ref['reference_sources']['windows/'+n]==sha(source/'windows'/n)
   for n in('NDK_object','reference','stdout','NDK_compiler','qemu'):d=ref[n];assert sha(d['path'])==d['sha256'];pin(d['path'])
   pin(a.reference);core=Path(ref['NDK_object']['path']);native=records(ref['stdout']['path']);assert ref['canonical_records']==dict(count=len(native),sha256=digest(native))
  else:
   core=out/'ndk-scan.o';run([ndk,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-c',source/'windows/libc_scan_profiles_guest.c','-o',core],'compile-NDK-caller');reference=out/'Bionic-reference';run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'windows/libc_scan_profiles_ref.c',core,'-o',reference],'compile-static-Bionic')
   with reference.open('rb')as f:
    elf=ELFFile(f);segments=list(elf.iter_segments());assert elf['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in segments);tls=[s for s in segments if s['p_type']=='PT_TLS'];assert len(tls)==1 and tls[0]['p_align']>=64;tls_info=dict(alignment=tls[0]['p_align'],memory_bytes=tls[0]['p_memsz'])
   run([a.qemu,reference],'actual-static-Bionic');native=records(out/'actual-static-Bionic.log');assert f'SCAN-BIONIC-PASS records={len(native)} TLS=17'in(out/'actual-static-Bionic.log').read_text();ref=dict(passed=True,actual_static_Bionic=True,reference_sources={'windows/'+n:sha(source/'windows'/n)for n in('libc_scan_profiles_cases.h','libc_scan_profiles_guest.c','libc_scan_profiles_ref.c')},canonical_records=dict(count=len(native),sha256=digest(native)),NDK_object=desc(core),reference=desc(reference),stdout=desc(out/'actual-static-Bionic.log'),NDK_compiler=desc(ndk),qemu=desc(a.qemu),PT_TLS=tls_info,no_PT_INTERP=True,commands=commands,limits='Actual static NDK Bionic scanf differential records. Complete output bytes/canaries and errno included. Not glibc or native Windows CRT reference. No invalid C caller cases run against Bionic.')
   (out/'Bionic-reference.json').write_text(json.dumps(ref,indent=2)+'\n')
  if a.reference_only:
   for p,h in held.items():assert sha(p)==h,p
   (out/'acceptance.json').write_text(json.dumps(ref,indent=2)+'\n');print('SCAN-REFERENCE',sha(out/'acceptance.json'),flush=True);return
  assert a.production_cpp_sha256 and a.production_header_sha256;production={'windows/libc.cpp':a.production_cpp_sha256,'windows/libc.h':a.production_header_sha256}
  for n,h in production.items():assert sha(source/n)==h and sha(a.support_source/n)==h;pin(a.support_source/n)
  base=a.support_source/'work/windows-first-frame-sched-yield1/sources/recomp/windows';binding=dict(passed=True,production_sources=production,baseline_sources={n:desc(base/Path(n).name)for n in production},candidate_sources={n:desc(source/n)for n in production},scope='Exact source binding to preceding actual game snapshot; not full semantic equivalence')
  (out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n');(out/'Bionic-reference.json').write_text(json.dumps(ref,indent=2)+'\n');pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'scan.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7b000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include'),'-I'+wp(translated),'-DSCAN_LIBRARY="'+wp(guest)+'"'];objects=[]
  for relative in('windows/libc.cpp','whole/runtime.cpp','windows/libc_scan_profiles_test.cpp'):
   obj=out/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[];run([cxx,*flags,*strict,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'scan.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows');text=(out/'actual-Windows.log').read_text();m=re.search(r'SCAN-PROFILES-PASS checks=(\d+) NDK_calls=(\d+) formats=4 old_integer=1 State=1200 Memory64=1',text);assert m;host=records(out/'actual-Windows.log');assert native==host,next((str(i)+': '+x[:80]+' != '+y[:80]for i,(x,y)in enumerate(zip(native,host))if x!=y),'record count mismatch');assert len(host)==int(m[2])
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),Bionic_reference=desc(out/'Bionic-reference.json'),NDK_object=desc(core),differential_records=dict(count=len(host),sha256=digest(host)),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=1,exact_string_formats=4,old_integer_profile=True,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/'actual-Windows.log'))),controls=['same actual NDK sixGP scanf object in staticBionic and Windows','EOF/mismatch/partialassignments/fullunchangedoutputrecords','width15 width3 suppressedwidth45 and %c exactly1 noNUL','CR/LF and highbyteUTF8 bytes','old%llu normal/negative/overflow/EOF regression','input/format outputaliases snapshot','unassigned invalidoutputs skipped; assignedRO/NOACCESS/GUARD/crosspage/null/overflow rejected','exactpagefit includingNUL','native errno LastError nonzeroFENV at genuine installedcallback','State1200align16/SIMD128/highcells/saved64regs/PCSP/opaqueMemory64'],held_inputs=held,commands=commands,limits='Four exact string formats plus retained %llu only; no general scanf or foreign va_list. Differential uses actual static Bionic on valid C caller cases. Assigned-output/profile negative tests are host defensive policy. Valid readable input/format C strings are required; no safe-input-pointer or catchable arbitrary-read-failure claim. Assigned fields publish sequentially, not transactional across multiple outputs. No production edit, game/fullhost build, observer, or old broad campaign.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('SCAN-PROFILES-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
