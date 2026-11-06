from pathlib import Path
import argparse,json,hashlib,re,subprocess,shutil,traceback
W=Path('/mnt/c/GitRepos/bunker/recomp/work');HERE=Path(__file__).resolve().parent
OWN=['cases.h','ref.c','ref.S','test.cpp','qualify.py','prefixes.json','0x83aaabec.bin','0x841ebd60.bin']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p);return dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(args,label):
  args=list(map(str,args));commands.append(dict(stage=label,argv=args));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
  return(out/(label+'.log')).read_text()
 try:
  audit=W/'numeric-minmax-eight-branch-audit1/acceptance.json';assert sha(audit)=='9bf29d7f0515df93883492b6fe3ef04a15d4c4f219248fa89accfb04d939afb0';pin(audit);ar=json.loads(audit.read_text());assert ar['passed']and len(ar['missing_selected_heads'])==8
  elf=W/'windows-first-frame-guest-transfer1/native/libil2cpp.so';assert sha(elf)=='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522';pin(elf)
  source=out/'source';source.mkdir()
  for n in OWN:shutil.copyfile(HERE/n,source/n);pin(HERE/n)
  prs=json.loads((source/'prefixes.json').read_text());heads=sorted({int(r['start'],16)for r in prs}|{int(r['default'],16)for r in prs}|{int(x['target'],16)for r in prs for x in r['rows']});assert len(heads)==12;(out/'heads.txt').write_text(''.join(hex(h)+'\n'for h in heads))
  root=W/'windows-first-frame-frinta1/sources/recomp'
  for folder in ['whole','fastaes']:
   dst=out/folder;dst.mkdir()
   for p in (root/folder).iterdir():
    if p.is_file()and(p.suffix in ['.h','.inc']or p.name in ['runtime.cpp','cooperative_poll.cpp']):shutil.copyfile(p,dst/p.name);pin(p)
  tools=W/'frinta-toolchain1/tools';lifter=tools/'remill-lift';sem=tools/'aarch64.bc';assert sha(lifter)=='73a1d6cf043bed30fc340059005a7ab931e9da350a057cc8e16b0304d614279d'and sha(sem)=='24e908b3be9b017ffb64e775df613a7aae675bdae59dd4995c402a0fdc303c2e';poll=Path('/home/user/bunker-recomp/recomp/work/guest-eh-rebuild-preparation1/.toolchain/poll-instrument');ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [lifter,sem,poll,ndk,qemu,cxx,Path('/usr/bin/clang++-18')]:pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'ref.c',source/'ref.S','-o',out/'original-guard'],'compile-original');arm=run([qemu,out/'original-guard',elf],'actual-original');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==36 and 'ORIGINAL-TMP-GUARD-PASS executions=36 TLS=17'in arm
  rawobjs=[];pollobjs=[];prefixes=[]
  for r in prs:
   h=r['start'];raw=out/(h+'.raw.ll');polled=out/(h+'.polled.ll');stats=out/(h+'.lowering.json')
   run([lifter,'--arch','aarch64','--os','linux','--semantics_dir',tools,'--bytes_file',source/(h+'.bin'),'--address',int(h,16),'--entry_address',int(h,16),'--trace_heads_file',out/'heads.txt','--guest_call_transfer=true','--guest_call_transfer_stats_out',stats,'--ir_out',raw],'lift-'+h)
   text=raw.read_text();assert len(re.findall(r'^define[^\n]*@sub_',text,re.M))==1 and not re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',text)
   run([poll,raw,polled],'poll-'+h);run(['opt-18','-passes=verify','-disable-output',polled],'verify-'+h)
   for label,ir,objects in [('raw',raw,rawobjs),('polled',polled,pollobjs)]:
    obj=out/(h+'.'+label+'.o');run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',ir,'-o',obj],'compile-'+h+'-'+label);objects.append(obj)
   prefixes.append(dict(start=h,end=r['end'],original_bytes=desc(source/(h+'.bin')),raw_IR=desc(raw),polled_IR=desc(polled),lowering=desc(stats)))
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source)]
  support=[]
  for n in ['runtime','cooperative_poll']:
   obj=out/(n+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(n+'.cpp')),'-o',wp(obj)],'compile-'+n);support.append(obj)
  # Direct unsigned-default edges are test observers at their genuine original PCs.
  defaults=[int(r['default'],16)for r in prs]
  sentinel=''.join('extern "C" Memory*sub_'+format(h,'x')+'(State&s,addr_t,Memory*m){return observe(s,'+hex(h)+',m);}\n'for h in defaults)
  # Declaration must follow observe definition; test source includes this file at that point.
  (out/'default-observers.inc').write_text(sentinel)
  result={}
  for label,objects in [('raw',rawobjs),('polled',pollobjs)]:
   exe=out/(label+'.exe');run([cxx,*flags,'-I'+wp(out),'-Wall','-Wextra','-Werror',wp(source/'test.cpp'),*map(wp,objects),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-'+label);actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'count mismatch');assert 'WINDOWS-TMP-GUARD-PASS executions=36'in text;result[label]=dict(executable=desc(exe),stdout=desc(out/('actual-'+label+'.log')),exact_records=36,objects=[desc(p)for p in objects])
  for p,s in held.items():assert sha(p)==s,p
  receipt=dict(passed=True,scope='Two genuine original integer dispatch prefixes only, with original signed tables and ten transparent observer destinations. No suffix/object graph execution.',guard_audit=desc(audit),original_ELF=desc(elf),prefixes=prefixes,executions_per_platform=36,records_exact=True,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),in_range_rows_exercised=8,default_observer_PCs=[hex(x)for x in defaults],unsigned_indices=[0,1,2,3,4,7,0x7fffffff,0x80000000,0xffffffff],incoming_X22_profiles=2,UGUI_W27_X22_W9_prelude_checked=True,NZCV_FPCR_FPSR_exact=True,all_SIMD_preserved=True,State_size=1200,State_align=16,Memory64_preserved=True,original_stdout=desc(out/'actual-original.log'),hosts=result,owned_sources={n:desc(source/n)for n in OWN},held_inputs=held,commands=commands,large_case_suffixes_executed=False,actual_sparse_case_object_execution_qualified=False,limits=['Native observers replace only test-owned mapped case/default destination bytes; original ELF file, guard prefixes and signed tables are unchanged. Observers report actual branch arrival PC and return transparently.','Windows uses standalone original-prefix lifts plus observers; this does not execute the large newly registered suffix bodies.','Separate static sparse8 packet binding will qualify entry identity/polls/ref closure; no full GenerateTextMesh object graph or gameplay/frame claim.','No host/full game build, original game process, new ISA semantics, or production callback/state changes.'])
  p=out/'acceptance.json';p.write_text(json.dumps(receipt,indent=2)+'\n');print('TMP-GUARD-PASS',sha(p))
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
