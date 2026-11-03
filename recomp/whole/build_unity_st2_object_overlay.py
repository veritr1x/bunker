"""Original full ST2 object initializer; exact sparse splice and unchanged poll pass."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, difflib

W=Path('/mnt/c/GitRepos/bunker/recomp/work')
L=Path('/home/user/bunker-recomp/recomp/work')
H=0x707bb458
p=argparse.ArgumentParser();p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--lifter-sha',required=True);p.add_argument('--semantics-sha',required=True);p.add_argument('--qualification',type=Path,required=True);p.add_argument('--qualification-sha',required=True);a=p.parse_args()
B=W/'unity-st2-object-overlay1';N=L/'unity-st2-object-overlay1'
assert not B.exists() and not N.exists();B.mkdir();N.mkdir()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def funcs(t):return {int(m[1],16):m[0] for m in re.finditer(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}',t,re.M|re.S)}
def attrs(t):return dict(re.findall(r'^attributes #(\d+) = (.*)$',t,re.M))
def errors(ff):return sorted(hex(h) for h,b in ff.items() if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',b))
T=a.toolchain.resolve();assert sha(T/'remill-lift')==a.lifter_sha and sha(T/'aarch64.bc')==a.semantics_sha
receipt=W/'game17-polled-cohort1/shard-00270.json';r=read(receipt)
oldpath=Path(r['source']['raw_ir']);old=oldpath.read_text();of=funcs(old);assert len(of)==128 and H in of and sha(oldpath)==r['source']['raw_ir_sha256']=='2af0fb3da5b7d55ca653b0f2d77c3418376e9c8f5f693e66e56573a494611253'
oldpolled=Path(r['instrument_command'][2]);oldobject=W/'game17-polled-cohort1/objects/shard-00270.o';assert sha(oldpolled)==r['instrumented_ir_sha256'];assert sha(oldobject)=='5504d089df69da73b12002d7e84dc9e9ecc2cac88a8e0d79b7b12df7d1089d47'
base=L/'whole-unity-fmla-fmul-indexed';manifest=read(base/'manifest.json');image=base/'executable.bin';heads=N/'original-heads.txt';heads.write_text(''.join(hex(h)+'\n' for h in manifest['traces']));entry=N/'one-entry.txt';entry.write_text(hex(H)+'\n')
elf=W/'windows-first-frame-fcsel2/native/libunity.so';assert sha(elf)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
POLL=W/'poll-admission3/poll-instrument';assert sha(POLL)=='716410d1dc2498041e90804bcee9ebe632263e82ad32ba827adfb09f1c85d7aa'
qualified=a.qualification;assert sha(qualified)==a.qualification_sha and read(qualified)['passed'];pins={str(x):sha(x) for x in [qualified,receipt,oldpath,oldpolled,oldobject,base/'manifest.json',image,elf,T/'remill-lift',T/'aarch64.bc',POLL,Path(__file__)]}
plan=dict(status='Frozen original ST2 object initializer complete-function lift plan; not selected',target=hex(H),original_FDE_end_exclusive='0x707bb55c',original_ELF_sha256=sha(elf),global_index=270,definitions=128,neighbors=127,input_pins=pins)
(B/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');shutil.copy2(__file__,B/'executed-builder.py')
commands={}
def run(cmd,label):
 commands[label]=list(map(str,cmd));print('STAGE',label,flush=True)
 with (B/(label+'.log')).open('w') as f:subprocess.run(commands[label],stdout=f,stderr=subprocess.STDOUT,check=True)
run([T/'remill-lift','--arch','aarch64','--os','linux','--semantics_dir',T,'--bytes_file',image,'--address',manifest['image_start'],'--entry_addresses_file',entry,'--trace_heads_file',heads,'--ir_out',N/'single-target.raw.ll'],'one-entry-lift')
fresh=(N/'single-target.raw.ll').read_text();ff=funcs(fresh);assert set(ff)=={H} and not errors(ff);assert errors(of).count(hex(H))==1
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
assert errors(cf)==[h for h in errors(of) if h!=hex(H)]
(N/'candidate-unpolled.ll').write_text(candidate);(B/'object-raw.diff').write_text(''.join(difflib.unified_diff(of[H].splitlines(True),body.splitlines(True),fromfile='selected/ST2object',tofile='ST2-supported/object')))
run([POLL,N/'candidate-unpolled.ll',N/'candidate-polled.ll'],'instrument')
polled=(N/'candidate-polled.ll').read_text();pf=funcs(polled);opf=funcs(oldpolled.read_text())
assert set(pf)==set(opf)==set(of) and all(pf[h]==opf[h] for h in of if h!=H)
assert state(polled)==state(old) and errors(pf)==[h for h in errors(of) if h!=hex(H)]
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
defs=sorted(int(x,16) for x in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M));ext=sorted(int(x,16) for x in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M));selected=W/'windows-first-frame-fcsel2/game_traces.h';selectedheads={int(x,16) for x in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',selected.read_text())}
assert len(selectedheads)==456689 and defs==sorted(of) and not(set(ext)-selectedheads)
native={}
for label,obj in [('old',oldobject),('candidate',N/'candidate.polled.o')]:
 text=subprocess.check_output([dump,'-dr',obj],text=True);(B/(label+'-disassembly.txt')).write_text(text);functions={}
 for z in re.finditer(r'(?m)^[0-9a-f]+ <(sub_[0-9a-f]+)>:\n(.*?)(?=^[0-9a-f]+ <|\Z)',text,re.S):
  bytes_=re.findall(r'^\s+[0-9a-f]+:\s+((?:[0-9a-f]{2} )+)',z[2],re.M);rel=re.findall(r'IMAGE_REL_AMD64_REL32\s+(\S+)',z[2]);functions[z[1]]=dict(bytes=''.join(''.join(x.split()) for x in bytes_),relocations=rel)
 assert set(functions)=={f'sub_{h:x}' for h in of};native[label]=functions
changed=[n for n in native['old'] if native['old'][n]!=native['candidate'][n]];assert changed==[f'sub_{H:x}']
for n,h in pins.items():assert sha(n)==h,n
for n in ['single-target.raw.ll','candidate-unpolled.ll','candidate-polled.ll','candidate.polled.o']:shutil.copy2(N/n,B/n)
pins.update({str(x):sha(x) for x in [clang,nm,dump,selected,B/'plan.json']})
result=dict(passed=True,status='Candidate ONLY; original ARM/fullfunction object qualification pending; unselected',target_head=hex(H),original_FDE_end_exclusive='0x707bb55c',global_index=270,definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,all_other_raw_module_bytes_unchanged=True,State_type_closure_sha256=state(old),State_size=1200,State_align=16,old_selected_object=dict(path=str(oldobject),sha256=sha(oldobject)),candidate_object=dict(path=str(B/'candidate.polled.o'),sha256=sha(B/'candidate.polled.o')),unsupported_heads=errors(cf),external_guest_references=ext,all_direct_refs_closed=True,old_poll_coverage=oldcov,all_poll_coverage=cov,native_changed_symbols=changed,native_functions=native,commands=commands,input_pins=pins,artifacts={str(f):sha(f) for root in [B,N] for f in root.iterdir() if f.is_file()},limits='Exactly one full original ST2 object initializer lifted from unchanged Unity image; only its prior unsupported head removed; other unsupported heads preserved; no whole-shard/global toolchain refresh or selected-game/backend/profile claim. Unchanged IR does not assume unchanged native optimization; changed symbols recorded.')
(B/'candidate.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-ST2-OBJECT-CANDIDATE',sha(B/'candidate.json'),'native-changes',changed,flush=True)
