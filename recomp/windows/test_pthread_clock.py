"""Incremental focused clock_getres qualification with actual static NDK Bionic."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OWN=['pthread_clock_guest.c','pthread_clock_ref.c','pthread_clock_test.cpp','pthread_clock.md','test_pthread_clock.py']
PROOF='e4c80d8fc84e9d6e9441b052eae81eb91779f8c2bc93fdde2fabe650dc62f918'
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',type=Path,required=True);ap.add_argument('--source-proof',type=Path,required=True);ap.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'));ap.add_argument('--reference-root',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root'));a=ap.parse_args();out=a.out.resolve();old=a.reuse.resolve();out.mkdir(exist_ok=False);commands=[]
 def run(argv,label):
  commands.append(dict(stage=label,argv=list(map(str,argv))));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:r=subprocess.run(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+': '+(out/(label+'.log')).read_text(errors='replace')[-3500:])
 try:
  assert sha(a.source_proof)==PROOF;proof=json.loads(a.source_proof.read_text());production=proof['production_sources'];assert proof['passed']and set(production)=={'windows/pthread_host.cpp'}
  assert sha(HERE/'pthread_host.cpp')==production['windows/pthread_host.cpp']and sha(HERE/'pthread_host.h')==proof['unchanged_pthread_header']['sha256']
  assert sha(old/'source/recomp/windows/pthread_clock_guest.c')==sha(HERE/'pthread_clock_guest.c')
  manifest=json.loads((old/'guest/manifest.json').read_text());assert sha(old/'clock.so')==manifest['sha256']and manifest['unsupported_traces']==manifest['unresolved_direct_targets']==[]
  previous_ref=json.loads((old/'Bionic-reference.json').read_text());core=old/'ndk-clock.o';assert sha(core)==previous_ref['NDK_object']['sha256']
  reuse=[old/'runtime.o',old/'cooperative_poll.o',old/'elfload.o',core,old/'clock.so',old/'guest/manifest.json',*[Path(p)for p in manifest['objects']],old/'source/recomp/whole/runtime.cpp',old/'source/recomp/whole/runtime.h',old/'source/recomp/whole/cooperative_poll.cpp']
  assert sha(old/'source/recomp/whole/runtime.cpp')=='052411ac09dd05a6dd229d17f1f991a93ee984ae1f447416cefdf610629f1c56'
  pins={str(p):sha(p)for p in reuse};owned={'windows/'+n:sha(HERE/n)for n in OWN};source=out/'source/recomp';(source/'windows').mkdir(parents=True);(source/'whole').mkdir();(source/'fastaes').mkdir()
  for p in(old/'source/recomp/whole').glob('*.h'):shutil.copyfile(p,source/'whole'/p.name)
  shutil.copyfile(old/'source/recomp/fastaes/elfload.h',source/'fastaes/elfload.h')
  for name in ['pthread_host.h','android_types.h']:shutil.copyfile(old/'source/recomp/windows'/name,source/'windows'/name)
  for name in ['pthread_host.cpp',*OWN]:shutil.copyfile(HERE/name,source/'windows'/name)
  frozen={str(p):sha(p)for p in source.rglob('*')if p.is_file()};(out/'reused-inputs.json').write_text(json.dumps(dict(reused=pins,frozen=frozen,production_sources=production),indent=2)+'\n')
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=a.reference_root/'usr/bin/qemu-aarch64-static';reference=out/'Bionic-reference'
  run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'windows/pthread_clock_ref.c',core,'-o',reference],'compile-NDK-static-Bionic')
  with reference.open('rb')as f:
   elf=ELFFile(f);segments=list(elf.iter_segments());assert elf['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in segments);tls=[s for s in segments if s['p_type']=='PT_TLS'];assert len(tls)==1 and tls[0]['p_align']>=64;tls_info=dict(alignment=tls[0]['p_align'],memory_bytes=tls[0]['p_memsz'])
  run([qemu,reference],'actual-Bionic-reference');reftext=(out/'actual-Bionic-reference.log').read_text();assert 'PTHREAD-CLOCK-REFERENCE-PASS calls=12 TLS=17'in reftext
  bionic=dict(passed=True,actual_static_Bionic=True,scope='Actual NDK static Bionic AArch64 executable under QEMU/Linux. Kernel resolution values need not match Windows.',calls=12,reference=desc(reference),NDK_object=desc(core),stdout=desc(out/'actual-Bionic-reference.log'),NDK_compiler=desc(ndk),qemu=desc(qemu),PT_TLS=tls_info,used_real_TLS_canary=17,no_PT_INTERP=True)
  (out/'Bionic-reference.json').write_text(json.dumps(bionic,indent=2)+'\n')
  oldcmd=json.loads((old/'commands.json').read_text());newobjects={}
  for label,name in [('compile-pthread_host','pthread_host.cpp'),('compile-pthread_clock_test','pthread_clock_test.cpp')]:
   cmd=list(next(x['argv']for x in oldcmd if x['stage']==label));obj=out/(Path(name).stem+'.o');cmd[cmd.index('-c')+1]=wp(source/'windows'/name);cmd[cmd.index('-o')+1]=wp(obj);run(cmd,label);newobjects[name]=obj
  cmd=list(next(x['argv']for x in oldcmd if x['stage']=='link-Windows'));cmd=[wp(newobjects['pthread_host.cpp'])if x.endswith('/pthread_host.o')else wp(newobjects['pthread_clock_test.cpp'])if x.endswith('/pthread_clock_test.o')else x for x in cmd];cmd.insert(1,'-Wl,--wrap='+WRAP);exe=out/'pthread-clock.exe';cmd[cmd.index('-o')+1]=wp(exe);run(cmd,'link-Windows');run([exe],'actual-Windows-clock')
  text=(out/'actual-Windows-clock.log').read_text();m=re.search(r'PTHREAD-CLOCK-PASS checks=(\d+) ndk_calls=(\d+) APIs=1 native_ids=2',text);assert m
  for p,h in {**pins,**frozen}.items():assert sha(p)==h,p
  for p,h in owned.items():assert sha(HERE.parent/p)==h,p
  assert sha(HERE/'pthread_host.cpp')==production['windows/pthread_host.cpp']
  controls=['native Winpthreads exact resolutions IDs0/1','66 genuine direct/pointer NDK calls','validNULL and clock-before-pointer validation','exactly-once guesterrno failures and success preservation','actual installed callback errno LastError/nonzeroFENV preserved via test-only AddImport link wrapper','unaligned/endpage/crosswritablepage16byte outputs and canaries','RO/NOACCESS/GUARD/crosspage/overflow EFAULT with no partial writes','outer Runtime/Pthreads scaffolding excluded from native callback guarantee']
  result=dict(passed=True,production_sources=production,unchanged_pthread_header_sha256=proof['unchanged_pthread_header']['sha256'],source_proof=desc(a.source_proof),owned_sources=owned,Bionic_reference=desc(out/'Bionic-reference.json'),native_clock_identity=desc(ROOT/'recomp/work/clock-boundary1/acceptance.json'),NDK_object=desc(core),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=1,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],native_resolution_ids=[0,1],controls=controls,executable=desc(exe),stdout=desc(out/'actual-Windows-clock.log'))),positive_stage=dict(recompiled_only=['pthread_host.cpp','pthread_clock_test.cpp'],reused_verified_inputs=desc(out/'reused-inputs.json'),previous_attempt=desc(old/'failure.json'),previous_frozen_controller=desc(old/'source/recomp/windows/test_pthread_clock.py'),final_controller=desc(HERE/'test_pthread_clock.py')),commands=commands,limits='Focused Windows provider gate only; no broadpthread replay or game. Q1 GNU/glibc reference retained but NOT the final Bionic oracle. Final reference is actual static NDK Bionic with genuine alignedTLS. Same original NDK object is linked into final Bionic executable and translated Windows library; otherQ1host support/guest objects reused by verified hashes. No claim that old Run/scaffolding preserves LastError; test interposes only registration to measure the genuine new callback.')
  result['evidence']={p.name:sha(p)for p in out.iterdir()if p.is_file()and p.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PTHREAD-CLOCK-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except Exception:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
