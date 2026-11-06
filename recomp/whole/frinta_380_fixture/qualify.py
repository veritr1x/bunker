from pathlib import Path
import argparse,json,hashlib,re,shutil,subprocess,traceback
W=Path('/mnt/c/GitRepos/bunker/recomp/work');HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);cmds=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(args,label):
  args=list(map(str,args));cmds.append(dict(stage=label,argv=args));(out/'commands.json').write_text(json.dumps(cmds,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
  return(out/(label+'.log')).read_text()
 try:
  c=json.loads(a.candidate.read_text());print('CANDIDATE_KEYS',list(c),flush=True)
  # Bind actual batch packet and select the entry by original target head.
  rows=[c] if 'global_index'in c else c.get('target_objects',c.get('shards',c.get('targets',[])));assert rows,'candidate schema needs actual shard records'
  row=next(r for r in rows if r.get('global_index')==166)
  objrow=row.get('candidate_object');rawrow=row.get('raw_ir',row.get('raw_IR'));pollrow=row.get('polled_ir',row.get('polled_IR'))
  assert c['passed'] and objrow and rawrow and pollrow
  obj=Path(objrow['path']);raw=Path(rawrow['path'])
  for d in [objrow,rawrow,pollrow]:assert sha(d['path'])==d['sha256'];pin(d['path'])
  pin(a.candidate)
  census=W/'frinta-retained-census1/acceptance.json';assert sha(census)=='4ddaddc979a2f4d5309c5e3c96d7d64acf35d00492aee6862e8f6aa8c6a40d56';pin(census)
  parentpath=W/'windows-first-frame-unity-switch-param1/overlay.json';parent=json.loads(parentpath.read_text());pin(parentpath)
  helperrows=[parent['objects'][i]for i in [161,93]];helpers=[Path(d['path'])for d in helperrows]
  for d in helperrows:assert sha(d['path'])==d['sha256'];pin(d['path'])
  source=out/'source';source.mkdir()
  for n in ['cases.h','ref.c','ref.S','test.cpp','qualify.py']:shutil.copyfile(HERE/n,source/n);pin(HERE/n)
  root=W/'windows-first-frame-unity-switch-param1/sources/recomp'
  if not root.exists():root=W/'windows-first-frame-paren-scan1/sources/recomp'
  for folder in ['whole','fastaes']:
   dst=out/folder;dst.mkdir()
   for p in (root/folder).iterdir():
    if p.is_file()and(p.suffix in ['.h','.inc']or p.name in ['runtime.cpp','cooperative_poll.cpp']):shutil.copyfile(p,dst/p.name);pin(p)
  elf=W/'windows-first-frame-guest-transfer1/native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(elf)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx,Path('/usr/bin/clang++-18'),Path('/usr/bin/llvm-nm-18')]:pin(p)
  run([ndk,'-static','-O2','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'ref.c',source/'ref.S','-o',out/'original380'],'compile-original')
  arm=run([qemu,out/'original380',elf],'actual-original');records=[x for x in arm.splitlines()if x.startswith('REC ')];assert len(records)==96 and 'ORIGINAL380-PASS executions=96 TLS=17'in arm
  defs=set();refs=set()
  for p in [obj,*helpers]:
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',p],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',p],text=True)))
  sentinels=sorted(refs-defs);assert not {'sub_7042dee4','sub_70416c5c','sub_7029cae8'}&set(sentinels)
  (out/'sentinels.inc').write_text(''.join('extern "C" Memory*'+n+'(State&,addr_t,Memory*){fputs("UNEXECUTED-LINK-SENTINEL '+n+'\\n",stderr);abort();}\n'for n in sentinels))
  flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(source),'-I'+wp(out)]
  support=[]
  for n in ['runtime','cooperative_poll']:
   p=out/(n+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(n+'.cpp')),'-o',wp(p)],'compile-'+n);support.append(p)
  result={}
  for label,p in [('polled',obj),('raw',out/'raw.o')]:
   if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',raw,'-o',p],'compile-raw')
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'test.cpp'),wp(p),*map(wp,helpers),*map(wp,support),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label)
   text=run([exe,wp(elf)],'actual-'+label);actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==records,next((f'{i}: {x} != {y}'for i,(x,y)in enumerate(zip(records,actual))if x!=y),'count mismatch');assert 'WINDOWS380-PASS executions=96'in text;result[label]=dict(executable=desc(exe),stdout=desc(out/('actual-'+label+'.log')),exact_records=len(actual),target_object=desc(p),helpers_linked_byte_exact=True)
  for p,h in held.items():assert sha(p)==h,p
  receipt=dict(passed=True,scope='Actual complete original7042dee4/380B vs exact batch166 polled object and unpolled166 raw; two genuine unchanged selected helper objects161/93 linked byteexact. Explicit TEST-owned cachedAPI/globals/virtual width-height providers, no substituted helperresult.',candidate=desc(a.candidate),census=desc(census),actual_selected_object=desc(obj),actual_selected_object_linked_byte_exact=True,original_ELF=desc(elf),helper_objects=helperrows,executions_per_platform=96,records_exact=True,records_sha256=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),samples=12,FPCR_modes=4,initial_FPSR_values=2,normal_body_samples=10,fallback_samples=2,State1200=True,Memory64=True,unexecuted_abort_only_link_sentinels=sentinels,original_stdout=desc(out/'actual-original.log'),hosts=result,owned_sources={n:desc(source/n)for n in ['cases.h','ref.c','ref.S','test.cpp','qualify.py']},held_inputs=held,commands=cmds,limits=['Test-owned initialized object/config/root/cachedAPI inputs only; actual live runtime values not inferred.','No JNI/global constructor paths; both original helpers run genuine selected bodies on initialized profile.','Virtual width/height providers are explicit TESTcallbacks with real objectidentity/datareads/callcounts, no production backend claim.','Integer-derived normal finite geometry only, all4rounding modes, twoFPSR sticky seeds; no NaN/subnormal/FZ/DN/universalFP claim.','No original game/system changes or rendered-frame claim.'])
  (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('380-PASS',sha(out/'acceptance.json'))
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=cmds),indent=2)+'\n');raise
if __name__=='__main__':main()
