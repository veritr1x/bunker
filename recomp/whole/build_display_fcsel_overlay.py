"""Original display refresh wrapper with its natural inline common tail; exact sparse splice and unchanged poll pass."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, difflib

W=Path('/mnt/c/GitRepos/bunker/recomp/work')
L=Path('/home/user/bunker-recomp/recomp/work')
H=0x70acc13c
p=argparse.ArgumentParser();p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--lifter-sha',required=True);p.add_argument('--semantics-sha',required=True);a=p.parse_args()
B=W/'unity-display-fcsel-overlay1';N=L/'unity-display-fcsel-overlay1'
assert not B.exists() and not N.exists();B.mkdir();N.mkdir()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def funcs(t):return {int(m[1],16):m[0] for m in re.finditer(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}',t,re.M|re.S)}
def attrs(t):return dict(re.findall(r'^attributes #(\d+) = (.*)$',t,re.M))
def errors(ff):return sorted(hex(h) for h,b in ff.items() if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',b))
T=a.toolchain.resolve();assert a.lifter_sha=='7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126' and a.semantics_sha=='316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3';assert sha(T/'remill-lift')==a.lifter_sha and sha(T/'aarch64.bc')==a.semantics_sha
receipt=W/'game17-polled-cohort1/shard-00459.json';r=read(receipt)
oldpath=Path(r['source']['raw_ir']);old=oldpath.read_text();of=funcs(old);assert len(of)==128 and H in of and 0x70abcbe0 not in of and sha(oldpath)==r['source']['raw_ir_sha256']=='408de4d6517e81dedf7d98909c3cb8f824be006079e38811e1cc30fa4f177b97'
oldpolled=Path(r['instrument_command'][2]);oldobject=W/'game17-polled-cohort1/objects/shard-00459.o';assert sha(oldpolled)==r['instrumented_ir_sha256'];assert sha(oldobject)=='142b008353679001d265e7288cd2a37d16062b39eebf28f9cdfd246c6fa8d5c3'
base=L/'whole-unity-fmla-fmul-indexed';manifest=read(base/'manifest.json');assert 0x70abcbe0 not in manifest['traces'];image=base/'executable.bin';heads=N/'original-heads.txt';heads.write_text(''.join(hex(h)+'\n' for h in manifest['traces']));entry=N/'one-entry.txt';entry.write_text(hex(H)+'\n')
elf=W/'windows-first-frame-attempt1/native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
POLL=W/'poll-admission3/poll-instrument';assert sha(POLL)=='716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa'
qualified=W/'fcsel-positive2/acceptance.json';assert sha(qualified)=='b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b' and read(qualified)['passed'];pins={str(x):sha(x) for x in [qualified,receipt,oldpath,oldpolled,oldobject,base/'manifest.json',image,elf,T/'remill-lift',T/'aarch64.bc',POLL,Path(__file__)]}
plan=dict(status='Frozen original-refresh-wrapper lift plan (natural common-tail inline); not selected',target=hex(H),wrapper_FDE_end_exclusive='0x70acc1d0',inline_tail_start='0x70abcbe0',inline_tail_end_exclusive='0x70abccdc',original_ELF_sha256=sha(elf),global_index=459,definitions=128,neighbors=127,input_pins=pins)
(B/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');shutil.copy2(__file__,B/'executed-builder.py')
commands={}
def run(cmd,label):
 commands[label]=list(map(str,cmd));print('STAGE',label,flush=True)
 with (B/(label+'.log')).open('w') as f:subprocess.run(commands[label],stdout=f,stderr=subprocess.STDOUT,check=True)
run([T/'remill-lift','--arch','aarch64','--os','linux','--semantics_dir',T,'--bytes_file',image,'--address',manifest['image_start'],'--entry_addresses_file',entry,'--trace_heads_file',heads,'--ir_out',N/'single-target.raw.ll'],'one-entry-lift')
fresh=(N/'single-target.raw.ll').read_text();ff=funcs(fresh);assert set(ff)=={H} and not errors(ff);assert 'inttoptr' in of[H] and 'inttoptr' not in ff[H]
oa,fa=attrs(old),attrs(fresh);reverse={v:k for k,v in oa.items()}
body=re.sub(r' #(\d+)(?=[ {\n])',lambda x:' #'+reverse[fa[x[1]]],ff[H])
assert old.count(of[H])==1;candidate=old.replace(of[H],body);cf=funcs(candidate)
assert set(cf)==set(of) and all(cf[h]==of[h] for h in of if h!=H)
assert candidate.replace(body,of[H])==old and attrs(candidate)==oa
def state(t):
 ty=dict(re.findall(r'^(%[-A-Za-z$._0-9]+) = type (.*)$',t,re.M));seen=set();todo=['%struct.State']
 while todo:
  x=todo.pop()
  if x in seen:continue
  seen.add(x);todo.extend(re.findall(r'%[-A-Za-z$._0-9]+',ty[x]))
 return hashlib.sha256(('\n'.join(x+' = type '+ty[x] for x in sorted(seen))+'\n').encode()).hexdigest()
assert state(old)==state(fresh)=='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
decls=set(re.findall(r'^declare[^\n]*@([^ (]+)',old,re.M));refs=set(re.findall(r'@([^ (]+)\(',body))-{f'sub_{H:x}'};assert refs<=decls|{f'sub_{h:x}' for h in of},refs-decls
assert errors(cf)==errors(of)
(N/'candidate-unpolled.ll').write_text(candidate);(B/'refresh-raw.diff').write_text(''.join(difflib.unified_diff(of[H].splitlines(True),body.splitlines(True),fromfile='selected/refresh',tofile='FCSEL-fixed/refresh')))
run([POLL,N/'candidate-unpolled.ll',N/'candidate-polled.ll'],'instrument')
polled=(N/'candidate-polled.ll').read_text();pf=funcs(polled);opf=funcs(oldpolled.read_text())
assert set(pf)==set(opf)==set(of) and all(pf[h]==opf[h] for h in of if h!=H)
assert state(polled)==state(old) and errors(pf)==errors(of)
def coverage(fs):
 result={}
 for h,b in fs.items():
  req=len(re.findall(r'call i32 @__bunker_guest_poll_requested\(',b));sites=re.findall(r'call void @__bunker_guest_poll_slow\(ptr [^,]+, i64 (\d+), i64 (\d+), i64 ([^,)]+)\)',b)
  assert req==len(sites)>=1 and all(int(x[0])==h for x in sites) and [int(x[1]) for x in sites]==list(range(len(sites)))
  result[hex(h)]=dict(entry=1,cycle=len(sites)-1,total=len(sites))
 return result
cov,oldcov=coverage(pf),coverage(opf);assert all(cov[hex(h)]==oldcov[hex(h)] for h in of if h!=H)
clang=Path(shutil.which('clang-18')).resolve();nm=Path(shutil.which('llvm-nm-18')).resolve();dump=Path(shutil.which('llvm-objdump-18')).resolve()
run([clang,'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',N/'candidate-polled.ll','-o',N/'candidate.polled.o'],'compile')
symbols=subprocess.check_output([nm,'--format=posix','--extern-only',N/'candidate.polled.o'],text=True);(B/'symbols.txt').write_text(symbols)
defs=sorted(int(x,16) for x in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M));ext=sorted(int(x,16) for x in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M));selected=W/'windows-first-frame-attempt1/game_traces.h';selectedheads={int(x,16) for x in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',selected.read_text())}
assert len(selectedheads)==456689 and defs==sorted(of) and not(set(ext)-selectedheads)
native={}
for label,obj in [('old',oldobject),('candidate',N/'candidate.polled.o')]:
 text=subprocess.check_output([dump,'-dr',obj],text=True);(B/(label+'-disassembly.txt')).write_text(text);functions={}
 for z in re.finditer(r'(?m)^[0-9a-f]+ <(sub_[0-9a-f]+)>:\n(.*?)(?=^[0-9a-f]+ <|\Z)',text,re.S):
  bytes_=re.findall(r'^\s+[0-9a-f]+:\s+((?:[0-9a-f]{2} )+)',z[2],re.M);rel=re.findall(r'IMAGE_REL_AMD64_REL32\s+(\S+)',z[2]);functions[z[1]]=dict(bytes=''.join(''.join(x.split()) for x in bytes_),relocations=rel)
 assert set(functions)=={f'sub_{h:x}' for h in of};native[label]=functions
changed=[n for n in native['old'] if native['old'][n]!=native['candidate'][n]]
for n,h in pins.items():assert sha(n)==h,n
for n in ['single-target.raw.ll','candidate-unpolled.ll','candidate-polled.ll','candidate.polled.o']:shutil.copy2(N/n,B/n)
pins.update({str(x):sha(x) for x in [clang,nm,dump,selected,B/'plan.json']})
result=dict(passed=True,status='Candidate ONLY; targeted FCSEL/native wrapper qualification pending; unselected',target_head=hex(H),wrapper_FDE_end_exclusive='0x70acc1d0',inline_tail_start='0x70abcbe0',inline_tail_end_exclusive='0x70abccdc',global_index=459,definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,all_other_raw_module_bytes_unchanged=True,State_type_closure_sha256=state(old),State_size=1200,State_align=16,old_selected_object=dict(path=str(oldobject),sha256=sha(oldobject)),candidate_object=dict(path=str(B/'candidate.polled.o'),sha256=sha(B/'candidate.polled.o')),unsupported_heads=errors(cf),external_guest_references=ext,all_direct_refs_closed=True,old_poll_coverage=oldcov,all_poll_coverage=cov,native_changed_symbols=changed,native_functions=native,commands=commands,input_pins=pins,artifacts={str(f):sha(f) for root in [B,N] for f in root.iterdir() if f.is_file()},limits='Exactly one original wrapper entry lifted from unmodified Unity image; preserves original tail B to common70abcbe0 inline because common is not a selected head; no whole-shard/global toolchain refresh or selected-game/backend/profile claim. Unchanged IR does not assume unchanged native optimization; changed symbols recorded.')
(B/'candidate.json').write_text(json.dumps(result,indent=2)+'\n');print('DISPLAY-FCSEL-CANDIDATE',sha(B/'candidate.json'),'native-changes',changed,flush=True)
