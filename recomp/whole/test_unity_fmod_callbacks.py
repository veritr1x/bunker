"""Six exact call-free FMOD descriptor callbacks; owned memory, no audio device."""
import argparse,collections,hashlib,json,re,shutil,subprocess
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
RANGES=[(0x70b3bbfc,0x70b3bc10),(0x70b3bc5c,0x70b3bc70),(0x70b3bd90,0x70b3bda8),(0x70b3be80,0x70b3beac),(0x70b3bef8,0x70b3bf1c),(0x70b3bf1c,0x70b3bfa0)]
HEADS=[hex(a)for a,b in RANGES]
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--toolchain',type=Path,required=True);a=ap.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir();T=a.toolchain.resolve();CP=a.candidate.resolve();C=read(CP)
 assert C['passed']is True and C['definitions']==6 and C['entry_heads']==HEADS and C['unsupported_heads']==[]and C['external_guest_references']==[]and C['all_direct_refs_closed']is True
 assert(C['all_old_objects_preserved'],C['old_head_count'],C['new_head_count'],C['proposed_object_count'])==(3577,456700,456706,3578)
 assert C['State_type_closure_sha256']=='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'and(C['State_size'],C['State_align'])==(1200,16)
 for name in('remill-lift','aarch64.bc'):assert C['input_pins'].get(str((T/name).resolve()))==sha(T/name)

 assert set(C['all_poll_coverage'])==set(HEADS)and all(x==dict(entry=1,cycle=0,total=1)for x in C['all_poll_coverage'].values())
 own=['unity_fmod_callbacks_fixture.h','unity_fmod_callbacks_native.S','unity_fmod_callbacks_ref.c','unity_fmod_callbacks_test.cpp','test_unity_fmod_callbacks.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 parent=W/'windows-first-frame-plane-switch1';assert sha(parent/'game_inputs.json')=='00ea9cacd474e9d389bf147ae844c6d12cd9024545ff5c9c653f46da4d9c2849'
 for n in ['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(parent/'sources/recomp/whole'/n,SUP/n)
 sourcepins={str(f):sha(f)for D in[S,SUP]for f in D.rglob('*')if f.is_file()};inputs={str(CP):sha(CP),str(parent/'game_inputs.json'):sha(parent/'game_inputs.json')};commands=[]
 for key in ['input_pins','artifacts']:
  for n,h in C[key].items():assert sha(n)==h,n;inputs[n]=h
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');elf=parent/'native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 for p in [ndk.resolve(),qemu.resolve(),elf,*[Path(shutil.which(n)).resolve()for n in ['clang-18','clang++-18']],Path('/mnt/c/mingw64/bin/g++.exe')]:inputs[str(p)]=sha(p)
 for f in(T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 with elf.open('rb')as f:
  E=ELFFile(f);rva=0xb3bbfc;n=0x3a4;seg=next(z for z in E.iter_segments()if z['p_type']=='PT_LOAD'and z['p_vaddr']<=rva<rva+n<=z['p_vaddr']+z['p_filesz']);original=seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+n]
 (O/'original-callbacks.bin').write_bytes(original);inputs[str(O/'original-callbacks.bin')]=sha(O/'original-callbacks.bin')
 dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);dis.detail=True;bodyproof=[]
 for start,end in RANGES:
  data=original[start-0x70b3bbfc:end-0x70b3bbfc];instructions=list(dis.disasm(data,start));assert sum(x.size for x in instructions)==len(data)and instructions[-1].mnemonic=='ret'
  assert not any(x.mnemonic in('bl','blr','br')for x in instructions)
  for x in instructions:
   if x.mnemonic=='b'or x.mnemonic.startswith('b.')or x.mnemonic in('cbz','cbnz','tbz','tbnz'):assert start<=x.operands[-1].imm<end
  bodyproof.append(dict(start=hex(start),end_exclusive=hex(end),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),callfree=True,branches_within_body=True,genuine_RET=True))
 traces='#pragma once\n'+''.join('extern "C" Memory*sub_'+h[2:]+'(State&,addr_t,Memory*);\n'for h in HEADS)+'static const recomp::Trace kFmodPureTraces[]={'+','.join('{'+h+',sub_'+h[2:]+'}'for h in HEADS)+'};\n';(S/'fmod_pure_traces.h').write_text(traces);sourcepins[str(S/'fmod_pure_traces.h')]=sha(S/'fmod_pure_traces.h')
 def run(cmd,label):
  cmd=list(map(str,cmd));commands.append(cmd)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  if r.returncode:
   (O/'failure.json').write_text(json.dumps(dict(stage=label,exit_code=r.returncode),indent=2)+'\n');raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return(O/(label+'.log')).read_text()
 run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_fmod_callbacks_ref.c'],'reference-strict')
 run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_fmod_callbacks_ref.c',S/'unity_fmod_callbacks_native.S','-o',O/'reference'],'reference-build')
 records={};observations={};binaries={}
 def collect(key,cmd,i):
  t=run(cmd,'case-'+key+'-'+str(i));r=[z for z in t.splitlines()if z.startswith('RECORD ')];ob=[z for z in t.splitlines()if z.startswith('OBSERVATION ')];assert len(r)==len(ob)==1
  if key!='arm64':assert r[0]==records['arm64'][i],key+' complete architecture/memory mismatch case'+str(i)
  records[key].append(r[0]);observations[key].append(ob[0])
 records['arm64']=[];observations['arm64']=[]
 for i in range(35):collect('arm64',[qemu,O/'reference',O/'original-callbacks.bin',i],i)
 print('ORIGINAL-PURE-CALLBACKS-ARM64-PASS35',flush=True)
 pattern=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
 for kind,key in [('raw','raw_ir'),('polled','polled_ir')]:
  p=Path(C[key]['path']);assert sha(p)==C[key]['sha256'];inputs[str(p)]=sha(p);assert sorted(hex(int(z[1],16))for z in re.finditer(pattern,p.read_text(),re.M|re.S))==HEADS
 for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
  D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];objects=[]
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_fmod_callbacks_test.cpp')],label+'-strict')
  for src in [SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_fmod_callbacks_test.cpp']:
   obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
  for kind in ['raw','polled']:
   if label=='windows'and kind=='polled':obj=Path(C['candidate_object']['path']);assert sha(obj)==C['candidate_object']['sha256'];inputs[str(obj)]=sha(obj)
   else:obj=D/(kind+'-entries.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',C[kind+'_ir']['path'],'-o',obj],label+'-'+kind+'-entries')
   exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects+[obj]),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;binaries[key]=dict(path=str(exe),sha256=sha(exe),new_object_sha256=sha(obj),actual_candidate_COFF=label=='windows'and kind=='polled');records[key]=[];observations[key]=[]
   for i in range(35):collect(key,[exe,int(kind=='polled'),i],i)
   print('ORIGINAL-PURE-CALLBACKS-HOST-PASS',key,35,flush=True)
 for group in[inputs,sourcepins]:
  for n,h in group.items():assert sha(n)==h,n
 for n in own:assert sha(HERE/n)==sha(S/n),n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(O/'source-pin.json').write_text(json.dumps(dict(inputs=inputs,sourcepins=sourcepins,live_sources={str(HERE/n):sha(HERE/n)for n in own}),indent=2)+'\n')
 result=dict(passed=True,records_each=35,platforms=list(records),candidate_sha256=sha(CP),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],actual_candidate_COFF_executed_windows_polled=True,definitions=6,entry_heads=HEADS,original_bodies=bodyproof,original_FDE_claimed=False,genuine_original_RET=True,architectural_snapshot_bytes=800,host_full_State_bytes=1200,independent_full_State_oracle=True,opaque_memory_token_bytes=64,owned_allocation_bytes=65536,complete_allocation_oracle=True,independent_signed_division_zero_and_overflow=True,ring_data_read_or_playback_claimed=False,physical_audio_device_claimed=False,sourcepins=sourcepins,inputs=inputs,binaries=binaries,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},limits='Exactly six complete call-free logical callback bodies, no unwind FDE invented. Valid ownedreceiver andmandatoryoutputs; NULLonlyfororiginal guardedoptionaloutputs. Independent integer width/flags/store-order/fullallocation oracle. Actual originalARM, Linuxraw/polled, Windowsraw/actualsix-functionCOFFpolled. All800architectural and65536memory bytes compared; x18/TPIDR and nativeRETaddress normalized only afterlocalchecks; full1200hostState/token independent. Ringdata remainsopaque, literals1/16/44100 are originalcode constants, no physical audio properties/playback/emulatedJava claims. Other10nonleaf descriptor callbacks andJNIhelpers excluded. No game/cohortselection.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-FMOD-PURE-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
