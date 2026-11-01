#pragma once
#include <stdint.h>
struct FrameReport {
  uint64_t layout[16];
  uint64_t signo,info_signo,info_errno,info_code,mask,alt_pointer,alt_flags,alt_size;
  uint64_t sp,pc,pstate,fault,fpcr,fpsr,magic,record_size,entry_sp,entry_fp,chain_fp,chain_lr;
  uint64_t gpr[31],vectors[64];
  uint64_t mutate,new_root;
};
