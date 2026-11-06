#pragma once
#include <stdint.h>
struct ThreadExitReport {
 uint64_t mode,thread,entered,after_exit,once_runs,after_once,destructors;
 uint64_t outer_at_tls,inner_at_tls,tls_sp,tls_state,errors;
};
