#pragma once
#include <stdint.h>
struct AltReport {
  uint64_t outer_sp,nested_sp,outer_frame,nested_frame,outer_saved_sp,nested_saved_sp;
  uint64_t outer_raw_flags,nested_raw_flags,outer_query_flags,nested_query_flags;
  uint64_t query_pointer,query_size,onstack_result,onstack_errno,onstack_old_unchanged;
  uint64_t nested_onstack_result,nested_onstack_errno,nested_old_unchanged;
  uint64_t root,vector_root[2],nested_count,lease_guards,changed_result,changed_query;
  uint64_t replacement,replacement_size,mode;
};
