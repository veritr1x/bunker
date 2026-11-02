"""Four scalar FRINTP/M decoders: exact numeric operands and adjacent boundaries."""
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
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext context;auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int width,d,n,plus;unsigned count=0;
while(std::cin>>std::hex>>word>>std::dec>>width>>d>>n>>plus){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool v,const char*why){if(!v)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool family=inst.function.find("FRINTP_")==0||inst.function.find("FRINTM_")==0;
if(width>0){check(ok&&family,"valid scalar FRINTP/M");check(inst.function==std::string(plus?"FRINTP_":"FRINTM_")+(width==32?"S_FLOATDP1":"D_FLOATDP1"),"exact scalar selector");check(inst.next_pc==0x1004&&inst.operands.size()==2,"two operands/fallthrough");auto&dst=inst.operands[0];auto&src=inst.operands[1];check(dst.type==remill::Operand::kTypeRegister&&dst.action==remill::Operand::kActionWrite&&dst.size==128&&dst.reg.name=="V"+std::to_string(d),"whole destination");check(src.type==remill::Operand::kTypeRegister&&src.action==remill::Operand::kActionRead&&src.size==unsigned(width)&&src.reg.name==std::string(width==32?"S":"D")+std::to_string(n),"scalar numeric source, never address");}
else if(width==-1){check(ok&&!family,"existing neighbor remains separate/supported");}else check(!ok,"half/vector/reserved/other-rounding baseline remains unsupported");std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"FRINT-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for n,h in pins.items():assert sha(n)==h
 source=a.out/'probe.cpp';source.write_text(PROBE);binary=a.out/'probe'
 with(a.out/'build.log').open('w')as log:subprocess.run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary],stdout=log,stderr=subprocess.STDOUT,check=True)
 rows=[]
 for width in(32,64):
  for plus in(0,1):
   for d in range(32):
    for n in range(32):rows.append((((0x1e24c000 if width==32 else 0x1e64c000)+(0 if plus else 0x8000))|(n<<5)|d,width,d,n,plus))
 rows.extend((word,width,d,n,plus)for word,width,d,n,plus in[(0x1e24c008,32,8,0,1),(0x1e254000,32,0,0,0),(0x1e64c000,64,0,0,1),(0x1e654000,64,0,0,0)])
 # H and ftype10 are deliberately not included in the four-form implementation.
 controls=[(0x1ee4c000,0),(0x1ee54000,0),(0x1ea4c000,0),(0x1ea54000,0),(0x0ea18820,0),(0x4ea18820,0),(0x0e219820,0),(0x4e219820,0),(0x1e244000,0),(0x1e264000,0),(0x1e27c000,0),(0x1e274000,0),(0x1e25c000,0),(0x1e204020,-1),(0x1e604020,-1),(0x1e201c20,-1),(0xbd400020,-1),(0xbd000020,-1)]
 rows.extend((w,kind,0,0,0)for w,kind in controls);corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{word:08x} {width} {d} {n} {plus}\n'for word,width,d,n,plus in rows))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'FRINT-DECODE-SUCCESS {len(rows)}'
 for n,h in pins.items():assert sha(n)==h
 (a.out/'acceptance.json').write_text(json.dumps(dict(passed=True,cases=len(rows),frozen_libraries=pins,evidence={f.name:sha(f)for f in a.out.iterdir()if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
