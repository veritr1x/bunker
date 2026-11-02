"""FCSEL scalar registers/condition aliases remain value operands, never memory."""
import argparse,hashlib,json,subprocess
from pathlib import Path
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
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext context;auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int width,d,n,m,cond;unsigned count=0;const char*conditions[]={"EQ","NE","CS","CC","MI","PL","VS","VC","HI","LS","GE","LT","GT","LE","AL","AL"};
while(std::cin>>std::hex>>word>>std::dec>>width>>d>>n>>m>>cond){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool v,const char*why){if(!v)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool fcsel=inst.function.find("FCSEL_S_")==0||inst.function.find("FCSEL_D_")==0;
if(width>0){check(ok&&fcsel,"valid scalar FCSEL");check(inst.function==std::string(width==32?"FCSEL_S_FLOATSEL_":"FCSEL_D_FLOATSEL_")+conditions[cond],"condition suffix/inversion selector");check(inst.next_pc==0x1004&&inst.operands.size()==3,"fallthrough/three value operands");for(unsigned i=0;i<3;++i)check(inst.operands[i].type==remill::Operand::kTypeRegister,"scalar source is not a memory/address operand");auto&dst=inst.operands[0];check(dst.action==remill::Operand::kActionWrite&&dst.size==128&&dst.reg.name=="V"+std::to_string(d),"whole vector destination");for(unsigned i=1;i<3;++i){auto&s=inst.operands[i];check(s.action==remill::Operand::kActionRead&&s.size==unsigned(width)&&s.reg.name==std::string(width==32?"S":"D")+std::to_string(i==1?n:m),"typed scalar numeric source register");}}
else{check(!fcsel,"neighbor cannot become FCSEL");if(width==-1)check(ok,"existing neighbor stays supported");else check(!ok,"half/reserved baseline remains unsupported");}std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"FCSEL-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for path,pin in pins.items():assert sha(path)==pin
 source=a.out/'probe.cpp';source.write_text(PROBE);binary=a.out/'probe'
 with(a.out/'build.log').open('w')as log:subprocess.run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary],stdout=log,stderr=subprocess.STDOUT,check=True)
 records=[]
 def add(width,d,n,m,c):records.append(((0x1e200c00 if width==32 else 0x1e600c00)|(m<<16)|(c<<12)|(n<<5)|d,width,d,n,m,c))
 for width in(32,64):
  for cond in range(16):
   for r in range(32):add(width,r,1,2,cond);add(width,0,r,2,cond);add(width,0,1,r,cond)
 controls=[(0x1ee00c00,0),(0x1ea00c00,0),(0x3e200c00,0),(0x1e2e1000,-1),(0x1e204020,-1),(0x1e604020,-1),(0xbd400020,-1),(0xbd000020,-1),(0x9a820020,-1)]
 records.extend((w,kind,0,0,0,0)for w,kind in controls);corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{w:08x} {width} {d} {n} {m} {c}\n'for w,width,d,n,m,c in records))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'FCSEL-DECODE-SUCCESS {len(records)}'
 for path,pin in pins.items():assert sha(path)==pin
 (a.out/'acceptance.json').write_text(json.dumps({'passed':True,'controls':len(records),'frozen_libraries':pins,'evidence':{f.name:sha(f)for f in a.out.iterdir()if f.is_file()}},indent=2)+'\n');print(f'FCSEL decoder PASS {len(records)}',flush=True)
if __name__=='__main__':main()
