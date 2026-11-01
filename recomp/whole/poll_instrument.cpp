// LLVM18 opt-in State escape barriers at trace entries and cycle-cut blocks.
#include <llvm/ADT/SmallPtrSet.h>
#include <llvm/ADT/SmallVector.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <map>
#include <set>
#include <vector>

int main(int argc, char **argv) {
  if (argc != 3) { llvm::errs() << "usage: poll-instrument input.ll output.ll\n"; return 2; }
  llvm::LLVMContext context;
  llvm::SMDiagnostic diagnostic;
  auto module = llvm::parseIRFile(argv[1], diagnostic, context);
  if (!module) { diagnostic.print(argv[0], llvm::errs()); return 1; }
  if (module->getFunction("__bunker_guest_poll_requested") || module->getFunction("__bunker_guest_poll_slow")) {
    llvm::errs() << "module already contains cooperative poll hooks\n"; return 1;
  }
  auto requested = module->getOrInsertFunction("__bunker_guest_poll_requested", llvm::FunctionType::get(llvm::Type::getInt32Ty(context), false));
  auto slow = module->getOrInsertFunction("__bunker_guest_poll_slow", llvm::FunctionType::get(llvm::Type::getVoidTy(context),
      {llvm::PointerType::getUnqual(context), llvm::Type::getInt64Ty(context), llvm::Type::getInt64Ty(context), llvm::Type::getInt64Ty(context)}, false));
  // These exact runtime helpers return their first boolean argument. Inline
  // them so a tight loop cannot rely on accidental opaque helper barriers.
  for (auto name : {"__remill_flag_computation_sign", "__remill_flag_computation_zero",
                    "__remill_flag_computation_overflow", "__remill_compare_neq"}) {
    auto *function = module->getFunction(name);
    if (!function) continue;
    if (!function->isDeclaration() || function->arg_empty() || !function->getReturnType()->isIntegerTy(1) ||
        !function->getArg(0)->getType()->isIntegerTy(1)) {
      llvm::errs() << "identity intrinsic differs from runtime contract\n"; return 1;
    }
    function->setAttributes(llvm::AttributeList());
    function->setLinkage(llvm::GlobalValue::InternalLinkage);
    function->addFnAttr(llvm::Attribute::AlwaysInline);
    llvm::IRBuilder<>(llvm::BasicBlock::Create(context, "", function)).CreateRet(function->getArg(0));
  }
  const llvm::Attribute::AttrKind effects[] = {llvm::Attribute::Memory, llvm::Attribute::NoSync, llvm::Attribute::NoFree,
      llvm::Attribute::NoCallback, llvm::Attribute::WillReturn, llvm::Attribute::Speculatable,
      llvm::Attribute::NoUnwind, llvm::Attribute::MustProgress};
  const llvm::Attribute::AttrKind state_effects[] = {llvm::Attribute::NoCapture, llvm::Attribute::ReadOnly,
      llvm::Attribute::ReadNone, llvm::Attribute::WriteOnly};
  // Imported trace declarations and existing direct-call sites must also lose
  // old effect/nounwind assertions now that the callee can invoke a poll hook.
  for (auto &function : *module) {
    if (function.getName().starts_with("sub_")) {
      for (auto attr : effects) function.removeFnAttr(attr);
      if (!function.arg_empty()) for (auto attr : state_effects) function.getArg(0)->removeAttr(attr);
    }
    for (auto &block : function) for (auto &instruction : block)
      if (auto *call = llvm::dyn_cast<llvm::CallBase>(&instruction))
        if (auto *callee = call->getCalledFunction(); callee && callee->getName().starts_with("sub_")) {
          for (auto attr : effects) call->removeFnAttr(attr);
          if (call->arg_size()) for (auto attr : state_effects) call->removeParamAttr(0, attr);
        }
  }
  size_t traces = 0, cycle_blocks = 0;
  for (auto &function : *module) {
    if (function.isDeclaration() || !function.getName().starts_with("sub_")) continue;
    if (function.arg_size() != 3 || !function.getArg(0)->getType()->isPointerTy() ||
        !function.getArg(1)->getType()->isIntegerTy(64) || !function.getArg(2)->getType()->isPointerTy() ||
        !function.getReturnType()->isPointerTy()) {
      llvm::errs() << "unexpected lifted signature\n"; return 1;
    }
    uint64_t entry;
    if (function.getName().drop_front(4).getAsInteger(16, entry)) return 1;
    // Removing all DFS backedges makes a directed graph acyclic, including
    // irreducible multi-entry loops. Poll once before each source terminator.
    // Search every component as well as the entry-reachable CFG; output block
    // order, not pointer ordering, determines stable site ordinals.
    std::map<llvm::BasicBlock *, unsigned> color;
    std::set<llvm::BasicBlock *> cuts;
    for (auto &root : function) if (!color[&root]) {
      std::vector<std::pair<llvm::BasicBlock *, unsigned>> stack{{&root, 0}};
      color[&root] = 1;
      while (!stack.empty()) {
        auto &[block, successor] = stack.back();
        auto *terminator = block->getTerminator();
        if (successor == terminator->getNumSuccessors()) {
          color[block] = 2; stack.pop_back(); continue;
        }
        auto *next = terminator->getSuccessor(successor++);
        if (color[next] == 1) cuts.insert(block);
        else if (!color[next]) { color[next] = 1; stack.emplace_back(next, 0); }
      }
    }
    // Hook calls synchronize, may throw, and escape State. Inferred attributes
    // of uninstrumented code must not survive those new observable effects.
    llvm::SmallVector<llvm::Instruction *, 16> sites;
    sites.push_back(&*function.getEntryBlock().getFirstInsertionPt());
    for (auto &block : function) if (cuts.count(&block)) { sites.push_back(block.getTerminator()); ++cycle_blocks; }
    uint64_t ordinal = 0;
    for (auto *site : sites) {
      llvm::IRBuilder<> builder(site);
      auto *check = builder.CreateCall(requested);
      // Split manually so the lifted block name and its PHIs retain their
      // normal semantics. LLVM updates successor PHIs on splitBasicBlock.
      auto *before = site->getParent();
      auto *continuation = before->splitBasicBlock(site, "poll.continue");
      before->getTerminator()->eraseFromParent();
      auto *delivery = llvm::BasicBlock::Create(context, "poll.deliver", &function, continuation);
      llvm::IRBuilder<> branch(before);
      branch.CreateCondBr(branch.CreateICmpNE(check, branch.getInt32(0)), delivery, continuation);
      llvm::IRBuilder<> handler(delivery);
      llvm::Value *incoming_pc = function.getArg(1);
      if (ordinal) incoming_pc = handler.getInt64(0);
      handler.CreateCall(slow, {function.getArg(0), handler.getInt64(entry), handler.getInt64(ordinal++), incoming_pc});
      handler.CreateBr(continuation);
    }
    ++traces;
  }
  if (llvm::verifyModule(*module, &llvm::errs())) return 1;
  std::error_code error;
  llvm::raw_fd_ostream output(argv[2], error);
  if (error) { llvm::errs() << error.message() << '\n'; return 1; }
  module->print(output, nullptr);
  llvm::outs() << "Cooperative polls: " << traces << " trace entries, " << cycle_blocks << " cycle-cut blocks\n";
}
