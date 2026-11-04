"""Four scalar numeric min/max decoders and their exact value-carrier ABI.

The public architecture is initialized from the frozen semantics module. Old
FMIN/FMAX and excluded numeric vector/pairwise controls are compared against an
explicit frozen baseline; this is not an instruction-result or whole-ISA gate.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,traceback

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
PROBE=r'''
#include <remill/Arch/Arch.h>
#include <remill/Arch/Name.h>
#include <remill/OS/OS.h>
#include <remill/BC/Util.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Function.h>
#include <llvm/IR/GlobalVariable.h>
#include <iostream>
#include <stdexcept>
#include <string>
int main(int argc,char **argv){try{
 if(argc!=2)return 2;
 llvm::LLVMContext context;
 auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);
 auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});
 uint32_t word;int width,lanes,d,n,m;std::string op;unsigned count=0;
 while(std::cin>>std::hex>>word>>std::dec>>width>>lanes>>op>>d>>n>>m){
  char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char(word>>(i*8));
  remill::Instruction inst;const bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());
  auto check=[&](bool value,const char *why){if(!value)throw std::runtime_error(std::string(why)+" "+inst.Serialize());};
  if(width>0){
   const bool scalar=lanes==1;const auto suffix=scalar?std::string(width==32?"_S_FLOATDP2":"_D_FLOATDP2"):"_ASIMDSAME_ONLY_"+std::to_string(lanes)+(width==32?"S":"D");
   check(ok,"valid scalar numeric or unchanged legacy min/max");check(inst.function==op+suffix,"exact min/max selector");
   check(inst.next_pc==0x1004&&inst.operands.size()==3,"three operands and fallthrough");
   for(const auto &operand:inst.operands)check(operand.type==remill::Operand::kTypeRegister,"value operands must not become memory/address inputs");
   const auto &dst=inst.operands[0];check(dst.action==remill::Operand::kActionWrite&&dst.size==128&&dst.reg.name=="V"+std::to_string(d),"whole128 vector destination for upper-bit clearing");
   const unsigned bits=scalar?unsigned(width):unsigned(width*lanes);
   const std::string prefix=scalar?(width==32?"S":"D"):(bits==64?"D":"Q");
   for(unsigned i=1;i<3;++i){const auto &src=inst.operands[i];check(src.action==remill::Operand::kActionRead&&src.size==bits&&src.reg.name==prefix+std::to_string(i==1?n:m),"exact typed numeric source register");}
   if(scalar){
    auto *selector=semantics->getGlobalVariable("ISEL_"+inst.function);
    check(selector&&selector->hasInitializer(),"frozen scalar selector exists");
    auto *function=llvm::dyn_cast<llvm::Function>(selector->getInitializer()->stripPointerCasts());
    check(function&&!function->isDeclaration()&&function->arg_size()==5,"scalar semantics actual function ABI");
    auto *type=function->getFunctionType();
    check(type->getReturnType()->isPointerTy()&&type->getParamType(0)->isPointerTy()&&type->getParamType(1)->isPointerTy(),"Memory/State ABI");
    check(type->getParamType(2)->isIntegerTy(64)&&type->getParamType(3)->isIntegerTy(64)&&type->getParamType(4)->isIntegerTy(64),"dest address and numeric sources are64-bit value carriers, never floating-bit pointers");
    check(function->getName().contains(width==32?"vec32_t":"vec64_t"),"exact V32/V64 source instantiation");
   }
  }else check(!ok,"reserved, half, numeric vector/pairwise remain unsupported");
  std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;
 }
 std::cout<<"FP-NUMERIC-MINMAX-DECODE-SUCCESS "<<count<<"\n";
 }catch(const std::exception &error){std::cerr<<error.what()<<"\n";return 1;}}
'''

def scalar(op,width,d,n,m,ftype=None):
 return (0x1e207800 if op=='FMINNM'else 0x1e206800 if op=='FMAXNM'else 0x1e205800 if op=='FMIN'else 0x1e204800)|(((width==64)if ftype is None else ftype)<<22)|(m<<16)|(n<<5)|d

def corpus():
 numeric=[];neighbors=[]
 for op in('FMINNM','FMAXNM'):
  for width in(32,64):
   for register in range(32):
    for d,n,m in((register,7,19),(11,register,19),(11,7,register),(register,register,register),(register,register,(register+11)%32),(register,(register+17)%32,register),((register+3)%32,register,register)):
     numeric.append((scalar(op,width,d,n,m),width,1,op,d,n,m))
 numeric.append((0x1e217800,32,1,'FMINNM',0,0,1))
 aliases=((0,1,2),(31,31,31),(31,0,31),(0,31,0),(9,17,23))
 for op in('FMINNM','FMAXNM'):
  for ftype in(2,3):
   for d,n,m in aliases:neighbors.append((scalar(op,32,d,n,m,ftype),0,0,'REJECT',d,n,m))
  for width,lanes in((32,2),(32,4),(64,2)):
   for d,n,m in aliases:
    word=0x0e20c400|((op=='FMINNM')<<23)|((width==64)<<22)|((width*lanes==128)<<30)|(m<<16)|(n<<5)|d
    neighbors.extend(((word,0,0,'REJECT',d,n,m),(word|0x20000000,0,0,'REJECT',d,n,m)))
  for width in(32,64):
   for d,n,_ in aliases:
    word=(0x7eb0c800 if op=='FMINNM'else 0x7e30c800)|((width==64)<<22)|(n<<5)|d
    neighbors.append((word,0,0,'REJECT',d,n,0))
 for op in('FMIN','FMAX'):
  for width in(32,64):
   for d,n,m in aliases:neighbors.append((scalar(op,width,d,n,m),width,1,op,d,n,m))
  for width,lanes in((32,2),(32,4),(64,2)):
   for d,n,m in aliases:
    word=0x0e20f400|((op=='FMIN')<<23)|((width==64)<<22)|((width*lanes==128)<<30)|(m<<16)|(n<<5)|d
    neighbors.append((word,width,lanes,op,d,n,m))
 return numeric,neighbors

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--toolchain',type=Path,required=True);parser.add_argument('--baseline-toolchain',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);commands=[];held={};numeric,neighbors=corpus()
 def write_rows(path,rows):path.write_text(''.join(f'{word:08x} {width} {lanes} {op} {d} {n} {m}\n'for word,width,lanes,op,d,n,m in rows))
 def run(argv,label,stdin=None):
  argv=list(map(str,argv));commands.append(dict(label=label,argv=argv));(a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  with(a.out/(label+'.log')).open('w')as log:subprocess.run(argv,stdin=stdin,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  held[str(Path(__file__).resolve())]=sha(__file__)
  source=a.out/'probe.cpp';source.write_text(PROBE)
  for label,toolchain,rows in [('new',a.toolchain,numeric+neighbors),('baseline',a.baseline_toolchain,neighbors)]:
   toolchain=toolchain.resolve();recipe_path=toolchain/'decoder-link-recipe.json';recipe=json.loads(recipe_path.read_bytes());held[str(recipe_path)]=sha(recipe_path)
   for row in recipe['libraries']:assert sha(row['frozen'])==row['sha256'];held[row['frozen']]=row['sha256']
   semantics=toolchain/'aarch64.bc';held[str(semantics)]=sha(semantics)
   binary=a.out/(label+'-probe');run([recipe['compiler'],*recipe['compile_flags'],source,*recipe['link_flags'],'-o',binary],label+'-build')
   inputs=a.out/(label+'-cases.txt');write_rows(inputs,rows)
   with inputs.open()as data:run([binary,toolchain],label+'-decoded',data)
   lines=(a.out/(label+'-decoded.log')).read_text().splitlines();assert lines[-1]==f'FP-NUMERIC-MINMAX-DECODE-SUCCESS {len(rows)}'
  newlines=(a.out/'new-decoded.log').read_text().splitlines();oldlines=(a.out/'baseline-decoded.log').read_text().splitlines()
  assert newlines[len(numeric):-1]==oldlines[:-1],'Legacy and excluded-neighbor serialization changed'
  for path,digest in held.items():assert sha(path)==digest,path
  receipt=dict(passed=True,scope='Public initialized architecture decoder operands and frozen selector value ABI only; no original instruction-result or game qualification',numeric_cases=len(numeric),independent_register_rows=384,mixed_alias_rows=512,original_word='1e217800',neighbor_cases=len(neighbors),old_FMIN_FMAX_scalar_vector_and_excluded_numeric_neighbors_byteexact=True,all32_Rd_Rn_Rm_and_mixed_aliases=True,destination_V128_for_upper_clear=True,numeric_V32_V64_sources_not_float_bit_pointers=True,half_reserved_vector_pairwise_unexpanded=True,held_inputs=held,commands=commands,evidence={p.name:sha(p)for p in a.out.iterdir()if p.is_file()})
  (a.out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('FP-NUMERIC-MINMAX-DECODE-PASS',len(numeric)+len(neighbors),sha(a.out/'acceptance.json'),flush=True)
 except BaseException as error:
  (a.out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
