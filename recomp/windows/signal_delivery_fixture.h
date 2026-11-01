#pragma once
#include <stdint.h>
struct DeliveryReport {
  uint32_t acknowledgment[4];
  volatile uint64_t world_stopped,done,stops,restarts;
  uint64_t root,counter,vector_root[2],interrupted_sp,interrupted_pc;
  uint64_t frame,handler_sp,handler_fp,worker_token,tls,error_before,error_after;
};
