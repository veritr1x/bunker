#pragma once
#include <cstdint>
#include <string>
#include <llvm/Support/Error.h>
namespace llvm { class Module; }
namespace bunker::guest_transfer {
struct LoweringStats {
 uint64_t direct_non_tail=0,dynamic_non_tail=0,direct_tail_transfers=0,jump_terminals=0,return_terminals=0,transformed_calls=0,SP_offset=0,PC_offset=0,metadata_records=0;
 bool inverse_verified=false;
};
// Apply once before the earliest guest-function inliner. Unknown forms fail.
llvm::Error LowerGuestCalls(llvm::Module&,LoweringStats&);
// Prototype audit only: verify transform+inverse and leave input unchanged.
llvm::Error AuditGuestCalls(llvm::Module&,LoweringStats&,std::string&transformedIR);
}
