"""One original ST2 constructor: sparse splice, polling and complete COFF checks.

Consumes the reviewed plan only. No game selection, global toolchain refresh,
constant-pool normalization or automatic fallback is supported.
"""
import argparse
import difflib
import hashlib
import json
import re
import shutil
import struct
import subprocess
import traceback
from pathlib import Path

HEAD = 0x707520c4
END = 0x707521bc
PLAN_SHA = 'ed9bcb292a7bb394ecd260f189fed754ccbe571612ed3ee963b5eed08dd7f8c9'
INITIAL_BUILDER_SHA = 'c6a314a55648b913a342bd38240aceb49c62f818addd78a1a1886a82aea48ac3'
SAVED_COFF_BUILDER_SHA = 'd808b6775c504837d334b587b2899054516603eba16c9f5379eb5fa8652aa2b9'
SAVED_COFF_SHA = 'ad6b08dbcebe0d007c60a6ccc6a8b71f6a8be8a80693cec4fda0223fab53fe5e'
STATE_SHA = '26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'
W = Path('/mnt/c/GitRepos/bunker/recomp/work')
PLAN = W/'unity-st2-constructor-overlay1/plan.json'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path): return json.loads(Path(path).read_text())
def save(path, obj):
    assert not path.exists(), path
    path.write_text(json.dumps(obj, indent=2)+'\n')

def functions(text):
    result = {int(m[1],16):m[0] for m in re.finditer(
        r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}', text, re.M|re.S)}
    assert len(result) == len(re.findall(r'^define[^\n]*@sub_[0-9a-f]+\(', text, re.M))
    return result

def internal_functions(text):
    return {m[1]:m[0] for m in re.finditer(r'^define[^\n]*@([^ (]+)\([^\n]*\).*?^}',text,re.M|re.S)
            if not m[1].startswith('sub_')}

def attrs(text): return dict(re.findall(r'^attributes #(\d+) = (.*)$', text, re.M))
def types(text): return dict(re.findall(r'^(%[-A-Za-z$._0-9]+) = type (.*)$', text, re.M))
def errors(fs):
    return sorted(hex(h) for h,b in fs.items()
                  if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(', b))

def state(text):
    ty=types(text);seen=set();todo=['%struct.State']
    while todo:
        x=todo.pop()
        if x in seen: continue
        seen.add(x);todo.extend(re.findall(r'%[-A-Za-z$._0-9]+',ty[x]))
    return hashlib.sha256(('\n'.join(x+' = type '+ty[x] for x in sorted(seen))+'\n').encode()).hexdigest()

def coverage(fs):
    result={}
    for h,b in fs.items():
        requests=len(re.findall(r'call i32 @__bunker_guest_poll_requested\(',b))
        sites=re.findall(r'call void @__bunker_guest_poll_slow\(ptr [^,]+, i64 (\d+), i64 (\d+), i64 ([^,)]+)\)',b)
        assert requests==len(sites)>=1
        assert all(int(s[0])==h for s in sites)
        assert [int(s[1]) for s in sites]==list(range(len(sites)))
        result[hex(h)]=dict(entry=1,cycle=len(sites)-1,total=len(sites))
    return result

def coff_projection(tool,path):
    """Complete actual bytes, exact rich relocs, and all .text span coverage."""
    data=Path(path).read_bytes()
    machine,ns,_,at,count,opt,_=struct.unpack_from('<HHIIIHH',data)
    assert machine==0x8664 and opt==0
    sections=[]
    for i in range(ns):
        x=struct.unpack_from('<8sIIIIIIHHI',data,20+40*i)
        sections.append(dict(name=x[0].rstrip(b'\0').decode(),size=x[3],raw=x[4],reloc=x[5],count=x[7],flags=x[9]))
    strings=data[at+18*count:];symbols={};i=0
    while i<count:
        x=data[at+18*i:at+18*(i+1)];name=x[:8]
        if name[:4]==b'\0'*4:
            k=struct.unpack_from('<I',name,4)[0];name=strings[k:strings.index(b'\0',k)]
        value,sn,typ,storage,aux=struct.unpack_from('<IhHBB',x,8)
        symbols[i]=dict(name=name.rstrip(b'\0').decode(),value=value,section=sn,type=typ,storage=storage)
        i+=1+aux
    assert i==count
    relocations={};relocation_tables=[]
    for sn,s in enumerate(sections,1):
        extended=bool(s['flags']&0x01000000);first=0;number=s['count'];sentinel=None
        if extended:
            assert s['count']==0xffff and s['reloc']+10<=len(data)
            total,sentinel_symbol,sentinel_type=struct.unpack_from('<IIH',data,s['reloc'])
            assert sentinel_symbol==0 and sentinel_type==0 and total>=0x10000
            # LLVM18 getNumberOfRelocations returns VirtualAddress-1;
            # getFirstReloc skips the repurposed first table entry.
            first=1;number=total-1
            sentinel=dict(total_records_including_dummy=total,symbol=0,type=0)
        assert s['reloc']+10*(first+number)<=len(data)
        if number: assert s['reloc']+10*(first+number)<=at
        rr=[]
        for j in range(first,first+number):
            offset,k,kind=struct.unpack_from('<IIH',data,s['reloc']+10*j)
            assert k in symbols and offset<=s['size']-4
            rr.append(dict(offset=offset,type=kind,symbol=symbols[k]['name'],
                           addend=struct.unpack_from('<i',data,s['raw']+offset)[0]))
        relocations[sn]=rr
        assert len(rr)==number
        relocation_tables.append(dict(section=sn,name=s['name'],header_count=s['count'],extended=extended,
            sentinel=sentinel,dummy_records_skipped=first,actual_relocations=number,
            table_offset=s['reloc'],table_end=s['reloc']+10*(first+number),complete_table_bounds_validated=True))
    text=subprocess.check_output([str(tool),'-dr',str(path)],text=True)
    result={};spans={}
    for m in re.finditer(r'(?m)^([0-9a-f]+) <sub_([0-9a-f]+)>:\n(.*?)(?=^[0-9a-f]+ <|\Z)',text,re.S):
        head=hex(int(m[2],16));start=int(m[1],16)
        matching=[s for s in symbols.values() if s['name']=='sub_'+m[2] and s['section']>0]
        assert len(matching)==1
        sym=matching[0];assert sym['value']==start
        section=sections[sym['section']-1];assert section['name']=='.text'
        rows=[(int(z[1],16),bytes.fromhex(z[2])) for z in re.finditer(
            r'^\s*([0-9a-f]+):[ ]+([0-9a-f ]+)\t.*$',m[3],re.M)]
        assert rows and rows[0][0]==start
        assert all(x[0]+len(x[1])==y[0] for x,y in zip(rows,rows[1:]))
        code=b''.join(x[1] for x in rows)
        assert data[section['raw']+start:section['raw']+start+len(code)]==code
        next_symbols=[s['value'] for s in symbols.values() if s['section']==sym['section'] and s['value']>start]
        end=min(next_symbols) if next_symbols else section['size']
        assert start+len(code)==end
        spans.setdefault(sym['section'],[]).append((start,end,len(code)))
        rr=[dict(r,offset=r['offset']-start) for r in relocations[sym['section']] if start<=r['offset']<end]
        assert all(r['offset']<=len(code)-4 for r in rr)
        result[head]=dict(code_sha256=hashlib.sha256(code).hexdigest(),bytes=len(code),instructions=len(rows),
                          relocations=rr,full_contiguous_COFF_bytes_validated=True)
    nonempty={i+1:s for i,s in enumerate(sections) if s['name']=='.text' and s['size']}
    assert set(nonempty)==set(spans)
    for sn,s in nonempty.items():
        ss=sorted(spans[sn]);assert ss[0][0]==0 and ss[-1][1]==s['size']
        assert len({x[0] for x in ss})==len(ss)
        assert all(x[1]==y[0] for x,y in zip(ss,ss[1:])) and sum(x[2]for x in ss)==s['size']
    return result,text,relocation_tables

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--builder-sha256',required=True)
    ap.add_argument('--resume-saved-ir',action='store_true',help='Only resume the preserved parser failure; never repeat lift/poll.')
    ap.add_argument('--resume-saved-coff',action='store_true',help='Read-only finish of the preserved extended-relocation parser failure.')
    a=ap.parse_args()
    assert not(a.resume_saved_ir and a.resume_saved_coff)
    reuse_ir=a.resume_saved_ir or a.resume_saved_coff
    assert sha(__file__)==a.builder_sha256 and sha(PLAN)==PLAN_SHA
    plan=read(PLAN);B=Path(plan['out']);N=Path(plan['native_out'])
    assert plan['target_heads']==[hex(HEAD)] and plan['global_index']==249
    for path,h in plan['input_pins'].items(): assert sha(path)==h,path
    assert not (B/'candidate.json').exists()
    resume_pins={}
    if reuse_ir:
        assert N.exists() and (B/'failure.json').exists()
        assert sha(B/'executed-builder.py')==INITIAL_BUILDER_SHA
        failure=read(B/'failure.json')
        assert failure['builder_sha256']==INITIAL_BUILDER_SHA and failure['plan_sha256']==PLAN_SHA
        assert list(failure['commands'])==['one-entry-lift','instrument']
        if a.resume_saved_coff:
            assert sha(B/'resumed-builder.py')==SAVED_COFF_BUILDER_SHA
            assert sha(N/'candidate.polled.o')==SAVED_COFF_SHA and not(B/'coff-recheck-failure.json').exists()
            compiled_failure=read(B/'resume-failure.json')
            assert compiled_failure['builder_sha256']==SAVED_COFF_BUILDER_SHA
            assert 'COFF relocation overflow needs explicit support' in compiled_failure['hold_reason']
            assert list(compiled_failure['commands'])==['one-entry-lift','instrument','compile']
        else:
            assert not(B/'resume-failure.json').exists()
            assert not (N/'candidate.polled.o').exists() and not (B/'compile.log').exists()
        resume_pins={str(path):sha(path) for path in [B/'executed-builder.py',B/'failure.json',
            B/'one-entry-lift.log',B/'instrument.log',N/'single-target.raw.ll',
            N/'candidate-unpolled.ll',N/'candidate-polled.ll',B/'object-raw.diff']}
        commands=dict(failure['commands'])
        if a.resume_saved_coff:
            extra=[B/'resumed-builder.py',B/'resume-failure.json',B/'compile.log',N/'candidate.polled.o',B/'symbols.txt']
            resume_pins.update({str(path):sha(path)for path in extra})
            commands=dict(compiled_failure['commands'])
    else:
        assert not N.exists() and not (B/'failure.json').exists()
        N.mkdir();commands={}
    def run(cmd,label):
        commands[label]=list(map(str,cmd));print('STAGE',label,flush=True)
        with (B/(label+'.log')).open('x') as log:
            subprocess.run(commands[label],stdout=log,stderr=subprocess.STDOUT,check=True)
    try:
        old=Path(plan['old_raw_ir']['path']).read_text();of=functions(old)
        assert len(of)==128 and errors(of)==[hex(HEAD)]
        if not reuse_ir: run(plan['lift_command'],'one-entry-lift')
        fresh=(N/'single-target.raw.ll').read_text();ff=functions(fresh)
        assert set(ff)=={HEAD} and not errors(ff)
        assert state(old)==state(fresh)==STATE_SHA
        oa,fa=attrs(old),attrs(fresh);reverse={v:k for k,v in oa.items()}
        body=re.sub(r' #(\d+)(?=[ {\n])',lambda m:' #'+reverse[fa[m[1]]],ff[HEAD])
        # This small original function must not import numeric metadata from a
        # fresh module into unrelated old metadata definitions.
        assert not re.search(r'!\d+',body), 'unmapped fresh metadata: HOLD'
        ot,ft=types(old),types(fresh)
        for name in set(re.findall(r'%[-A-Za-z$._0-9]+',body))&set(ft): assert ot.get(name)==ft[name]
        decls=set(re.findall(r'^declare[^\n]*@([^ (]+)',old,re.M))
        refs=set(re.findall(r'@([^ (]+)\(',body))-{f'sub_{HEAD:x}'}
        assert refs<=decls|{f'sub_{h:x}'for h in of},refs-decls
        assert old.count(of[HEAD])==1
        candidate=old.replace(of[HEAD],body);cf=functions(candidate)
        assert set(cf)==set(of) and all(cf[h]==of[h]for h in of if h!=HEAD)
        assert candidate.replace(body,of[HEAD])==old and attrs(candidate)==oa
        assert state(candidate)==STATE_SHA and not errors(cf)
        diff=''.join(difflib.unified_diff(of[HEAD].splitlines(True),body.splitlines(True),fromfile='selected/707520c4',tofile='ST2-supported/707520c4'))
        if reuse_ir:
            assert (N/'candidate-unpolled.ll').read_bytes()==candidate.encode()
            assert (B/'object-raw.diff').read_text()==diff
        else:
            (N/'candidate-unpolled.ll').write_text(candidate)
            (B/'object-raw.diff').write_text(diff)
            run(plan['poll_command'],'instrument')
        polled=(N/'candidate-polled.ll').read_text();pf=functions(polled)
        old_polled=Path(plan['old_polled_ir']['path']).read_text();opf=functions(old_polled)
        assert set(pf)==set(opf)==set(of) and all(pf[h]==opf[h]for h in of if h!=HEAD)
        internal=internal_functions(polled)
        assert internal==internal_functions(old_polled)
        assert set(internal)=={'__remill_flag_computation_sign','__remill_flag_computation_zero',
                              '__remill_flag_computation_overflow','__remill_compare_neq'}
        assert len(pf)==128 and len(re.findall(r'^define ',polled,re.M))==132
        assert state(polled)==STATE_SHA and not errors(pf)
        cov,oldcov=coverage(pf),coverage(opf)
        assert all(cov[hex(h)]==oldcov[hex(h)]for h in of if h!=HEAD)
        assert cov[hex(HEAD)]['cycle']>=1
        if not a.resume_saved_coff: run(plan['compile_command'],'compile')
        obj=N/'candidate.polled.o'
        symbols=subprocess.check_output([plan['tools']['llvm-nm-18'],'--format=posix','--extern-only',str(obj)],text=True)
        if a.resume_saved_coff: assert (B/'symbols.txt').read_text()==symbols
        else: (B/'symbols.txt').write_text(symbols)
        defs=sorted(int(x,16)for x in re.findall(r'^sub_([0-9a-f]+) T(?: |$)',symbols,re.M))
        direct=sorted(int(x,16)for x in re.findall(r'^sub_([0-9a-f]+) U(?: |$)',symbols,re.M))
        heads={int(x,16)for x in (B/'trace-heads.txt').read_text().splitlines()}
        assert len(heads)==456689 and defs==sorted(of) and not set(direct)-heads
        native={};tables={}
        for label,path in [('old',plan['old_selected_object']['path']),('candidate',obj)]:
            projection,asm,table=coff_projection(plan['tools']['llvm-objdump-18'],path)
            (B/(label+'-disassembly.txt')).write_text(asm)
            assert set(projection)=={hex(h)for h in of};native[label]=projection;tables[label]=table
        changed=sorted(h for h in native['old'] if native['old'][h]!=native['candidate'][h])
        assert changed==[hex(HEAD)],('unaffected native differences',changed)
        for path,h in plan['input_pins'].items(): assert sha(path)==h,path
        for path,h in resume_pins.items(): assert sha(path)==h,path
        for name in ['single-target.raw.ll','candidate-unpolled.ll','candidate-polled.ll','candidate.polled.o']:
            shutil.copy2(N/name,B/name)
        result=dict(passed=True,status='Candidate ONLY; original-function qualification pending; NOT SELECTED',
            target_head=hex(HEAD),original_FDE_end_exclusive=hex(END),global_index=249,definitions=128,
            parent_input=plan['parent_input'],parent_v8_proof=plan['parent_v8_proof'],
            raw_neighbors_byte_exact=127,polled_neighbors_byte_exact=127,native_neighbors_full_bytes_exact=127,
            all_other_raw_module_bytes_unchanged=True,State_type_closure_sha256=STATE_SHA,State_size=1200,State_align=16,
            old_selected_object=plan['old_selected_object'],
            candidate_object=dict(path=str(B/'candidate.polled.o'),sha256=sha(obj)),
            raw_ir=dict(path=str(B/'candidate-unpolled.ll'),sha256=sha(B/'candidate-unpolled.ll')),
            polled_ir=dict(path=str(B/'candidate-polled.ll'),sha256=sha(B/'candidate-polled.ll')),
            unsupported_heads=[],old_unsupported_heads=[hex(HEAD)],external_guest_references=direct,
            all_direct_refs_closed=True,old_poll_coverage=oldcov,all_poll_coverage=cov,
            native_changed_symbols=changed,native_functions=native,
            native_projection_basis='Complete actual contiguous COFF bytes; exact rich relative relocations; complete unique guest .text coverage',
            historical_B_parser_used=False,builder_sha256=a.builder_sha256,plan_sha256=PLAN_SHA,
            resumed_saved_IR_only=a.resume_saved_ir,resume_input_pins=resume_pins,
            saved_COFF_read_only_followup=a.resume_saved_coff,
            repeated_lifter_invocations=0 if reuse_ir else None,
            repeated_poller_invocations=0 if reuse_ir else None,
            repeated_compiler_invocations=0 if a.resume_saved_coff else None,
            COFF_relocation_tables=tables,
            polled_internal_helpers_byte_exact={name:hashlib.sha256(body.encode()).hexdigest()for name,body in internal.items()},
            input_pins=plan['input_pins'],commands=commands,
            artifacts={str(f):sha(f)for directory in [B,N]for f in directory.iterdir()if f.is_file()},
            limits='One complete original FDE only. No other current raw/polled/native function admitted as changed. No game/parent-object/guard/toolchain selection. Original actual-memset function qualification remains required.')
        save(B/'candidate.json',result)
        print('UNITY-ST2-CONSTRUCTOR-CANDIDATE',sha(B/'candidate.json'),sha(B/'candidate.polled.o'),flush=True)
    except Exception as e:
        save(B/('coff-recheck-failure.json'if a.resume_saved_coff else 'resume-failure.json'if a.resume_saved_ir else 'failure.json'),dict(passed=False,hold_reason=str(e),traceback=traceback.format_exc(),commands=commands,
                                   plan_sha256=PLAN_SHA,builder_sha256=a.builder_sha256))
        raise

if __name__=='__main__': main()
