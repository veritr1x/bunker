"""Exact original YIELD/B block: ARM reference and raw/polled host projections.

No host scheduler, lock helper, full lock-function return or fairness claim.
"""
import argparse,hashlib,json,re,shutil,subprocess,traceback
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
 O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();T=a.toolchain.resolve();CP=a.candidate.resolve();C=read(CP);commands=[];inputs={};sources={}
 def pin(path):path=Path(path).resolve();inputs[str(path)]=sha(path)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(dict(label=label,argv=cmd));save(O/'commands.json',commands)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return(O/(label+'.log')).read_text()
 try:
  assert C['passed']and C['target_head']=='0x703835a0'and C['global_index']==129 and C['definitions']==128
  assert C['raw_neighbors_byte_exact']==C['polled_neighbors_byte_exact']==C['native_neighbors_full_bytes_exact']==127
  pin(CP)
  for group in ['input_pins','artifacts']:
   for n,h in C[group].items():assert sha(n)==h;pin(n)
  own=['yield_fixture.h','yield_native.S','yield_ref.c','yield_test.cpp','test_yield.py']
  for n in own+['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:
   shutil.copy2(HERE/n,S/n);sources[str(HERE/n)]=sha(HERE/n)
  for f in (T/'include').rglob('*'):
   if f.is_file():pin(f)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang')
  qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');unity=W/'windows-first-frame-external-main1/native/libunity.so'
  assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  with unity.open('rb')as f:
   e=ELFFile(f);rva=0x3835e4;seg=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+16<=s['p_vaddr']+s['p_filesz']);blob=seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+16]
  assert blob==bytes.fromhex('3f2003d503000014c4000094e8031f2a');(O/'original-block.bin').write_bytes(blob)
  for f in [ndk,qemu,unity,O/'original-block.bin']:pin(f)
  run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror',S/'yield_ref.c',S/'yield_native.S','-o',O/'reference'],'reference-build')
  with(O/'reference').open('rb')as f:assert ELFFile(f)['e_machine']=='EM_AARCH64'
  records={'arm64':[]};observations={'arm64':[]}
  def collect(label,text):
   r=[x for x in text.splitlines()if x.startswith('RECORD ')];b=[x for x in text.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1;records[label]+=r;observations[label]+=b
  for i in range(16):collect('arm64',run([qemu,O/'reference',O/'original-block.bin',i],f'case-arm64-{i:02}'))
  print('YIELD ARM64 PASS16',flush=True)
  target_re=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
  projections={};proof={};target=''
  for kind,key in [('raw','raw_ir'),('polled','polled_ir')]:
   text=Path(C[key]['path']).read_text();matches=list(re.finditer(target_re,text,re.M|re.S));assert len(matches)==128
   target=next(m[0]for m in matches if m[1]=='703835a0');assert not re.search(r'blockaddress\(',text)
   blocks=list(re.finditer(r'^([0-9]+):[^\n]*\n(.*?)(?=^[0-9]+:|^})',target,re.M|re.S))
   # YIELD is the unique normal instruction with PC advance and pure identity
   # memory semantics, immediately followed by the original direct B +12.
   yields=[b for b in blocks if re.search(r'load i64, ptr %NEXT_PC.*?store i64 .*?, ptr %PC.*?add i64 .*?, 4.*?store i64 .*?, ptr %NEXT_PC.*?load ptr, ptr %MEMORY.*?store ptr .*?, ptr %MEMORY.*?br label %\d+\s*$',b[2],re.S)and not re.search(r'ptr %(?:X|W|SP)|call |getelementptr',b[2])]
   assert len(yields)==1,[(b[1],b[2])for b in yields];entry_label=yields[0][1]
   branch_label=re.search(r'br label %(\d+)\s*$',yields[0][2])[1];branch=next(b for b in blocks if b[1]==branch_label)
   assert re.search(r'add i64 %\d+, 12',branch[2])and not re.search(r'call |ptr %X|ptr %W',branch[2]);capture_label=re.search(r'br label %(\d+)\s*$',branch[2])[1]
   edge=re.search(r'(store i64 %program_counter, ptr %NEXT_PC, align 8\n  br label %)([0-9]+)',target);assert edge
   replacement=edge[1]+entry_label;changed=target[:edge.start()]+replacement+target[edge.end():]
   stop=re.search(r'^'+capture_label+r':[^\n]*\n',changed,re.M);assert stop
   insertion='  %yield_capture_memory = load ptr, ptr %MEMORY, align 8\n  %yield_capture_pc = load i64, ptr %NEXT_PC, align 8\n  store i64 %yield_capture_pc, ptr %PC, align 8\n  call void @yield_capture(ptr %state, i64 %yield_capture_pc, ptr %yield_capture_memory)\n'
   changed=changed[:stop.end()]+insertion+changed[stop.end():];assert changed.replace(insertion,'',1).replace(replacement,edge[0],1)==target
   def project(m):
    if m[1]=='703835a0':return changed
    signature=m[0].split('\n',1)[0];assert signature.endswith('{');return'declare '+signature[len('define '):-1].rstrip()
   result=re.sub(target_re,project,text,flags=re.M|re.S)+'\ndeclare void @yield_capture(ptr,i64,ptr)\n';P=O/(kind+'-projection.ll');P.write_text(result);projections[kind]=P
   proof[kind]=dict(source_ir=C[key],original_target_sha256=hashlib.sha256(target.encode()).hexdigest(),projected_target_sha256=hashlib.sha256(changed.encode()).hexdigest(),entry_label=entry_label,branch_label=branch_label,capture_label=capture_label,original_entry_edge=edge[0],projected_entry_edge=replacement,capture_insertion=insertion,exact_inverse_recovers_complete_target=True,original_B_and_suffix_retained=True,unselected_guest_definitions_declared=127)
  fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
  for h in sorted(set(int(h,16)for h in re.findall(r'@sub_([0-9a-f]+)\(',target))-{0x703835a0}):fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fputs("YIELD unexpected original helper{h:x}\\n",stderr);std::exit(21);}}\n'
  (O/'fences.cpp').write_text(fences);bins={}
  for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
   D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(S)];objects=[]
   run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'yield_test.cpp')],label+'-strict')
   for src in [S/'runtime.cpp',S/'cooperative_poll.cpp',S/'yield_test.cpp',O/'fences.cpp']:
    obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.name=='yield_test.cpp'else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
   for kind in ['raw','polled']:
    obj=D/(kind+'.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',projections[kind],'-o',obj],label+'-'+kind+'-projection')
    exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;bins[key]=dict(path=str(exe),sha256=sha(exe),projection_object_sha256=sha(obj));records[key]=[];observations[key]=[]
    for i in range(16):collect(key,run([exe,int(kind=='polled'),i],f'case-{key}-{i:02}'));assert records[key][i]==records['arm64'][i],key+' full state mismatch'+str(i)
    print('YIELD HOST PASS',key,16,flush=True)
  for name in ['clang-18','clang++-18','llvm-nm-18','llvm-objdump-18']:pin(Path(shutil.which(name)).resolve())
  pin('/mnt/c/mingw64/bin/g++.exe')
  for n,h in inputs.items():assert sha(n)==h,n
  for n,h in sources.items():assert sha(n)==h and sha(S/Path(n).name)==h,n
  result=dict(passed=True,records_each=16,platforms=list(records),target_head='0x703835a0',candidate_sha256=sha(CP),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],projection_proof=proof,original_FDE=['0x703835a0','0x70383620'],original_block=['0x703835e4','0x703835f4'],capture_pc='0x703835f4',native_complete_original_function=False,full_selected_COFF_executed=False,architectural_snapshot_bytes=800,host_full_State_bytes=1200,opaque_memory_token_bytes=64,data_canaries_bytes=65536,stack_canaries_bytes=65536,sourcepins=sources,inputs=inputs,binaries=bins,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},limits='Exact original YIELD703835e4 and B703835e8 to703835f4; original BL/MOV path skipped by genuine B. Native exact16bytes, full architecture state and canaries; x18/TLS locally validated then normalized. Raw/polled Win/Linux execute complete candidate target-body projection with only entry edge redirected and capture inserted at original continuation; exact inverse restores entire target. No lock acquisition/helper/full FDE/heap/game/frame/scheduler/fairness claim.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
  save(O/'acceptance.json',result);print('YIELD QUALIFIED',sha(O/'acceptance.json'),flush=True)
 except Exception as ex:save(O/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands));raise
if __name__=='__main__':main()
