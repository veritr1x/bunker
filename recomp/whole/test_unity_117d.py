"""Original504B outer+280B helper versus exact old/new selected Windows COFF."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=['unity_117d_cases.h','unity_117d_ref.c','unity_117d_ref.S','unity_117d_test.cpp','test_unity_117d.py']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--candidate-sha',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stderr.decode(errors='replace')[-4000:])
  return r
 try:
  assert sha(a.candidate)==a.candidate_sha;pin(a.candidate);candidate=json.loads(a.candidate.read_text());assert candidate['passed']and candidate['parent_objects']==4659 and candidate['proposed_objects']==4660 and candidate['parent_heads']==595540 and candidate['proposed_heads']==595548
  for key in ['candidate_object','polled_IR','component_trace_header','original_static_boundary']:assert sha(candidate[key]['path'])==candidate[key]['sha256'];pin(candidate[key]['path'])
  boundary=json.loads(Path(candidate['original_static_boundary']['path']).read_text());old=Path(boundary['selected_object']['path']);assert sha(old)==boundary['selected_object']['sha256']=='36880ad00ef1dc10519ae93a7031781c3ca0e082de60440a3743d6ca9bbae57d';pin(old)
  assert candidate['candidate_object']['sha256']=='f32e3c58f3b49371e179174fab226f84055a314eb98c3eca976f3c244f890a1b'
  pending=['whole/'+n for n in OWN]+['whole/runtime.cpp','whole/cooperative_poll.cpp'];root=HERE.parent;seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  shutil.copyfile(candidate['component_trace_header']['path'],out/'component_entries.h')
  native=Path(boundary['original_ELF']['path']);assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(native)
  from elftools.elf.elffile import ELFFile
  blobs={}
  with native.open('rb')as f:
   elf=ELFFile(f);segments=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD']
   for name,lo,n in [('outer',0x117c5c,504),('helper',0x1172fc,280),('tables',0xe7a000,4096)]:
    segment=next(s for s in segments if s['p_vaddr']<=lo and lo+n<=s['p_vaddr']+s['p_filesz']);f.seek(segment['p_offset']+lo-segment['p_vaddr']);blobs[name]=f.read(n)
  (source/'whole/unity_117d_native.h').write_text('\n'.join('static const unsigned char u17_original_'+n+'[]={'+','.join(map(str,b))+'};'for n,b in blobs.items())+'\n');tables=out/'original-tables.bin';tables.write_bytes(blobs['tables'])
  coff=[old,Path(candidate['candidate_object']['path'])];defined=set();undefined=set()
  for i,obj in enumerate(coff):
   symbols=run(['/usr/lib/llvm-18/bin/llvm-nm','--extern-only','--format=posix',obj],'symbols-'+str(i)).stdout.decode();defined.update(re.findall(r'^(sub_[0-9a-f]+) T',symbols,re.M));undefined.update(re.findall(r'^(sub_[0-9a-f]+) U',symbols,re.M))
  required={'sub_70117c5c','sub_701172fc','sub_70117d1c','sub_70117d24','sub_70117d34','sub_70117d3c'}|{'sub_'+x[2:]for x in candidate['added_heads']};assert required<=defined
  undefined=sorted(undefined-defined);stub=out/'closed-unreached-callouts.cpp';stub.write_text('#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'+''.join('extern "C" Memory*'+name+'(State&,addr_t pc,Memory*){std::fprintf(stderr,"unexpected original callout '+name+' pc=%llx\\n",(unsigned long long)pc);std::_Exit(92);}\n'for name in undefined))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  native_memory=out/'native-data.bin';Windows_memory=out/'Windows-data.bin';reference=out/'original-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'whole/unity_117d_ref.c',source/'whole/unity_117d_ref.S','-o',reference],'compile-Bionic');r=run([qemu,reference,native_memory],'actual-Bionic',60);lines=r.stdout.decode().splitlines();rows=[s for s in lines if s.startswith('UNITY-117D id=')];assert len(rows)==88 and 'UNITY-117D-BIONIC-PASS cases=88 success=64 failure=24 outer=504 helper=280'in lines
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out),'-I'+wp(source/'whole')];objects=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','whole/unity_117d_test.cpp']:
   output=out/(Path(name).stem+'.o');run([cxx,*flags,'-c',wp(source/name),'-o',wp(output)],'compile-'+output.stem);objects.append(output)
  exe=out/'actual-original-outer-and-eight.exe';run([cxx,*flags,*map(wp,objects),*map(wp,coff),wp(stub),'-static','-pthread','-latomic','-o',wp(exe)],'link');r=run([exe,wp(tables),wp(Windows_memory)],'actual-Windows',60);text=r.stdout.decode();actual=[s for s in text.splitlines()if s.startswith('UNITY-117D id=')];assert actual==rows,'Original native/actual selected COFF result/flags/callback/output disagreement';match=re.search(r'UNITY-117D-WINDOWS-PASS checks=(\d+) cases=88 success=64 failure=24 State=1200 Memory64=8 oldAndNewCOFF=1',text);assert match,text[-1000:]
  assert native_memory.stat().st_size==Windows_memory.stat().st_size==88*49152
  with native_memory.open('rb')as left,Windows_memory.open('rb')as right:
   while True:
    first=left.read(1024*1024);second=right.read(1024*1024);assert first==second,'Original/Windows data corpus byte disagreement'
    if not first:break
  for p,digest in held.items():assert sha(p)==digest,p
  result=dict(passed=True,candidate=desc(a.candidate),actual_selected_object=candidate['candidate_object'],unchanged_old_object=desc(old),objects_linked_byte_exact=True,actual_selected_object_linked_byte_exact=True,candidate_polled_IR=candidate['polled_IR'],component_trace_header=candidate['component_trace_header'],owned_sources={n:sha(source/'whole'/n)for n in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},native_ELF=desc(native),original_outer_bytes=504,original_helper_bytes=280,original_native_bodies={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())for n,b in blobs.items()},reference=desc(reference),executable=desc(exe),native_output=desc(out/'actual-Bionic.stdout'),Windows_output=desc(out/'actual-Windows.stdout'),data_corpus=dict(native=desc(native_memory),Windows=desc(Windows_memory),all_bytes_equal=True,bytes_per_case=49152,cases=88),cases=88,success_cases=64,failure_cases=24,checks=int(match[1]),all_three_four_row_original_tables_covered=True,added_targets_exercised=8,float_storage_edge_variants=16,failure_controls=dict(component_index_out_of_bounds=12,component_count_zero=4,disabled_type1_flag=1,false_virtual_readiness=4,unsigned_type_out_of_range=3),actual_native_virtual_callback_only_test=True,virtual_callback_scope='One explicit boolean test readiness method at object vtable+0x130; genuine original280B helper performs its own two calls, count check, TLS canary and return. No helper substitution. Virtual method backend validity semantics not qualified.',full_outer_normal_prologue_epilogue_and_callee_saved_checked=True,callee_save_GPR19_through29=True,callee_save_D8_through15=True,SP_LR_PC_normal_return_checked=True,Memory64_preserved=True,State_size=1200,State_align=16,all_unrelated_State_bytes_and_padding_preserved=True,full_fixture_data_and_guards_compared=True,Windows_guest_stack_guards_checked=True,original_instructions_patched=False,original_game_execution=False,first_frame_claim=False,commands=commands,held_inputs=held,limits='Finite cases execute all504 original outer bytes as reached through genuine entry and epilogues plus the real280B original validation helper. Windows links entire unchanged330124B selected oldCOFF and unchanged8283B added8-entry COFF. Only the object readiness virtual method is an explicitly test-defined boolean callback. Failure controls cover component indices/count, type1 enabled flag, false readiness and unsigned type guards; helper invalid-index formatting/logging/error branches are not reached or qualified, and all unrelated guest imports are fail-closed. Native helper uses actual Bionic TPIDR TLS/canary; Windows uses controlled guest TLS/canary. The full49152B fixture data prefix is byte-compared and independently checked against an output-only write oracle; native host stack and Windows guest stack are separate, with normal ABI/guest stack guards checked. No whole5688B prior function, backend API, original game or first-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-117D-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
