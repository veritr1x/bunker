"""Original Regex Go TrackPush-to-Stop path and helper-free Stop entry gate (WSL)."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=('regex_nonleaf_cases.h','regex_nonleaf_ref.S','regex_nonleaf_ref.c','regex_nonleaf_test.cpp','test_regex_nonleaf.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';source.mkdir();commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
  return(out/(label+'.log')).read_text()
 try:
  packet=W/'regex-nonleaf-entry-packet1/acceptance.json';existing=W/'regex-existing-helpers1/acceptance.json'
  for p,h in((packet,'ce02a9c53cbf05dddc26762e80ab16d711377e06e1bfc4f16c250db9e5654a82'),(existing,'f0436df88c9110c6053814fe01805f8e1e7121b3601d73d83d135199f329b087')):assert sha(p)==h;pin(p)
  p=json.loads(packet.read_text());qualification=Path(p['qualification']['path']);assert sha(qualification)==p['qualification']['sha256'];pin(qualification);q=json.loads(qualification.read_text())['results'][0];e=json.loads(existing.read_text());polled=Path(q['object']['path']);raw_ir=Path(q['raw_ir']['path']);assert sha(polled)==q['object']['sha256']and sha(raw_ir)==q['raw_ir']['sha256'];pin(polled);pin(raw_ir)
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  for name,pth in(('component_entries.h',packet.parent/'component_entries.h'),('component_helpers.h',existing.parent/'component_helpers.h')):pin(pth);shutil.copyfile(pth,out/name)
  for row in e['rows']:
   for form in('raw','polled'):d=row['forms'][form]['object'];assert sha(d['path'])==d['sha256'];pin(d['path'])
  elf=W/'windows-first-frame-guest-transfer1/native/libil2cpp.so';assert elf.stat().st_size==127359872;ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for f in(ndk,qemu,cxx):pin(f)
  # Reuse the qualified whole-image identity and independently verify this exact FDE.
  from elftools.elf.elffile import ELFFile
  with elf.open('rb')as f:
   image=ELFFile(f);address=0x4315734;s=next(s for s in image.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=address<s['p_vaddr']+s['p_filesz']);f.seek(s['p_offset']+address-s['p_vaddr']);assert hashlib.sha256(f.read(4444)).hexdigest()=='7cea44867b6efbf379d2a505a3304a03f3c504f4ad93437ba0f5dffbb407144e'
  parent=HERE.parent;pending=['whole/runtime.cpp','whole/cooperative_poll.cpp','fastaes/elf64.h'];seen=set()
  while pending:
   name=pending.pop();f=(parent/name).resolve();name=str(f.relative_to(parent))
   if name in seen:continue
   seen.add(name);target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target);pin(f)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',f.read_text(),re.M):
    child=(f.parent/inc).resolve()
    if child.is_file()and child.is_relative_to(parent):pending.append(str(child.relative_to(parent)))
  ref=out/'original-ARM';run([ndk,'-static','-O1','-fno-emulated-tls',source/'regex_nonleaf_ref.c',source/'regex_nonleaf_ref.S','-o',ref],'compile-original-ARM');text=run([qemu,ref,elf],'actual-original-ARM',30);original=[x for x in text.splitlines()if x.startswith('REC ')];assert len(original)==16 and 'REGEX-ARM-PASS records=16 TLS=17'in text
  defs=set();refs=set()
  for obj in[polled,*[Path(row['forms']['polled']['object']['path'])for row in e['rows']]]:
   defs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--defined-only',obj],text=True)));refs.update(re.findall(r'\bsub_[0-9a-f]+\b',subprocess.check_output(['llvm-nm-18','--undefined-only',obj],text=True)))
  sentinels=sorted(refs-defs);(out/'unexecuted-sentinels.inc').write_text(''.join('extern "C" Memory*'+n+'(State&,addr_t,Memory*){fputs("UNEXECUTED-SENTINEL '+n+'\\n",stderr);abort();}\n'for n in sentinels))
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out/'whole'),'-I'+wp(out/'fastaes'),'-I'+wp(out),'-I'+wp(source)];common=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(out/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);common.append(obj)
  hosts={}
  for label,obj in(('polled',polled),('raw',out/'raw-cases.o')):
   if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',raw_ir,'-o',obj],'compile-raw-cases')
   exe=out/(label+'.exe');support=[Path(row['forms'][label]['object']['path'])for row in e['rows']];run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'regex_nonleaf_test.cpp'),wp(obj),*map(wp,support),*map(wp,common),'-Wl,--wrap=__bunker_guest_call','-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe,wp(elf)],'actual-Windows-'+label,30);actual=[x for x in text.splitlines()if x.startswith('REC ')];assert actual==original,next((str(i)+': '+x[:120]+' != '+y[:120]for i,(x,y)in enumerate(zip(original,actual))if x!=y),'record count mismatch');match=re.search(r'REGEX-WINDOWS-PASS records=16 checks=(\d+) TrackPush=8 Stop=16 helpers=40 State=1200 Memory64=1',text);assert match;hosts[label]=dict(checks=int(match[1]),executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),actual_new_case_object=desc(obj),actual_existing_helpers=[desc(o)for o in support],TrackPush_hits=8,Stop_hits=16,real_helper_calls=40)
  for pth,h in held.items():assert sha(pth)==h,pth
  result=dict(passed=True,scope='Genuine full RegexInterpreter.Go entry with predefined TEST-owned code [23,unused,40], actual Goto/TrackPush/Advance/CheckTimeout helpers, reached TrackPush84315bd4 and Stop84316814. Also helper-free Stop interior entry with original96B saved frame.',entry_packet=desc(packet),producer_qualification=desc(qualification),existing_entry_helpers=desc(existing),original_ELF=dict(path=str(elf),sha256='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522',bytes=elf.stat().st_size),original_identity_basis='Qualified parent wholeimage identity, exact4444B FDE bytes independently rechecked.',platforms=['original_ARM_static_Bionic','raw_Windows','exact_polled_Windows'],records_each=16,records_exact=True,record_sha256=hashlib.sha256(('\n'.join(original)+'\n').encode()).hexdigest(),profiles=dict(runtext_positions=[0,1,31,1024],status_profiles=2,timeout_disabled_and_nonexpired_counter=True,opcode_flags=[0,0x240],owned_bytes_checked=16384),dynamic_new_heads=['0x84315bd4','0x84316814'],static_complete_new_heads=q['heads'],hosts=hosts,State1200=True,Memory64=True,abort_only_link_sentinels=sentinels,original_stdout=desc(out/'actual-original-ARM.log'),owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='Only TrackPush-to-Stop code sequence and direct Stop are dynamically qualified; all58 guarded switch heads statically lifted/preserved separately. No clock timeout, EnsureStorage/allocation, malformed array, exception helper or arbitrary pattern/whole regex behavior claim. One original metadata-init byte seeded in TEST image, not a guest production mutation. No fake helper results, normalization, full game or first frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('REGEX-NONLEAF-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
