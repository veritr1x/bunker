"""Original940B function/real helpers: actual ARM versus repaired selected polled IR."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=['sshll_function_cases.h','sshll_function_ref.c','sshll_function_test.cpp','test_sshll_function.py']
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
  assert sha(a.candidate)==a.candidate_sha;pin(a.candidate);candidate=json.loads(a.candidate.read_text());assert candidate['passed']and candidate['global_index']==301 and candidate['target_head']=='0x708d13a8';assert candidate['raw_neighbors_byte_exact']and candidate['polled_neighbors_byte_exact']and candidate['native_neighbors_full_bytes_exact']
  for key in ['candidate_object','polled_ir','old_selected_object']:assert sha(candidate[key]['path'])==candidate[key]['sha256'];pin(candidate[key]['path'])
  pending=['whole/'+n for n in OWN]+['whole/runtime.cpp','whole/cooperative_poll.cpp'];root=HERE.parent;seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  native=W/'windows-first-frame-guest-transfer1/native/libunity.so';assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(native)
  from elftools.elf.elffile import ELFFile
  blobs={}
  with native.open('rb')as f:
   elf=ELFFile(f);segments=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD']
   for name,lo,n in [('body',0x8d13a8,940),('1008',0x8d1008,8),('1010',0x8d1010,16),('102c',0x8d102c,20),('1970',0x8d1970,24)]:
    segment=next(s for s in segments if s['p_vaddr']<=lo and lo+n<=s['p_vaddr']+s['p_filesz']);f.seek(segment['p_offset']+lo-segment['p_vaddr']);blobs[name]=f.read(n)
  assert blobs['body'][0x30:0x34]==bytes.fromhex('00a4200f');(source/'whole/sshll_function_native.h').write_text('\n'.join('static const unsigned char sshll_'+('original_body'if n=='body'else'helper_'+n)+'[]={'+','.join(map(str,b))+'};'for n,b in blobs.items())+'\n')
  text=Path(candidate['polled_ir']['path']).read_text();kept={}
  def extract(m):
   body=m[0];name=re.search(r'@([^ (]+)\(',body)[1];address=int(name[4:],16)if name.startswith('sub_')else 0
   if address in [0x708d1008,0x708d1010,0x708d102c,0x708d1970]or 0x708d13a8<=address<0x708d1754:kept[address]=dict(name=name,sha256=hashlib.sha256(body.encode()).hexdigest());return body
   header=body.split('\n',1)[0].rstrip().removesuffix('{').rstrip();return re.sub(r'^define\s+(?:internal\s+|private\s+)?','declare ',header)
  isolated=re.sub(r'^define [^\n]+\{\n.*?^}',extract,text,flags=re.M|re.S);assert set(kept)=={0x708d13a8,0x708d1008,0x708d1010,0x708d102c,0x708d1970};ir=out/'selected-extract.ll';ir.write_text(isolated);obj=out/'selected-extract.o';run(['clang++-18','--target=x86_64-w64-windows-gnu','-O2','-x','ir','-c',ir,'-o',obj],'extract-selected')
  symbols=run(['/usr/lib/llvm-18/bin/llvm-nm','--extern-only','--undefined-only','--format=posix',obj],'undefined-symbols').stdout.decode();undefined=sorted(set(re.findall(r'^(sub_[0-9a-f]+) U',symbols,re.M)));stub=out/'closed-unused-callouts.cpp';stub.write_text('#include "runtime.h"\n#include <cstdio>\n#include <cstdlib>\nextern "C" Memory*SSHLLFunctionImport(State&,addr_t,Memory*);\n'+''.join('extern "C" Memory*'+name+'(State&s,addr_t pc,Memory*m){'+('return SSHLLFunctionImport(s,pc,m);'if name=='sub_708ccfc8'else'(void)s;(void)m;std::fprintf(stderr,"unreached function callout '+name+' pc=%llx\\n",(unsigned long long)pc);std::_Exit(92);')+'}\n'for name in undefined))
  (out/'sshll_function_traces.h').write_text('\n'.join('extern "C" Memory*'+v['name']+'(State&,addr_t,Memory*);'for _,v in sorted(kept.items()))+'\nstatic const recomp::Trace sshll_function_traces[]={\n'+''.join('{'+hex(address)+','+v['name']+'},\n'for address,v in sorted(kept.items()))+'};\n')
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  reference=out/'original-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'whole/sshll_function_ref.c','-o',reference],'compile-Bionic');r=run([qemu,reference],'actual-Bionic',30);rows=[s for s in r.stdout.decode().splitlines()if s.startswith('SSHLL-FDE ')];assert len(rows)==256 and 'SSHLL-FDE-BIONIC-PASS'in r.stdout.decode()
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(out),'-I'+wp(source/'whole')];objects=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','whole/sshll_function_test.cpp']:
   output=out/(Path(name).stem+'.o');run([cxx,*flags,'-c',wp(source/name),'-o',wp(output)],'compile-'+output.stem);objects.append(output)
  exe=out/'selected-original-function.exe';run([cxx,*flags,*map(wp,objects),wp(obj),wp(stub),'-static','-pthread','-latomic','-o',wp(exe)],'link');r=run([exe],'actual-Windows',30);text=r.stdout.decode();assert[s for s in text.splitlines()if s.startswith('SSHLL-FDE ')]==rows;match=re.search(r'SSHLL-FDE-PASS checks=(\d+) cases=256 State=1200 Memory64=8',text);assert match,text
  for p,digest in held.items():assert sha(p)==digest,p
  result=dict(passed=True,candidate=desc(a.candidate),candidate_object=candidate['candidate_object'],candidate_polled_IR=candidate['polled_ir'],actual_function_body_sha256=kept[0x708d13a8]['sha256'],extracted_functions={hex(k):v for k,v in kept.items()},fixture_extracted_IR=desc(ir),fixture_extracted_object=desc(obj),fixture_unreached_callouts=desc(stub),owned_sources={n:sha(source/'whole'/n)for n in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},native_ELF=desc(native),original_native_bodies={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())for n,b in blobs.items()},reference=desc(reference),executable=desc(exe),actual_Bionic_rows=desc(out/'actual-Bionic.stdout'),actual_Windows_rows=desc(out/'actual-Windows.stdout'),checks=int(match[1]),cases=256,real_original_function_bytes=940,real_original_helper_bytes=68,actual_nonnull_Memory64=True,State1200=True,full_original_callee_saved_GPR_SP_LR_PC_checked=True,all_fixture_memory_changes_checked=True,commands=commands,held_inputs=held,limits='Actual original940B ARM function and four original helper bodies execute unmodified. One explicit TEST font-subsystem callback at708ccfc8 observes real signed spill and returns controlled nonzero status for a genuine early-error epilogue path. Windows runs exact extracted repaired polled IR plus current Runtime; isolated codegen is not exact selected COFF byte-identity. Other callouts are fail-closed and never reached. No full font loader/backend semantics, success/normal font rendering paths, original game or first-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('SSHLL-FUNCTION-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
