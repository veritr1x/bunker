"""Actual repaired288B Unity function versus original ARM+Bionic modff, finite normal ABI."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=['frinta_function_cases.h','frinta_function_ref.c','frinta_function_ref.S','frinta_function_test.cpp','test_frinta_function.py']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--candidate-sha',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';held={};commands=[]
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stderr.decode(errors='replace')[-5000:])
  return r
 try:
  assert sha(a.candidate)==a.candidate_sha;pin(a.candidate);packet=json.loads(a.candidate.read_text());assert packet['passed']is True
  candidate=next(row for row in packet['target_objects']if row['global_index']==289);assert int(candidate['target_head'],16)==0x70828b78
  for name in ['candidate_object','raw_ir','polled_ir','old_object']:assert sha(candidate[name]['path'])==candidate[name]['sha256'];pin(candidate[name]['path'])
  selected=Path(candidate['candidate_object']['path']);family=W/'frinta-qualification1/acceptance.json';assert sha(family)=='cb9960c0e2735683217584594daf675c924cb01437926f578ddde97b037295f6';pin(family)
  pending=['whole/'+name for name in OWN]+['whole/runtime.cpp','whole/cooperative_poll.cpp'];root=HERE.parent;seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  native=W/'windows-first-frame-guest-transfer1/native/libunity.so';assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(native)
  from elftools.elf.elffile import ELFFile
  with native.open('rb')as stream:
   elf=ELFFile(stream);segment=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=0x828b78<0x828c98<=s['p_vaddr']+s['p_filesz']);body=segment.data()[0x828b78-segment['p_vaddr']:0x828c98-segment['p_vaddr']]
  assert len(body)==288 and body[0xac:0xb0]==bytes.fromhex('6340261e');(source/'whole/frinta_function_native.h').write_text('static const unsigned char ff_original_body[]={'+','.join(map(str,body))+'};\n')
  symbols=run(['/usr/lib/llvm-18/bin/llvm-nm','--extern-only','--format=posix',selected],'actual-selected-symbols').stdout.decode();assert re.search(r'^sub_70828b78 T',symbols,re.M);undefined=sorted(set(re.findall(r'^(sub_[0-9a-f]+) U',symbols,re.M)));assert'sub_700b8f40'in undefined
  stub=out/'closed-unreached-callouts.cpp';stub.write_text('#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\nextern "C" Memory*FRINTAFunctionImport(State&,addr_t,Memory*);\n'+''.join('extern "C" Memory*'+name+'(State&s,addr_t pc,Memory*m){'+('return FRINTAFunctionImport(s,pc,m);'if name=='sub_700b8f40'else'(void)s;(void)m;std::fprintf(stderr,"unexpected original callout '+name+' pc=%llx\\n",(unsigned long long)pc);std::_Exit(92);')+'}\n'for name in undefined))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  native_data=out/'native-data.bin';Windows_data=out/'Windows-data.bin';reference=out/'actual-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-fno-stack-protector','-fno-builtin-modff','-Wall','-Wextra','-Werror',source/'whole/frinta_function_ref.c',source/'whole/frinta_function_ref.S','-lm','-o',reference],'compile-Bionic')
  disasm=run(['/usr/lib/llvm-18/bin/llvm-objdump','--disassemble-symbols=observed_modff',reference],'native-modff-call').stdout.decode();assert re.search(r'\bbl\s+[^\n]*<modff>',disasm),'Native fixture must call actual statically linked Bionic modff'
  r=run([qemu,reference,native_data],'actual-Bionic',60);lines=r.stdout.decode().splitlines();expected=[line for line in lines if line.startswith('FRINTA-FUNCTION id=')];assert len(expected)==384 and'FRINTA-FUNCTION-BIONIC-PASS cases=384 body=288 genuine_modff=1'in lines
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(source/'whole')];objects=[]
  for name in ['runtime.cpp','cooperative_poll.cpp','frinta_function_test.cpp']:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name=='frinta_function_test.cpp'else[]),'-c',wp(source/'whole'/name),'-o',wp(obj)],'compile-'+Path(name).stem);objects.append(obj)
  exe=out/'actual-selected-function.exe';run([cxx,*flags,*map(wp,objects),wp(selected),wp(stub),'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');r=run([exe,wp(Windows_data)],'actual-Windows',60);text=r.stdout.decode();actual=[line for line in text.splitlines()if line.startswith('FRINTA-FUNCTION id=')];assert actual==expected,'OriginalBionic/Windows fullfunction value/status/callback disagreement';match=re.search(r'FRINTA-FUNCTION-WINDOWS-PASS checks=(\d+) cases=384 State=1200 Memory64=8',text);assert match,text[-1000:]
  assert native_data.stat().st_size==Windows_data.stat().st_size==384*64 and native_data.read_bytes()==Windows_data.read_bytes()
  for p,digest in held.items():assert sha(p)==digest,p
  result=dict(passed=True,candidate=desc(a.candidate),candidate_global_index=289,actual_selected_object=candidate['candidate_object'],actual_selected_object_linked_byte_exact=True,candidate_polled_IR=candidate['polled_ir'],original_selected_object=candidate['old_object'],primitive_family_qualification=desc(family),owned_sources={name:sha(source/'whole'/name)for name in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},native_ELF=desc(native),original_function_bytes=288,original_function_body_sha256=hashlib.sha256(body).hexdigest(),reached_instruction_word='1e264063',reached_instruction_PC='0x70828c24',cases=384,executions_per_platform=384,checks=int(match[1]),records_exact=True,real_Bionic_modff=True,Bionic_modff_actual_call_disassembly=desc(out/'native-modff-call.stdout'),Windows_tracked_modf_equivalent_to_production_bridge=True,production_bridge_reference='windows/libc.cpp modff uses std::modf(float,float*) and tracked guest write; fixture matches this scoped callback behavior',full_normal_ABI_checked=True,callee_saved_GPR19_through29=True,callee_saved_D8_through15=True,normal_SP_LR_PC_return_checked=True,exact_binary_function_cases_FPSR_zero=True,no_new_IXC_checked=True,Memory64_preserved=True,State_size=1200,State_align=16,unrelated_State_and_padding_preserved=True,output_write_footprint_bytes=8,all_output_guards_preserved=True,data_corpus=dict(native=desc(native_data),Windows=desc(Windows_data),all_bytes_equal=True,bytes_per_case=64,cases=384),reference=desc(reference),executable=desc(exe),native_output=desc(out/'actual-Bionic.stdout'),Windows_output=desc(out/'actual-Windows.stdout'),commands=commands,held_inputs=held,original_game_execution=False,first_frame_claim=False,scope='Finite original288B normal-entry and real-return function gate; both flag bits, sign, six binary-exact progress inputs, two ranges, two quantization values and two offsets. Native executes exact unmodified original ARM bytes and genuine Bionic modff; Windows executes entire byteexact selected candidate COFF plus current Runtime and one explicit std::modf/trackedwrite callback. All unrelated guest imports fail closed. Complete Libc/backend, nonfinite/fullfunctionFPCR modes, original game, frame or gameplay not claimed; scalar special-value/mode coverage is supplied separately by primitive family gate.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FRINTA-FUNCTION-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
