"""Real static Bionic / translated Windows resolver qualification, without game execution."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('libc_getaddrinfo_cases.h','libc_getaddrinfo_guest.c','libc_getaddrinfo_ref.c','libc_getaddrinfo_test.cpp','libc_getaddrinfo.md','test_libc_getaddrinfo.py')
REFERENCE=OWN[:3]
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def records(p):return [s for s in Path(p).read_text().splitlines()if s.startswith(('REC ','ERR ','FREE '))]
def digest(lines):return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
def normalize(lines):
 result=[]
 for line in lines:
  if line.startswith('REC '):
   fields=line.split(' ',5)
   if fields[3]=='0':fields[4]='unspecified';line=' '.join(fields)
  result.append(line)
 return result
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--mode',choices=('reference','qualification'),required=True)
 for k in ('ndk','out'):ap.add_argument('--'+k,type=Path,required=True)
 for k in ('lift','semantics-dir','support-source','reference','production-manifest'):ap.add_argument('--'+k,type=Path)
 a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));save(out/'commands.json',commands);print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk)
  if a.mode=='reference':
   source=out/'source';source.mkdir();qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');pin(qemu)
   for n in REFERENCE:shutil.copyfile(HERE/n,source/n);pin(HERE/n)
   core=out/'ndk-getaddrinfo.o';exe=out/'Bionic-reference';run([ndk,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-c',source/'libc_getaddrinfo_guest.c','-o',core],'compile-NDK-object');run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'libc_getaddrinfo_ref.c',core,'-o',exe],'compile-static-Bionic')
   programs=subprocess.check_output(['readelf','-l',str(exe)],text=True);assert 'INTERP'not in programs and 'TLS'in programs;run([qemu,exe],'actual-static-Bionic');text=(out/'actual-static-Bionic.log').read_text();m=re.search(r'GAI-BIONIC-PASS records=(\d+) TLS=17',text);lines=records(out/'actual-static-Bionic.log');assert m and len(lines)==int(m[1]);assert all(sha(p)==h for p,h in held.items())
   result=dict(passed=True,actual_static_Bionic=True,reference_sources={'windows/'+n:sha(source/n)for n in REFERENCE},canonical_records=dict(count=len(lines),sha256=digest(normalize(lines))),raw_records=dict(count=len(lines),sha256=digest(lines)),comparison_rule='Only errno of successful getaddrinfo REC records is unspecified and normalized; every other field and all failure/free errno values remain exact.',api_records={key:sum(s.startswith(prefix)for s in lines)for key,prefix in [('getaddrinfo','REC '),('freeaddrinfo','FREE '),('gai_strerror','ERR ')]},NDK_object=desc(core),reference=desc(exe),stdout=desc(out/'actual-static-Bionic.log'),NDK_compiler=desc(ndk),qemu=desc(qemu),no_PT_INTERP=True,native_TLS=True,commands=commands)
  else:
   assert all((a.lift,a.semantics_dir,a.support_source,a.reference,a.production_manifest));production=json.loads(a.production_manifest.read_text());assert production and set(production)<= {'windows/libc.cpp','windows/libc.h','windows/libc_resolver_detail.h'};source=out/'source'
   for folder in('windows','whole','fastaes'):
    target=source/folder;target.mkdir(parents=True)
    for f in(a.support_source/folder).iterdir():
     if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
   for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
   for n,h in production.items():assert sha(source/n)==sha(HERE.parent/n)==h;pin(HERE.parent/n)
   ref=json.loads(a.reference.read_text());assert ref['passed']and ref['actual_static_Bionic'];pin(a.reference)
   investigation_root=a.support_source/'work/libc-getaddrinfo-reference2';investigation={n:desc(investigation_root/n)for n in ('probe-canon2.c','probe-canon2','probe-canon2.log','probe-canon3.c','probe-canon3','probe-canon3.log')}
   for value in investigation.values():pin(value['path'])
   for n in REFERENCE:assert ref['reference_sources']['windows/'+n]==sha(source/'windows'/n)
   for n in('NDK_object','reference','stdout','NDK_compiler','qemu'):d=ref[n];assert sha(d['path'])==d['sha256'];pin(d['path'])
   native=records(ref['stdout']['path']);assert ref['canonical_records']==dict(count=len(native),sha256=digest(normalize(native)));assert ref['raw_records']==dict(count=len(native),sha256=digest(native));core=Path(ref['NDK_object']['path']);save(out/'Bionic-reference.json',ref)
   base=a.support_source/'work/windows-first-frame-inet-pton1/sources/recomp';binding=dict(passed=True,production_sources=production,baseline_sources={n:desc(base/n)for n in ('windows/libc.cpp','windows/libc.h')},candidate_sources={n:desc(source/n)for n in production},scope='Byte binding to preceding actual inet_pton game snapshot; no semantic whole-file equivalence claim');save(out/'source-binding.json',binding)
   pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'resolver.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7c000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
   cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include'),'-I'+wp(translated),'-DGAI_LIBRARY="'+wp(guest)+'"'];objects=[]
   for relative in('windows/libc.cpp','whole/runtime.cpp','windows/libc_getaddrinfo_test.cpp'):
    obj=out/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[];run([cxx,*flags,*strict,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
   exe=out/'resolver.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows');text=(out/'actual-Windows.log').read_text();m=re.search(r'GETADDRINFO-PASS checks=(\d+) differential_NDK_calls=(\d+) actual_NDK_calls=(\d+) concurrent_NDK_calls=(\d+) APIs=3 forms=2 State=1200 Memory64=1 nativeNameLookup=1',text);assert m;host=records(out/'actual-Windows.log');assert normalize(native)==normalize(host),next((str(i)+': '+x[:150]+' != '+y[:150]for i,(x,y)in enumerate(zip(normalize(native),normalize(host)))if x!=y),'record count mismatch');assert len(host)==int(m[2])and int(m[3])==int(m[2])+int(m[4])and int(m[4])==32;assert all(sha(p)==h for p,h in held.items())
   raw_differences=[dict(record=i,Bionic=x,Windows=y)for i,(x,y)in enumerate(zip(native,host))if x!=y];errno_scope=dict(rule=ref['comparison_rule'],successful_errno_fields_normalized=sum(s.startswith('REC ')and s.split()[3]=='0'for s in native),failure_errno_fields_compared_exactly=True,free_errno_immediately_initialized_to123=True,raw_differences=raw_differences,EAI_SYSTEM_failure_cases=0,isolated_Bionic_probes=investigation,notes='Successful resolver errno is unspecified. Actual Bionic first strdup sets incidental errno22 under QEMU; no warmup or synthetic errno is added. All raw observations remain pinned. EAI_SYSTEM/native failure mapping is source-reviewed, not fault-injected by this profile.')
   result=dict(passed=True,production_sources=production,owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),Bionic_reference=desc(out/'Bionic-reference.json'),NDK_object=desc(core),differential_records=dict(count=len(host),sha256=digest(normalize(host))),raw_Windows_records=dict(count=len(host),sha256=digest(host)),errno_comparison=errno_scope,api_records=ref['api_records'],platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),differential_NDK_calls=int(m[2]),actual_NDK_calls=int(m[3]),concurrent_NDK_calls=int(m[4]),APIs=3,forms=2,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/'actual-Windows.log'))),controls=['same actual NDK object in actualstaticBionic and translatedWindows direct/volatilepointer calls','actual NDK addrinfo48/addrlen32/canon24/addr32/next40 staticasserts','complete sorted chain records preserve duplicates and all namedfields/addressbytes/canon','Androidfamilies/flags/errorcodes/errorstrings and errno/outputpublication','numeric/null-host/passive/canonical/service range and strtoul edges','invalidflags/family/socktype/protocol and nonzero reservedhintfields','free successful chain/null via real translatedcaller','real nativeWindows localhost name lookup separately from crossplatform records','native errno LastError nonzeroFENV at installed callback','State1200/SIMD128/highcells/saved64regs/PCSP/opaqueMemory64','two nativeworker concurrent provider allocations and crossed free ownership'],held_inputs=held,commands=commands,limits='Cross-Bionic comparison is deterministic numeric/null/service/error profile only. Complete chains are sorted for comparison, preserving duplicates; host-dependent address order, DNS results, ADDRCONFIG/interface state and network routing are not asserted byteidentical across OS. Successful getaddrinfo errno is explicitly unspecified and normalized; raw observations remain in hashed logs. Failure/free errno remains exact. The Windows localhost lookup exercises real native name resolution but does not prove an external DNS packet or real game networking. No socket creation/game/fullhost build/settings modification. Pointer contract is valid readable strings/hints and writable output storage, not arbitrary C pointer safety. Allocation-pressure/nativeDNSfailure fault injection excluded; reviewed error mapping is separately bound production source.')
  save(out/'acceptance.json',result);print('GETADDRINFO-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  save(out/'failure.json',dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held));raise
if __name__=='__main__':main()
