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

// Providers must snapshot guest input and publish guest output through these
// APIs to participate in exclusive reservations and shared-memory ordering.
void ReadGuestMemory(void *destination, addr_t address, size_t size);
void WriteGuestMemory(addr_t address, const void *source, size_t size);
// Allocation lifetime changes invalidate stale reservations without touching
// bytes. Providers must supply the complete known allocation range.
void InvalidateGuestMemory(addr_t address, size_t size);
// The callback executes under a non-recursive memory lock. It must only do a
// short native write; no guest callbacks, runtime access, or waits on guests.
void WithGuestMemoryWrite(addr_t address, size_t size, const std::function<void()> &write);
// Target-thread-only view, innermost first. Valid only during this execution;
// includes suspended parents of nested Runtime::Run callbacks. It does not
// enumerate roots kept solely in native provider temporaries.
std::vector<State *> CurrentExecutionFrames(State &top);

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

extern "C" uint64_t __remill_aarch64_load_exclusive(State &, addr_t, uint64_t size, uint64_t acquire);
extern "C" uint32_t __remill_aarch64_store_exclusive(State &, addr_t, uint64_t value, uint64_t size, uint64_t release);
extern "C" void __remill_aarch64_clear_exclusive(State &);
extern "C" void __remill_aarch64_load_exclusive_pair(State &, addr_t, uint64_t element_size, uint64_t acquire, uint64_t *first, uint64_t *second);
extern "C" uint32_t __remill_aarch64_store_exclusive_pair(State &, addr_t, uint64_t first, uint64_t second, uint64_t element_size, uint64_t release);
