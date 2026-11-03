"""Bounded scalar unsigned fixed-point decoder: scale, registers, numeric source ABI."""
from pathlib import Path
import argparse,hashlib,json,subprocess

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
PROBE=r'''
#include <remill/Arch/Arch.h>
#include <remill/Arch/Name.h>
#include <remill/OS/OS.h>
#include <remill/BC/Util.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <iostream>
#include <stdexcept>
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext context;auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int width,out,d,n,fbits;unsigned count=0;
while(std::cin>>std::hex>>word>>std::dec>>width>>out>>d>>n>>fbits){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool v,const char*why){if(!v)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool family=inst.function.find("FCVTZU_")==0&&inst.function.find("FLOAT2FIX")!=std::string::npos;
if(width>0){check(ok,"valid scalar unsigned FCVTZU");check(inst.function==std::string("FCVTZU_")+(out==32?"32":"64")+(width==32?"S":"D")+(fbits?"_FLOAT2FIX":"_FLOAT2INT"),"exact selector");check(inst.next_pc==0x1004&&inst.operands.size()==unsigned(fbits?3:2),"three operands/fallthrough");auto&dst=inst.operands[0];auto&src=inst.operands[1];check(dst.type==remill::Operand::kTypeRegister&&dst.action==remill::Operand::kActionWrite&&dst.size==64&&dst.reg.name==(d==31?"IGNORE_WRITE_TO_XZR":"X"+std::to_string(d)),"GPR destination/zero-extension/ZR not SP");check(src.type==remill::Operand::kTypeRegister&&src.action==remill::Operand::kActionRead&&src.size==unsigned(width)&&src.reg.name==std::string(width==32?"S":"D")+std::to_string(n),"numeric scalar source");if(fbits){auto&imm=inst.operands[2];check(imm.type==remill::Operand::kTypeImmediate&&imm.size==64&&!imm.imm.is_signed&&imm.imm.val==unsigned(fbits),"unsigned decoded fbits");}}
else if(width==-1)check(ok&&!family,"existing supported separate neighbor");else check(!ok,"reserved/half unchanged unsupported");std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"FCVTZU_FIXED-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def word(w,o,d,n,f):return 0x1e190000|((o==64)<<31)|((w==64)<<22)|((64-f)<<10)|(n<<5)|d

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for n,h in pins.items():assert sha(n)==h
 source=a.out/'probe.cpp';source.write_text(PROBE);binary=a.out/'probe'
 with(a.out/'build.log').open('w')as log:subprocess.run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary],stdout=log,stderr=subprocess.STDOUT,check=True)
 rows=[]
 for w in(32,64):
  for o in(32,64):
   for f in range(1,o+1):rows.append((word(w,o,9,0,f),w,o,9,0,f))
   for d in range(32):rows.append((word(w,o,d,7,10),w,o,d,7,10))
   for n in range(32):rows.append((word(w,o,17,n,10),w,o,17,n,10))
 for w in(32,64):
  for scale in range(32):rows.append((word(w,32,0,0,64-scale),0,0,0,0,0))
 rows.append((0x9e19d809,32,64,9,0,10))
 for w,o,d,n in ((32,64,8,0),(32,32,17,31),(64,32,5,31),(64,64,17,7)):
  rows.append((0x1e390000|((o==64)<<31)|((w==64)<<22)|(n<<5)|d,w,o,d,n,0))
 for o in(32,64):
  for ftype in(2,3):rows.append(((word(32,o,0,0,10)&~(3<<22))|(ftype<<22),0,0,0,0,0))
 for word_ in(0x1e390000,0x9e390000,0x1e790000,0x9e790000,0x9e230120,0x1e230000,0x1e204020,0x1e604020,0xbd400020,0xbd000020):rows.append((word_,-1,0,0,0,0))
 corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{word_:08x} {w} {o} {d} {n} {f}\n'for word_,w,o,d,n,f in rows))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'FCVTZU_FIXED-DECODE-SUCCESS {len(rows)}'
 for n,h in pins.items():assert sha(n)==h
 (a.out/'acceptance.json').write_text(json.dumps(dict(passed=True,cases=len(rows),legal_scale_encodings=192,register_rows=256,original_word='9e19d809',frozen_libraries=pins,evidence={f.name:sha(f)for f in a.out.iterdir()if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
