"""Actual static Bionic versus Windows numeric-address import qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('libc_inet_pton_cases.h','libc_inet_pton_guest.c','libc_inet_pton_ref.c','libc_inet_pton_test.cpp','libc_inet_pton.md','test_libc_inet_pton.py')
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def records(p):
 lines=[s for s in Path(p).read_text().splitlines()if s.startswith('REC ')];assert lines and all(int(s.split()[1])*2+int(s.split()[2])==i for i,s in enumerate(lines));return lines
def digest(lines):return hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','support-source','out','reference'):ap.add_argument('--'+k,type=Path,required=True)
 ap.add_argument('--production-cpp-sha256',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=out/'source';commands=[];held={}
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
  ref=json.loads(a.reference.read_text());assert ref['passed']is True and ref['actual_static_Bionic']is True
  for n in('libc_inet_pton_cases.h','libc_inet_pton_guest.c','libc_inet_pton_ref.c'):assert ref['reference_sources']['windows/'+n]==sha(source/'windows'/n)
  for n in('NDK_object','reference','stdout','NDK_compiler','qemu'):d=ref[n];assert sha(d['path'])==d['sha256'];pin(d['path'])
  pin(a.reference);native=records(ref['stdout']['path']);assert ref['canonical_records']==dict(count=len(native),sha256=digest(native));core=Path(ref['NDK_object']['path']);(out/'Bionic-reference.json').write_text(json.dumps(ref,indent=2)+'\n')
  production={'windows/libc.cpp':a.production_cpp_sha256};assert sha(source/'windows/libc.cpp')==a.production_cpp_sha256 and sha(HERE/'libc.cpp')==a.production_cpp_sha256;pin(HERE/'libc.cpp');pin(HERE/'libc.h');header=sha(HERE/'libc.h');base=a.support_source/'work/windows-first-frame-sscanf1/sources/recomp/windows/libc.cpp';pin(base)
  binding=dict(passed=True,production_sources=production,unchanged_LibC_header_sha256=header,baseline=desc(base),candidate=desc(source/'windows/libc.cpp'),scope='Exact source binding to preceding actual game snapshot; no whole-file semantic equivalence claim');(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';assert sha(ndk)==ref['NDK_compiler']['sha256'];pin(a.lift);pin(a.semantics_dir/'aarch64.bc');guest=out/'inet.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7c000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include'),'-I'+wp(translated),'-DINET_LIBRARY="'+wp(guest)+'"'];objects=[]
  for relative in('windows/libc.cpp','whole/runtime.cpp','windows/libc_inet_pton_test.cpp'):
   obj=out/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[];run([cxx,*flags,*strict,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'inet.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows');text=(out/'actual-Windows.log').read_text();m=re.search(r'INET-PTON-PASS checks=(\d+) NDK_calls=(\d+) forms=2 State=1200 Memory64=1 networkRequests=0',text);assert m;host=records(out/'actual-Windows.log');assert native==host,next((str(i)+': '+x[:70]+' != '+y[:70]for i,(x,y)in enumerate(zip(native,host))if x!=y),'record count mismatch');assert len(host)==int(m[2])
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,unchanged_LibC_header_sha256=header,owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),Bionic_reference=desc(out/'Bionic-reference.json'),NDK_object=desc(core),differential_records=dict(count=len(host),sha256=digest(host)),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=1,forms=2,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/'actual-Windows.log'))),controls=['same actual NDK direct/volatilepointer caller object in staticBionic and Windows','AndroidAF2/10 mapping and unsupportedfamily97','IPv4 decimal leadingzeros/range/count/abbreviations/rejectedtrailingtext','IPv6 compression/groups/mixedcase/IPv4tails/brackets/scope/trailingtext','complete4/16output and failurecanaries/status/guesterrno','unsupportedfamily status97 and unchanged valid output','invalidsyntax leaves valid output unchanged','alias snapshot and exactunaligned/pageend outputs','validunaligned and exactpageend binaryoutput canaries','native errno LastError nonzeroFENV at realcallback','State1200align16/SIMD128/highcells/saved64regs/PCSP/opaqueMemory64','noWSAStartup/socket/networkRequests'],held_inputs=held,commands=commands,primary_API='https://learn.microsoft.com/en-us/windows/win32/api/ws2tcpip/nf-ws2tcpip-inet_pton',limits='Actual static Bionic differential profile, not glibc. Onlynumericaddressconversion; no socket, DNS, network, WSAStartup, setting change, game or fullhost build. Input must be valid readable Cstring; arbitrary invalidsourcepointer testing excluded. Invalid pointer tests are excluded; checked-write defensive policy is reviewed separately in production source. Current sourcebinding does not claim oldmethods semantic equivalence.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('INET-PTON-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
