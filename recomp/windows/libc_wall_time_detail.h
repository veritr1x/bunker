#pragma once
#include <cstdint>
namespace bunker::windows::libc_detail {
struct Timeval {int64_t seconds,microseconds;};
static_assert(sizeof(Timeval)==16);
// FILETIME's epoch differs by whole seconds. Divide before subtracting so
// dates before1970 and every unsigned64 FILETIME value remain representable.
constexpr Timeval UnixTimeval(uint64_t ticks){
  return {static_cast<int64_t>(ticks/10000000)-INT64_C(11644473600),
          static_cast<int64_t>((ticks%10000000)/10)};
}
}
