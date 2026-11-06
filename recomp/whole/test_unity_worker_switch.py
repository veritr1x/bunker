"""Bounded original Unity worker switch guard qualification; no suffix/game run."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
from elftools.elf.elffile import ELFFile
W=Path('/mnt/c/GitRepos/bunker/recomp/work');HERE=Path(__file__).resolve().parent
OWN=['unity_worker_switch_cases.h','unity_worker_switch_ref.c','unity_worker_switch_ref.S','unity_worker_switch_test.cpp','test_unity_worker_switch.py']
FRONTIER=W/'runtime25-unresolved-switch-frontier1/acceptance.json';FRONTIER_SHA='45d4ccac1abbb53b8a73e6d6534ee99e020eacc8c938c199567720c0839dcb48'
def hp(p):
 p=str(p).replace('\\','/');return Path('/mnt/'+p[0].lower()+p[2:])if len(p)>1 and p[1]==':'else Path(p)
def sha(p):
 with hp(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=hp(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);held={};commands=[]
 def pin(p,expected=None):
  value=sha(p);assert expected is None or value==expected,str(p);held[str(hp(p).resolve())]=value
 def run(args,label,timeout=180):
  args=list(map(str,args));commands.append(dict(stage=label,argv=args));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('x')as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
  return(out/(label+'.log')).read_text(errors='replace')
 try:
  pin(FRONTIER,FRONTIER_SHA);frontier=json.loads(FRONTIER.read_text());assert frontier['passed']and frontier['guarded_switch']['row_count']==8;elf=hp(frontier['original_ELF']['path']);pin(elf,frontier['original_ELF']['sha256']);source=out/'source';source.mkdir()
  for n in OWN:shutil.copyfile(HERE/n,source/n);pin(HERE/n)
  with elf.open('rb')as f:
   image=ELFFile(f)
   def readva(pc,size):
    for segment in image.iter_segments():
     va=0x70000000+int(segment['p_vaddr']);offset=pc-va
     if segment['p_type']=='PT_LOAD'and offset>=0 and offset+size<=segment['p_filesz']:return segment.data()[offset:offset+size]
    raise RuntimeError('unmapped original range')
   code=readva(0x70ddd584,28);table=readva(0x70fef300,32)
  assert code.hex()=='680243b91f1d0071482a0054e803082a687ba8b808011b8b00011fd6';assert table==hp(frontier['guarded_switch']['table_bytes']['path']).read_bytes();(source/'original-prefix.bin').write_bytes(code);(source/'original-table.bin').write_bytes(table)
  heads=[0x70ddd584,0x70dddad4,*[int(r['target'],16)for r in frontier['guarded_switch']['rows']]];(out/'heads.txt').write_text(''.join(hex(h)+'\n'for h in sorted(heads)));assert len(set(heads))==10
  parent=W/'windows-first-frame-thread-exit1';pin(parent/'overlay.json','57430fa2285cb1bc9400e82ea3c1ed296e49ff28498cf4709ce0524e95643581');root=parent/'sources/recomp';dependencies={}
  for folder in('whole','fastaes'):
   dst=out/folder;dst.mkdir()
   for p in(root/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or p.name in('runtime.cpp','cooperative_poll.cpp')):shutil.copyfile(p,dst/p.name);pin(p);dependencies[folder+'/'+p.name]=desc(p)
  tools=W/'frinta-toolchain1/tools';lifter=tools/'remill-lift';sem=tools/'aarch64.bc';pin(lifter,'73a1d6cf043bed30fc340059005a7ab931e9da350a057cc8e16b0304d614279d');pin(sem,'24e908b3be9b017ffb64e775df613a7aae675bdae59dd4995c402a0fdc303c2e')
  poll=Path('/home/user/bunker-recomp/recomp/work/guest-eh-rebuild-preparation1/.toolchain/poll-instrument');ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in(poll,ndk,qemu,cxx,Path('/usr/bin/clang++-18')):pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'unity_worker_switch_ref.c',source/'unity_worker_switch_ref.S','-o',out/'original-guard'],'compile-original');arm=run([qemu,out/'original-guard',elf],'actual-original');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==30 and 'ORIGINAL-UNITY-WORKER-SWITCH-PASS executions=30 TLS=17'in arm
  raw=out/'guard.raw.ll';polled=out/'guard.polled.ll';stats=out/'lowering.json';run([lifter,'--arch','aarch64','--os','linux','--semantics_dir',tools,'--bytes_file',source/'original-prefix.bin','--address','0x70ddd584','--entry_address','0x70ddd584','--trace_heads_file',out/'heads.txt','--guest_call_transfer=true','--guest_call_transfer_stats_out',stats,'--ir_out',raw],'lift-original-prefix');text=raw.read_text();assert len(re.findall(r'^define[^\n]*@sub_',text,re.M))==1 and not re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',text)
  run([poll,raw,polled],'poll');run(['opt-18','-passes=verify','-disable-output',polled],'verify-polled');rawobj=out/'guard.raw.o';pollobj=out/'guard.polled.o'
  for ir,obj,label in((raw,rawobj,'raw'),(polled,pollobj,'polled')):run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',ir,'-o',obj],'compile-'+label)
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source),'-I'+wp(out)];support=[]
  for p in(W/'remill-src/include').rglob('*'):
   if p.is_file():pin(p)
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);support.append(obj)
  (out/'default-observer.inc').write_text('extern "C" Memory*sub_70dddad4(State&s,addr_t,Memory*m){return observe(s,0x70dddad4,m);}\n')
  hosts={}
  for label,obj in(('raw',rawobj),('polled',pollobj)):
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'unity_worker_switch_test.cpp'),wp(obj),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);log=run([exe,wp(elf)],'actual-'+label);actual=[x for x in log.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'record count differs');m=re.search(r'WINDOWS-UNITY-WORKER-SWITCH-PASS executions=30 checks=(\d+) State1200=1 Memory64=1 observers=9',log);assert m;hosts[label]=dict(checks=int(m[1]),exact_records=30,object=desc(obj),executable=desc(exe),stdout=desc(out/('actual-'+label+'.log')))
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,scope='One genuine28B original integer dispatch prefix and original signed32 table; destination observers only. No case suffix/object graph execution.',frontier=desc(FRONTIER),parent_manifest=desc(parent/'overlay.json'),original_ELF=desc(elf),prefix=dict(start='0x70ddd584',end='0x70ddd5a0',original_bytes=desc(source/'original-prefix.bin'),raw_IR=desc(raw),polled_IR=desc(polled),lowering=desc(stats)),original_table=desc(source/'original-table.bin'),table_base='0x70fef300',original_targets=[r['target']for r in frontier['guarded_switch']['rows']],default_PC='0x70dddad4',unsigned_bound=7,executions_per_platform=30,in_range_rows_exercised=8,in_range_executions_per_platform=16,unsigned_default_controls_per_platform=14,invalid_table_default_controls_per_platform=7,incoming_X8_profiles=2,records_exact=True,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),State_size=1200,State_align=16,full_State1200_expected_effects_checked=True,Memory64_preserved=True,NZCV_FPCR_FPSR_exact=True,all_other_GPR_SIMD_and_owned_memory_preserved=True,hosts=hosts,original_stdout=desc(out/'actual-original.log'),owned_sources={n:desc(source/n)for n in OWN},frozen_support_dependencies=dependencies,held_inputs=held,commands=commands,case_suffixes_executed=False,actual_sparse_case_object_execution_qualified=False,full_original1808B_function_executed=False,original_game_executed=False,limits=['Original28B guard and32B signed table execute in Bionic/QEMU; only TEST mapped destination bytes are transparent observers. Original ELF file unchanged.','Windows executes standalone original-prefix lifts, not the new sparse suffix bodies. Static candidate preservation/ref/poll binding is separate.','No original1808B object graph/fullfunction/game/frame or host-build claim.'])
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-WORKER-SWITCH-GUARD-PASS',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:(out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
