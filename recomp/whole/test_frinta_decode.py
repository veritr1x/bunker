"""Initialized public decoder: all2048 scalar FRINTA register pairs and adjacent forms."""
from pathlib import Path
import argparse,hashlib,json,subprocess
PROBE=r'''
#include <remill/Arch/Arch.h>
#include <remill/Arch/Name.h>
#include <remill/OS/OS.h>
#include <remill/BC/Util.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <iostream>
#include <stdexcept>
int main(int argc,char**argv){try{if(argc!=2)return 2;llvm::LLVMContext context;auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});uint32_t word;int width,d,n;unsigned count=0;
while(std::cin>>std::hex>>word>>std::dec>>width>>d>>n){char bytes[4];for(unsigned i=0;i<4;i++)bytes[i]=char(word>>(i*8));remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());auto need=[&](bool value,const char*why){if(!value)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};bool family=inst.function.find("FRINTA_")==0;
if(width>0){need(ok&&family,"valid scalarFRINTA");need(inst.function==std::string("FRINTA_")+(width==32?"S_FLOATDP1":"D_FLOATDP1"),"exact scalar selector");need(inst.next_pc==0x1004&&inst.operands.size()==2,"two operands/fallthrough");auto&dst=inst.operands[0];auto&src=inst.operands[1];need(dst.type==remill::Operand::kTypeRegister&&dst.action==remill::Operand::kActionWrite&&dst.size==128&&dst.reg.name=="V"+std::to_string(d),"whole128 destination");need(src.type==remill::Operand::kTypeRegister&&src.action==remill::Operand::kActionRead&&src.size==unsigned(width)&&src.reg.name==std::string(width==32?"S":"D")+std::to_string(n),"numeric scalar source");}
else if(width==-1)need(ok&&!family,"existing supported neighbor stays separate");else need(!ok,"reserved/half/vector/otherrounding remains unsupported");std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";count++;}
std::cout<<"FRINTA-DECODE-SUCCESS "<<count<<"\n";}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--toolchain',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=False);recipe_path=a.toolchain/'decoder-link-recipe.json';recipe=json.loads(recipe_path.read_text());pins={row['frozen']:row['sha256']for row in recipe['libraries']}
 for name,digest in pins.items():assert sha(name)==digest
 source=a.out/'probe.cpp';source.write_text(PROBE);binary=a.out/'probe';command=[recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary]
 with(a.out/'build.log').open('w')as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True)
 rows=[((0x1e264000 if width==32 else 0x1e664000)|(n<<5)|d,width,d,n)for width in [32,64]for d in range(32)for n in range(32)];rows.append((0x1e264063,32,3,3))
 controls=[(0x1ee64000,0),(0x1ea64000,0),(0x2e218820,0),(0x6e218820,0),(0x2e618820,0),(0x6e618820,0),(0x9e264000,0),(0x3e264000,0),(0x1e244000,0),(0x1e25c000,0),(0x1e274000,0),(0x1e27c000,0),(0x1e24c000,-1),(0x1e254000,-1),(0x1e64c000,-1),(0x1e654000,-1),(0x1e204020,-1),(0x1e604020,-1),(0xbd400020,-1),(0xbd000020,-1)]
 rows.extend((word,width,0,0)for word,width in controls);corpus=a.out/'cases.txt';corpus.write_text(''.join(f'{word:08x} {width} {d} {n}\n'for word,width,d,n in rows))
 with corpus.open()as data,(a.out/'decoded.log').open('w')as log:subprocess.run([binary,a.toolchain],stdin=data,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert(a.out/'decoded.log').read_text().splitlines()[-1]==f'FRINTA-DECODE-SUCCESS {len(rows)}'
 for name,digest in pins.items():assert sha(name)==digest
 receipt=dict(passed=True,cases=len(rows),all_scalar_register_pairs=2048,original_literal_extra_case=True,adjacent_controls=len(controls),initialized_public_decoder=True,exact_operand_widths_and_names_and_actions=True,lifter=desc(a.toolchain/'remill-lift'),semantics=desc(a.toolchain/'aarch64.bc'),decoder_link_recipe=desc(recipe_path),actual_libraries=pins,probe_source=desc(source),probe_executable=desc(binary),case_corpus=desc(corpus),output=desc(a.out/'decoded.log'),owned_source=desc(Path(__file__).resolve()),scope='ScalarFRINTA S/D exact numeric register decoding; existing P/M remain separate supported neighbors; half/vector/reserved/other rounding controls rejected. No instruction execution/game claim.')
 (a.out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('FRINTA-DECODE-PASS',sha(a.out/'acceptance.json'))
if __name__=='__main__':main()
