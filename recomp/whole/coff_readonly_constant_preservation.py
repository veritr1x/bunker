"""Strict saved-COFF neighbor preservation with complete readonly-payload checks.

No compiler, disassembler, lifter or process is invoked. The caller supplies the
actual disassembly strings and separately pins inputs/target qualifications.
Every non-target .rdata reference is checked, including unchanged addends.
Only relocation-free readonly constant sections are admitted.
"""
from pathlib import Path
import hashlib,re,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_AC_READ,CS_AC_WRITE,CS_GRP_CALL,CS_GRP_JUMP
from capstone.x86 import X86_OP_MEM,X86_REG_RIP

class PreservationError(AssertionError):
 def __init__(self,code,**details):
  self.code=code;self.details=details;super().__init__(code+': '+repr(details))

def _need(value,code,**details):
 if not value:raise PreservationError(code,**details)

def _parse_coff(path):
 data=Path(path).read_bytes();_need(len(data)>=20,'coff_header');machine,count,_,at,nsyms,opt,_=struct.unpack_from('<HHIIIHH',data);_need(machine==0x8664 and opt==0,'coff_target');_need(20+40*count<=len(data)and at+18*nsyms+4<=len(data),'coff_bounds');strings=data[at+18*nsyms:];sections=[]
 for i in range(count):
  x=struct.unpack_from('<8sIIIIIIHHI',data,20+40*i);s=dict(name=x[0].rstrip(b'\0').decode(),size=x[3],raw=x[4],reloc=x[5],count=x[7],flags=x[9],header_at=20+40*i);_need(s['raw']+s['size']<=len(data)or s['raw']==0,'coff_section_bounds');sections.append(s)
 symbols={};i=0
 while i<nsyms:
  x=data[at+18*i:at+18*(i+1)];name=x[:8]
  if name[:4]==bytes(4):
   k=struct.unpack_from('<I',name,4)[0];_need(4<=k<len(strings),'coff_string_bounds');name=strings[k:strings.index(b'\0',k)]
  value,sn,typ,storage,aux=struct.unpack_from('<IhHBB',x,8);_need(i+1+aux<=nsyms,'coff_aux_bounds');symbols[i]=dict(name=name.rstrip(b'\0').decode(),value=value,section=sn,type=typ,storage=storage);i+=1+aux
 rels={}
 for sn,s in enumerate(sections,1):
  first=0;n=s['count']
  if s['flags']&0x01000000:
   _need(n==0xffff and s['reloc']+10<=len(data),'coff_extended_relocations');total,si,ty=struct.unpack_from('<IIH',data,s['reloc']);_need(total>=0x10000 and si==ty==0,'coff_extended_sentinel');first=1;n=total-1
  _need(s['reloc']+10*(first+n)<=at if n else True,'coff_relocation_table_bounds')
  for j in range(first,first+n):
   record_at=s['reloc']+10*j;off,si,ty=struct.unpack_from('<IIH',data,record_at);_need(si in symbols and off+4<=s['size'],'coff_relocation_bounds');_need((sn,off)not in rels,'coff_duplicate_relocation');rels[sn,off]=dict(type=ty,symbol=symbols[si],addend=struct.unpack_from('<i',data,s['raw']+off)[0],record_at=record_at)
 return dict(data=data,sections=sections,symbols=symbols,relocations=rels)

def _frames(c):
 fs=sorted((s for s in c['symbols'].values()if s['type']==0x20 and s['section']>0),key=lambda s:(s['section'],s['value']));_need(fs and len({s['name']for s in fs})==len(fs),'function_symbols');out={}
 for i,s in enumerate(fs):
  sec=c['sections'][s['section']-1];_need(sec['name']=='.text','function_section');n=fs[i+1]if i+1<len(fs)else None;end=n['value']if n and n['section']==s['section']else sec['size'];_need(s['value']<end<=sec['size'],'function_bounds',name=s['name']);out[s['name']]=dict(symbol=s,code=c['data'][sec['raw']+s['value']:sec['raw']+end],relocs={off-s['value']:r for(sn,off),r in c['relocations'].items()if sn==s['section']and s['value']<=off<end})
 return out

# Bounded data-read profile. Unknown/implicit-address/control-flow operations fail.
_READ_MNEMONICS=frozenset('mov movzx movsx movsxd movd movq movss movsd movaps movups movapd movupd movdqa movdqu andps andpd orps orpd xorps xorpd pand pandn por pxor ucomiss ucomisd comiss comisd addss addsd subss subsd mulss mulsd divss divsd minss minsd maxss maxsd sqrtss sqrtsd cmp test add sub and or xor'.split())

def _disassembly_blocks(text):
 matches=list(re.finditer(r'^([0-9a-f]+) <([^>]+)>:\n',text,re.M));return {m[2]:(m.end(),matches[i+1].start()if i+1<len(matches)else len(text))for i,m in enumerate(matches)}

def _instructions_at_fields(text,frame,name,fields,blocks):
 _need(name in blocks,'disassembly_function',name=name);lo,hi=blocks[name];wanted=set(fields);out={};start=frame['symbol']['value']
 for r in re.finditer(r'^\s*([0-9a-f]+):[ ]+([0-9a-f ]+)\t(.*)$',text[lo:hi],re.M):
  address=int(r[1],16);b=bytes.fromhex(r[2]);off=address-start;hits=[f for f in wanted if off<=f<off+len(b)]
  if hits:
   _need(len(hits)==1 and frame['code'][off:off+len(b)]==b,'disassembly_bytes',name=name,offset=off);_need(hits[0]not in out,'disassembly_duplicate_field');out[hits[0]]=(address,off,b)
 _need(set(out)==wanted,'disassembly_field_coverage',name=name,missing=sorted(wanted-set(out)));return out

def _read_payload(c,frame,name,field,instruction,decoder):
 address,offset,b=instruction;ins=list(decoder.disasm(b,address));_need(len(ins)==1 and ins[0].size==len(b),'instruction_decode',name=name,field=field);i=ins[0];_need(i.mnemonic in _READ_MNEMONICS and not i.group(CS_GRP_CALL)and not i.group(CS_GRP_JUMP),'not_supported_data_read',name=name,instruction=i.mnemonic+' '+i.op_str)
 mem=[o for o in i.operands if o.type==X86_OP_MEM];_need(len(mem)==1,'memory_operand_count',name=name);op=mem[0];_need(op.mem.base==X86_REG_RIP and op.mem.index==0 and op.access&CS_AC_READ and not op.access&CS_AC_WRITE,'not_actual_read',name=name,instruction=i.mnemonic+' '+i.op_str)
 # REL32 supplies the authoritative four-byte field width. Capstone5 reports
 # disp_size=2 for some66-prefixed RIP-relative MOVAPD, despite the encoded4B.
 _need(offset+i.disp_offset==field and i.disp_offset+4==len(b),'not_exact_REL32_displacement',name=name,field=field);width=op.size;_need(width in (1,2,4,8,16),'unsupported_read_width',name=name,width=width)
 r=frame['relocs'][field];_need(r['type']==4,'not_REL32',name=name,field=field);sym=r['symbol'];_need(0<sym['section']<=len(c['sections']),'constant_symbol_section');sec=c['sections'][sym['section']-1];_need(sec['name']=='.rdata'and sec['flags']&0x40000000 and not sec['flags']&(0x80000000|0x20000000),'not_readonly_rdata',name=name,field=field);at=sym['value']+r['addend'];_need(0<=at<=sec['size']-width,'constant_payload_bounds',name=name,field=field);_need(not any(sn==sym['section']for sn,off in c['relocations']),'embedded_payload_relocation',name=name,field=field)
 power=(sec['flags']>>20)&15;_need(power>0,'constant_alignment',name=name);alignment=1<<(power-1)
 # Deliberately conservative: natural read-width alignment even where a scalar
 # x86 opcode permits less. This is a sufficient admitted profile, not a claim
 # that every accepted instruction architecturally requires this alignment.
 required=width;_need(alignment>=required and at%required==0,'constant_alignment',name=name,field=field,required=required);payload=c['data'][sec['raw']+at:sec['raw']+at+width]
 return dict(instruction_offset=offset,instruction_bytes=b.hex(),instruction=i.mnemonic+' '+i.op_str,field_offset=i.disp_offset,encoded_displacement_bytes=4,read_width=width,readonly_section=True,relocation_type=r['type'],symbol_name=sym['name'],symbol_value=sym['value'],section_flags=sec['flags'],section_alignment=alignment,required_alignment=required,alignment_profile='conservative natural read-width',required_alignment_satisfied=True,addend=r['addend'],resolved_offset=at,resolved_bytes=payload.hex(),payload_file_offset=sec['raw']+at,section_header_file_offset=sec['header_at'],relocation_record_file_offset=r['record_at'])

def prove_neighbors(old_object,new_object,changed_targets,old_disassembly_text,new_disassembly_text):
 """Prove every non-target code byte/relocation and ALL referenced RO payloads.

 Targets are exact guest-head integers; their qualification remains the caller's
 responsibility. No blanket object waiver or target semantic claim is emitted.
 """
 A=_parse_coff(old_object);B=_parse_coff(new_object);fa,fb=_frames(A),_frames(B);_need(fa.keys()==fb.keys(),'function_set');targets={'sub_'+format(h,'x')for h in changed_targets};_need(targets and targets<=fa.keys(),'target_set');cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True;asm_a=_disassembly_blocks(old_disassembly_text);asm_b=_disassembly_blocks(new_disassembly_text);records=[];reads=[];native_exact=0;changed=0
 for name in fa:
  if name in targets:continue
  a,b=fa[name],fb[name];ca,cb=bytearray(a['code']),bytearray(b['code']);_need(len(ca)==len(cb),'function_size',name=name);_need(a['relocs'].keys()==b['relocs'].keys(),'relocation_positions',name=name);ro=[];changed_fields=[]
  for off in a['relocs']:
   ra,rb=a['relocs'][off],b['relocs'][off];_need(ra['type']==rb['type'],'relocation_type',name=name,field=off);_need(ra['symbol']['name']==rb['symbol']['name'],'relocation_symbol',name=name,field=off)
   isa=ra['symbol']['section']>0 and A['sections'][ra['symbol']['section']-1]['name']=='.rdata';isb=rb['symbol']['section']>0 and B['sections'][rb['symbol']['section']-1]['name']=='.rdata';_need(isa==isb,'constant_section_identity',name=name,field=off)
   if isa:
    _need(ra['type']==4,'not_REL32',name=name,field=off);ro.append(off)
    if ra['addend']!=rb['addend']:changed_fields.append(off)
    ca[off:off+4]=cb[off:off+4]=bytes(4)
   else:_need(ra['addend']==rb['addend'],'other_relocation_addend',name=name,field=off)
  _need(ca==cb,'other_instruction_bytes',name=name);calls=lambda f:[dict(offset=o,symbol=r['symbol']['name'],type=r['type'],addend=r['addend'])for o,r in f['relocs'].items()if r['symbol']['name'].startswith('sub_')];_need(calls(a)==calls(b),'guest_call_records',name=name)
  if ro:
   ia=_instructions_at_fields(old_disassembly_text,a,name,ro,asm_a);ib=_instructions_at_fields(new_disassembly_text,b,name,ro,asm_b)
   for off in ro:
    ar=_read_payload(A,a,name,off,ia[off],cs);br=_read_payload(B,b,name,off,ib[off],cs);_need(ar['instruction_offset']==br['instruction_offset']and ar['read_width']==br['read_width'],'read_shape',name=name,field=off);_need(ar['resolved_bytes']==br['resolved_bytes'],'constant_payload_bytes',name=name,field=off);reads.append(dict(name=name,offset=off,addend_changed=off in changed_fields,old=ar,candidate=br))
  exact=a['code']==b['code']and all(a['relocs'][o]['addend']==b['relocs'][o]['addend']for o in a['relocs']);native_exact+=exact;changed+=not exact
  records.append(dict(name=name,head='0x'+name[4:]if name.startswith('sub_')else None,bytes=len(ca),changed_fields=changed_fields,all_rdata_read_fields=ro,all_nonfield_instruction_bytes_equal=True,relative_relocation_positions_types_symbols_exact=True,all_other_relocation_addends_exact=True,guest_calls_exact=True,masked_sha256=hashlib.sha256(ca).hexdigest(),native_guest_calls=calls(a)))
 return dict(passed=True,scope='Strict saved-COFF non-target code and every referenced readonly data operand; target qualification is separate.',protected_functions=len(records),native_byte_and_rich_relocation_exact_functions=native_exact,functions_with_changed_readonly_displacements=changed,readonly_read_fields_checked=len(reads),changed_readonly_displacement_fields=sum(r['addend_changed']for r in reads),unchanged_displacement_payload_fields_checked=sum(not r['addend_changed']for r in reads),all_nonfield_instruction_bytes_equal=True,all_relative_relocation_positions_types_symbols_exact=True,all_other_relocation_addends_exact=True,all_guest_calls_exact=True,all_function_sizes_equal=True,all_non_target_rdata_references_accounted=True,all_resolved_read_payloads_equal=True,all_required_alignments_satisfied=True,functions=records,relocation_reads=reads,raw_native_byte_equality_claimed_for_changed_functions=False,whole_rdata_pool_identity_claimed=False,no_target_semantic_qualification_claim=True)
