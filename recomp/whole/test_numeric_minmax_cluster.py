"""Exact reached32B fragment, truefallthrough stop: original Bionic versus current fresh lift."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=['numeric_minmax_cluster_cases.h','numeric_minmax_cluster_ref.c','numeric_minmax_cluster_ref.S','numeric_minmax_cluster_test.cpp','test_numeric_minmax_cluster.py']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stderr.decode(errors='replace')[-5000:])
  return r
 try:
  pending=['whole/'+name for name in OWN]+['whole/runtime.cpp'];root=HERE.parent;seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  native=W/'windows-first-frame-guest-transfer1/native/libil2cpp.so';assert sha(native)=='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522';pin(native)
  from elftools.elf.elffile import ELFFile
  with native.open('rb')as stream:
   elf=ELFFile(stream);segment=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=0x41e55d0<0x41e55f0<=s['p_vaddr']+s['p_filesz']);body=segment.data()[0x41e55d0-segment['p_vaddr']:0x41e55f0-segment['p_vaddr']]
  assert len(body)==32 and body[-8:]==bytes.fromhex('a169201ec669201e');raw=out/'original32.bin';raw.write_bytes(body);(source/'whole/numeric_minmax_cluster_native.h').write_text('static const unsigned char nmc_original_bytes[]={'+','.join(map(str,body))+'};\n')
  fixture_boundary_heads=out/'fixture-boundary-heads.txt';fixture_boundary_heads.write_text('0x841e55d0\n0x841e55f0\n');lift=W/'frinta-toolchain1/tools/remill-lift';semantics=W/'frinta-toolchain1/tools/aarch64.bc';assert sha(lift)=='73a1d6cf043bed30fc340059005a7ab931e9da350a057cc8e16b0304d614279d'and sha(semantics)=='24e908b3be9b017ffb64e775df613a7aae675bdae59dd4995c402a0fdc303c2e';pin(lift);pin(semantics)
  ir=out/'fresh-fragment.ll';run([lift,'--arch','aarch64','--os','linux','--semantics_dir',semantics.parent,'--bytes_file',raw,'--address','0x841e55d0','--entry_address','0x841e55d0','--trace_heads_file',fixture_boundary_heads,'--guest_call_transfer=true','--ir_out',ir],'fresh-lift')
  ir_text=ir.read_text();definitions=re.findall(r'^define[^\n]*@(sub_[0-9a-f]+)\(',ir_text,re.M);assert definitions==['sub_841e55d0']and not re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',ir_text);assert re.search(r'call[^\n]*@sub_841e55f0\(',ir_text),'Fallthrough must stop at explicit fixture boundary beforeFMUL'
  obj=out/'fresh-fragment.o';run(['clang++-18','--target=x86_64-w64-windows-gnu','-O2','-x','ir','-c',ir,'-o',obj],'compile-fresh-fragment');symbols=run(['/usr/lib/llvm-18/bin/llvm-nm','--extern-only','--undefined-only','--format=posix',obj],'fragment-undefined').stdout.decode();assert sorted(set(re.findall(r'^(sub_[0-9a-f]+) U',symbols,re.M)))==['sub_841e55f0']
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  native_snapshots=out/'native-snapshots.bin';Windows_snapshots=out/'Windows-snapshots.bin';reference=out/'actual-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'whole/numeric_minmax_cluster_ref.c',source/'whole/numeric_minmax_cluster_ref.S','-o',reference],'compile-Bionic');r=run([qemu,reference,native_snapshots],'actual-Bionic',60);lines=r.stdout.decode().splitlines();rows=[line for line in lines if line.startswith('NUMERIC-CLUSTER pair=')];assert len(rows)==1024 and'NUMERIC-CLUSTER-BIONIC-PASS cases=1024 original_bytes=32 exact_fallthrough=841e55f0'in lines
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(source/'whole')];objects=[]
  for name in ['runtime.cpp','numeric_minmax_cluster_test.cpp']:
   target=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name=='numeric_minmax_cluster_test.cpp'else[]),'-c',wp(source/'whole'/name),'-o',wp(target)],'compile-'+Path(name).stem);objects.append(target)
  exe=out/'fresh-context.exe';run([cxx,*map(wp,objects),wp(obj),'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');r=run([exe,wp(Windows_snapshots)],'actual-Windows',60);text=r.stdout.decode();assert[line for line in text.splitlines()if line.startswith('NUMERIC-CLUSTER pair=')]==rows;match=re.search(r'NUMERIC-CLUSTER-WINDOWS-PASS checks=(\d+) cases=1024 State=1200 Memory64=8 exact_fallthrough=841e55f0',text);assert match,text[-1000:]
  assert native_snapshots.stat().st_size==Windows_snapshots.stat().st_size==1024*808 and native_snapshots.read_bytes()==Windows_snapshots.read_bytes()
  for p,digest in held.items():assert sha(p)==digest,p
  reuse=W/'numeric-minmax-reuse-review1/acceptance.json';assert sha(reuse)=='d07c42d4b5fe9860e13da9ed95095cebda60d4557fda22764f888ef7572bc029';pin(reuse)
  result=dict(passed=True,actual_original_fragment=desc(raw),original_fragment_start='0x841e55d0',original_fragment_end_exclusive='0x841e55f0',original_fragment_bytes=32,original_instruction_count=8,all_original_fragment_bytes_unchanged=True,no_guest_RET_added=True,stopped_at_true_fallthrough_before_FMUL=True,fresh_fragment_IR=desc(ir),fresh_fragment_object=desc(obj),actual_lifter=desc(lift),actual_semantics=desc(semantics),compiled_semantics_reuse_review=desc(reuse),test_only_entry_and_stop_heads=desc(fixture_boundary_heads),cases=1024,input_pairs=32,FPCR_profiles=16,initial_FPSR_profiles=2,checks=int(match[1]),snapshot_corpus=dict(native=desc(native_snapshots),Windows=desc(Windows_snapshots),all_bytes_equal=True,bytes_per_case=808,cases=1024),all_GPR_SP_LR_Simd_NZCV_FPSR_FPCR_snapshot_bytes_compared=True,all_original_unrelated_State_bytes_and_padding_preserved=True,State_size=1200,State_align=16,Memory64_identity_and_contents_preserved=True,read_only_arena_bytes=65536,all_input_load_and_opaque_memory_guards_preserved=True,fixture_memory_excluded_intervals=[[0x1f00,0x2000],[0x8000,0x8000+808]],synthetic_initialized_context=dict(S9=4,S10=2,S11=1,stack_SP_plus_0x5c=0.5,controlled_X11_plus_0x7e0=0.25,X11='fixtureBASE+0x4000',S13_S14='signedzeros/normals/infinities/qNaNs/sNaNs/subnormals',actual_original_game_field_values_captured=False),owned_sources={name:sha(source/'whole'/name)for name in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},native_ELF=desc(native),reference=desc(reference),executable=desc(exe),native_output=desc(out/'actual-Bionic.stdout'),Windows_output=desc(out/'actual-Windows.stdout'),commands=commands,held_inputs=held,original_game_execution=False,whole_38572B_TMP_function_executed=False,actual_large_candidate_object_executed=False,full_outer_ABI_return_claim=False,first_frame_claim=False,scope='Supplemental bounded original32B instruction-context differential only. Native executes unmodified original bytes with generated fixture boundary outside the fragment; Windows executes a fresh current-tool lift of only those32B with a test-only trace boundary at true fallthrough. Both stop before FMUL. Synthetic SP/register/read-memory inputs are explicit and not captured game object state. All808B architectural snapshots match the independent per-lane oracle and each other. This qualifies neither the whole38572B TMP method nor its actual selected retained candidate object; those require separate static preservation/closure audits and original startup integration.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('NUMERIC-CLUSTER-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
