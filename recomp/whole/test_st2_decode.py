"""ST2 multiple structured operands, writeback and unchanged neighbors."""
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
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext ctx;auto arch=remill::Arch::Build(&ctx,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int q,size,rt,rn,mode,rm;unsigned count=0;
while(std::cin>>std::hex>>word>>std::dec>>q>>size>>rt>>rn>>mode>>rm){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool x,const char*why){if(!x)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};
if(q>=0){std::string arr=size==0?(q?"16B":"8B"):size==1?(q?"8H":"4H"):size==2?(q?"4S":"2S"):"2D";std::string prefix=mode==0?"ST2_ASISDLSE_R2_":mode==1?"ST2_ASISDLSEP_I2_I_":"ST2_ASISDLSEP_R2_R_";check(ok&&inst.function==prefix+arr,"exact ST2 multiple selector");check(inst.next_pc==0x1004&&inst.operands.size()==unsigned(mode?5:3),"operand count/fallthrough");for(unsigned i=0;i<2;++i){auto&o=inst.operands[i];check(o.type==remill::Operand::kTypeRegister&&o.action==remill::Operand::kActionRead&&o.size==unsigned(q?128:64)&&o.reg.name==std::string(q?"Q":"D")+std::to_string((rt+i)&31),"natural vector source and Rt wrap");}std::string base=rn==31?"SP":"X"+std::to_string(rn);auto&o=inst.operands[2];check(o.type==remill::Operand::kTypeAddress&&o.action==remill::Operand::kActionWrite&&o.size==unsigned(q?256:128)&&o.addr.kind==remill::Operand::Address::kMemoryWrite&&o.addr.base_reg.name==base&&o.addr.address_size==64&&o.addr.displacement==0&&o.addr.index_reg.name.empty(),"exact memory write span/base");if(mode){auto&w=inst.operands[3];auto&n=inst.operands[4];check(w.type==remill::Operand::kTypeRegister&&w.action==remill::Operand::kActionWrite&&w.size==64&&w.reg.name==base,"base writeback destination");check(n.type==remill::Operand::kTypeAddress&&n.action==remill::Operand::kActionRead&&n.size==64&&n.addr.kind==remill::Operand::Address::kAddressCalculation&&n.addr.base_reg.name==base&&n.addr.address_size==64,"next address calculation");if(mode==1)check(n.addr.displacement==(q?32:16)&&n.addr.index_reg.name.empty(),"post immediate exact byte count");else check(n.addr.index_reg.name=="X"+std::to_string(rm)&&n.addr.scale==1&&n.addr.displacement==0,"post register unscaled snapshot");}}
else{if(q==-1)check(!ok,"reserved or single-lane baseline remains unsupported");else check(ok&&inst.function.find("ST2_ASISDLSE")==std::string::npos,"old supported neighbor remains outside ST2 multiple");}std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"ST2-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for n,h in pins.items():assert sha(n)==h
 source=a.out/'probe.cpp';source.write_text(PROBE);exe=a.out/'probe'
 with(a.out/'build.log').open('w')as f:subprocess.run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',exe],stdout=f,stderr=subprocess.STDOUT,check=True)
 rows=[]
 def add(q,size,rt,rn,mode,rm):
  w=0x0c008000|(q<<30)|(size<<10)|(rn<<5)|rt
  if mode:w|=0x00800000|((31 if mode==1 else rm)<<16)
  rows.append((w,q,size,rt,rn,mode,rm))
 for q,size in [(0,0),(1,0),(0,1),(1,1),(0,2),(1,2),(1,3)]:
  for mode in range(3):
   for r in range(32):add(q,size,r,r,mode,r if r<31 else 0)
 for mode in range(3):
  for r in (0,31):
   word=0x0c008000|(3<<10)|(r<<5)|r
   if mode:word|=0x00800000|((31 if mode==1 else 12)<<16)
   rows.append((word,-1,0,0,0,0,0))
 rows.extend((w,kind,0,0,0,0,0)for w,kind in[(0x0d200180,-1),(0x4d208180,-1),(0x4c000180,-2),(0x4c007180,-2),(0x3d800180,-2),(0xd503201f,-2)])
 rows.append((0x4c008d80,1,3,0,12,0,20));corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{w:08x} {q} {s} {t} {n} {m} {r}\n'for w,q,s,t,n,m,r in rows))
 with corpus.open()as f,(a.out/'decoded.log').open('w')as log:subprocess.run([exe,a.toolchain],stdin=f,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'ST2-DECODE-SUCCESS {len(rows)}'
 for n,h in pins.items():assert sha(n)==h
 (a.out/'acceptance.json').write_text(json.dumps(dict(passed=True,cases=len(rows),frozen_libraries=pins,evidence={f.name:sha(f)for f in a.out.iterdir()if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
