#pragma once
#include <cstdint>
#include <functional>
#include <string>
#include "bridge.h"

namespace recomp {
struct FormatArguments {
  std::function<uint64_t()> integer;
  std::function<double()> floating;
};
// Android AAPCS64 va_list, passed indirectly as a 32-byte aggregate.
class VaArguments {
 public:
  explicit VaArguments(const void *guest_list);
  uint64_t Integer();
  double Floating();
 private:
  uint64_t Stack();
  struct Layout { uint64_t stack, gr_top, vr_top; int32_t gr_offs, vr_offs; } value_;
};
std::string Format(const char *format, FormatArguments args);
std::string Format(const char *format, bridge_detail::Arguments &args);
std::string Format(const char *format, VaArguments &args);
}  // namespace recomp
