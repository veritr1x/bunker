#pragma once
#include "../whole/runtime.h"

namespace bunker::windows::GuestCallRouting {
using Original = Memory *(*)(State &,addr_t,Memory *,addr_t,addr_t,recomp::Entry) noexcept;

// Keep the qualified Runtime's logical-call protocol and all six arguments.
// Only the existing automatic-environment owner must replace a static fastpath;
// dynamic calls continue through the Runtime's selected trace table.
inline Memory *Forward(Original original,recomp::Entry save_helper,State &state,
                       addr_t target,Memory *memory,addr_t expected_return_pc,
                       addr_t caller_sp,recomp::Entry direct_entry) noexcept {
  const auto selected=(target==0x825b0544ULL&&direct_entry)?save_helper:direct_entry;
  return original(state,target,memory,expected_return_pc,caller_sp,selected);
}
}  // namespace bunker::windows::GuestCallRouting
