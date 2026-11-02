#pragma once
#include <stdint.h>
struct WorkerLifecycleReport {
  uint64_t thread,mode,token,native_tid,stack_low,stack_size,tls,mask;
  uint64_t environment,allocation,destructors,probes,errors;
  struct WorkerLifecycleReport *child;
};
#ifdef __cplusplus
static_assert(sizeof(WorkerLifecycleReport)==112);
#else
_Static_assert(sizeof(struct WorkerLifecycleReport)==112,"report wire size");
#endif
