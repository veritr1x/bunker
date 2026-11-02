"""USHLL legal/reserved encoding boundaries and exact original Unity bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from elftools.elf.elffile import ELFFile
from compile import freeze_toolchain


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--semantics-dir',type=Path)
    parser.add_argument('--unity',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out;out.mkdir(parents=True)
    lift,semantics,hashes=freeze_toolchain(args.lift,args.semantics_dir,out)

    def run(name,raw,address,entry,unsupported):
        ir=out/(name+'.ll')
        command=[str(lift),'--arch','aarch64','--os','linux','--semantics_dir',str(semantics),
                 '--bytes_file',str(raw),'--address',hex(address),'--entry_address',hex(entry),'--ir_out',str(ir)]
        with (out/(name+'.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        body=re.search(r'^define[^\n]*@sub_'+f'{entry:x}'+r'\([^\n]*\).*?^}',ir.read_text(),re.M|re.S).group()
        error=bool(re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',body))
        assert error==unsupported,(name,error,unsupported)
        return dict(case=name,entry=hex(entry),unsupported=error,reads_v17='%V17' in body,command=command,
                    ir_sha256=hashlib.sha256(ir.read_bytes()).hexdigest())

    results=[]
    for q in (0,1):
        for immh in range(16):
            for immb in range(8):
                word=0x2f00a400|(q<<30)|(immh<<19)|(immb<<16)|(17<<5)|31
                name=f'Q{q}_immh{immh}_immb{immb}'
                raw=out/(name+'.bin');raw.write_bytes(struct.pack('<II',word,0xd65f03c0))
                record=run(name,raw,0x1000,0x1000,immh>=8)
                if immh==0:
                    assert not record['reads_v17'],'immh0 belongs to modified-immediate MOVI, not USHLL'
                    record['family']='separate MOVI modified-immediate encoding'
                elif immh<8:
                    assert record['reads_v17'],'valid USHLL must read the original source'
                    record['family']='USHLL/USHLL2'
                record['word']=f'{word:08x}';results.append(record)
    for name,word,unsupported in [('actual_unity_70413eb0',0x2f20a400,False),
                                  ('signed_sshll_unchanged',0x0f20a400,True),
                                  ('fixed_shift_shll_unchanged',0x2e213800,True)]:
        raw=out/(name+'.bin');raw.write_bytes(struct.pack('<II',word,0xd65f03c0))
        record=run(name,raw,0x70413eb0,0x70413eb0,unsupported)
        record['word']=f'{word:08x}';results.append(record)
    digest=hashlib.sha256(args.unity.read_bytes()).hexdigest()
    assert digest=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
    with args.unity.open('rb') as stream:
        elf=ELFFile(stream);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_flags']&1]
        start=min(s['p_vaddr'] for s in segments);end=max(s['p_vaddr']+s['p_filesz'] for s in segments)
        image=bytearray(end-start)
        for segment in segments:image[segment['p_vaddr']-start:segment['p_vaddr']-start+segment['p_filesz']]=segment.data()
    assert struct.unpack_from('<I',image,0x413eb0-start)[0]==0x2f20a400
    raw=out/'original-unity-executable.bin';raw.write_bytes(image)
    result=run('original_zip_enumerator_70413e00',raw,0x70000000+start,0x70413e00,False)
    result.update(original_elf_sha256=digest,reached_ushll_pc='0x70413eb0',historical_error_next_pc='0x70413eb4');results.append(result)
    assert len(results)==260
    (out/'acceptance.json').write_text(json.dumps(dict(passed=True,controls=len(results),toolchain=hashes,results=results),indent=2)+'\n')
    print(f'USHLL decode PASS: {len(results)} controls, including actual original ZIP enumerator')


if __name__=='__main__':main()
