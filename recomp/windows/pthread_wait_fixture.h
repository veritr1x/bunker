#pragma once
#include <stdint.h>
struct PthreadWaitReport {
  uint64_t mutex[8], condition[8];
  uint64_t thread, token, result, returns, errors, permits, timed;
  int64_t seconds, nanoseconds;
};
#ifdef __cplusplus
static_assert(sizeof(PthreadWaitReport)==200);
#else
_Static_assert(sizeof(struct PthreadWaitReport)==200,"wire report");
#endif
