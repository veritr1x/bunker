#pragma once
#include <cstdint>
namespace bunker::windows {
struct AndroidTimespec { int64_t seconds, nanoseconds; };
static_assert(sizeof(AndroidTimespec) == 16);
}  // namespace bunker::windows
