#pragma once
#include <cstddef>
#include <functional>
#include <map>
#include <vector>

#include "remill/Arch/AArch64/Runtime/State.h"
#include "remill/Arch/Runtime/Intrinsics.h"

namespace recomp {
using Entry = Memory *(*)(State &, addr_t, Memory *);
struct Trace { addr_t address; Entry entry; };

class Runtime {
 public:
  void AddTraces(const Trace *traces, size_t count);
  void AddImport(addr_t address, std::function<void(State &)> bridge);
  Memory *Run(State &state, addr_t address, Memory *memory = nullptr);
  Memory *Dispatch(State &state, addr_t address, Memory *memory);
 private:
  std::map<addr_t, Entry> traces_;
  std::map<addr_t, std::function<void(State &)>> imports_;
};
}  // namespace recomp
