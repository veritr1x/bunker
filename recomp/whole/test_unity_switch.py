"""Actual appended12-entry COFF: bounded original Bionic switch/target qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=['unity_switch_cases.h','unity_switch_ref.c','unity_switch_ref.S','unity_switch_test.cpp','test_unity_switch.py']
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
  assert sha(a.candidate)==a.candidate_sha;pin(a.candidate);candidate=json.loads(a.candidate.read_text());assert candidate['passed']and candidate['parent_objects']==4658 and candidate['proposed_objects']==4659 and candidate['parent_heads']==595528 and candidate['proposed_heads']==595540
  for key in ['candidate_object','polled_IR','component_trace_header','original_static_boundary']:assert sha(candidate[key]['path'])==candidate[key]['sha256'];pin(candidate[key]['path'])
  assert candidate['candidate_object']['sha256']=='88e21e57f84ad1b0c4c8bf5e722268d0e06a59b56af3887a5dfc2eb8b31caae3'
  pending=['whole/'+n for n in OWN]+['whole/runtime.cpp','whole/cooperative_poll.cpp'];root=HERE.parent;seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  shutil.copyfile(candidate['component_trace_header']['path'],out/'component_entries.h')
  native=W/'windows-first-frame-guest-transfer1/native/libunity.so';assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(native)
  from elftools.elf.elffile import ELFFile
  blobs={}
  with native.open('rb')as f:
   elf=ELFFile(f);segments=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD']
   for name,lo,n in [('FDE',0x1068d8,5688),('tables',0xe7a000,4096)]:
    segment=next(s for s in segments if s['p_vaddr']<=lo and lo+n<=s['p_vaddr']+s['p_filesz']);f.seek(segment['p_offset']+lo-segment['p_vaddr']);blobs[name]=f.read(n)
  (source/'whole/unity_switch_native.h').write_text('\n'.join('static const unsigned char us_original_'+n+'[]={'+','.join(map(str,b))+'};'for n,b in blobs.items())+'\n');tables=out/'unity-switch-tables.bin';tables.write_bytes(blobs['tables'])
  nm=run(['/usr/lib/llvm-18/bin/llvm-nm','--extern-only','--undefined-only','--format=posix',candidate['candidate_object']['path']],'undefined-symbols').stdout.decode();undefined=sorted(set(re.findall(r'^(sub_[0-9a-f]+) U',nm,re.M)));assert len(undefined)==19
  stub=out/'closed-old-callouts.cpp';stub.write_text('#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\nextern "C" Memory*UnitySwitchImport(State&,addr_t,Memory*);\n'+''.join('extern "C" Memory*'+name+'(State&s,addr_t pc,Memory*m){'+('return UnitySwitchImport(s,pc,m);'if name in ['sub_7036fb34','sub_707f48cc','sub_7036d29c']else'(void)s;(void)m;std::fprintf(stderr,"unexpected original callout '+name+' pc=%llx\\n",(unsigned long long)pc);std::_Exit(92);')+'}\n'for name in undefined))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  native_memory=out/'native-memory.bin';Windows_memory=out/'Windows-memory.bin'
  reference=out/'original-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'whole/unity_switch_ref.c',source/'whole/unity_switch_ref.S','-o',reference],'compile-Bionic');r=run([qemu,reference,native_memory],'actual-Bionic',60);lines=r.stdout.decode().splitlines();rows=[s for s in lines if s.startswith('UNITY-SWITCH head=')];guards=[s for s in lines if s.startswith('UNITY-SWITCH-GUARD ')];assert len(rows)==384 and len(guards)==28 and 'UNITY-SWITCH-BIONIC-PASS guards=28 cases=384 originalFDE=5688'in lines
  # Independently decode the original signed little-endian words. Native guard
  # slices above execute their real LDRSW/ADD/BR and unsigned range branch.
  for line in guards:
   m=re.fullmatch(r'UNITY-SWITCH-GUARD group=(\d+) source=([0-9a-f]+) target=([0-9a-f]+) nzcv=([0-9a-f]+)',line);assert m
   group,value,target=int(m[1]),int(m[2],16),int(m[3],16);base=[0x70e7a0b4,0x70e7a0c4,0x70e7a0e4][group];count=[4,8,4][group];index=(value-1)&0xffffffff
   expected=base+struct.unpack_from('<i',blobs['tables'],base-0x70e7a000+index*4)[0]if index<count else[0x70107080,0x70107954,0x70107c18][group];assert target==expected
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out),'-I'+wp(source/'whole')];objects=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','whole/unity_switch_test.cpp']:
   output=out/(Path(name).stem+'.o');run([cxx,*flags,'-c',wp(source/name),'-o',wp(output)],'compile-'+output.stem);objects.append(output)
  exe=out/'actual-selected-switch.exe';run([cxx,*flags,*map(wp,objects),wp(Path(candidate['candidate_object']['path'])),wp(stub),'-static','-pthread','-latomic','-o',wp(exe)],'link');r=run([exe,wp(tables),wp(Windows_memory)],'actual-Windows',60);text=r.stdout.decode();actual=[s for s in text.splitlines()if s.startswith('UNITY-SWITCH head=')];assert actual==rows,'Actual selected COFF/native boundary register or memory disagreement';match=re.search(r'UNITY-SWITCH-WINDOWS-PASS checks=(\d+) cases=384 State=1200 Memory64=8 actualCOFF=1',text);assert match,text[-1000:]
  assert native_memory.stat().st_size==Windows_memory.stat().st_size==384*(0xf00+0x6000+0x7000)
  with native_memory.open('rb')as left,Windows_memory.open('rb')as right:
   while True:
    first=left.read(1024*1024);second=right.read(1024*1024);assert first==second,'Actual memory/guard corpus byte disagreement'
    if not first:break
  for p,digest in held.items():assert sha(p)==digest,p
  result=dict(passed=True,candidate=desc(a.candidate),actual_selected_object=candidate['candidate_object'],actual_selected_object_linked_byte_exact=True,candidate_polled_IR=candidate['polled_IR'],component_trace_header=candidate['component_trace_header'],owned_sources={n:sha(source/'whole'/n)for n in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},native_ELF=desc(native),original_FDE=dict(bytes=5688,sha256=hashlib.sha256(blobs['FDE']).hexdigest()),original_table_page=desc(tables),reference=desc(reference),executable=desc(exe),native_output=desc(out/'actual-Bionic.stdout'),Windows_output=desc(out/'actual-Windows.stdout'),original_table_rows=16,original_unsigned_default_controls=12,original_guard_cases=28,actual_candidate_targets=12,variants_per_target=32,actual_boundary_cases=384,checks=int(match[1]),State_size=1200,State_align=16,Memory64_identity_and_contents_preserved=True,all32_SIMD_preserved=True,all32_GPR_SP_and_NZCV_compared_at_same_boundary=True,all_unrelated_State_bytes_preserved=True,fixture_memory_and_guards_compared=True,full_outer_ABI_return_claim=False,full_FDE_coverage_claim=False,original_game_execution=False,first_frame_claim=False,commands=commands,held_inputs=held,limits='Original guard slices execute all16 signed table rows and12 unsigned out-of-range defaults, with explicit generated fixture exit veneers at successor entry addresses. Separately original unmodified5688B FDE bytes run from each of12 original target entries until a genuine outgoing call; the actual unchanged candidate COFF runs matching target entries through current Runtime and guest-transfer guards. Three explicit fixture observers capture arguments/registers/memory and stop without executing callee semantics. Body maps never patch original FDE instructions. Interior-State setup is synthetic and does not establish wholeouterprologue/epilogue ABI or full5688B control-flow coverage. Memory hash covers entire64KB fixture arena except seed-input page, designated observer scratch256B, and snapshot output page; controlled original global/table pages are shared-identical inputs. Native fixture uses host Bionic setjmp solely for collector exit; Windows uses an explicit fixture transfer to registered root, leaving normal Runtime protocols intact.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-SWITCH-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
