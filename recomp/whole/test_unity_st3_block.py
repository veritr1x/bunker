"""Exact original ST3 initialization prefix; projected candidate IR, not full FDE."""
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
 assert C['passed']and C['target_head']=='0x704fd850'and C['global_index']==200 and C['definitions']==128 and C['raw_neighbors_byte_exact']==C['polled_neighbors_byte_exact']==C['native_neighbors_full_bytes_exact']==127
 own=['unity_st3_block_fixture.h','unity_st3_block_native.S','unity_st3_block_ref.c','unity_st3_block_test.cpp','test_unity_st3_block.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 frozen=W/'windows-first-frame-label2/sources/recomp/whole'
 for n in ['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(frozen/n,SUP/n)
 sourcepins={str(f):sha(f)for d in[S,SUP]for f in d.rglob('*')if f.is_file()};inputs={str(CP):sha(CP)};commands=[]
 for group in ['input_pins','artifacts']:
  for n,h in C[group].items():assert sha(n)==h;inputs[n]=h
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');elfpath=W/'windows-first-frame-label2/native/libunity.so';assert sha(elfpath)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 with elfpath.open('rb')as f:
  e=ELFFile(f)
  def extract(rva,size):
   seg=next(s for s in e.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+size<=s['p_vaddr']+s['p_filesz']);return seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+size]
  (O/'original-prefix.bin').write_bytes(extract(0x4fd850,0x2f4));(O/'original-constants.bin').write_bytes(b''.join(extract(v,65536)for v in [0xeb0000,0xe70000,0xf00000]))
 assert (O/'original-prefix.bin').read_bytes()[0x2e8:0x2ec]==bytes.fromhex('5441004c')and (O/'original-prefix.bin').read_bytes()[-4:]==bytes.fromhex('a2040094')
 for x in [ndk.resolve(),qemu.resolve(),elfpath,O/'original-prefix.bin',O/'original-constants.bin',W/'windows-first-frame-label2/game_inputs.json']:inputs[str(x)]=sha(x)
 for f in (T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return (O/(label+'.log')).read_text()
 run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_st3_block_ref.c'],'reference-precheck')
 run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_st3_block_ref.c',S/'unity_st3_block_native.S','-o',O/'reference'],'reference-build')
 records={};observations={};bins={};records['arm64']=[];observations['arm64']=[]
 for i in range(16):
  t=run([qemu,O/'reference',O/'original-prefix.bin',O/'original-constants.bin',i],f'case-arm64-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1;records['arm64']+=r;observations['arm64']+=b
 print('ORIGINAL-PREFIX-ARM64-PASS16',flush=True)
 with(O/'reference').open('rb')as f:
  e=ELFFile(f);assert e['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in e.iter_segments());assert any(s['p_type']=='PT_TLS'and s['p_align']>=64 for s in e.iter_segments())
 target_re=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
 projections={};projection_proof={}
 for kind,key in [('raw','raw_ir'),('polled','polled_ir')]:
  text=Path(C[key]['path']).read_text();matches=list(re.finditer(target_re,text,re.M|re.S));assert len(matches)==128
  target=next(m[0]for m in matches if m[1]=='704fd850');assert not re.search(r'blockaddress\(',text),'external label address: HOLD'
  def project(m):
   if m[1]=='704fd850':return m[0]
   signature=m[0].split('\n',1)[0];assert signature.endswith('{');return 'declare '+signature[len('define '):-1].rstrip()
  result=re.sub(target_re,project,text,flags=re.M|re.S);assert re.search(target_re,result,re.M|re.S)[0]==target
  P=O/(kind+'-target-projection.ll');P.write_text(result);projections[kind]=P;sourcepins[str(P)]=sha(P);projection_proof[kind]=dict(source_ir=C[key],target_body_sha256=hashlib.sha256(target.encode()).hexdigest(),target_body_byte_exact=True,unselected_guest_definitions_declared=127,full_selected_COFF_executed=False)
 fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
 refs=set(int(h,16)for h in re.findall(r'@sub_([0-9a-f]+)\(',target))-{0x704fd850,0x704fedc8}
 for h in sorted(refs):fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"ST3-BLOCK-FAIL unexpected inherited helper{h:x}\\n");std::exit(21);}}\n'
 (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp')
 for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
  D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];objects=[]
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_st3_block_test.cpp')],label+'-strict')
  for src in [SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_st3_block_test.cpp',O/'fences.cpp']:
   obj=D/(src.stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if src.parent==S else[]),'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
  for kind in ['raw','polled']:
   obj=D/(kind+'.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',projections[kind],'-o',obj],label+'-'+kind+'-projection')
   exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects),conv(obj),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;bins[key]=dict(path=str(exe),sha256=sha(exe),projection_object_sha256=sha(obj));records[key]=[];observations[key]=[]
   for i in range(16):
    t=run([exe,int(kind=='polled'),conv(O/'original-constants.bin'),i],f'case-{key}-{i:02}');r=[x for x in t.splitlines()if x.startswith('RECORD ')];b=[x for x in t.splitlines()if x.startswith('OBSERVATION ')];assert len(r)==len(b)==1 and r[0]==records['arm64'][i],key+' actual full state/global/frame mismatch case'+str(i);records[key]+=r;observations[key]+=b
   print('ORIGINAL-PREFIX-HOST-PASS',key,16,flush=True)
 for name in ['clang-18','clang++-18','llvm-nm-18','llvm-objdump-18']:
  f=Path(shutil.which(name)).resolve();inputs[str(f)]=sha(f)
 inputs['/mnt/c/mingw64/bin/g++.exe']=sha('/mnt/c/mingw64/bin/g++.exe')
 for group in [inputs,sourcepins]:
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(O/'source-pin.json').write_text(json.dumps(dict(inputs=inputs,sourcepins=sourcepins,live_sources={str(HERE/n):sha(HERE/n)for n in own}),indent=2)+'\n')
 for n in own:assert sha(HERE/n)==sha(S/n),n
 result=dict(passed=True,records_each=16,platforms=list(records),candidate_sha256=sha(CP),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],projection_proof=projection_proof,native_complete_original_function=False,original_FDE=['0x704fd850','0x704fdb60'],original_prefix=['0x704fd850','0x704fdb44'],capture_helper_entry='0x704fedc8',helper_body_executed=False,binaries=bins,sourcepins=sourcepins,inputs=inputs,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},architectural_snapshot_bytes=800,host_GPR_high_cell_preservation=True,output_table_bytes=768,index_table_oracle=True,global_allocation_bytes=65536,original_saved_frame_bytes=64,limits='Exact original prefix includes realBL to704fedc8; fixture captures at helper entry without executing helper body. ARM runs original bytes; both hosts compile exact candidate target-body IR projections with other127definitions declared, avoiding unrelated helper IPO. Full selected128functionWindowsCOFF is statically qualified, not dynamically executed here. All800architecture/full65536global/index/output/canary and64frame bytes compared; x18/TPIDR alone normalized. No full1200 independent arithmetic oracle or full non-leaf FDE return claim; host GPR high cells separately guarded. No game/frame/cohort selection.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-ST3-PREFIX-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
