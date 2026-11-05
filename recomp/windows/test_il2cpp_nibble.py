"""Actual valid-capacity IL2CPP nibble-formatter entry and twelve interior heads."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('il2cpp_nibble_cases.h','il2cpp_nibble_ref.S','il2cpp_nibble_ref.c','il2cpp_nibble_test.cpp','test_il2cpp_nibble.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';source.mkdir();commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  return(out/(label+'.log')).read_text()
 try:
  packet=W/'il2cpp-format-entry-packet1/acceptance.json';qualification=W/'neg4s1-il2cpp-entry-preparation1/qualification-result.json';existing=W/'il2cpp-format-existing-entry1/acceptance2.json'
  for p,h in((packet,'10630b83bfaf34c1f74b311f7a769c75edd090d188ce36748a7f4aad69920b87'),(qualification,'b251c1ca3bcf69a9caf19851735d07ac364229171f36c7a6f3da9a86a092a44e'),(existing,'03a9357f2af629503f15a2fda28e1751be320c449a73a9b7c1febca44589b9ef')):assert sha(p)==h;pin(p)
  q=json.loads(qualification.read_text())['results'][0];e=json.loads(existing.read_text());polled=Path(q['object']['path']);raw_ir=Path(q['raw_ir']['path']);assert sha(polled)==q['object']['sha256']and sha(raw_ir)==q['raw_ir']['sha256'];pin(polled);pin(raw_ir)
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  for name,p in(('component_entries.h',packet.parent/'component_entries.h'),('component_entry2.h',existing.parent/'component_entry2.h')):pin(p);shutil.copyfile(p,out/name)
  for label in('raw','polled'):row=e['forms'][label]['object'];assert sha(row['path'])==row['sha256'];pin(row['path'])
  elf=W/'windows-first-frame-guest-transfer1/native/libil2cpp.so';assert elf.stat().st_size==127359872;ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe');parent=W/'windows-first-frame-neg4s1/sources/recomp';
  # Frozen whole-image identity comes from the admitted entry packet. Verify
  # the exact executed original body/tables independently below, not a second
  # unrelated whole-image hashing campaign.
  original_identity=dict(path=str(elf),sha256='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522',bytes=elf.stat().st_size)
  from elftools.elf.elffile import ELFFile
  with elf.open('rb')as f:
   image=ELFFile(f);segments=list(image.iter_segments())
   def read(address,size):
    rva=address-0x80000000;s=next(x for x in segments if x['p_type']=='PT_LOAD'and x['p_vaddr']<=rva and rva+size<=x['p_vaddr']+x['p_filesz']);f.seek(s['p_offset']+rva-s['p_vaddr']);return f.read(size)
   boundary=W/'neg4s1-il2cpp-indirect-boundary1';instructions=(boundary/'target-FDE.txt').read_text();body=b''.join(bytes.fromhex(line.split()[1])for line in instructions.splitlines());assert len(body)==628 and read(0x849b021c,628)==body;tables=json.loads((boundary/'tables.json').read_text());assert all(read(int(t['table'],16),len(bytes.fromhex(t['raw'])))==bytes.fromhex(t['raw'])for t in tables);pin(boundary/'target-FDE.txt');pin(boundary/'tables.json')
  for p in(ndk,qemu,cxx):pin(p)
  for folder in('whole','fastaes'):
   target=out/folder;target.mkdir()
   for p in(parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc')or p.name in('runtime.cpp','cooperative_poll.cpp')):shutil.copyfile(p,target/p.name);pin(p)
  ref=out/'original-ARM';run([ndk,'-static','-O1','-fno-emulated-tls',source/'il2cpp_nibble_ref.c',source/'il2cpp_nibble_ref.S','-o',ref],'compile-original-ARM');text=run([qemu,ref,elf],'actual-original-ARM');original=[x for x in text.splitlines()if x.startswith('REC ')];assert len(original)==84 and 'IL2CPP-NIBBLE-ARM-PASS records=84 TLS=17'in text
  defs=set();refs=set()
  for obj in(polled,Path(e['forms']['polled']['object']['path'])):
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',obj],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',obj],text=True)))
  sentinels=sorted(refs-defs);assert not {'sub_'+h[2:]for h in q['heads']} & set(sentinels);(out/'unexecuted-sentinels.inc').write_text(''.join('extern "C" Memory*'+name+'(State&,addr_t,Memory*){fputs("UNEXECUTED-SENTINEL '+name+'\\n",stderr);abort();}\n'for name in sentinels))
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(out),'-I'+wp(source)];common=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);common.append(obj)
  coverage={};hosts={}
  for label,obj in(('polled',polled),('raw',out/'raw-cases.o')):
   if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',raw_ir,'-o',obj],'compile-raw-cases')
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'il2cpp_nibble_test.cpp'),wp(obj),wp(e['forms'][label]['object']['path']),*map(wp,common),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-Windows-'+label);actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==original,next((str(i)+': '+x[:100]+' != '+y[:100]for i,(x,y)in enumerate(zip(original,actual))if x!=y),'record count mismatch');match=re.search(r'IL2CPP-NIBBLE-COVERAGE ([\d,]+)',text);assert match;hits=list(map(int,match[1].split(',')));assert len(hits)==12 and all(v>0 for v in hits);coverage[label]=dict(heads=q['heads'],hits=hits,mask=4095);assert 'IL2CPP-NIBBLE-WINDOWS-PASS records=84 covered_heads=12'in text;hosts[label]=dict(executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),actual_new_case_object=desc(obj),actual_existing_entry=e['forms'][label]['object'])
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,scope='Whole existing849b021c FDE under TEST-owned validnonnull array/capacity128 profiles through all12 new actual table entries. Independent uint16(0x30|nibble) reverse-order bitmodel; no class/SDK/decimal-input-role inference.',entry_packet=desc(packet),producer_qualification=desc(qualification),existing_entry=desc(existing),original_ELF=original_identity,original_identity_basis='Admitted ancestor wholeimage hash; actual628B body/table bytes and file size rechecked independently. No new wholeimage hash claim.',platforms=['original_ARM_static_Bionic','raw_Windows','exact_polled_Windows'],records_each=84,records_exact=True,record_sha256=hashlib.sha256(('\n'.join(original)+'\n').encode()).hexdigest(),input_spans=42,word_status_profiles=2,coverage=coverage,State1200=True,Memory64=True,actual_full_FDE_closed_profile=True,resize_exception_paths_claim=False,abort_only_link_sentinels=sentinels,helpers_executed=0,original_stdout=desc(out/'actual-original-ARM.log'),hosts=hosts,owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='No capacity growth/null/bounds exception helpers or arbitrary malformed objects. Selected entry is exact fixture-only extraction from original current body; newpolledcaseobject is exact production candidate. Callback wrappers only count actual table-entry execution and call unchanged real code. No live start/end/word values or wholeIL2CPP/runtime/game/frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('IL2CPP-NIBBLE-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
