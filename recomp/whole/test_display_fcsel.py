"""Small original refresh-wrapper/native FCSEL regression; no game execution."""
import argparse,hashlib,json,re,shutil,subprocess,sys,importlib.util
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
T=W/'fcsel-toolchain/7e3e484c165a1308-316ab92e11637e57'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False)
 B=W/'unity-display-fcsel-overlay1';C=read(B/'candidate.json');assert sha(B/'candidate.json')=='8911f23e4fa017fda6148a1883b176bc841749f73c6e2d900e75dee92d4dd838' and C['passed']
 S=O/'source/recomp';(S/'whole').mkdir(parents=True);(S/'windows').mkdir();owned=['display_fcsel_test.cpp','display_fcsel_native.S','display_fcsel_ref.c','test_display_fcsel.py']
 for n in owned:shutil.copy2(HERE/n,S/'whole'/n)
 frozen=W/'windows-first-frame-attempt1/sources/recomp'
 for rel in ['whole/runtime.h','whole/runtime.cpp','whole/guest_memory.h','whole/cooperative_poll.h','whole/cooperative_poll.cpp','windows/jni_host.h','windows/jni_host.cpp']:shutil.copy2(frozen/rel,S/rel)
 stubs='\n'.join('extern "C" Memory *sub_%x(State&s,addr_t pc,Memory*m){return active_runtime->Dispatch(s,pc,m);}'%h for h in C['external_guest_references']);(S/'whole/display_fcsel_stubs.h').write_text(stubs+'\n')
 inputs={str(x):sha(x) for x in S.rglob('*') if x.is_file()}
 for m in [C['input_pins'],C['artifacts']]:
  for x,h in m.items():assert sha(x)==h;inputs[x]=h
 inputs[str(B/'candidate.json')]=sha(B/'candidate.json')
 for x in (T/'include').rglob('*'):
  if x.is_file():inputs[str(x)]=sha(x)
 qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');R=qemu.parents[2];ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang')
 for x in [ndk,qemu,Path('/usr/lib/llvm-18/bin/clang'),Path('/mnt/c/mingw64/bin/g++.exe'),T/'aarch64.bc',T/'remill-lift']:inputs[str(x)]=sha(x)
 (O/'source-pin.json').write_text(json.dumps({'inputs':inputs,'candidate_sha256':sha(B/'candidate.json'),'owned_sources':{n:sha(HERE/n) for n in owned}},indent=2)+'\n')
 commands={}
 def run(cmd,label,timeout=240):
  commands[label]=list(map(str,cmd));print('STAGE',label,flush=True)
  with (O/(label+'.log')).open('w') as log:subprocess.run(commands[label],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 def wp(x):return subprocess.check_output(['wslpath','-m',str(Path(x).resolve())],text=True).strip()
 # Strict fixture-only syntax before execution; same full support sources compile below.
 for win in [False,True]:
  compiler='/mnt/c/mingw64/bin/g++.exe' if win else 'clang++-18';path=wp if win else str
  flags=['-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',path(T/'include'),'-I'+path(S/'whole'),'-I'+path(S/'windows')]
  run([compiler,*flags,'-Wall','-Wextra','-Werror','-fsyntax-only',path(S/'whole/display_fcsel_test.cpp')],('windows' if win else 'linux')+'-strict')
 # The independent ARM probe copies the literal original scalar FCSEL instruction.
 elf=W/'windows-first-frame-attempt1/native/libunity.so'
 with elf.open('rb') as f:
  e=ELFFile(f);seg=next(s for s in e.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=0xabccbc<s['p_vaddr']+s['p_filesz']);assert seg.data()[0xabccbc-seg['p_vaddr']:0xabccc0-seg['p_vaddr']]==bytes.fromhex('081c281e')
 obj=O/'native-probe.o';run([ndk,'-Wall','-Wextra','-Werror','-c',S/'whole/display_fcsel_native.S','-o',obj],'ndk-probe')
 helper=W/'fcsel-positive2/host/recomp/whole/test_fastaes.py';spec=importlib.util.spec_from_file_location('prior_helper',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.build_reference('clang-18',R,[S/'whole/display_fcsel_ref.c',obj],O/'arm-reference');run([qemu,O/'arm-reference'],'arm-reference');oracle=[x for x in (O/'arm-reference.log').read_text().splitlines() if x.startswith('ORACLE ')];assert len(oracle)==4
 # Execute the complete original wrapper in full128-definition objects, with real JNI float return.
 streams={};binaries={}
 for win in [False,True]:
  label='windows' if win else 'linux';D=O/label;D.mkdir();compiler='/mnt/c/mingw64/bin/g++.exe' if win else 'clang++-18';path=wp if win else str;flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',path(T/'include'),'-I'+path(S/'whole'),'-I'+path(S/'windows')];support=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','windows/jni_host.cpp','whole/display_fcsel_test.cpp']:
   out=D/(Path(name).stem+'.o');run([compiler,*flags,*(['-Wall','-Wextra','-Werror'] if 'test.cpp' in name else []),'-c',path(S/name),'-o',path(out)],label+'-'+Path(name).stem);support.append(out)
  for polled in [False,True]:
   kind='polled' if polled else 'raw';ir=B/('candidate-polled.ll' if polled else 'candidate-unpolled.ll');out=D/(kind+'.o')
   if win and polled:shutil.copy2(B/'candidate.polled.o',out)
   else:run(['clang-18','-target','x86_64-w64-windows-gnu' if win else 'x86_64-linux-gnu','-O2','-Wno-override-module','-c',ir,'-o',out],label+'-'+kind+'-object')
   binary=D/(kind+('.exe' if win else ''));run([compiler,*map(path,support),path(out),'-latomic','-pthread',*(['-static'] if win else []),'-o',path(binary)],label+'-'+kind+'-link');run([binary],label+'-'+kind+'-records');lines=[x for x in (O/(label+'-'+kind+'-records.log')).read_text().splitlines() if x.startswith('WRAPPER ')];assert len(lines)==4;assert [x.split()[1:4] for x in lines]==[x.split()[1:] for x in oracle];streams[label+'-'+kind]=lines;binaries[label+'-'+kind]={'path':str(binary),'sha256':sha(binary),'object_sha256':sha(out)}
 assert all(v==next(iter(streams.values())) for v in streams.values()),streams
 for x,h in inputs.items():assert sha(x)==h,x
 for n in owned:assert sha(HERE/n)==sha(S/'whole'/n)
 evidence={str(f.relative_to(O)):sha(f) for f in O.rglob('*') if f.is_file() and f.name!='acceptance.json'}
 result=dict(passed=True,candidate_path=str(B/'candidate.json'),candidate_sha256=sha(B/'candidate.json'),candidate_COFF_sha256=C['candidate_object']['sha256'],records_each=4,variants=list(streams),native_original_opcode='1e281c08',oracle=oracle,full_State_wrapper_streams=streams,binaries=binaries,inputs=inputs,commands=commands,evidence=evidence,limits='Small directed exact original FCSEL/native opcode oracle plus complete original refresh wrapper from actual candidate128defs. Real Host CallFloatMethodV120/0; explicit C++ current-env/assertion/exception-checker seams, not actual original helper bodies, wholegame or first-frame qualification. Prior58112matrix/pair reused by pin only.')
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('DISPLAY-FCSEL-QUALIFIED',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
