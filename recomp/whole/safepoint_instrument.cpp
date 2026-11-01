// Isolated LLVM 18 prototype. Run before any State-eliminating optimization.
#include <llvm/ADT/SmallVector.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Transforms/Utils/BasicBlockUtils.h>

int main(int argc, char **argv) {
  if (argc != 3) { llvm::errs() << "usage: safepoint-instrument input.ll output.ll\n"; return 2; }
  llvm::LLVMContext context;
  llvm::SMDiagnostic diagnostic;
  auto module = llvm::parseIRFile(argv[1], diagnostic, context);
  if (!module) { diagnostic.print(argv[0], llvm::errs()); return 1; }
  // The actual runtime implements these exact helpers as `return first_arg`.
  // Inline those identities in this experiment so opaque flag-helper calls
  // cannot accidentally provide an additional materialization barrier inside
  // the tight loop. This does not change the shared runtime or lifter.
  for (auto name : {"__remill_flag_computation_sign", "__remill_flag_computation_zero",
                    "__remill_flag_computation_overflow", "__remill_compare_neq"}) {
    auto *function = module->getFunction(name);
    if (!function) continue;
    if (!function->isDeclaration() || function->arg_empty() || !function->getReturnType()->isIntegerTy(1) ||
        !function->getArg(0)->getType()->isIntegerTy(1)) {
      llvm::errs() << "identity intrinsic signature differs from the proved runtime implementation\n"; return 1;
    }
    function->setAttributes(llvm::AttributeList());
    function->setLinkage(llvm::GlobalValue::InternalLinkage);
    function->addFnAttr(llvm::Attribute::AlwaysInline);
    auto *body = llvm::BasicBlock::Create(context, "", function);
    llvm::IRBuilder<>(body).CreateRet(function->getArg(0));
  }
  auto requested = module->getOrInsertFunction("__bunker_poll_requested", llvm::FunctionType::get(llvm::Type::getInt32Ty(context), false));
  auto slow = module->getOrInsertFunction("__bunker_poll_slow", llvm::FunctionType::get(llvm::Type::getVoidTy(context),
      {llvm::PointerType::getUnqual(context), llvm::Type::getInt64Ty(context)}, false));
  size_t traces = 0, backedges = 0;
  for (auto &function : *module) {
    if (function.isDeclaration() || !function.getName().starts_with("sub_")) continue;
    if (function.arg_size() != 3 || !function.getArg(0)->getType()->isPointerTy()) {
      llvm::errs() << "unexpected lifted signature\n"; return 1;
    }
    // Instrumentation introduces synchronization and a State-pointer escape.
    // Do not retain inferred attributes from the uninstrumented function.
    for (auto attr : {llvm::Attribute::Memory, llvm::Attribute::NoSync, llvm::Attribute::NoFree,
                      llvm::Attribute::NoCallback, llvm::Attribute::WillReturn, llvm::Attribute::Speculatable})
      function.removeFnAttr(attr);
    function.getArg(0)->removeAttr(llvm::Attribute::NoCapture);
    function.getArg(0)->removeAttr(llvm::Attribute::ReadOnly);
    function.getArg(0)->removeAttr(llvm::Attribute::ReadNone);
    function.getArg(0)->removeAttr(llvm::Attribute::WriteOnly);
    llvm::DominatorTree dominators(function);
    llvm::SmallVector<llvm::Instruction *, 16> sites;
    sites.push_back(&*function.getEntryBlock().getFirstInsertionPt());
    for (auto &block : function) {
      auto *terminator = block.getTerminator();
      for (unsigned i = 0; i < terminator->getNumSuccessors(); ++i) {
        if (dominators.dominates(terminator->getSuccessor(i), &block)) {
          sites.push_back(terminator); ++backedges; break;
        }
      }
    }
    uint64_t entry = 0;
    if (function.getName().drop_front(4).getAsInteger(16, entry)) return 1;
    if (entry > (UINT64_MAX >> 8) || sites.size() > 256) {
      llvm::errs() << "proof site identity exceeds its explicitly bounded format\n"; return 1;
    }
    unsigned ordinal = 0;
    for (auto *site : sites) {
      llvm::IRBuilder<> builder(site);
      auto *check = builder.CreateCall(requested);
      auto *condition = builder.CreateICmpNE(check, builder.getInt32(0));
      auto *then_terminator = llvm::SplitBlockAndInsertIfThen(condition, site, false);
      llvm::IRBuilder<> parked(then_terminator);
      // Site identity is not a fabricated guest PC. State contains the actual
      // guest PC; the low ordinal distinguishes entry from backedge checks.
      parked.CreateCall(slow, {function.getArg(0), parked.getInt64((entry << 8) | ordinal++)});
    }
    ++traces;
  }
  if (!traces || !backedges || llvm::verifyModule(*module, &llvm::errs())) {
    llvm::errs() << "proof requires at least one trace and one natural loop backedge\n"; return 1;
  }
  std::error_code error;
  llvm::raw_fd_ostream output(argv[2], error);
  if (error) { llvm::errs() << error.message() << '\n'; return 1; }
  module->print(output, nullptr);
  llvm::outs() << "Safepoint prototype: " << traces << " trace entries, " << backedges << " loop backedge blocks\n";
}
