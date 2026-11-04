"""Extract unchanged current original helper bodies and raw native byte packets."""
import argparse,hashlib,json,re
from pathlib import Path
from elftools.elf.elffile import ELFFile
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
FUNCTION=r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def descriptor(p):return {'path':str(p.resolve()),'sha256':sha(p)}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
 candidate=json.loads(a.candidate.read_text());assert candidate['passed']is True and len(candidate['entry_heads'])==27
 shard=json.loads((W/'game17-polled-cohort1/shard-01572.json').read_text());raw=Path(shard['source']['raw_ir']);polled=Path('/home/user/bunker-recomp/recomp/work/game17-polled-cohort1/shard-01572/instrumented.ll');assert sha(raw)==shard['source']['raw_ir_sha256']and sha(polled)==shard['instrumented_ir_sha256']
 ranges=[(0x826249d4,0x82624b2c),(0x82624b2c,0x82624c40),(0x82624c40,0x82624cd4),(0x82624eac,0x82624f24),(0x82625840,0x82626000)]
 selected={};proofs={};outputs={}
 for kind,source in [('raw',raw),('polled',polled)]:
  text=source.read_text();bodies={int(m[1],16):m[0]for m in re.finditer(FUNCTION,text,re.M|re.S)if any(lo<=int(m[1],16)<hi for lo,hi in ranges)};assert bodies
  def replace(m):
   if int(m[1],16)in bodies:return m[0]
   first=m[0].split('\n',1)[0];assert first.endswith('{');return'declare '+first[len('define '):-1].rstrip()
  projected=re.sub(FUNCTION,replace,text,flags=re.M|re.S);actual={int(m[1],16):m[0]for m in re.finditer(FUNCTION,projected,re.M|re.S)};assert actual==bodies
  if selected:assert selected.keys()==bodies.keys()
  else:selected=bodies
  dest=out/('retained-'+kind+'.ll');dest.write_text(projected);outputs[kind]=descriptor(dest);proofs[kind]={'source':descriptor(source),'heads':[hex(v)for v in sorted(bodies)],'selected_bodies_byte_exact':True,'source_inverse_scope':'All selected definitions are byteexact; unrelated translated definitions become declarations. No selected instructions/CFG/attributes changed.','body_hashes':{hex(v):hashlib.sha256(body.encode()).hexdigest()for v,body in bodies.items()}}
 allrefs={int(h,16)for body in selected.values()for h in re.findall(r'@sub_([0-9a-f]+)\(',body)};assert allrefs-selected.keys()=={0x820cb8d0,0x820cbb10},[hex(v)for v in allrefs-selected.keys()]
 heads=sorted(int(v,16)for v in candidate['entry_heads']);assert not(set(heads)&selected.keys())
 header='#pragma once\n'
 for v in sorted(set(heads)|selected.keys()):header+=f'extern "C" Memory*sub_{v:x}(State&,addr_t,Memory*);\n'
 header+='static constexpr recomp::Trace kUnwindTraces[]={'+','.join('{'+hex(v)+f',sub_{v:x}'+'}'for v in sorted(selected))+'};\n'
 header+='static constexpr std::array<recomp::Trace,27> kUnwindNewTraces={{'+','.join('{'+hex(v)+f',sub_{v:x}'+'}'for v in heads)+'}};\n';(out/'unwind_cases_traces.h').write_text(header)
 elf=W/'windows-first-frame-phdr1/native/libil2cpp.so'
 with elf.open('rb')as f:
  image=ELFFile(f)
  for name,address in [('code',0x2620000),('tables',0x5b60000)]:
   segment=next(s for s in image.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=address<address+65536<=s['p_vaddr']+s['p_filesz']);(out/(name+'.bin')).write_bytes(segment.data()[address-segment['p_vaddr']:address-segment['p_vaddr']+65536])
 result={'passed':True,'candidate':descriptor(a.candidate),'original_ELF':descriptor(elf),'code':descriptor(out/'code.bin'),'tables':descriptor(out/'tables.bin'),'traces_header':descriptor(out/'unwind_cases_traces.h'),'raw_ir':outputs['raw'],'polled_ir':outputs['polled'],'retained_projections':proofs,'retained_heads':[hex(v)for v in sorted(selected)],'new_heads':[hex(v)for v in heads],'original_imports':['0x820cb8d0','0x820cbb10'],'architecture_bytes':800,'full_state_bytes':1200,'opaque_token_bytes':64,'case_count':55,'excluded_original_LDURSH':['0x82625a98','0x82625d78'],'abort_policy':'Capture only after original BLabort reached; original abort body never executes or returns. TEST-only capture is not production behavior.'}
 (out/'projection.json').write_text(json.dumps(result,indent=2)+'\n');print('UNWIND-PROJECTION',len(selected),sha(out/'projection.json'))
if __name__=='__main__':main()
