// Canonical recursive LLVM State layout, including offsets/sizes/alignment.
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/DerivedTypes.h>
#include <llvm/IR/DataLayout.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <fstream>
#include <string>
std::string Shape(llvm::Type *type,const llvm::DataLayout &layout){
  const std::string facts=type->isSized()?"[size="+std::to_string(layout.getTypeAllocSize(type).getFixedValue())+",abi="+std::to_string(layout.getABITypeAlign(type).value())+"]":"";
  if(auto *structure=llvm::dyn_cast<llvm::StructType>(type)){
    if(structure->isOpaque())return "opaque";
    auto *shape=layout.getStructLayout(structure);
    std::string result="struct("+std::to_string(structure->isPacked())+",size="+std::to_string(shape->getSizeInBytes())+",align="+std::to_string(shape->getAlignment().value())+":";
    for(unsigned i=0;i<structure->getNumElements();++i)result+=std::to_string(shape->getElementOffset(i))+"="+Shape(structure->getElementType(i),layout)+";";
    return result+")";
  }
  if(auto *array=llvm::dyn_cast<llvm::ArrayType>(type))return facts+"["+std::to_string(array->getNumElements())+"x"+Shape(array->getElementType(),layout)+"]";
  if(auto *integer=llvm::dyn_cast<llvm::IntegerType>(type))return facts+"i"+std::to_string(integer->getBitWidth());
  if(auto *pointer=llvm::dyn_cast<llvm::PointerType>(type))return facts+"ptr"+std::to_string(pointer->getAddressSpace())+"/"+std::to_string(layout.getPointerSize(pointer->getAddressSpace()));
  if(auto *vector=llvm::dyn_cast<llvm::FixedVectorType>(type))return facts+"<"+std::to_string(vector->getNumElements())+"x"+Shape(vector->getElementType(),layout)+">";
  std::string text;llvm::raw_string_ostream output(text);type->print(output);return facts+text;
}
std::string Read(const char *path){
  llvm::LLVMContext context;llvm::SMDiagnostic error;auto module=llvm::parseIRFile(path,error,context);
  if(!module){error.print("il2cpp-state-layout",llvm::errs());return {};}
  auto *state=llvm::StructType::getTypeByName(context,"struct.State");
  if(!state||state->isOpaque()){llvm::errs()<<"No concrete named struct.State in module\n";return {};}
  return Shape(state,module->getDataLayout());
}
int main(int argc,char **argv){
  if(argc!=4){llvm::errs()<<"usage: il2cpp-state-layout old.ll new.ll output-prefix\n";return 2;}
  const auto old=Read(argv[1]),fresh=Read(argv[2]);if(old.empty()||fresh.empty())return 1;
  std::ofstream(std::string(argv[3])+".old.txt")<<old<<"\n";
  std::ofstream(std::string(argv[3])+".new.txt")<<fresh<<"\n";
  if(old!=fresh){llvm::errs()<<"Canonical recursive State layouts differ\n";return 1;}
  llvm::outs()<<"Canonical recursive State layout identical (field shapes,offsets,sizes,alignment)\n";
}
