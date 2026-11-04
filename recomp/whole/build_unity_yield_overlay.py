"""One original YIELD hint at the original contention branch; exact current-v14 module splice."""
import argparse,difflib,hashlib,importlib.util,json,re,shutil,subprocess,traceback
from pathlib import Path
HEAD=0x703835a0
END=0x70383620
STATE='26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,j):Path(p).write_text(json.dumps(j,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--builder-sha256',required=True);a=p.parse_args();assert sha(__file__)==a.builder_sha256 and sha(a.plan)==a.plan_sha256
 plan=read(a.plan);B=Path(plan['output']);N=Path(plan['native_output']);assert B.exists()and not N.exists()and not(B/'candidate.json').exists()and not(B/'failure.json').exists();N.mkdir();commands={}
 try:
  for n,h in plan['input_pins'].items():assert sha(n)==h,n
  assert sha(plan['base_builder']['path'])==plan['base_builder']['sha256']
  spec=importlib.util.spec_from_file_location('strict_coff_base',plan['base_builder']['path']);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
  def run(cmd,label):
   commands[label]=list(map(str,cmd));print('STAGE',label,flush=True)
   with(B/(label+'.log')).open('x')as f:subprocess.run(commands[label],stdout=f,stderr=subprocess.STDOUT,check=True)
  old=Path(plan['old_raw_ir']['path']).read_text();oldf=base.functions(old);assert len(oldf)==128 and hex(HEAD) in base.errors(oldf)and base.state(old)==STATE
  run(plan['lift_command'],'one-entry-lift');fresh=(N/'single-target.raw.ll').read_text();freshf=base.functions(fresh);assert set(freshf)=={HEAD}and not base.errors(freshf)and base.state(fresh)==STATE
  oa,fa=base.attrs(old),base.attrs(fresh);reverse={v:k for k,v in oa.items()};body=re.sub(r' #(\d+)(?=[ {\n])',lambda m:' #'+reverse[fa[m[1]]],freshf[HEAD]);assert not re.search(r'!\d+',body),'numeric metadata mapping required: HOLD'
  ot,ft=base.types(old),base.types(fresh)
  for name in set(re.findall(r'%[-A-Za-z$._0-9]+',body))&set(ft):assert ot.get(name)==ft[name]
  decls=set(re.findall(r'^declare[^\n]*@([^ (]+)',old,re.M));refs=set(re.findall(r'@([^ (]+)\(',body))-{f'sub_{HEAD:x}'};assert refs<=decls|{f'sub_{h:x}'for h in oldf},refs-decls
  assert old.count(oldf[HEAD])==1;candidate=old.replace(oldf[HEAD],body);cf=base.functions(candidate)
  assert set(cf)==set(oldf)and all(cf[h]==oldf[h]for h in oldf if h!=HEAD)
  assert candidate.replace(body,oldf[HEAD])==old and base.attrs(candidate)==oa and base.state(candidate)==STATE and base.errors(cf)==sorted(set(base.errors(oldf))-{hex(HEAD)})
  (N/'candidate-unpolled.ll').write_text(candidate);(B/'target.diff').write_text(''.join(difflib.unified_diff(oldf[HEAD].splitlines(True),body.splitlines(True),fromfile='current-v14/703835a0',tofile='current-YIELD/703835a0')))
  run(plan['poll_command'],'instrument');polled=(N/'candidate-polled.ll').read_text();pf=base.functions(polled);old_polled=Path(plan['old_polled_ir']['path']).read_text();opf=base.functions(old_polled)
  assert set(pf)==set(opf)==set(oldf)and all(pf[h]==opf[h]for h in oldf if h!=HEAD)
  oldinternal=base.internal_functions(old_polled);newinternal=base.internal_functions(polled);assert all(newinternal.get(n)==b for n,b in oldinternal.items())
  added=set(newinternal)-set(oldinternal);without_added=polled
  for n in added:without_added=without_added.replace(newinternal[n],'')
  for n in added:assert not re.search(r'@'+re.escape(n)+r'\b',without_added),'new live internal helper: HOLD'
  assert base.state(polled)==STATE and base.errors(pf)==sorted(set(base.errors(oldf))-{hex(HEAD)});coverage,oldcoverage=base.coverage(pf),base.coverage(opf);assert all(coverage[hex(h)]==oldcoverage[hex(h)]for h in oldf if h!=HEAD)
  run(plan['compile_command'],'compile');obj=N/'candidate.polled.o';symbols=subprocess.check_output([plan['tools']['llvm-nm-18'],'--format=posix','--extern-only',str(obj)],text=True);(B/'symbols.txt').write_text(symbols)
  defs=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M));direct=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M));heads={int(x,16)for x in Path(plan['trace_heads']['path']).read_text().splitlines()};assert len(heads)==456706 and defs==sorted(oldf)and not set(direct)-heads
  native={};tables={}
  for label,path in[('old',plan['old_selected_object']['path']),('candidate',obj)]:
   native[label],asm,tables[label]=base.coff_projection(plan['tools']['llvm-objdump-18'],path);(B/(label+'-disassembly.txt')).write_text(asm);assert set(native[label])=={hex(h)for h in oldf}
  changed=sorted(h for h in native['old']if native['old'][h]!=native['candidate'][h]);assert changed==[hex(HEAD)],('unaffected native delta',changed)
  olddirect=sorted(int(h,16)for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',subprocess.check_output([plan['tools']['llvm-nm-18'],'--format=posix','--extern-only',plan['old_selected_object']['path']],text=True),re.M))
  for n,h in plan['input_pins'].items():assert sha(n)==h,n
  assert sha(__file__)==a.builder_sha256 and sha(a.plan)==a.plan_sha256
  for n in['single-target.raw.ll','candidate-unpolled.ll','candidate-polled.ll','candidate.polled.o']:shutil.copy2(N/n,B/n)
  result=dict(passed=True,status='Candidate only; original-prefix qualification required; NOT SELECTED',target_head=hex(HEAD),original_FDE_end_exclusive=hex(END),global_index=129,definitions=128,parent_input=plan['parent_input'],parent_cohort=plan['parent_cohort'],old_selected_object=plan['old_selected_object'],candidate_object=dict(path=str(B/'candidate.polled.o'),sha256=sha(obj)),raw_ir=dict(path=str(B/'candidate-unpolled.ll'),sha256=sha(B/'candidate-unpolled.ll')),polled_ir=dict(path=str(B/'candidate-polled.ll'),sha256=sha(B/'candidate-polled.ll')),raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,native_neighbors_full_bytes_exact=127,all_other_raw_module_bytes_unchanged=True,State_type_closure_sha256=STATE,State_size=1200,State_align=16,old_unsupported_heads=base.errors(oldf),unsupported_heads=base.errors(cf),external_guest_references=direct,old_external_guest_references=olddirect,added_external_guest_references=sorted(set(direct)-set(olddirect)),removed_external_guest_references=sorted(set(olddirect)-set(direct)),all_direct_refs_closed=True,old_poll_coverage=oldcoverage,all_poll_coverage=coverage,native_changed_symbols=changed,native_functions=native,native_relocation_tables=tables,native_projection_basis='Complete actual contiguous COFF bytes, rich relative relocations, every guest span and .text boundary, extended relocation sentinel handled',historical_B_parser_used=False,dead_added_internal_helpers={n:hashlib.sha256(newinternal[n].encode()).hexdigest()for n in sorted(added)},old_internal_helpers_byte_exact=True,builder_sha256=a.builder_sha256,plan_sha256=a.plan_sha256,input_pins=plan['input_pins'],commands=commands,limits='Only703835a0 changed;127neighbors exact. Complete static non-leaf FDE and actual direct-ref closure retained. Qualification covers exact original YIELD703835e4 and branch703835e8 to703835f4 only; lock acquisition, platform helper and full function return are not dynamically qualified. No scheduler/fairness/game/cohort/toolchain selection.')
  result['artifacts']={str(f):sha(f)for directory in[B,N]for f in directory.iterdir()if f.is_file()and f.name!='candidate.json'};save(B/'candidate.json',result);print('YIELD-CANDIDATE',sha(B/'candidate.json'),sha(obj),flush=True)
 except Exception as ex:save(B/'failure.json',dict(passed=False,error=str(ex),traceback=traceback.format_exc(),commands=commands,plan_sha256=a.plan_sha256,builder_sha256=a.builder_sha256));raise
if __name__=='__main__':main()
