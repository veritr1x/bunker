"""Exact original USHLL mask loop; projected candidate IR, not full FDE."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir();T=a.toolchain.resolve();CP=a.candidate.resolve();C=read(CP)
 assert C['passed']and C['target_head']=='0x702b3d34'and C['global_index']==94 and C['definitions']==128 and C['raw_neighbors_byte_exact']==C['polled_neighbors_byte_exact']==C['native_neighbors_full_bytes_exact']==127
 own=['unity_ushll_mask_block_fixture.h','unity_ushll_mask_block_native.S','unity_ushll_mask_block_ref.c','unity_ushll_mask_block_test.cpp','test_unity_ushll_mask_block.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 frozen=W/'windows-first-frame-texture3d1/sources/recomp/whole'
 for n in ['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(frozen/n,SUP/n)
 sourcepins={str(f):sha(f)for d in[S,SUP]for f in d.rglob('*')if f.is_file()};inputs={str(CP):sha(CP)};commands=[]
 for group in ['input_pins','artifacts']:
  for n,h in C[group].items():assert sha(n)==h;inputs[n]=h
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');elfpath=W/'windows-first-frame-texture3d1/native/libunity.so';assert sha(elfpath)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 with elfpath.open('rb')as f:
  e=ELFFile(f)
  def extract(rva,size):
   seg=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+size<=s['p_vaddr']+s['p_filesz']);return seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+size]
  (O/'original-block.bin').write_bytes(extract(0x2b3e98,0xe0));(O/'original-table.bin').write_bytes(extract(0xebe840,16))
 assert (O/'original-block.bin').read_bytes()[0x24:0x28]==bytes.fromhex('22a4082f')and (O/'original-table.bin').read_bytes()==bytes.fromhex('00090309090409070209010909060905')
 for x in [ndk.resolve(),qemu.resolve(),elfpath,O/'original-block.bin',O/'original-table.bin',W/'windows-first-frame-texture3d1/game_inputs.json']:inputs[str(x)]=sha(x)
 for f in (T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return (O/(label+'.log')).read_text()
 run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_ushll_mask_block_ref.c'],'reference-precheck')
 run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_ushll_mask_block_ref.c',S/'unity_ushll_mask_block_native.S','-o',O/'reference'],'reference-build')
 records={};observations={};bins={};records['arm64']=[];observations['arm64']=[]
 for i in range(16):
  t=run([qemu,O/'reference',O/'original-block.bin',O/'original-table.bin',i],f'case-arm64-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1;records['arm64']+=r;observations['arm64']+=b
 print('ORIGINAL-BLOCK-ARM64-PASS16',flush=True)
 with(O/'reference').open('rb')as f:
  e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());assert any(s['p_type']=='PT_TLS'and s['p_align']>=64 for s in e.iter_segments())
 target_re=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
 projections={};projection_proof={}
 for kind,key in [('raw','raw_ir'),('polled','polled_ir')]:
  text=Path(C[key]['path']).read_text();matches=list(re.finditer(target_re,text,re.M|re.S));assert len(matches)==128
  target=next(m[0]for m in matches if m[1]=='702b3d34');assert not re.search(r'blockaddress\(',text),'external label address: HOLD'
  # The second real helper call returns to original702b3e98; the unique
  # sub_70346214 call begins at original702b3f78. Bound these private labels
  # by exact captured candidate instructions, retaining the complete body.
  enter_call=list(re.finditer(r'call ptr @sub_7026e878\(',target))[-1]
  entry_label=re.search(r'^([0-9]+):[^\n]*',target[enter_call.start():],re.M)[1]
  stop_call=list(re.finditer(r'call ptr @sub_70346214\(',target));assert len(stop_call)==1
  stop_label=list(re.finditer(r'^([0-9]+):[^\n]*',target[:stop_call[0].start()],re.M))[-1][1]
  assert (entry_label,stop_label)==({'raw':('771','1570'),'polled':('775','1578')}[kind]),'candidate label binding changed'
  edge=re.search(r'(store i64 %program_counter, ptr %NEXT_PC, align 8\n  br label %)([0-9]+)',target);assert edge
  replacement=edge[1]+entry_label
  changed=target[:edge.start()]+replacement+target[edge.end():]
  stop=re.search(r'^'+stop_label+r':[^\n]*\n',changed,re.M);assert stop
  insertion=('  %mask_capture_memory = load ptr, ptr %MEMORY, align 8\n'
             '  %mask_capture_pc = load i64, ptr %NEXT_PC, align 8\n'
             '  store i64 %mask_capture_pc, ptr %PC, align 8\n'
             '  call void @mask_block_capture(ptr %state, i64 %mask_capture_pc, ptr %mask_capture_memory)\n')
  changed=changed[:stop.end()]+insertion+changed[stop.end():]
  inverse=changed.replace(insertion,'',1).replace(replacement,edge[0],1)
  assert inverse==target,'exact projection inverse'
  def project(m):
   if m[1]=='702b3d34':return changed
   signature=m[0].split('\n',1)[0];assert signature.endswith('{');return 'declare '+signature[len('define '):-1].rstrip()
  result=re.sub(target_re,project,text,flags=re.M|re.S)+'\ndeclare void @mask_block_capture(ptr, i64, ptr)\n'
  P=O/(kind+'-target-projection.ll');P.write_text(result);projections[kind]=P;sourcepins[str(P)]=sha(P)
  projection_proof[kind]=dict(source_ir=C[key],original_target_sha256=hashlib.sha256(target.encode()).hexdigest(),projected_target_sha256=hashlib.sha256(changed.encode()).hexdigest(),entry_label=entry_label,original_entry_edge=edge[0],projected_entry_edge=replacement,capture_label=stop_label,capture_insertion=insertion,exact_inverse_recovers_complete_target=True,original_suffix_retained=True,unselected_guest_definitions_declared=127,full_selected_COFF_executed=False)
 fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
 refs=set(int(h,16)for h in re.findall(r'@sub_([0-9a-f]+)\(',target))-{0x702b3d34}
 for h in sorted(refs):fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"USHLL-MASK-BLOCK-FAIL unexpected inherited helper{h:x}\\n");std::exit(21);}}\n'
 (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp')
 for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
  D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];objects=[]
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_ushll_mask_block_test.cpp')],label+'-strict')
  for src in [SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_ushll_mask_block_test.cpp',O/'fences.cpp']:
   obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
  for kind in ['raw','polled']:
   obj=D/(kind+'.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',projections[kind],'-o',obj],label+'-'+kind+'-projection')
   exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;bins[key]=dict(path=str(exe),sha256=sha(exe),projection_object_sha256=sha(obj));records[key]=[];observations[key]=[]
   for i in range(16):
    t=run([exe,int(kind=='polled'),conv(O/'original-table.bin'),i],f'case-{key}-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1 and r[0]==records['arm64'][i],key+' actual full state/global/frame mismatch case'+str(i);records[key]+=r;observations[key]+=b
   print('ORIGINAL-BLOCK-HOST-PASS',key,16,flush=True)
 for name in ['clang-18','clang++-18','llvm-nm-18','llvm-objdump-18']:
  f=Path(shutil.which(name)).resolve();inputs[str(f)]=sha(f)
 inputs['/mnt/c/mingw64/bin/g++.exe']=sha('/mnt/c/mingw64/bin/g++.exe')
 for group in [inputs,sourcepins]:
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(O/'source-pin.json').write_text(json.dumps(dict(inputs=inputs,sourcepins=sourcepins,live_sources={str(HERE/n):sha(HERE/n)for n in own}),indent=2)+'\n')
 for n in own:assert sha(HERE/n)==sha(S/n),n
 result=dict(passed=True,records_each=16,platforms=list(records),target_head='0x702b3d34',candidate_sha256=sha(CP),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],projection_proof=projection_proof,native_complete_original_function=False,full_selected_COFF_executed=False,original_FDE=['0x702b3d34','0x702b4034'],original_block=['0x702b3e98','0x702b3f78'],capture_pc='0x702b3f78',capture_before_original_BL='0x70346214',helper_body_executed=False,binaries=bins,sourcepins=sourcepins,inputs=inputs,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},architectural_snapshot_bytes=800,host_full_State_bytes=1200,independent_full_State_oracle=True,opaque_memory_token_bytes=64,output_table_bytes=256,readonly_table_bytes=16,allocation_canaries_bytes=65536,original_stack_frame_bytes=0,limits='Exact original loop only; native executes224originalbytes and realreadonly16byte table. Both hosts compile complete candidate target-body IR projections: only private entry edge redirected and explicit testcapture inserted before originalBL70346214. All original body including suffix retained, exact inverse proven. Other127guestdefinitions declared; whole selected128functionCOFF staticallyqualified, not dynamicallyexecuted here. All800architecture and all256output bytes crosscompared; x18/TPIDR alone normalized after localchecks. Independent integer-lane/GPR/mask model and full1200hostState/token/canaries. No preceding platformcalls, originalhelper execution, fullFDEreturn, game/frame/cohortselection.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-USHLL-MASK-BLOCK-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
