"""Original ARM and raw/exact-polled Windows fullbody frame-rounding oracle."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('frame_rounding_cases.h','frame_rounding_ref.c','frame_rounding_ref.S','frame_rounding_test.cpp','test_frame_rounding.py')
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
  candidate=W/'unity-70167bbc-repair1/candidate.json';helpers=W/'frame-rounding-helper-closure1/acceptance.json'
  assert sha(candidate)=='df875e23f758b58b708791bef948666e3182a697569ad8e00c1f27cba3324e54'and sha(helpers)=='bc7e11a748d3562a669d11ad8f569eba3ce369eb9fc282f4f22262b3cfa00d4c'
  c=json.loads(candidate.read_text());h=json.loads(helpers.read_text());assert c['passed']and h['passed']and c['definitions']==128 and c['target_head']=='0x70167bbc'
  polled=Path(c['candidate_object']['path']);raw_ir=Path(c['raw_IR']['path']);helperobj=helpers.parent/'real-helpers.o';header=helpers.parent/'component_helpers.h'
  for row in(c['candidate_object'],c['raw_IR'],c['polled_IR']):assert sha(row['path'])==row['sha256'];pin(row['path'])
  assert sha(helperobj)=='da75bdb990d496ddc6cc3c26c0230549fbd065e089034b0c290b4cd9e3f5af7a'
  for p in(candidate,helpers,helperobj,header):pin(p)
  source=out/'source';source.mkdir()
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  shutil.copyfile(header,out/'component_helpers.h')
  parent=W/'windows-first-frame-paren-scan1/sources/recomp';elf=W/'windows-first-frame-guest-transfer1/native/libunity.so';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  for p in(elf,ndk,qemu,cxx,Path('/usr/bin/clang++-18'),Path('/usr/bin/llvm-nm-18')):pin(p)
  for folder in('whole','fastaes'):
   target=out/folder;target.mkdir()
   for p in(parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or p.name in('runtime.cpp','cooperative_poll.cpp')):shutil.copyfile(p,target/p.name);pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls',source/'frame_rounding_ref.c',source/'frame_rounding_ref.S','-o',out/'original-ARM'],'compile-original-ARM');arm=run([qemu,out/'original-ARM',elf],'actual-original-ARM');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==336 and 'ORIGINAL-FRAME-ROUNDING-PASS executions=336 TLS=17'in arm
  defs=set();refs=set()
  for obj in(polled,helperobj):
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',obj],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',obj],text=True)))
  sentinels=sorted(refs-defs);assert not {'sub_70167bbc','sub_7025d944','sub_70366140','sub_70365b10'}&set(sentinels)
  (out/'unexecuted-sentinels.inc').write_text(''.join('extern "C" Memory*'+name+'(State&,addr_t,Memory*){fputs("UNEXECUTED-LINK-SENTINEL '+name+'\\n",stderr);abort();}\n'for name in sentinels))
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source),'-I'+wp(out)]
  support=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);support.append(obj)
  result={}
  for label,obj in(('polled',polled),('raw',out/'raw.o')):
   if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',raw_ir,'-o',obj],'compile-raw')
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'frame_rounding_test.cpp'),wp(obj),wp(helperobj),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-Windows-'+label)
   actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'record count mismatch');assert 'WINDOWS-FRAME-ROUNDING-PASS executions=336'in text;result[label]=dict(executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),exact_records=len(actual))
  for p,v in held.items():assert sha(p)==v,p
  earlier=W/'frame-rounding-qualification2';edge_paths=[earlier/n for n in ('failure.json','mismatch-summary.json','actual-original-ARM.log','actual-Windows-polled.log')];edges={p.name:desc(p)for p in edge_paths};assert json.loads((earlier/'mismatch-summary.json').read_text())['mismatches']==96
  receipt=dict(passed=True,normal_finite_geometry_profile='Before execution select each input scalar by exponent!=255 and (exponent!=0 or mantissa==0); signedzero allowed. No output/record-based filtering.',known_excluded_edge_observation=dict(records_each=2176,mismatches=96,scope='Preserved Q2 full-profile discrepancy: signalingNaN secondFCMP misses IOC; subnormal scale with FZ can change results. Not normalized or accepted.',artifacts=edges),scope='Normal-finite geometry profile of actual complete original70167bbc function with three genuine currentselected helpers, TEST-owned clean component/type-range/chain data. Exact raw128function and productionpolled128function candidate objects executed; no helper-result substitution.',candidate=desc(candidate),helper_closure=desc(helpers),original_ELF=desc(elf),platforms=['original_ARM_static_Bionic','raw_Windows','exact_polled_Windows'],executions_per_platform=336,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),records_exact=True,samples=19,lookup_miss_profiles=2,parent_chain_shapes=2,FPCR_modes=4,initial_FPSR_values=2,State1200=True,Memory64=True,real_helper_heads=['0x7025d944','0x70366140','0x70365b10'],helper_result_stubs=0,unexecuted_abort_only_link_sentinels=sentinels,original_stdout=desc(out/'actual-original-ARM.log'),hosts=result,owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='Explicit TEST seed of type range7123fcf8 and validclean owned components; not whole Unity initialization or dirty transform/update helper paths. Normal/zero geometry inputs only, four rounding modes and two stickyFPSR seeds; FZ/DN, nonfinite and subnormal inputs excluded by explicit input predicate. Known Q2 edge mismatches preserved separately; no universal floating-point correctness or unlogged runtime values inferred. Neighbor127 preservation is separately pinned in candidate receipt. No host/game/system changes.')
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('FRAME-ROUNDING-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
