"""Bounded complete original constructor qualification; real memset, ABI-defined comparison."""
import argparse,hashlib,json,re,shutil,subprocess,traceback
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
 O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';(SUP/'whole').mkdir(parents=True);(SUP/'windows').mkdir()
 commands=[];inputs={};sourcepins={};bins={};records={};observations={}
 def run(cmd,label,timeout=300):
  cmd=list(map(str,cmd));commands.append({'label':label,'command':cmd});print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('x')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return (O/(label+'.log')).read_text()
 def pin(path):inputs[str(path)]=sha(path)
 try:
  CP=a.candidate.resolve();assert sha(CP)==a.candidate_sha256;C=read(CP);assert C['passed']and C['target_head']=='0x707520c4'and C['original_FDE_end_exclusive']=='0x707521bc'and C['definitions']==128
  assert C['raw_neighbors_byte_exact']==C['polled_neighbors_byte_exact']==C['native_neighbors_full_bytes_exact']==127 and C['all_direct_refs_closed'];pin(CP)
  for group in['input_pins','artifacts']:
   for n,h in C[group].items():assert sha(n)==h;inputs[n]=h
  T=a.toolchain.resolve();frozen=W/'windows-first-frame-fcsel-batch1/sources/recomp'
  own=['unity_st2_constructor_fixture.h','unity_st2_constructor_native.S','unity_st2_constructor_ref.c','unity_st2_constructor_test.cpp','test_unity_st2_constructor.py']
  for n in own:shutil.copy2(HERE/n,S/n)
  for n in['whole/runtime.h','whole/runtime.cpp','whole/bridge.h','whole/guest_memory.h','whole/cooperative_poll.h','whole/cooperative_poll.cpp','windows/provider_memory.h']:shutil.copy2(frozen/n,SUP/n)
  for d in[S,SUP]:
   for f in d.rglob('*'):
    if f.is_file():sourcepins[str(f)]=sha(f)
  for f in(T/'include').rglob('*'):
   if f.is_file():pin(f)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
  for x in[ndk.resolve(),qemu.resolve(),Path('/mnt/c/mingw64/bin/g++.exe')]:pin(x)
  for name in['clang-18','clang++-18']:pin(Path(shutil.which(name)).resolve())
  elfpath=W/'windows-first-frame-fcsel-batch1/native/libunity.so';assert sha(elfpath)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(elfpath);pin(W/'windows-first-frame-fcsel-batch1/game_inputs.json')
  with elfpath.open('rb')as f:
   e=ELFFile(f)
   def extract(rva,size):
    seg=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+size<=s['p_vaddr']+s['p_filesz']);return seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+size]
   (O/'original-function.bin').write_bytes(extract(0x7520c4,0xf8));(O/'original-plt.bin').write_bytes(extract(0xb8440,16));(O/'original-global.bin').write_bytes(extract(0x123cc90,8));(O/'original-literals.bin').write_bytes(extract(0xe78fa0,16)+extract(0xe810e8,8))
   rel=e.get_section_by_name('.rela.plt');dyn=e.get_section(rel['sh_link']);matches=[r for r in rel.iter_relocations()if r['r_offset']==0x123e1e8];assert len(matches)==1 and matches[0]['r_info_type']==1026 and matches[0]['r_addend']==0 and dyn.get_symbol(matches[0]['r_info_sym']).name=='memset'
  assert (O/'original-function.bin').read_bytes()[0xac:0xb0]==bytes.fromhex('408d004c')
  for n in['original-function.bin','original-plt.bin','original-global.bin','original-literals.bin']:pin(O/n)
  fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
  assert 0x700b8440 in C['external_guest_references']
  for h in C['external_guest_references']:
   if h!=0x700b8440:fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"ST2-CONSTRUCTOR-FAIL unexpected inherited helper{h:x}\\n");std::exit(21);}}\n'
  (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp')
  save(O/'preexecution-source-pin.json',{'candidate_sha256':sha(CP),'sources':sourcepins,'inputs':inputs})
  run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_st2_constructor_ref.c'],'reference-strict')
  hosts=[]
  for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
   D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP/'whole'),'-isystem',conv(SUP/'windows'),'-I'+conv(S)]
   run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_st2_constructor_test.cpp')],label+'-strict');hosts.append((label,target,cxx,D,conv,flags))
  run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_st2_constructor_ref.c',S/'unity_st2_constructor_native.S','-o',O/'reference'],'reference-build')
  with(O/'reference').open('rb')as f:
   e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());tls=[s for s in e.iter_segments()if s['p_type']=='PT_TLS'];assert tls and all(s['p_align']>=64 for s in tls)
  def capture(key,i,cmd):
   t=run(cmd,f'case-{key}-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1
   if key!='arm64':assert r[0]==records['arm64'][i],('normalized record mismatch',key,i)
   records.setdefault(key,[]).extend(r);observations.setdefault(key,[]).extend(b)
  for i in range(16):capture('arm64',i,[qemu,O/'reference',O/'original-function.bin',O/'original-plt.bin',O/'original-global.bin',O/'original-literals.bin',i])
  for label,target,cxx,D,conv,flags in hosts:
   objects=[]
   for src in[SUP/'whole/runtime.cpp',SUP/'whole/cooperative_poll.cpp',S/'unity_st2_constructor_test.cpp',O/'fences.cpp']:
    obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
   for kind in['raw','polled']:
    obj=Path(C['candidate_object']['path'])if label=='windows'and kind=='polled'else D/(kind+'.o')
    if not(label=='windows'and kind=='polled'):run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',C['raw_ir'if kind=='raw'else'polled_ir']['path'],'-o',obj],label+'-'+kind+'-object')
    exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;bins[key]={'path':str(exe),'sha256':sha(exe),'object_sha256':sha(obj)}
    for i in range(16):capture(key,i,[exe,int(kind=='polled'),conv(O/'original-global.bin'),conv(O/'original-literals.bin'),i])
  for group in[inputs,sourcepins]:
   for n,h in group.items():assert sha(n)==h,n
  save(O/'commands.json',commands)
  result={'passed':True,'candidate_sha256':sha(CP),'actual_Windows_COFF_sha256':C['candidate_object']['sha256'],'records_each':16,'platforms':list(records),'native_complete_original_function':True,'original_FDE':['0x707520c4','0x707521bc'],'actual_memset_effect_all_platforms':True,'architectural_snapshot_bytes':800,'full_State_cross_platform_equality_claimed':False,'object_bytes':0x590,'owned_allocation_bytes':65536,'binaries':bins,'sourcepins':sourcepins,'inputs':inputs,'observations':observations,'record_digests':{k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},'limits':'Complete original true return and real memset; only declared ABI-preserved/post-call-defined state compared. Caller-volatile registers and FPSR observed without equality claim. Controlled opaque global; original Q/D literals. Stack guards plus canaries outside declared16KiB libc/capture budget; no leaf-stack identity. No game/frame/cohort-selection claim.'}
  result['evidence']={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'};save(O/'acceptance.json',result);print('CONSTRUCTOR-QUALIFIED',sha(O/'acceptance.json'),flush=True)
 except Exception as ex:
  save(O/'failure.json',{'passed':False,'error':str(ex),'traceback':traceback.format_exc(),'commands':commands,'sourcepins':sourcepins,'inputs':inputs});raise
if __name__=='__main__':main()
