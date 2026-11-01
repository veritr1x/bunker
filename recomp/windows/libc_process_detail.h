#pragma once
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace bunker::windows::libc_detail {
// FILETIME CPU durations use100ns; Android ARM64 clock_t uses microseconds.
// Divide before adding: even two UINT64_MAX inputs do not overflow the sum.
constexpr int64_t CpuMicroseconds(uint64_t kernel,uint64_t user){
  const uint64_t ticks=kernel/10+user/10+(kernel%10+user%10)/10;
  if(ticks>uint64_t(std::numeric_limits<int64_t>::max()))throw std::overflow_error("process CPU time exceeds Android clock_t");
  return static_cast<int64_t>(ticks);
}
constexpr bool AndroidSysconfName(int32_t name){
  switch(name){
#define BUNKER_SYSCONF_NAME(symbol,value) case value:return true;
#include "libc_sysconf_names.inc"
#undef BUNKER_SYSCONF_NAME
    default:return false;
  }
}
} // namespace bunker::windows::libc_detail
