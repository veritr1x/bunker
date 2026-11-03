"""Unsigned widening-add operands, half selection and reserved-size boundaries."""
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
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext context;auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int bits,d,n,m,high;unsigned count=0;
while(std::cin>>std::hex>>word>>std::dec>>bits>>d>>n>>m>>high){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool v,const char*why){if(!v)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool family=inst.function.find("CMHI_ASIMDSAME_ONLY_")==0||inst.function=="CMHI_ASISDSAME_ONLY";
if(bits>0){std::string arr=bits==8?(high?"16B":"8B"):bits==16?(high?"8H":"4H"):bits==32?(high?"4S":"2S"):"2D";check(ok&&family&&inst.function==(high==2?"CMHI_ASISDSAME_ONLY":"CMHI_ASIMDSAME_ONLY_"+arr),"exact unsigned compare selector");check(inst.next_pc==0x1004&&inst.operands.size()==3,"three operands/fallthrough");for(unsigned i=0;i<3;++i){auto&o=inst.operands[i];bool scalar=high==2&&i;check(o.type==remill::Operand::kTypeRegister&&o.size==(scalar?64:128)&&o.reg.name==(scalar?"D":"V")+std::to_string(i==0?d:i==1?n:m),"numeric scalar/full vector transport");check(o.action==(i?remill::Operand::kActionRead:remill::Operand::kActionWrite),"operand direction");}}
else{if(bits==-1)check(ok&&!family,"existing neighbor stays supported without becoming CMHI");else check(!ok,"reserved/signed/other-compare baseline stays unsupported");}std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"CMHI-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for n,h in pins.items():assert sha(n)==h
 src=a.out/'probe.cpp';src.write_text(PROBE);binary=a.out/'probe'
 with(a.out/'build.log').open('w')as log:subprocess.run([recipe['compiler'],*recipe['compile_flags'],src,*recipe['link_flags'],'-o',binary],stdout=log,stderr=subprocess.STDOUT,check=True)
 rows=[]
 def add(size,q,d,n,m):rows.append(((0x7ee03400 if q==2 else 0x2e203400|(size<<22)|(q<<30))|(m<<16)|(n<<5)|d,8<<size,d,n,m,q))
 for size in range(4):
  for q in(0,1,2):
   if(size==3 and q==0)or(size!=3 and q==2):continue
   for r in range(32):add(size,q,r,1,2);add(size,q,0,r,2);add(size,q,0,1,r);add(size,q,r,r,r)
 rows.append((0x6eb034b0,32,16,5,16,1))
 controls=[(0x2ee03400,0),(0x7e203400,0),(0x7e603400,0),(0x7ea03400,0),(0x2e203c00,0),(0x6e203c00,0),(0x0e203400,-1),(0x4e203400,-1),(0x2e641047,-1),(0x6f08a403,-1),(0x1e24c000,-1),(0xbd400020,-1),(0xbd000020,-1)]
 rows.extend((w,kind,0,0,0,0)for w,kind in controls);corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{w:08x} {bits} {d} {n} {m} {h}\n'for w,bits,d,n,m,h in rows))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'CMHI-DECODE-SUCCESS {len(rows)}'
 for n,h in pins.items():assert sha(n)==h
 (a.out/'acceptance.json').write_text(json.dumps(dict(passed=True,cases=len(rows),frozen_libraries=pins,evidence={f.name:sha(f)for f in a.out.iterdir()if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
