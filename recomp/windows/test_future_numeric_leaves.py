"""Unselected future four-leaf original ARM/raw/exact-polled ordinary-geometry oracle."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('future_numeric_leaf_cases.h','future_numeric_leaf_ref.c','future_numeric_leaf_ref.S','future_numeric_leaf_test.cpp','test_future_numeric_leaves.py')
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
  candidate=W/'future-fp-leaf-batch-preparation1/static-candidates.json';assert sha(candidate)=='dc23430a88b2a3c7df8e002ada041f65e21d25b7ad22b0dfb1fcd4e03a6c2d78';batch=json.loads(candidate.read_text());assert batch['passed']is True and batch['selected']is False
  expected=['0x70652c68','0x7066e6c0','0x707877a0','0x70a41660'];assert [row['head']for row in batch['candidates']]==expected;polled=[];raw_irs=[]
  for row in batch['candidates']:
   c=row['payload'];assert sha(row['candidate']['path'])==row['candidate']['sha256']and c['definitions']==128 and c['target_head']==row['head'];pin(row['candidate']['path']);polled.append(Path(c['candidate_object']['path']));raw_irs.append(Path(c['raw_IR']['path']))
   for item in(c['candidate_object'],c['raw_IR'],c['polled_IR']):assert sha(item['path'])==item['sha256'];pin(item['path'])
  pin(candidate);(out/'entries.inc').write_text(''.join('ENTRY('+h[2:]+')\n'for h in expected))
  source=out/'source';source.mkdir()
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  parent=W/'windows-first-frame-frame-rounding1/sources/recomp';elf=W/'windows-first-frame-guest-transfer1/native/libunity.so';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  for p in(elf,ndk,qemu,cxx,Path('/usr/bin/clang++-18'),Path('/usr/bin/llvm-nm-18')):pin(p)
  for folder in('whole','fastaes'):
   target=out/folder;target.mkdir()
   for p in(parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or p.name in('runtime.cpp','cooperative_poll.cpp')):shutil.copyfile(p,target/p.name);pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls',source/'future_numeric_leaf_ref.c',source/'future_numeric_leaf_ref.S','-o',out/'original-ARM'],'compile-original-ARM');arm=run([qemu,out/'original-ARM',elf],'actual-original-ARM');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==2304 and 'ORIGINAL-FUTURE-LEAF-PASS executions=2304 TLS=17'in arm
  defs=set();refs=set()
  for obj in polled:
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',obj],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',obj],text=True)))
  sentinels=sorted(refs-defs);assert not {'sub_'+h[2:]for h in expected}&set(sentinels)
  (out/'unexecuted-sentinels.inc').write_text(''.join('extern "C" Memory*'+name+'(State&,addr_t,Memory*){fputs("UNEXECUTED-LINK-SENTINEL '+name+'\\n",stderr);abort();}\n'for name in sentinels))
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source),'-I'+wp(out)]
  support=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);support.append(obj)
  result={}
  for label in('polled','raw'):
   objects=polled
   if label=='raw':
    objects=[]
    for index,ir in enumerate(raw_irs):
     obj=out/('raw-'+str(index)+'.o');run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',ir,'-o',obj],'compile-raw-'+str(index));objects.append(obj)
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'future_numeric_leaf_test.cpp'),*map(wp,objects),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-Windows-'+label)
   actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'record count mismatch');assert 'WINDOWS-FUTURE-LEAF-PASS executions=2304'in text;result[label]=dict(executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),exact_records=len(actual))
  for p,v in held.items():assert sha(p)==v,p
  prior=W/'unity-70167bbc-repair1/final-acceptance.json';assert sha(prior)=='d459f6fe88a8ca337ef80bd3e939bc2cdc5120fc5d679da89861b93e610d8d4b'
  receipt=dict(passed=True,selected=False,actual_original_reach_observed=False,scope='Four future unselected whole-leaf candidates, exact512definition polledCOFF total and original ARM/rawWindows. Predefined normal/zero scalar and vector inputs with bounded owned memory; no helpers.',candidate_batch=desc(candidate),heads=expected,indices=[231,234,262,366],original_ELF=desc(elf),platforms=['original_ARM_static_Bionic','raw_Windows','exact_polled_Windows'],executions_per_platform=2304,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),records_exact=True,scalar_inputs_each=16,vector_inputs=8,vector_alias_shapes=['distinct','output_equals_first_input','output_equals_second_input'],FPCR_modes=16,initial_FPSR_values=2,State1200=True,full_State_nonoutput_bytes_checked_each_call=True,Memory64=True,helpers=0,helper_result_stubs=0,unexecuted_abort_only_link_sentinels=sentinels,original_stdout=desc(out/'actual-original-ARM.log'),hosts=result,prior_function_qualification_and_known_edge_limits=desc(prior),universal_FP_equivalence_claim=False,live_input_domain_observed=False,owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='Future unselected code only. Ordinary normal/zero scalar and vector operands, bounded finite vector intermediates; no NaN/subnormal inputs/traps/AFP claim. Earlier96/2176 sibling edge gaps retained separately, not normalized. No claim these fourheads or values have been reached in game.127neighbor preservation percontainer separately pinned by staticcandidatepacket. No fullhost/game/system changes.')
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('FUTURE-NUMERIC-LEAVES-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
