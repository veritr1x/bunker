"""Complete original70362a2c,16 no-call cases; fixed-point FCVTZU qualification."""
import argparse,hashlib,json,shutil,subprocess,traceback
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,j):Path(p).write_text(json.dumps(j,indent=2)+'\n')
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--candidate-sha256',required=True);p.add_argument('--toolchain',type=Path,required=True);a=p.parse_args()
 O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir();commands=[];inputs={};sourcepins={};records={};observations={};binaries={}
 def pin(p):inputs[str(p)]=sha(p)
 def run(cmd,label,timeout=600):
  cmd=list(map(str,cmd));commands.append(dict(label=label,command=cmd));print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return (O/(label+'.log')).read_text()
 try:
  CP=a.candidate.resolve();assert sha(CP)==a.candidate_sha256;C=read(CP);assert C['passed']and C['target_head']=='0x70362a2c'and C['original_FDE_end_exclusive']=='0x70362a8c'and C['definitions']==128
  assert C['raw_neighbors_byte_exact']==C['polled_neighbors_byte_exact']==C['native_neighbors_full_bytes_exact']==127 and C['all_direct_refs_closed'];pin(CP)
  for group in['input_pins','artifacts']:
   for n,h in C[group].items():assert sha(n)==h;inputs[n]=h
  T=a.toolchain.resolve()
  for n in['unity_fcvtzu_fixed_fixture.h','unity_fcvtzu_fixed_native.S','unity_fcvtzu_fixed_ref.c','unity_fcvtzu_fixed_test.cpp','test_unity_fcvtzu_fixed_function.py']:shutil.copy2(HERE/n,S/n)
  for n in['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(W/'windows-first-frame-st2-2/sources/recomp/whole'/n,SUP/n)
  for d in[S,SUP]:
   for f in d.rglob('*'):
    if f.is_file():sourcepins[str(f)]=sha(f)
  for f in(T/'include').rglob('*'):
   if f.is_file():pin(f)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
  for p in[ndk.resolve(),qemu.resolve(),Path('/mnt/c/mingw64/bin/g++.exe')]:pin(p)
  for n in['clang-18','clang++-18']:pin(Path(shutil.which(n)).resolve())
  elfpath=W/'windows-first-frame-st2-2/native/libunity.so';assert sha(elfpath)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(elfpath);pin(W/'windows-first-frame-st2-2/game_inputs.json')
  with elfpath.open('rb')as f:
   e=ELFFile(f)
   for name,rva,size in[('original-function.bin',0x362a2c,0x60),('original-literal.bin',0xecbdf8,4)]:
    s=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+size<=s['p_vaddr']+s['p_filesz']);(O/name).write_bytes(s.data()[rva-s['p_vaddr']:rva-s['p_vaddr']+size])
  assert(O/'original-function.bin').read_bytes()[0x18:0x1c]==bytes.fromhex('09d8199e')and(O/'original-literal.bin').read_bytes()==bytes.fromhex('00008044');pin(O/'original-function.bin');pin(O/'original-literal.bin')
  fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
  for h in C['external_guest_references']:fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"UNITY-FCVTZU-FIXED-FAIL unqualified real callee{h:x} reached\\n");std::exit(21);}}\n'
  (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp');save(O/'preexecution-source-pin.json',dict(candidate_sha256=sha(CP),sourcepins=sourcepins,inputs=inputs))
  run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_fcvtzu_fixed_ref.c'],'reference-strict')
  hosts=[]
  for label,target,cxx in[('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
   D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_fcvtzu_fixed_test.cpp')],label+'-strict');hosts.append((label,target,cxx,D,conv,flags))
  run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_fcvtzu_fixed_ref.c',S/'unity_fcvtzu_fixed_native.S','-o',O/'reference'],'reference-build')
  with(O/'reference').open('rb')as f:
   e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());tls=[s for s in e.iter_segments()if s['p_type']=='PT_TLS'];assert tls and all(s['p_align']>=64 for s in tls)
  def capture(key,i,cmd):
   t=run(cmd,f'case-{key}-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1
   if key!='arm64':assert r[0]==records['arm64'][i],('record mismatch',key,i)
   records.setdefault(key,[]).extend(r);observations.setdefault(key,[]).extend(b)
  for i in range(16):capture('arm64',i,[qemu,O/'reference',O/'original-function.bin',O/'original-literal.bin',i])
  for label,target,cxx,D,conv,flags in hosts:
   objects=[]
   for src in[SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_fcvtzu_fixed_test.cpp',O/'fences.cpp']:
    obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
   for kind in['raw','polled']:
    obj=Path(C['candidate_object']['path'])if label=='windows'and kind=='polled'else D/(kind+'.o')
    if not(label=='windows'and kind=='polled'):run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',C['raw_ir'if kind=='raw'else'polled_ir']['path'],'-o',obj],label+'-'+kind+'-object')
    exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;binaries[key]=dict(path=str(exe),sha256=sha(exe),object_sha256=sha(obj))
    for i in range(16):capture(key,i,[exe,int(kind=='polled'),conv(O/'original-literal.bin'),i])
  for group in[inputs,sourcepins]:
   for n,h in group.items():assert sha(n)==h,n
  save(O/'commands.json',commands);result=dict(passed=True,candidate_sha256=sha(CP),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],records_each=16,platforms=list(records),native_complete_original_function=True,original_FDE=['0x70362a2c','0x70362a8c'],architectural_snapshot_bytes=800,host_independent_full_State_bytes=1200,object_window_bytes=0x200,owned_allocation_bytes=65536,zero_result_real_callee_branch_qualified=False,sourcepins=sourcepins,inputs=inputs,binaries=binaries,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},limits='Untouched24-instruction original function, true return, only equal/nonzero no-call paths exercised. Both B.EQ outcomes and CB NZ taken; CB NZ not-taken/real703631a8 call branch excluded. Full800 architecture compared after local X18/LR/TLS normalization; independently enumerated host1200 State oracle separately checked. Actual readonly1024 literal, complete0x200 owned object window/allocation canaries, exact guest frame and stack canaries outside native800 capture. No game/frame/cohort-selection claim.')
  result['evidence']={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'};save(O/'acceptance.json',result);print('UNITY-FCVTZU-FIXED-FUNCTION-QUALIFIED',sha(O/'acceptance.json'),flush=True)
 except Exception as ex:save(O/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands,sourcepins=sourcepins,inputs=inputs));raise
if __name__=='__main__':main()
