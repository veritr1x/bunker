#pragma once
#include "runtime.h"
#include <limits>
#include <stdexcept>
#include <string>

namespace recomp {
// Read through the shared-memory protocol without speculatively touching a
// byte beyond NUL or a printf precision bound (which may end at a page edge).
inline std::string ReadGuestString(addr_t address,
                                  size_t maximum = std::numeric_limits<size_t>::max()) {
  std::string result;
  while (result.size() < maximum) {
    if (!address || address > std::numeric_limits<addr_t>::max() - result.size())
      throw std::invalid_argument("invalid guest string address");
    char value;
    ReadGuestMemory(&value, address + result.size(), 1);
    if (!value) break;
    result += value;
  }
  return result;
}
}  // namespace recomp
