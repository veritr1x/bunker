"""Original ARM and raw/exact-polled Windows whole-leaf normal-geometry oracle."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('leaf_rounding_cases.h','leaf_rounding_ref.c','leaf_rounding_ref.S','leaf_rounding_test.cpp','test_leaf_rounding.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
  return(out/(label+'.log')).read_text()
 try:
  candidate=W/'unity-70167fc4-repair1/candidate.json';assert sha(candidate)=='9dd8a4b417d49149eb9c12ea79de9f8428cb7a0389182d8c40304bb9eb387f4c'
  c=json.loads(candidate.read_text());assert c['passed']and c['definitions']==128 and c['target_head']=='0x70167fc4';polled=Path(c['candidate_object']['path']);raw_ir=Path(c['raw_IR']['path'])
  for row in(c['candidate_object'],c['raw_IR'],c['polled_IR']):assert sha(row['path'])==row['sha256'];pin(row['path'])
  pin(candidate)
  source=out/'source';source.mkdir()
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  parent=W/'windows-first-frame-frame-rounding1/sources/recomp';elf=W/'windows-first-frame-guest-transfer1/native/libunity.so';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  for p in(elf,ndk,qemu,cxx,Path('/usr/bin/clang++-18'),Path('/usr/bin/llvm-nm-18')):pin(p)
  for folder in('whole','fastaes'):
   target=out/folder;target.mkdir()
   for p in(parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or p.name in('runtime.cpp','cooperative_poll.cpp')):shutil.copyfile(p,target/p.name);pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls',source/'leaf_rounding_ref.c',source/'leaf_rounding_ref.S','-o',out/'original-ARM'],'compile-original-ARM');arm=run([qemu,out/'original-ARM',elf],'actual-original-ARM');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==768 and 'ORIGINAL-LEAF-ROUNDING-PASS executions=768 TLS=17'in arm
  defs=set();refs=set()
  for obj in(polled,):
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',obj],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',obj],text=True)))
  sentinels=sorted(refs-defs);assert 'sub_70167fc4'not in sentinels
  (out/'unexecuted-sentinels.inc').write_text(''.join('extern "C" Memory*'+name+'(State&,addr_t,Memory*){fputs("UNEXECUTED-LINK-SENTINEL '+name+'\\n",stderr);abort();}\n'for name in sentinels))
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source),'-I'+wp(out)]
  support=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);support.append(obj)
  result={}
  for label,obj in(('polled',polled),('raw',out/'raw.o')):
   if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',raw_ir,'-o',obj],'compile-raw')
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'leaf_rounding_test.cpp'),wp(obj),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-Windows-'+label)
   actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'record count mismatch');assert 'WINDOWS-LEAF-ROUNDING-PASS executions=768'in text;result[label]=dict(executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),exact_records=len(actual))
  for p,v in held.items():assert sha(p)==v,p
  prior=W/'unity-70167bbc-repair1/final-acceptance.json';assert sha(prior)=='d459f6fe88a8ca337ef80bd3e939bc2cdc5120fc5d679da89861b93e610d8d4b'
  receipt=dict(passed=True,scope='Actual original complete28byte70167fc4 leaf and exact repaired128definition COFF, predefined24normal/zero geometry input pairs. No helpers or helper substitutions.',normal_geometry_input_profile='Each operand checked by exponent!=255 and (exponent!=0 or mantissa==0) before execution. Signedzero, signs, threshold/clamp, signedconversion bounds and overflow from finite operands included; no NaN/subnormal inputs.',candidate=desc(candidate),original_ELF=desc(elf),platforms=['original_ARM_static_Bionic','raw_Windows','exact_polled_Windows'],executions_per_platform=768,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),records_exact=True,input_pairs=24,FPCR_modes=16,initial_FPSR_values=2,State1200=True,full_State_nonoutput_bytes_checked_each_call=True,Memory64=True,helpers=0,helper_result_stubs=0,unexecuted_abort_only_link_sentinels=sentinels,original_stdout=desc(out/'actual-original-ARM.log'),hosts=result,prior_function_qualification_and_known_edge_limits=desc(prior),universal_FP_equivalence_claim=False,live_input_domain_observed=False,owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='Only predefined24normal/zero geometry pairs; no nonfinite/subnormal input or traps/AFP claim. Earlier96/2176 edge gaps from sibling function retained in prior packet, not normalized or accepted. Actual live leaf inputs/FPCR unlogged.127neighbor and sibling repair preservation separately pinned by candidate. No host/game/system changes.')
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('LEAF-ROUNDING-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
