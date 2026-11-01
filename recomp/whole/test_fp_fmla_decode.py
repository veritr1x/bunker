"""Indexed FMLA encoding controls and the exact original Unity matrix routine."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from elftools.elf.elffile import ELFFile
from compile import freeze_toolchain

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--semantics-dir',type=Path)
    parser.add_argument('--unity',type=Path,help='Optional original pinned libunity.so for exact original-code liftability proof')
    args=parser.parse_args();out=HERE.parent/'work/fp-fmla-decode';out.mkdir(exist_ok=True,parents=True)
    lift,semantics,hashes=freeze_toolchain(args.lift,args.semantics_dir,out)

    def run(name,raw,address,entry,unsupported):
        ir=out/(name+'.ll')
        command=[str(lift),'--arch','aarch64','--os','linux','--semantics_dir',str(semantics),
                 '--bytes_file',str(raw),'--address',hex(address),'--entry_address',hex(entry),'--ir_out',str(ir)]
        with (out/(name+'.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        body=re.search(r'^define[^\n]*@sub_'+f'{entry:x}'+r'\([^\n]*\).*?^}',ir.read_text(),re.M|re.S).group()
        error=bool(re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',body))
        if error!=unsupported:raise RuntimeError(f'Unexpected decoder result for {name}: unsupported={error}')
        return {'case':name,'entry':hex(entry),'unsupported':error,'body_lines':len(body.splitlines()),'command':command}

    controls=[('actual_unity_4fa01234',0x4fa01234,False),('legal_vector_D',0x4fc21020,False),
              ('legal_scalar_D',0x5fc21020,False),('reserved_vector_D_Q0',0x0fc21020,True),
              ('reserved_vector_D_L1',0x4fe21020,True),('reserved_scalar_D_L1',0x5fe21020,True)]
    results=[]
    for name,word,unsupported in controls:
        raw=out/(name+'.bin');raw.write_bytes(struct.pack('<II',word,0xd65f03c0))
        result=run(name,raw,0x1000,0x1000,unsupported);result['opcode']=f'{word:08x}';results.append(result)
    if args.unity:
        digest=hashlib.sha256(args.unity.read_bytes()).hexdigest()
        if digest!='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f':raise RuntimeError('Original Unity proof requires the pinned game ELF')
        with args.unity.open('rb') as stream:
            elf=ELFFile(stream);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_flags']&1]
            start=min(s['p_vaddr']for s in segments);end=max(s['p_vaddr']+s['p_filesz']for s in segments)
            image=bytearray(end-start)
            for segment in segments:image[segment['p_vaddr']-start:segment['p_vaddr']-start+segment['p_filesz']]=segment.data()
        if struct.unpack_from('<I',image,0x91bd08-start)[0]!=0x4fa01234:raise RuntimeError('Original FMLA bytes changed')
        raw=out/'original-unity-executable.bin';raw.write_bytes(image)
        result=run('original_matrix_7091bce0',raw,0x70000000+start,0x7091bce0,False)
        result['original_elf_sha256']=digest;result['actual_fmla_pc']='0x7091bd08';results.append(result)
    (out/'acceptance.json').write_text(json.dumps({'passed':True,'toolchain':hashes,'results':results},indent=2)+'\n')
    print(f'Indexed FMLA decode/original-code gate PASS: {len(results)} controls')


if __name__=='__main__':main()
