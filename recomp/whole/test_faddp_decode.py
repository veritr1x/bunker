"""Four scalar FADDP decoders: exact numeric operands and adjacent boundaries."""
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
while(std::cin>>std::hex>>word>>std::dec>>width>>d>>n>>plus){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto check=[&](bool v,const char*why){if(!v)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool family=inst.function.find("FADDP_ASISDPAIR_ONLY_SD_")==0;
if(width>0){check(ok&&family,"valid scalar FADDP");check(inst.function==std::string("FADDP_ASISDPAIR_ONLY_SD_")+(width==32?"S":"D"),"exact scalar selector");check(inst.next_pc==0x1004&&inst.operands.size()==2,"two operands/fallthrough");auto&dst=inst.operands[0];auto&src=inst.operands[1];check(dst.type==remill::Operand::kTypeRegister&&dst.action==remill::Operand::kActionWrite&&dst.size==128&&dst.reg.name=="V"+std::to_string(d),"whole destination");check(src.type==remill::Operand::kTypeRegister&&src.action==remill::Operand::kActionRead&&src.size==128&&src.reg.name=="V"+std::to_string(n),"full snapshotted vector source");}
else if(width==-1){check(ok&&!family,"existing neighbor remains separate/supported");}else check(!ok,"half/vector/reserved/other-rounding baseline remains unsupported");std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;}
std::cout<<"FADDP-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False);recipe=json.loads((a.toolchain/'decoder-link-recipe.json').read_text());pins={x['frozen']:x['sha256']for x in recipe['libraries']}
 for n,h in pins.items():assert sha(n)==h
 source=a.out/'probe.cpp';source.write_text(PROBE);binary=a.out/'probe'
 with(a.out/'build.log').open('w')as log:subprocess.run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary],stdout=log,stderr=subprocess.STDOUT,check=True)
 rows=[]
 for width in(32,64):
  for d in range(32):
   for n in range(32):rows.append(((0x7e30d800 if width==32 else 0x7e70d800)|(n<<5)|d,width,d,n,0))
 rows.append((0x7e30d800,32,0,0,0))
 controls=[(0x5e30d800,0),(0x5e70d800,0),(0x2e22d420,-1),(0x6e22d420,-1),(0x6e62d420,-1),(0x1e222820,-1),(0xbd400020,-1),(0xbd000020,-1)]
 rows.extend((w,kind,0,0,0)for w,kind in controls);corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{word:08x} {width} {d} {n} {plus}\n'for word,width,d,n,plus in rows))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'FADDP-DECODE-SUCCESS {len(rows)}'
 for n,h in pins.items():assert sha(n)==h
 (a.out/'acceptance.json').write_text(json.dumps(dict(passed=True,cases=len(rows),frozen_libraries=pins,evidence={f.name:sha(f)for f in a.out.iterdir()if f.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
