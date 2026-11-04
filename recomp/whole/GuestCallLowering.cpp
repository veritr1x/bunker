#include "GuestCallLowering.h"
#include <llvm/AsmParser/Parser.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Transforms/Utils/BasicBlockUtils.h>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
using namespace llvm;
static void require(bool ok,const std::string &message){if(!ok)throw std::runtime_error(message);}
static std::string print(Module &m){std::string s;raw_string_ostream out(s);m.print(out,nullptr);return s;}
static std::string inst(const Instruction &i){std::string s;raw_string_ostream out(s);i.print(out);return s;}
static LoadInst* returnLoadAfter(CallInst *call){
 auto *next=call->getNextNonDebugInstruction();
 if(auto *branch=dyn_cast_or_null<BranchInst>(next)){require(branch->isUnconditional(),"conditional post-call transfer is unknown");next=branch->getSuccessor(0)->getFirstNonPHIOrDbgOrLifetime();}
 auto *load=dyn_cast_or_null<LoadInst>(next);require(load&&load->getType()->isIntegerTy(64),"expected return load must follow guest call or its unconditional edge: "+inst(*call));return load;
}
struct Edit{CallInst *replacement;std::unique_ptr<Instruction,ValueDeleter> original;SmallVector<Value*,8>operands;BasicBlock *before,*continuation,*abnormal;std::vector<Instruction*>pre,generated;std::string name;};

namespace bunker::guest_transfer {
static void lowerImpl(llvm::Module&m,LoweringStats&stats,bool verifyInverse,std::string*output){
 auto &context=m.getContext();require(!verifyModule(m,&errs()),"input module invalid");
const auto original=verifyInverse?print(m):std::string();const auto &dl=m.getDataLayout();
 auto *state=StructType::getTypeByName(context,"struct.State"),*arch=StructType::getTypeByName(context,"struct.AArch64State"),*gpr=StructType::getTypeByName(context,"struct.GPR");
 require(state&&arch&&gpr&&!state->isOpaque()&&!arch->isOpaque()&&!gpr->isOpaque(),"unsupported State type structure");
 require(dl.getTypeAllocSize(state)==1200&&dl.getABITypeAlign(state).value()==16,"unsupported State size/alignment");
 require(state->getNumElements()==1&&state->getElementType(0)==arch&&arch->getNumElements()>3&&arch->getElementType(3)==gpr&&gpr->getNumElements()==66,"unsupported State GPR path");
 const auto base=dl.getStructLayout(state)->getElementOffset(0)+dl.getStructLayout(arch)->getElementOffset(3);
 const auto spOffset=base+dl.getStructLayout(gpr)->getElementOffset(63),pcOffset=base+dl.getStructLayout(gpr)->getElementOffset(65);
 require(spOffset==1040&&pcOffset==1056,"unexpected SP/PC field offsets");
 require(!m.getFunction("__bunker_guest_call")&&!m.getFunction("__bunker_guest_transfer_pending")&&!m.getNamedMetadata("bunker.guest.call.lowering"),"module already transformed");
 auto *ptr=PointerType::getUnqual(context);auto *i64=Type::getInt64Ty(context);auto *i32=Type::getInt32Ty(context);
 auto callGuest=m.getOrInsertFunction("__bunker_guest_call",FunctionType::get(ptr,{ptr,i64,ptr,i64,i64,ptr},false));
 auto pending=m.getOrInsertFunction("__bunker_guest_transfer_pending",FunctionType::get(i32,{ptr},false));
 for(auto value:{callGuest,pending}){auto *f=cast<Function>(value.getCallee());f->addFnAttr(Attribute::NoUnwind);f->addFnAttr(Attribute::NoInline);}
 std::vector<CallInst*>work;unsigned direct=0,indirect=0,tails=0,jumps=0,returns=0;json::Array origins;
 for(auto &f:m)if(!f.isDeclaration()&&f.getName().starts_with("sub_"))for(auto &bb:f)for(auto &instruction:bb){
  auto *call=dyn_cast<CallInst>(&instruction);if(!call)continue;auto *callee=dyn_cast<Function>(call->getCalledOperand()->stripPointerCasts());if(!callee)continue;auto name=callee->getName();
  bool sub=name.starts_with("sub_"),dynamic=name=="__remill_function_call",jump=name=="__remill_jump",ret=name=="__remill_function_return";
  if(!sub&&!dynamic&&!jump&&!ret)continue;
  require(call->arg_size()==3&&call->getType()->isPointerTy()&&call->getArgOperand(0)->getType()->isPointerTy()&&call->getArgOperand(1)->getType()->isIntegerTy(64)&&call->getArgOperand(2)->getType()->isPointerTy(),"unknown guest call signature: "+name.str());
  require(call->getCallingConv()==CallingConv::C&&call->getNumOperandBundles()==0&&!call->isMustTailCall(),"unknown guest call convention/bundle/musttail");
  auto *next=call->getNextNonDebugInstruction();auto *terminal=dyn_cast_or_null<ReturnInst>(next);bool immediate=terminal&&terminal->getReturnValue()==call;
  if(jump||ret){require(immediate,"nonterminal remill jump/return requires separate lowering");jump?++jumps:++returns;continue;}
  if(sub&&immediate){require(call->isTailCall(),"terminal direct call lacks tail-transfer annotation");++tails;continue;}
  require(!immediate,"ambiguous terminal guest call form");
  auto *load=returnLoadAfter(call);
  auto *allocation=dyn_cast<AllocaInst>(load->getPointerOperand()->stripPointerCasts());require(allocation&&allocation->getName()=="RETURN_PC"&&allocation->getAllocatedType()->isIntegerTy(64),"unknown RETURN_PC source: "+inst(*load));
  auto *store=dyn_cast_or_null<StoreInst>(load->getNextNonDebugInstruction());require(store&&store->getValueOperand()==load,"missing original NEXT_PC reset");
  auto *nextAllocation=dyn_cast<AllocaInst>(store->getPointerOperand()->stripPointerCasts());require(nextAllocation&&nextAllocation->getName()=="NEXT_PC","unknown NEXT_PC reset target");
  work.push_back(call);sub?++direct:++indirect;
 }
 std::vector<Edit>edits;auto *metadata=m.getOrInsertNamedMetadata("bunker.guest.call.lowering");
 for(auto *old:work){
  auto *returnLoad=returnLoadAfter(old);auto *suffixStart=old->getNextNode();auto *before=old->getParent();IRBuilder<>b(old);
  auto *expected=b.CreateLoad(i64,returnLoad->getPointerOperand(),"guest.expected_return");expected->setAlignment(Align(8));
  auto *spPtr=b.CreateConstGEP1_64(Type::getInt8Ty(context),old->getArgOperand(0),spOffset,"guest.sp.ptr");auto *callerSP=b.CreateLoad(i64,spPtr,"guest.caller_sp");callerSP->setAlignment(Align(8));
  auto *callee=cast<Function>(old->getCalledOperand()->stripPointerCasts());Value *entry=callee->getName().starts_with("sub_")?static_cast<Value*>(callee):ConstantPointerNull::get(ptr);
  std::unique_ptr<Instruction,ValueDeleter> saved(old->clone());SmallVector<Value*,8>savedOperands;for(auto &operand:old->operands())savedOperands.push_back(operand.get());saved->dropAllReferences();const auto originalCall=inst(*old);const auto oldName=old->getName().str();
  auto *replacement=b.CreateCall(callGuest,{old->getArgOperand(0),old->getArgOperand(1),old->getArgOperand(2),expected,callerSP,entry});replacement->setDoesNotThrow();replacement->setDebugLoc(old->getDebugLoc());replacement->takeName(old);
  old->replaceAllUsesWith(replacement);old->eraseFromParent();
  auto *continuation=before->splitBasicBlock(suffixStart,"guest.normal_continuation");before->getTerminator()->eraseFromParent();
  auto *abnormal=BasicBlock::Create(context,"guest.abnormal_return",before->getParent(),continuation);IRBuilder<>a(abnormal);a.CreateRet(replacement);
  IRBuilder<>guard(before);auto *pendingCall=guard.CreateCall(pending,{replacement->getArgOperand(0)},"guest.transfer_pending");pendingCall->setDoesNotThrow();
  auto *pcPtr=guard.CreateConstGEP1_64(Type::getInt8Ty(context),replacement->getArgOperand(0),pcOffset,"guest.pc.ptr");auto *actualPC=guard.CreateLoad(i64,pcPtr,"guest.actual_pc");actualPC->setAlignment(Align(8));auto *actualSP=guard.CreateLoad(i64,spPtr,"guest.actual_sp");actualSP->setAlignment(Align(8));
  auto *normal=guard.CreateAnd(guard.CreateICmpEQ(pendingCall,ConstantInt::get(i32,0)),guard.CreateAnd(guard.CreateICmpEQ(actualPC,expected),guard.CreateICmpEQ(actualSP,callerSP)),"guest.normal_return");guard.CreateCondBr(normal,continuation,abnormal);
  SmallVector<Metadata*,6>row{MDString::get(context,before->getParent()->getName()),MDString::get(context,originalCall),MDString::get(context,callee->getName()),MDString::get(context,"RETURN_PC"),ConstantAsMetadata::get(ConstantInt::get(i64,spOffset)),ConstantAsMetadata::get(ConstantInt::get(i64,pcOffset))};metadata->addOperand(MDNode::get(context,row));
  Edit edit{replacement,std::move(saved),std::move(savedOperands),before,continuation,abnormal,{expected,cast<Instruction>(spPtr),callerSP},{},oldName};bool after=false;
  for(auto &i:*before){if(&i==replacement){after=true;continue;}if(after&&!i.isTerminator())edit.generated.push_back(&i);}
  edits.push_back(std::move(edit));
 }
 require(!verifyModule(m,&errs()),"transformed module invalid");const auto transformed=print(m);
stats.direct_non_tail=direct;stats.dynamic_non_tail=indirect;stats.direct_tail_transfers=tails;stats.jump_terminals=jumps;stats.return_terminals=returns;stats.transformed_calls=work.size();stats.SP_offset=spOffset;stats.PC_offset=pcOffset;stats.metadata_records=work.size();if(output)*output=transformed;if(!verifyInverse)return;
 // Undo in reverse order in memory; original continuations/attrs must survive exactly.
 for(auto it=edits.rbegin();it!=edits.rend();++it){auto &e=*it;
  e.abnormal->dropAllReferences();e.abnormal->eraseFromParent();e.before->getTerminator()->eraseFromParent();
  for(auto rit=e.generated.rbegin();rit!=e.generated.rend();++rit){auto *i=*rit;if(i->getParent()){require(i->use_empty(),"inverse generated instruction still referenced");i->eraseFromParent();}}
  for(unsigned index=0;index<e.operands.size();++index)e.original->setOperand(index,e.operands[index]);e.original->insertBefore(e.replacement->getIterator());e.replacement->replaceAllUsesWith(e.original.get());e.replacement->eraseFromParent();e.original->setName(e.name);e.original.release();
  for(auto rit=e.pre.rbegin();rit!=e.pre.rend();++rit){require((*rit)->use_empty(),"inverse pre-call value still referenced");(*rit)->eraseFromParent();}
  e.continuation->replaceAllUsesWith(e.before);e.before->splice(e.before->end(),e.continuation);e.continuation->eraseFromParent();
 }
 m.eraseNamedMetadata(metadata);cast<Function>(callGuest.getCallee())->eraseFromParent();cast<Function>(pending.getCallee())->eraseFromParent();
 require(!verifyModule(m,&errs()),"inverse module invalid");require(print(m)==original,"normalized whole-module inverse differs");
stats.inverse_verified=true;
}
llvm::Error LowerGuestCalls(llvm::Module&m,LoweringStats&stats){try{lowerImpl(m,stats,false,nullptr);return llvm::Error::success();}catch(const std::exception&e){return llvm::createStringError(llvm::inconvertibleErrorCode(),"%s",e.what());}}
llvm::Error AuditGuestCalls(llvm::Module&m,LoweringStats&stats,std::string&out){try{lowerImpl(m,stats,true,&out);return llvm::Error::success();}catch(const std::exception&e){return llvm::createStringError(llvm::inconvertibleErrorCode(),"%s",e.what());}}
}
