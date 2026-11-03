"""Original complete Unity ST2 object initializer, independent State/memory oracle."""
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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--toolchain',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--reuse-reference',type=Path);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir()
 own=['unity_st2_object_fixture.h','unity_st2_object_native.S','unity_st2_object_ref.c','unity_st2_object_test.cpp','test_unity_st2_object.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 frozen=W/'windows-first-frame-fcsel2/sources/recomp/whole'
 for n in ['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(frozen/n,SUP/n)
 sourcepins={str(f):sha(f)for d in[S,SUP]for f in d.rglob('*')if f.is_file()};inputs={};commands=[]
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');elfpath=W/'windows-first-frame-fcsel2/native/libunity.so';assert sha(elfpath)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 with elfpath.open('rb')as f:
  e=ELFFile(f)
  for name,rva,size in [('original-function.bin',0x7bb458,0x104),('original-global.bin',0x123cc90,8)]:
   seg=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+size<=s['p_vaddr']+s['p_filesz']);(O/name).write_bytes(seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+size])
 assert (O/'original-function.bin').read_bytes()[0x60:0x64]==bytes.fromhex('808d004c')
 for x in[ndk.resolve(),qemu.resolve(),elfpath,O/'original-function.bin',O/'original-global.bin',W/'windows-first-frame-fcsel2/game_inputs.json']:inputs[str(x)]=sha(x)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return (O/(label+'.log')).read_text()
 records={};observations={};reused={}
 if a.reuse_reference:
  R=a.reuse_reference.resolve();j=read(R/'acceptance.json');assert j['passed']and j['records_each']==16 and j['platforms']==['arm64']
  for n in ['unity_st2_object_fixture.h','unity_st2_object_native.S','unity_st2_object_ref.c']:assert sha(S/n)==sha(R/'source'/n)
  for n,h in {**j['inputs'],**j['sourcepins']}.items():assert sha(n)==h;reused[n]=h
  for n,h in j['evidence'].items():assert sha(R/n)==h;reused[str(R/n)]=h
  for n in ['reference','reference-build.log','reference-precheck.log']+[f'case-arm64-{i:02}.log'for i in range(16)]:shutil.copy2(R/n,O/n)
  assert sha(O/'original-function.bin')==sha(R/'original-function.bin')and sha(O/'original-global.bin')==sha(R/'original-global.bin');reused[str(R/'acceptance.json')]=sha(R/'acceptance.json')
 else:
  run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_st2_object_ref.c'],'reference-precheck')
  run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_st2_object_ref.c',S/'unity_st2_object_native.S','-o',O/'reference'],'reference-build')
  for i in range(16):run([qemu,O/'reference',O/'original-function.bin',O/'original-global.bin',i],f'case-arm64-{i:02}')
 with(O/'reference').open('rb')as f:
  e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());tls=[s for s in e.iter_segments()if s['p_type']=='PT_TLS'];assert tls and all(s['p_align']>=64 for s in tls)
 records['arm64']=[];observations['arm64']=[]
 for i in range(16):
  t=(O/f'case-arm64-{i:02}.log').read_text();r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1;records['arm64']+=r;observations['arm64']+=b
 print('ORIGINAL-ARM64-PASS16',flush=True)
 C=None;CP=None;bins={}
 if a.toolchain:
  assert a.candidate;T=a.toolchain.resolve();CP=a.candidate.resolve();C=read(CP);assert C['passed']and C['target_head']=='0x707bb458'and C['definitions']==128 and C['raw_neighbors_byte_exact']==127
  for group in['input_pins','artifacts']:
   for n,h in C[group].items():assert sha(n)==h;inputs[n]=h
  inputs[str(CP)]=sha(CP)
  for f in(T/'include').rglob('*'):
   if f.is_file():inputs[str(f)]=sha(f)
  fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
  for h in C['external_guest_references']:fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"ST2-OBJECT-FAIL unexpected inherited helper{h:x}\\n");std::exit(21);}}\n'
  (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp')
  for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
   D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];objects=[]
   run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_st2_object_test.cpp')],label+'-strict')
   for src in[SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_st2_object_test.cpp',O/'fences.cpp']:
    obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
   for kind in ['raw','polled']:
    obj=Path(C['candidate_object']['path'])if label=='windows'and kind=='polled'else D/(kind+'.o')
    if not(label=='windows'and kind=='polled'):run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',CP.parent/('candidate-'+('unpolled'if kind=='raw'else'polled')+'.ll'),'-o',obj],label+'-'+kind+'-object')
    exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;bins[key]={'path':str(exe),'sha256':sha(exe),'object_sha256':sha(obj)};records[key]=[];observations[key]=[]
    for i in range(16):
     t=run([exe,int(kind=='polled'),conv(O/'original-global.bin'),i],f'case-{key}-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1 and r[0]==records['arm64'][i];records[key]+=r;observations[key]+=b
    print('ORIGINAL-HOST-PASS',key,16,flush=True)
  for name in['clang-18','clang++-18','llvm-nm-18','llvm-objdump-18']:
   f=Path(shutil.which(name)).resolve();inputs[str(f)]=sha(f)
  inputs['/mnt/c/mingw64/bin/g++.exe']=sha('/mnt/c/mingw64/bin/g++.exe')
 # Fresh final physical rehash of all inputs/sources, with no cached verification.
 for group in[inputs,sourcepins,reused]:
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(O/'source-pin.json').write_text(json.dumps({'inputs':inputs,'sourcepins':sourcepins,'reference_reuse':reused},indent=2)+'\n')
 result={'passed':True,'records_each':16,'platforms':list(records),'native_complete_original_function':True,'original_FDE':['0x707bb458','0x707bb55c'],'candidate_sha256':sha(CP)if CP else None,'actual_Windows_COFF_sha256':C['candidate_object']['sha256']if C else None,'binaries':bins,'sourcepins':sourcepins,'inputs':inputs,'reference_reuse':reused,'observations':observations,'record_digests':{k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},'architectural_snapshot_bytes':800,'host_independent_full_State_bytes':1200,'object_bytes':0x498,'owned_allocation_bytes':65536,'limits':'Original complete no-call FDE, true normal return; original file-backed opaque global is fixture input alternating with labelled opaquepoison. Only independently checked native x18/LR/TPIDR are normalized. Native capture800B stack excluded; original leaf stack otherwise exact. No game/backend/threadroot/provider capability claim.','evidence':{str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'}}
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-ST2-OBJECT-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
