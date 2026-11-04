"""Actual NDK uname ABI and real Windows host identity/fault qualification.

The small leaf callers use unchanged compile.py. Production guarded game code
is independently frozen and is not rebuilt or launched by this component gate.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent
OWN=('libc_uname_guest.c','libc_uname_test.cpp','test_libc_uname.py')
PRODUCTION=('windows/libc.cpp','windows/libc_uname_detail.h')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def desc(path):return dict(path=str(path),sha256=sha(path))
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for key in('ndk','lift','semantics-dir','support-source','out'):parser.add_argument('--'+key,type=Path,required=True)
 parser.add_argument('--source-proof',type=Path);parser.add_argument('--source-proof-sha256');a=parser.parse_args()
 out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);source=out/'source';commands=[];held={}
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def pin(path):held[str(Path(path).resolve())]=sha(path)
 def run(argv,label):
  argv=list(map(str,argv));print('STAGE',label,flush=True);commands.append(dict(label=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  if a.source_proof:
   assert a.source_proof_sha256 and sha(a.source_proof)==a.source_proof_sha256 and json.loads(a.source_proof.read_bytes())['passed']is True;pin(a.source_proof)
  for directory in('windows','whole','fastaes'):
   target=source/directory;target.mkdir(parents=True)
   for original in(a.support_source/directory).iterdir():
    if original.is_file()and original.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(original,target/original.name)
  for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name);pin(HERE/name)
  for relative in PRODUCTION:pin(a.support_source/relative);assert sha(source/relative)==sha(a.support_source/relative)
  unchanged_header=sha(a.support_source/'windows/libc.h');assert sha(source/'windows/libc.h')==unchanged_header
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.lift);pin(a.semantics_dir/'aarch64.bc')
  pin(a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/sys/utsname.h')
  for tool in('/usr/bin/clang-18','/usr/bin/clang++-18','/mnt/c/mingw64/bin/g++.exe','/mnt/c/mingw64/bin/gcc.exe'):pin(tool)
  guest=out/'uname.so';run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/libc_uname_guest.c','-o',guest],'compile-NDK-caller')
  translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x5a000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-actual-NDK')
  manifest=json.loads((translated/'manifest.json').read_bytes());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader')
  includes=a.support_source/'work/remill-src/include';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(includes)]
  objects=[]
  for relative in('windows/libc.cpp','whole/runtime.cpp'):
   obj=out/(Path(relative).stem+'.o');run([cxx,*flags,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  fixture=source/'windows/libc_uname_test.cpp';test=out/'uname-test.o';run([cxx,*flags,'-Wall','-Wextra','-Werror','-I'+wp(translated),f'-DUNAME_LIBRARY="{wp(guest)}"','-c',wp(fixture),'-o',wp(test)],'strict-compile-test')
  exe=out/'uname-test.exe';run([cxx,wp(test),*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows')
  run([exe],'actual-Windows-NDK-calls');text=(out/'actual-Windows-NDK-calls.log').read_text();match=re.fullmatch(r'UNAME-PASS checks=(\d+) NDK_calls=(\d+) actual_host_fields=1 Bionic_bytes=390 native_layout_calls=8 identity_fabricated=0\s*',text);assert match,text[-2000:]
  assert int(match[1])>0 and int(match[2])==24
  for path,digest in held.items():assert sha(path)==digest,path
  assert sha(a.support_source/'windows/libc.h')==unchanged_header
  result=dict(passed=True,scope='Real Windows host identity mapped to Bionic utsname390 ABI, with actual NDK direct/indirect callers and stable mapped-protection fault tests; no fabricated Linux/kernel/device identity or game execution',production_sources={relative:sha(source/relative)for relative in PRODUCTION},test_sources={'windows/'+name:sha(source/'windows'/name)for name in OWN},unchanged_LibC_header_sha256=unchanged_header,source_proof=desc(a.source_proof)if a.source_proof else None,platforms=dict(windows=dict(exit_code=0,checks=int(match[1]),actual_NDK_calls=int(match[2]),actual_NDK_layout_calls=8,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=manifest['unsupported_traces'],unresolved=manifest['unresolved_direct_targets'],executable=desc(exe),stdout=desc(out/'actual-Windows-NDK-calls.log'))),checks=dict(Bionic390_and_all_field_offsets_verified_by_NDK=True,independent_actual_Windows_OS_name_release_version_native_machine_node_domain=True,direct_and_indirect_signed32_errno_contract=True,only390_bytes_and_unaligned_output=True,exact_writable_page_end_succeeds=True,null_overflow_readonly_guard_crosspage_EFAULT=True,guard_protection_never_consumed=True,query_failure_and_UTF8_errors_never_publish_success=True,native_errno_LastError_FENV_restored=True,actual_native_thread_guest_errno_isolated=True,old_marker_prefix_unchanged=True),held_inputs=held,commands=commands,limits='Existing leaf compile.py path, not a production-cohort regeneration. No assertion that native Linux/ARM uname field contents equal Windows. Concurrent external page-protection races remain outside this bounded stable-mapping profile.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNAME-QUALIFICATION',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
