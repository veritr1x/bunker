"""Bounded read-only evaluation of existing scalar FCSEL select predicates."""
from __future__ import annotations
import hashlib,re
LOCAL=r'%[-A-Za-z$._0-9]+'
IDENTITY_COMPARE={'eq','neq','sle','slt','sge','sgt','ule','ult','uge','ugt'}
class ConditionHold(ValueError):pass

def condition_holds(condition:int,nzcv:int)->bool:
 n,z,c,v=((nzcv>>i)&1 for i in (3,2,1,0))
 if not 0<=condition<16:raise ConditionHold('invalid original condition code')
 base=(bool(z),bool(c),bool(n),bool(v),bool(c and not z),n==v,bool(not z and n==v),True)[condition>>1]
 return not base if condition&1 and condition!=15 else base

class Predicate:
 def __init__(self,body,definitions,before):
  self.defs=definitions;self.before=before;self.nodes={};self.active=set();self.operations=set();self.flag_loads=[]
  first=body.splitlines()[0].split('(',1)[1].split(',',1)[0];args=re.findall(LOCAL,first)
  if len(args)!=1:raise ConditionHold('unknown State argument')
  self.state=args[0]
 def node(self,value,width,depth=0):
  if depth>64 or len(self.nodes)>256:raise ConditionHold('predicate exceeds bounded graph')
  if value in ('true','false'):
   if width!=1:raise ConditionHold('boolean constant width mismatch')
   return ('constant',width,int(value=='true'))
  if re.fullmatch('-?[0-9]+',value):return('constant',width,int(value)&((1<<width)-1))
  if not re.fullmatch(LOCAL,value):raise ConditionHold('unknown predicate operand')
  key=value,width
  if key in self.nodes:return self.nodes[key]
  if key in self.active:raise ConditionHold('cyclic predicate')
  self.active.add(key)
  if value not in self.defs or self.defs[value][0]>=self.before:raise ConditionHold('predicate value absent or not before FCSEL')
  rhs=self.defs[value][1];result=None
  m=re.fullmatch(r'load i8, ptr ('+LOCAL+r'), align 1',rhs)
  if m:
   if width!=8:raise ConditionHold('flag load width differs')
   pointer=m[1]
   if pointer not in self.defs or self.defs[pointer][0]>=self.defs[value][0]:raise ConditionHold('flag pointer not prior')
   g=re.fullmatch(r'getelementptr inbounds %struct.AArch64State, ptr '+re.escape(self.state)+r', i64 0, i32 9, i32 (5|7|9|11)',self.defs[pointer][1])
   if not g:raise ConditionHold('load is not a qualified N/Z/C/V split flag')
   result=('flag',8,{5:3,7:2,9:1,11:0}[int(g[1])]);self.operations.add('split-flag-load');self.flag_loads.append(dict(value=value,pointer=pointer,offset=self.defs[value][0],flag={5:'N',7:'Z',9:'C',11:'V'}[int(g[1])]))
  m=re.fullmatch(r'icmp (eq|ne|ugt|uge|ult|ule|sgt|sge|slt|sle) i(1|8|16|32|64) ([^,]+), ([^,]+)',rhs)
  if m:
   if width!=1:raise ConditionHold('icmp result width differs')
   bits=int(m[2]);result=('icmp',1,m[1],bits,self.node(m[3],bits,depth+1),self.node(m[4],bits,depth+1));self.operations.add('icmp-'+m[1])
  m=re.fullmatch(r'(and|or|xor) i(1|8|16|32|64) ([^,]+), ([^,]+)',rhs)
  if m:
   if width!=int(m[2]):raise ConditionHold('logical result width differs')
   result=(m[1],width,self.node(m[3],width,depth+1),self.node(m[4],width,depth+1));self.operations.add(m[1])
  m=re.fullmatch(r'(zext|sext|trunc) i(1|8|16|32|64) ('+LOCAL+r') to i(1|8|16|32|64)',rhs)
  if m:
   if width!=int(m[4]):raise ConditionHold('cast result width differs')
   source=int(m[2])
   if m[1]=='trunc'and source<=width or m[1]!='trunc'and source>=width:raise ConditionHold('cast width relation invalid')
   result=(m[1],width,source,self.node(m[3],source,depth+1));self.operations.add(m[1])
  m=re.fullmatch(r'select i1 ([^,]+), i(1|8|16|32|64) ([^,]+), i\2 ([^,]+)',rhs)
  if m:
   if width!=int(m[2]):raise ConditionHold('select result width differs')
   result=('select',width,self.node(m[1],1,depth+1),self.node(m[3],width,depth+1),self.node(m[4],width,depth+1));self.operations.add('select')
  m=re.fullmatch(r'(?:tail )?call(?: noundef)? i1 @__remill_compare_([a-z]+)\(i1(?: noundef)? ([^)]+)\)(?: #\d+)?',rhs)
  if m:
   if width!=1 or m[1]not in IDENTITY_COMPARE:raise ConditionHold('unqualified compare hook')
   result=('identity',1,self.node(m[2],1,depth+1));self.operations.add('__remill_compare_'+m[1])
  if result is None:raise ConditionHold('unsupported predicate instruction: '+rhs)
  self.nodes[key]=result;self.active.remove(key);return result
 @staticmethod
 def evaluate(node,nzcv):
  tag,width,*args=node;mask=(1<<width)-1
  if tag=='constant':return args[0]
  if tag=='flag':return nzcv>>args[0]&1
  if tag=='identity':return Predicate.evaluate(args[0],nzcv)
  if tag in('and','or','xor'):
   a,b=(Predicate.evaluate(x,nzcv)for x in args);return {'and':a&b,'or':a|b,'xor':a^b}[tag]&mask
  if tag in('zext','sext','trunc'):
   source,n=args;value=Predicate.evaluate(n,nzcv)
   if tag=='sext'and value>>(source-1)&1:value-=1<<source
   return value&mask
  if tag=='select':return Predicate.evaluate(args[1]if Predicate.evaluate(args[0],nzcv)else args[2],nzcv)
  if tag=='icmp':
   comparison,bits,a,b=args;a=Predicate.evaluate(a,nzcv);b=Predicate.evaluate(b,nzcv)
   if comparison.startswith('s'):
    if a>>(bits-1)&1:a-=1<<bits
    if b>>(bits-1)&1:b-=1<<bits
   op=comparison[1:]if comparison[0]in('s','u')else comparison
   return int({'eq':a==b,'ne':a!=b,'gt':a>b,'ge':a>=b,'lt':a<b,'le':a<=b}[op])
  raise ConditionHold('unknown predicate node')

def qualify_condition(body,site,*,checker,definitions=None):
 definitions=definitions if definitions is not None else checker._definitions(body)
 match=checker.PAIR.match(body,site['IR_offset'])
 if not match:raise ConditionHold('site does not bind the captured transport idiom')
 source=match['source']
 if source not in definitions or definitions[source][0]>=match.start():raise ConditionHold('carrier absent or not before FCSEL')
 selection=re.fullmatch(r'select i1 ('+LOCAL+r'), i64 ('+LOCAL+r'), i64 ('+LOCAL+r')',definitions[source][1])
 if not selection:raise ConditionHold('nonselect carrier outside this observed profile')
 arms=[checker._source_register(body,definitions,v,match.start())for v in selection.group(2,3)]
 p=Predicate(body,definitions,match.start());tree=p.node(selection[1],1)
 markers=list(re.finditer(r'^  store i64 [^\n]+, ptr %PC(?:[0-9.]*)?, align 8',body[:match.start()],re.M))
 if not markers or not p.flag_loads:raise ConditionHold('current instruction or predicate flags absent')
 instruction_start=markers[-1].start()
 if any(x['offset']<instruction_start for x in p.flag_loads):raise ConditionHold('cached/forwarded flag from before current instruction')
 first_flag=min(x['offset']for x in p.flag_loads);interval=body[first_flag:match.start()]
 if re.search(r'^  store\b|^  (?:'+LOCAL+r' = )?(?:atomicrmw|cmpxchg|fence|invoke|callbr)\b',interval,re.M):raise ConditionHold('store/atomic/opaque operation between flags and FCSEL')
 if re.search(r'^[-A-Za-z$._0-9]+:|^  (?:br|switch|indirectbr|ret|unreachable)\b',interval,re.M):raise ConditionHold('control-flow boundary between flags and FCSEL')
 for line in interval.splitlines():
  if re.search(r'\b(?:call|invoke|callbr)\b',line):
   call=re.fullmatch(r'  '+LOCAL+r' = (?:tail )?call(?: noundef)? i1 @__remill_compare_([a-z]+)\(i1(?: noundef)? '+LOCAL+r'\)(?: #\d+)?',line)
   if not call or call[1]not in IDENTITY_COMPARE:raise ConditionHold('opaque call between flags and FCSEL')
 booleans=[p.evaluate(tree,nzcv)for nzcv in range(16)]
 if any(v not in(0,1)for v in booleans):raise ConditionHold('predicate result is not boolean')
 actual=[arms[0]if v else arms[1]for v in booleans]
 candidates=site['original_opcode_candidates'];checks=[]
 for candidate in candidates:
  word=int(candidate['word'],16);bits=word>>22&3
  if word&0xff200c00!=0x1e200c00 or bits not in(0,1)or candidate['cond']!=word>>12&15 or candidate['rn']!=word>>5&31 or candidate['rm']!=word>>16&31 or candidate['rd']!=word&31 or candidate['width']!=(32 if bits==0 else 64):raise ConditionHold('original opcode fields differ')
  expected=[candidate['rn']if condition_holds(candidate['cond'],nzcv)else candidate['rm']for nzcv in range(16)]
  checks.append(dict(candidate=candidate,matches=actual==expected,expected_selected_registers=expected))
 matches=[x['candidate']for x in checks if x['matches']]
 if not matches:raise ConditionHold('existing predicate/arm wiring matches no original candidate condition')
 return dict(passed=True,IR_offset=site['IR_offset'],body_sha256=hashlib.sha256(body.encode()).hexdigest(),carrier=source,predicate=selection[1],true_source_register=arms[0],false_source_register=arms[1],predicate_truth_table=booleans,selected_registers_by_NZCV=actual,evaluations=16,matching_original_candidates=matches,nonmatching_original_candidates=[x['candidate']for x in checks if not x['matches']],original_candidate_list_preserved=True,candidate_checks=checks,predicate_operations=sorted(p.operations),predicate_node_count=len(p.nodes),flag_loads=p.flag_loads,flag_freshness=dict(current_instruction_PC_store_offset=instruction_start,first_flag_load_offset=first_flag,FCSEL_pair_offset=match.start(),same_basic_block=True,no_intervening_store=True,no_intervening_opaque_call=True,no_intervening_atomic=True))
