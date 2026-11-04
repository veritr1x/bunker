"""Original plane-dispatch reachable graph and real helpers; finite preset domain."""
import argparse,copy,hashlib,json,re,resource,shutil,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
HEADS=['0x70ae3f7c','0x70ae3f84','0x70ae400c','0x70ae4094','0x70ae4134','0x70ae4208','0x70ae42ec','0x70ae4300','0x70ae4308','0x70ae4310','0x70ae4428']
FUNCTION=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def reference_only(out,candidate):
 C=read(candidate);assert C['passed']is True and C['definitions']==11 and C['entry_heads']==HEADS
 O=out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();own=['unity_plane_dispatch_fixture.h','unity_plane_dispatch_native.S','unity_plane_dispatch_ref.c','unity_plane_dispatch_test.cpp','test_unity_plane_dispatch.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 native_sources={n:sha(S/n)for n in own[:3]};inputs={str(candidate.resolve()):sha(candidate)}
 parent=W/'windows-first-frame-ushll-mask1';elf=parent/'native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';inputs[str(elf)]=sha(elf)
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
 for f in [ndk.resolve(),qemu.resolve()]:inputs[str(f)]=sha(f)
 with elf.open('rb')as f:
  E=ELFFile(f)
  def extract(rva,n):
   seg=next(z for z in E.iter_segments()if z['p_type']=='PT_LOAD'and z['p_vaddr']<=rva<rva+n<=z['p_vaddr']+z['p_filesz']);return seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+n]
  (O/'original-code.bin').write_bytes(extract(0xae31f0,0x124c));(O/'original-constants.bin').write_bytes(extract(0xfa0000,65536)+extract(0xeb0000,65536))
 commands=[];records=[];observations=[]
 def run(cmd,label):
  cmd=list(map(str,cmd));commands.append(cmd)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  if r.returncode:
   (O/'failure.json').write_text(json.dumps(dict(stage=label,exit_code=r.returncode,scope='Native reference only; no host qualification or game'),indent=2)+'\n');raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return(O/(label+'.log')).read_text()
 run([ndk,'-fno-emulated-tls','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(S),S/'unity_plane_dispatch_ref.c'],'reference-strict')
 run([ndk,'-O2','-static','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S),S/'unity_plane_dispatch_ref.c',S/'unity_plane_dispatch_native.S','-o',O/'reference'],'reference-build')
 for i in range(16):
  text=run([qemu,O/'reference',O/'original-code.bin',O/'original-constants.bin',i],'case-arm64-'+str(i));r=[z for z in text.splitlines()if z.startswith('RECORD ')];ob=[z for z in text.splitlines()if z.startswith('OBSERVATION ')];assert len(r)==len(ob)==1;records+=r;observations+=ob;print('NATIVE-DISPATCH-PASS',i,flush=True)
 for n in own:assert sha(HERE/n)==sha(S/n)
 for f,h in inputs.items():assert sha(f)==h
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,records_each=16,platforms=['arm64'],native_sources=native_sources,snapshot_sources={n:sha(S/n)for n in own},inputs=inputs,original_code_sha256=sha(O/'original-code.bin'),original_constants_sha256=sha(O/'original-constants.bin'),record_digest=hashlib.sha256(('\n'.join(records)+'\n').encode()).hexdigest(),observations=observations,scope='Actual original native dispatcher plus real helper graph, all13slots/13/UINT_MAX/disabled control, owned finitepreset object/resourceNULL, genuineRET/object/ABI/canary checks; no host/game/FDE claim. Snapshot test/controller files are provenance, not native executed source.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-PLANE-NATIVE-QUALIFIED',sha(O/'acceptance.json'),flush=True)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--toolchain',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--helper-candidate',type=Path);ap.add_argument('--reference-only',action='store_true');ap.add_argument('--reference-reuse',type=Path);a=ap.parse_args()
 if a.reference_only:return reference_only(a.out,a.candidate)
 assert a.helper_candidate is not None and a.reference_reuse is not None,'Full qualification requires helper candidate and saved native reference'
 O=a.out.resolve();O.mkdir(exist_ok=False);S=O/'source';S.mkdir();SUP=O/'support';SUP.mkdir();CP=a.candidate.resolve();C=read(CP);HP=a.helper_candidate.resolve();H=read(HP);T=a.toolchain.resolve()
 assert C['passed']is True and C['definitions']==11 and C['entry_heads']==HEADS
 assert C['all_direct_refs_closed']is True
 assert H['passed']is True and H['global_index']==466 and H['target_head']=='0x70ae31f0' and H['definitions']==106
 assert H['raw_neighbors_byte_exact']==H['polled_neighbors_byte_exact']==H['native_neighbors_full_bytes_exact']==105
 assert H['all_direct_refs_closed']is True
 assert H['approved_added_declarations']==['declare i32 @llvm.smax.i32(i32, i32) #3']and H['added_attribute_groups']==[]
 assert H['all_other_raw_module_bytes_unchanged']is False and H['all_other_raw_module_bytes_unchanged_except_approved_declaration']is True and H['entire_old_module_recovered_by_target_and_declaration_inverse']is True and H['no_relift_on_declaration_followup']is True
 old_descriptor=next(z for z in C['retained_modules']if z['index']==466)['raw_ir'];assert sha(old_descriptor['path'])==old_descriptor['sha256']
 old_bytes=Path(old_descriptor['path']).read_bytes();new_bytes=Path(H['raw_ir']['path']).read_bytes();target_re=rb'^define[^\n]*@sub_70ae31f0\([^\n]*\).*?^}'
 old_target=re.search(target_re,old_bytes,re.M|re.S)[0];new_target=re.search(target_re,new_bytes,re.M|re.S)[0];approved=b'\ndeclare i32 @llvm.smax.i32(i32, i32) #3\n'
 assert new_bytes.count(approved)==1 and new_bytes.replace(new_target,old_target,1).replace(approved,b'',1)==old_bytes,'Exact target+approved-declaration raw inverse'

 own=['unity_plane_dispatch_fixture.h','unity_plane_dispatch_native.S','unity_plane_dispatch_ref.c','unity_plane_dispatch_test.cpp','test_unity_plane_dispatch.py']
 for n in own:shutil.copy2(HERE/n,S/n)
 parent=W/'windows-first-frame-ushll-mask1';assert sha(parent/'game_inputs.json')=='fbbbbda1ebb959f32333eae42359a2f058345c37df57f6756367b573cb0ad857'
 for n in ['runtime.h','runtime.cpp','cooperative_poll.h','cooperative_poll.cpp']:shutil.copy2(parent/'sources/recomp/whole'/n,SUP/n)
 sourcepins={str(f):sha(f)for D in[S,SUP]for f in D.rglob('*')if f.is_file()};inputs={str(CP):sha(CP),str(HP):sha(HP),str(parent/'game_inputs.json'):sha(parent/'game_inputs.json')};commands=[]
 for packet in [C,H]:
  for key in ['input_pins','artifacts']:
   for n,h in packet[key].items():assert sha(n)==h,n;inputs[n]=h
 ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');elf=parent/'native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 for f in [ndk.resolve(),qemu.resolve(),elf,*[Path(shutil.which(n)).resolve()for n in ['clang-18','clang++-18']],Path('/mnt/c/mingw64/bin/g++.exe')]:inputs[str(f)]=sha(f)
 for f in (T/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 with elf.open('rb')as f:
  E=ELFFile(f)
  def extract(rva,n):
   seg=next(z for z in E.iter_segments()if z['p_type']=='PT_LOAD'and z['p_vaddr']<=rva<rva+n<=z['p_vaddr']+z['p_filesz']);return seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+n]
  (O/'original-code.bin').write_bytes(extract(0xae31f0,0x124c));(O/'original-constants.bin').write_bytes(extract(0xfa0000,65536)+extract(0xeb0000,65536))
 assert (O/'original-code.bin').read_bytes()[0x3f04-0x31f0:0x3f08-0x31f0]==bytes.fromhex('ff0301d1')
 assert (O/'original-code.bin').read_bytes()[-4:]==bytes.fromhex('c0035fd6')
 assert (O/'original-constants.bin').read_bytes()[0xb758:0xb758+52]==bytes.fromhex('d08cb3ff2488b3ff2c88b3ffb488b3ff3c89b3ffdc89b3ffb08ab3ff948bb3ff948bb3ff948bb3ffa88bb3ffb08bb3ffb88bb3ff')
 for f in [O/'original-code.bin',O/'original-constants.bin']:inputs[str(f)]=sha(f)
 def run(cmd,label,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd)
  if not label.startswith('case-'):print('STAGE',label,flush=True)
  with(O/(label+'.log')).open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(label+' exit'+str(r.returncode)+'\n'+(O/(label+'.log')).read_text(errors='replace')[-3000:])
  return(O/(label+'.log')).read_text()
 # Construct exact retained-body projections; all helper instructions/CFG stay
 # unchanged. These are original current selected bodies, not success shims.
 old_helper_module=next(z for z in C['retained_modules']if z['index']==466)
 modules=copy.deepcopy(C['retained_modules']);modules.sort(key=lambda z:z['index'])
 for z in modules:
  if z['index']==466:z.update(raw_ir=H['raw_ir'],polled_ir=H['polled_ir'],heads=['0x70ae31f0'])
 assert {z['index']for z in modules}=={463,465,466}
 retained_heads={h for z in modules for h in z['heads']};assert {'0x70ae3f04','0x70ae3d10','0x70ae31f0'}<=retained_heads
 allheads=set(HEADS)|retained_heads;assert len(allheads)==len(HEADS)+len(retained_heads)
 traces='#pragma once\n'
 for h in sorted(allheads,key=lambda x:int(x,0)):traces+='extern "C" Memory*sub_'+h[2:]+'(State&,addr_t,Memory*);\n'
 traces+='static const recomp::Trace kPlaneDispatchTraces[]={'+','.join('{'+h+',sub_'+h[2:]+'}'for h in sorted(allheads,key=lambda x:int(x,0)))+'};\n';(S/'plane_dispatch_traces.h').write_text(traces);sourcepins[str(S/'plane_dispatch_traces.h')]=sha(S/'plane_dispatch_traces.h')
 projections={};proofs={};guestrefs=set()
 for kind,key in [('raw','raw_ir'),('polled','polled_ir')]:
  projections[kind]=[];proofs[kind]=[]
  for z in modules:
   p=Path(z[key]['path']);assert sha(p)==z[key]['sha256'];inputs[str(p)]=sha(p);text=p.read_text();matches=list(re.finditer(FUNCTION,text,re.M|re.S));wanted={int(h,0)for h in z['heads']};bodies={int(m[1],16):m[0]for m in matches if int(m[1],16)in wanted};assert set(bodies)==wanted and not re.search(r'blockaddress\(',text)
   def project(m):
    if int(m[1],16)in wanted:return m[0]
    sig=m[0].split('\n',1)[0];assert sig.endswith('{');return'declare '+sig[len('define '):-1].rstrip()
   projected=re.sub(FUNCTION,project,text,flags=re.M|re.S);actual={int(m[1],16):m[0]for m in re.finditer(FUNCTION,projected,re.M|re.S)};assert actual==bodies
   out=O/(kind+'-retained-'+str(z['index'])+'.ll');out.write_text(projected);projections[kind].append(out);sourcepins[str(out)]=sha(out);proofs[kind].append(dict(source_ir=z[key],heads=z['heads'],selected_bodies_byte_exact=True,body_sha256={hex(h):hashlib.sha256(v.encode()).hexdigest()for h,v in bodies.items()},full_old_selected_COFF_executed=False))
   for body in bodies.values():guestrefs.update(int(h,16)for h in re.findall(r'@sub_([0-9a-f]+)\(',body))
  p=Path(C[key]['path']);assert sha(p)==C[key]['sha256'];inputs[str(p)]=sha(p);text=p.read_text();matches=list(re.finditer(FUNCTION,text,re.M|re.S));assert sorted(hex(int(m[1],16))for m in matches)==HEADS
  for m in matches:guestrefs.update(int(h,16)for h in re.findall(r'@sub_([0-9a-f]+)\(',m[0]))
 guestrefs.update(int(h,0)if isinstance(h,str)else h for h in H['external_guest_references'])
 helper_defined={int(h,0)for h in H['all_poll_coverage']}
 fences='#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'
 for h in sorted(guestrefs-{int(h,0)for h in allheads}-helper_defined):fences+=f'extern "C" Memory*sub_{h:x}(State&,addr_t,Memory*){{std::fprintf(stderr,"PLANE-DISPATCH-FAIL excluded real helper/import{h:x} reached\\n");std::exit(21);}}\n'
 (O/'fences.cpp').write_text(fences);sourcepins[str(O/'fences.cpp')]=sha(O/'fences.cpp')
 saved=a.reference_reuse.resolve();R=read(saved);assert R['passed']is True and R['records_each']==16 and R['platforms']==['arm64']
 for n,h in R['native_sources'].items():assert sha(S/n)==h,'Saved native reference source differs: '+n
 assert sha(O/'original-code.bin')==R['original_code_sha256']and sha(O/'original-constants.bin')==R['original_constants_sha256']
 inputs[str(saved)]=sha(saved)
 for n,h in R['inputs'].items():assert sha(n)==h;inputs[n]=h
 for n,h in R['evidence'].items():
  f=saved.parent/n;assert sha(f)==h;inputs[str(f)]=h
 records={'arm64':[]};observations={'arm64':[]};binaries={};old_controls=[];old_failure_case=None
 for i in range(16):
  text=(saved.parent/('case-arm64-'+str(i)+'.log')).read_text();r=[z for z in text.splitlines()if z.startswith('RECORD ')];ob=[z for z in text.splitlines()if z.startswith('OBSERVATION ')];assert len(r)==len(ob)==1;records['arm64']+=r;observations['arm64']+=ob
 assert hashlib.sha256(('\n'.join(records['arm64'])+'\n').encode()).hexdigest()==R['record_digest']
 print('ORIGINAL-DISPATCH-ARM64-REUSED16',flush=True)
 def collect(key,cmd,i):
  text=run(cmd,'case-'+key+'-'+str(i));r=[z for z in text.splitlines()if z.startswith('RECORD ')];ob=[z for z in text.splitlines()if z.startswith('OBSERVATION ')];assert len(r)==len(ob)==1 and r[0]==records['arm64'][i],key+' completeobject/return/ABI mismatch case'+str(i);records[key].append(r[0]);observations[key].append(ob[0])
 for label,target,cxx in [('linux','x86_64-linux-gnu','clang++-18'),('windows','x86_64-w64-windows-gnu','/mnt/c/mingw64/bin/g++.exe')]:
  D=O/label;D.mkdir();conv=wp if label=='windows'else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',conv(T/'include'),'-I'+conv(SUP),'-I'+conv(S)];objects=[]
  run([cxx,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',conv(S/'unity_plane_dispatch_test.cpp')],label+'-strict')
  for src in [SUP/'runtime.cpp',SUP/'cooperative_poll.cpp',S/'unity_plane_dispatch_test.cpp',O/'fences.cpp']:
   obj=D/(src.stem+'.o');run([cxx,*flags,'-c',conv(src),'-o',conv(obj)],label+'-'+src.stem);objects.append(obj)
  for kind in ['raw','polled']:
   selected=[]
   for j,ir in enumerate(projections[kind]):
    if label=='windows'and kind=='polled'and modules[j]['index']==466:
     obj=Path(H['candidate_object']['path']);assert sha(obj)==H['candidate_object']['sha256'];inputs[str(obj)]=sha(obj);selected.append(obj);continue
    obj=D/(kind+'-retained-'+str(j)+'.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',ir,'-o',obj],label+'-'+kind+'-retained-'+str(j));selected.append(obj)
   if label=='windows'and kind=='polled':
    obj=Path(C['candidate_object']['path']);assert sha(obj)==C['candidate_object']['sha256'];inputs[str(obj)]=sha(obj)
   else:
    obj=D/(kind+'-new-entries.o');run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',C[kind+'_ir']['path'],'-o',obj],label+'-'+kind+'-entries')
   exe=D/(kind+('.exe'if label=='windows'else''));run([cxx,*map(conv,objects+selected+[obj]),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread',*(['-static']if label=='windows'else[]),'-o',conv(exe)],label+'-'+kind+'-link');key=label+'-'+kind;binaries[key]=dict(path=str(exe),sha256=sha(exe),new_entry_object_sha256=sha(obj),actual_candidate_COFF=label=='windows'and kind=='polled',actual_helper_COFF=label=='windows'and kind=='polled');records[key]=[];observations[key]=[]
   for i in range(16):collect(key,[exe,int(kind=='polled'),conv(O/'original-constants.bin'),i],i)
   print('ORIGINAL-DISPATCH-HOST-PASS',key,16,flush=True)
   if label=='linux'and kind=='raw':
    oldpath=Path(old_helper_module['raw_ir']['path']);assert sha(oldpath)==old_helper_module['raw_ir']['sha256'];inputs[str(oldpath)]=sha(oldpath);oldtext=oldpath.read_text();oldmatches=list(re.finditer(FUNCTION,oldtext,re.M|re.S));oldbody=next(m[0]for m in oldmatches if m[1]=='70ae31f0')
    def oldproject(m):
     if m[1]=='70ae31f0':return m[0]
     sig=m[0].split('\n',1)[0];assert sig.endswith('{');return'declare '+sig[len('define '):-1].rstrip()
    oldir=O/'old-helper466-control.ll';oldir.write_text(re.sub(FUNCTION,oldproject,oldtext,flags=re.M|re.S));assert next(m[0]for m in re.finditer(FUNCTION,oldir.read_text(),re.M|re.S)if m[1]=='70ae31f0')==oldbody;sourcepins[str(oldir)]=sha(oldir)
    oldobj=D/'old-helper466-control.o';run(['clang-18','-target',target,'-O2','-Wno-override-module','-c',oldir,'-o',oldobj],'linux-old-helper466-control')
    oldselected=[oldobj if z['index']==466 else q for z,q in zip(modules,selected)];oldexe=D/'old-helper466-control';run([cxx,*map(conv,objects+oldselected+[obj]),'-Wl,--wrap=__bunker_guest_poll_requested','-Wl,--wrap=__bunker_guest_poll_slow','-latomic','-pthread','-o',oldexe],'linux-old-helper466-control-link')
    for i in range(2,7):
     cmd=list(map(str,[oldexe,0,O/'original-constants.bin',i]));commands.append(cmd);dest=O/('old-helper466-case-'+str(i)+'.log')
     with dest.open('w')as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
     text=dest.read_text(errors='replace');observed='recomp: unliftable instruction at 0x70ae33c0'in text
     old_controls.append(dict(case=i,exit_code=r.returncode,expected_old_unliftable_observed=observed,log_path=str(dest),log_sha256=sha(dest),corresponding_new_case_passed=True))
     if observed:
      assert r.returncode!=0;old_failure_case=i;print('EXPECTED-OLD-HELPER-FADDP-FAILURE case',i,'NEXT_PC70ae33c0',flush=True);break
     assert r.returncode==0 and 'RECORD 'in text,'unexpected old-helper control failure'
    assert old_failure_case is not None,'finite preset cases did not demonstrate old FADDP failure; report without inventing coverage'

 for group in [inputs,sourcepins]:
  for n,h in group.items():assert sha(n)==h,n
 for n in own:assert sha(HERE/n)==sha(S/n),n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(O/'source-pin.json').write_text(json.dumps(dict(inputs=inputs,sourcepins=sourcepins,live_sources={str(HERE/n):sha(HERE/n)for n in own}),indent=2)+'\n')
 result=dict(passed=True,records_each=16,platforms=list(records),candidate_sha256=sha(CP),native_reference_reused_path=str(saved),native_reference_reused_sha256=sha(saved),actual_Windows_COFF_sha256=C['candidate_object']['sha256'],old_helper_regression_controls=old_controls,old_FADDP_failure_case=old_failure_case,old_FADDP_NEXT_PC='0x70ae33c0',helper_candidate_sha256=sha(HP),actual_helper_Windows_COFF_sha256=H['candidate_object']['sha256'],actual_candidate_COFF_executed_windows_polled=True,actual_helper_COFF_executed_windows_polled=True,retained_body_projections=proofs,original_reachable_graph=['0x70ae3f04','0x70ae443c'],original_FDE_claimed=False,real_dependency_heads=sorted(retained_heads),original_native_code_range=['0x70ae31f0','0x70ae443c'],genuine_original_RET=True,optional_resource_NULL=True,finite_preset_domain=True,excluded_sqrtf_fallback_reached=False,full_caller_clobber_equality_claimed=False,object_allocation_bytes=65536,return_SP_callee_saved_ABI=True,sourcepins=sourcepins,inputs=inputs,binaries=binaries,observations=observations,record_digests={k:hashlib.sha256(('\n'.join(v)+'\n').encode()).hexdigest()for k,v in records.items()},limits='Original dispatcher reachable branch/RET graph without an .eh_frame FDE claim. All13slots plus13/UINT_MAX/disabled control. Optional resource NULL. Realoriginal3d10/31f0 helpers, finitepreset inputs; excluded sqrtf import is fatal, never a success shim. Full64KiBobject/canaries, returnedW0/SP/x19..29/low64v8..15/FPCR crosscompared; callerclobbered register equality not claimed. Retained exactselectedIR helpers compiled separately; Windows-polled executesactual11functioncandidateCOFF andactual106functionhelper466COFF; retained dispatcher/setter bodies compiledexactly. Otherhelper466neighbors presentbutnotclaimed dynamicallyexecuted. No game/frame/cohortselection.',evidence={str(f.relative_to(O)):sha(f)for f in O.rglob('*')if f.is_file()and f.name!='acceptance.json'})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGINAL-PLANE-DISPATCH-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
