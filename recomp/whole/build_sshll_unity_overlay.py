"""One original Unity SSHLL FDE; preserve the other 127 selected shard bodies.

Default is a read-only dry run. Candidate compilation is not selection and does
not substitute for independent instruction and original-function qualification.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,traceback
from elftools.elf.elffile import ELFFile
W=Path('/mnt/c/GitRepos/bunker/recomp/work');L=Path('/home/user/bunker-recomp/recomp/work')
HEAD=0x708d13a8;END=0x708d1754;INDEX=301
FRONTIER_SHA='34f3df53f9b277880c8861728d69639409bd1f2feb56bcaab477273b1e04eba2'
TOOLS_SHA='968e994489732dad02e501e0f10396cff5029e58794a7956de0ff7afc4b068d0'
BASE_SHA='37c2c4dfa49c285e545b7ed041ea07d20ee4b2c7bcb6e1026414eda199bc2e1b'
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):assert not p.exists(),p;p.write_text(json.dumps(v,indent=2)+'\n')
def pin(row):assert sha(row['path'])==row['sha256'],row['path']
def remap_attrs(text,mapping):return re.sub(r' #(\d+)(?=[ {\n])',lambda m:' #'+mapping[m[1]],text)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=W/'sshll-unity-fde-overlay1');ap.add_argument('--native-out',type=Path,default=L/'sshll-unity-fde-overlay1');ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 frontier_path=W/'runtime15-sshll-frontier1/acceptance.json';tool_path=W/'sshll-toolchain1/tools-ready.json'
 assert sha(frontier_path)==FRONTIER_SHA and sha(tool_path)==TOOLS_SHA
 frontier=read(frontier_path);tools=read(tool_path);parent_path=Path(frontier['selected_build']['path']);pin(frontier['selected_build']);parent=read(parent_path)
 assert len(parent['objects'])==4658 and parent['trace_heads']==595528 and parent['objects'][INDEX]==frontier['selected_object']
 if not a.execute:print(json.dumps(dict(dry_run=True,target=hex(HEAD),bytes=END-HEAD,replace_index=INDEX,preserved_other_objects=4657,heads=595528,tool_candidate_only=True)));return
 assert not a.out.exists()and not a.native_out.exists();a.out.mkdir();a.native_out.mkdir();commands=[];held={}
 def hold(p):p=Path(p);held[str(p)]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));save_path=a.out/'commands.json';save_path.write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(a.out/(label+'.log')).open('x')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  base_path=Path(__file__).with_name('build_unity_st2_constructor_overlay.py');assert sha(base_path)==BASE_SHA;hold(base_path)
  sp=importlib.util.spec_from_file_location('qualified_coff_projection',base_path);base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
  for p in [Path(__file__),frontier_path,tool_path,parent_path]:hold(p)
  for key in ['lifter','semantics']:pin(tools[key]);hold(tools[key]['path'])
  producer=read(W/'neg4s1-il2cpp-entry-preparation1/plan.json')
  for name in ['poll','compiler','nm','llvm_opt','optimized_auditor']:pin(producer[name]);hold(producer[name]['path'])
  old_raw=Path(frontier['guarded_raw_IR']['path']);old_poll=Path(frontier['guarded_polled_IR']['path']);old_obj=Path(parent['objects'][INDEX]['path'])
  for row in [frontier['guarded_raw_IR'],frontier['guarded_polled_IR'],parent['objects'][INDEX],frontier['original_ELF']]:pin(row);hold(row['path'])
  old=old_raw.read_text();oldp=old_poll.read_text();of=base.functions(old);opf=base.functions(oldp);assert len(of)==len(opf)==128 and set(of)==set(opf)and base.errors(of)==[hex(HEAD)]and base.state(old)==STATE
  header=Path(parent['trace_header']['path']);pin(parent['trace_header']);hold(header);heads=sorted({int(x,16)for x in re.findall(r'^extern "C" Memory \*sub_([0-9a-f]+)\(',header.read_text(),re.M)});assert len(heads)==595528
  head_file=a.native_out/'all-heads.txt';head_file.write_text(''.join(hex(h)+'\n'for h in heads))
  with Path(frontier['original_ELF']['path']).open('rb')as f:
   elf=ELFFile(f);seg=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=HEAD-0x70000000 and END-0x70000000<=s['p_vaddr']+s['p_filesz']);f.seek(seg['p_offset']+HEAD-0x70000000-seg['p_vaddr']);raw=f.read(END-HEAD)
  assert hashlib.sha256(raw).hexdigest()==frontier['original_FDE']['sha256'];image=a.native_out/'original-fde.bin';image.write_bytes(raw)
  fresh_path=a.native_out/'single-target.raw.ll';stats=a.native_out/'lowering-stats.json'
  run([tools['lifter']['path'],'--arch','aarch64','--os','linux','--semantics_dir',str(Path(tools['semantics']['path']).parent),'--bytes_file',image,'--address',str(HEAD),'--entry_address',str(HEAD),'--trace_heads_file',head_file,'--guest_call_transfer=true','--guest_call_transfer_stats_out',stats,'--ir_out',fresh_path],'one-entry-lift')
  fresh=fresh_path.read_text();ff=base.functions(fresh);assert set(ff)=={HEAD}and not base.errors(ff)and base.state(fresh)==STATE
  lowering=read(stats);assert lowering['passed']and lowering['State_bytes']==1200 and lowering['SP_offset']==1040 and lowering['PC_offset']==1056
  oa=base.attrs(old);fa=base.attrs(fresh);reverse={v:k for k,v in oa.items()};attr_map={};extra_attrs=[];next_attr=max(map(int,oa))+1
  for key,value in fa.items():
   if value not in reverse:reverse[value]=str(next_attr);extra_attrs.append('attributes #'+str(next_attr)+' = '+value+'\n');next_attr+=1
   attr_map[key]=reverse[value]
  body=remap_attrs(ff[HEAD],attr_map)
  old_md={int(m[1]):m[2]for m in re.finditer(r'^!(\d+) = (.*)$',old,re.M)};fresh_md={int(m[1]):m[2]for m in re.finditer(r'^!(\d+) = (.*)$',fresh,re.M)};offset=max(old_md,default=-1)+1
  md_map={str(k):str(k+offset)for k in fresh_md};map_md=lambda text:re.sub(r'!(\d+)\b',lambda m:'!'+md_map[m[1]],text)
  body=map_md(body);extra_md=['!'+str(k+offset)+' = '+map_md(v)+'\n'for k,v in fresh_md.items()]
  ot=base.types(old);ft=base.types(fresh)
  for name in set(re.findall(r'%[-A-Za-z$._0-9]+',body))&set(ft):assert ot.get(name)==ft[name],name
  refs=set(re.findall(r'@([-A-Za-z$._0-9]+)',body));old_defined=set(re.findall(r'^define[^\n]*@([^ (]+)',old,re.M));old_decls={m[1]:m[0]for m in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',old,re.M)};fresh_decls={m[1]:m[0]for m in re.finditer(r'^declare[^\n]*@([^ (]+)[^\n]*',fresh,re.M)};globals=set(re.findall(r'^@([^ =]+)',old,re.M));extra_decls=[]
  for name in sorted(refs-old_defined-set(old_decls)-globals):assert name in fresh_decls,name;extra_decls.append(remap_attrs(fresh_decls[name],attr_map)+'\n')
  assert all(int(n[4:],16)in heads for n in refs if n.startswith('sub_'))
  candidate=old.replace(of[HEAD],body);old_named=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',old,re.M);fresh_named=re.search(r'^!bunker\.guest\.call\.lowering = !\{(.*?)\}$',fresh,re.M);named_before=named_after=None
  if fresh_named:
   assert old_named;named_before=old_named[0];named_after='!bunker.guest.call.lowering = !{'+old_named[1]+(', 'if old_named[1]else'')+map_md(fresh_named[1])+'}';candidate=candidate.replace(named_before,named_after)
  suffix='\n'+''.join(extra_decls+extra_attrs+extra_md);candidate+=suffix
  inverse=candidate[:-len(suffix)];inverse=inverse.replace(named_after,named_before)if named_after else inverse;inverse=inverse.replace(body,of[HEAD]);assert inverse==old
  cf=base.functions(candidate);assert set(cf)==set(of)and all(cf[h]==of[h]for h in of if h!=HEAD)and base.errors(cf)==[]and base.state(candidate)==STATE
  raw_path=a.native_out/'candidate-unpolled.ll';raw_path.write_text(candidate);polled=a.native_out/'candidate-polled.ll'
  run([producer['poll']['path'],raw_path,polled],'instrument');pf=base.functions(polled.read_text());assert set(pf)==set(opf)and all(pf[h]==opf[h]for h in opf if h!=HEAD)
  old_internal=base.internal_functions(oldp);new_internal=base.internal_functions(polled.read_text());assert old_internal==new_internal
  coverage=base.coverage(pf);old_coverage=base.coverage(opf);assert all(coverage[hex(h)]==old_coverage[hex(h)]for h in of if h!=HEAD)
  run([producer['llvm_opt']['path'],'-passes=verify','-disable-output',polled],'verify')
  optimized=a.native_out/'optimized.ll';audit=a.native_out/'optimized-guard-audit.json'
  run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-S','-emit-llvm',polled,'-o',optimized],'optimized-IR')
  run([producer['optimized_auditor']['path'],optimized,audit],'audit-guards');audited=read(audit);assert audited['passed']
  obj=a.native_out/'candidate.polled.o';run([producer['compiler']['path'],'-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',polled,'-o',obj],'compile')
  symbols=subprocess.check_output([producer['nm']['path'],'--format=posix','--extern-only',obj],text=True);definitions={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M)};direct={int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M)};assert definitions==set(of)and direct<=set(heads)
  native={};tables={}
  for name,path in [('old',old_obj),('candidate',obj)]:native[name],asm,tables[name]=base.coff_projection('/usr/lib/llvm-18/bin/llvm-objdump',path);(a.out/(name+'-disassembly.txt')).write_text(asm)
  changed=[h for h in native['old']if native['old'][h]!=native['candidate'][h]];assert changed==[hex(HEAD)],changed
  for name,path in [('single-target.raw.ll',fresh_path),('candidate-unpolled.ll',raw_path),('candidate-polled.ll',polled),('candidate.polled.o',obj),('optimized-guard-audit.json',audit),('lowering-stats.json',stats)]:shutil.copyfile(path,a.out/name)
  new_objects=list(parent['objects']);new_objects[INDEX]=desc(a.out/'candidate.polled.o');assert all(new_objects[i]==parent['objects'][i]for i in range(4658)if i!=INDEX);save(a.out/'object-manifest.json',new_objects)
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,selected=False,component_qualification_pending=True,target_head=hex(HEAD),original_FDE_end_exclusive=hex(END),global_index=INDEX,parent_manifest=desc(parent_path),frontier=desc(frontier_path),tool_candidate=desc(tool_path),old_selected_object=desc(old_obj),candidate_object=desc(a.out/'candidate.polled.o'),raw_ir=desc(a.out/'candidate-unpolled.ll'),polled_ir=desc(a.out/'candidate-polled.ll'),one_entry_raw_ir=desc(a.out/'single-target.raw.ll'),object_manifest=desc(a.out/'object-manifest.json'),definitions=128,raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,native_neighbors_full_bytes_exact=127,native_changed_symbols=changed,old_internal_helpers_byte_exact=True,all_other_raw_module_bytes_unchanged_by_exact_inverse=True,added_declarations=extra_decls,added_attributes=extra_attrs,added_metadata_records=len(extra_md),named_metadata_only_appended=True,State_type_closure_sha256=STATE,State_size=1200,State_align=16,old_poll_coverage=old_coverage,all_poll_coverage=coverage,optimized_guard_audit=desc(a.out/'optimized-guard-audit.json'),observed_guard_audit=audited,lowering_stats=lowering,external_guest_references=sorted(direct),all_direct_refs_closed=True,guest_objects=4658,other_guest_objects_exact=4657,trace_heads=595528,all_four_generated_headers_unchanged=True,original_instruction_bytes_unchanged=True,held_inputs=held,commands=commands,limits='Candidate static codegen only. Full family/decode and original-function gates are separate requirements before selection. No full Windows host build, original game run, frame or gameplay claim.')
  save(a.out/'acceptance.json',result);print('SSHLL-FDE-CANDIDATE',sha(a.out/'acceptance.json'),sha(obj),flush=True)
 except BaseException as ex:save(a.out/'failure.json',dict(passed=False,error=str(ex),commands=commands,held_inputs=held));raise
if __name__=='__main__':main()
