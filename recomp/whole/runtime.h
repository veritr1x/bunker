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
// Short fault-safe native read under the shared-memory lock. No epoch changes.
// Callback may only read native memory into owned host storage; no guest/runtime
// calls, waits, guest writes or allocation. It must not reenter this protocol.
void WithGuestMemoryRead(const std::function<void()> &read);
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
State *CurrentExecutionState() noexcept;

class Runtime {
 public:
  void AddTraces(const Trace *traces, size_t count);
  void AddImport(addr_t address, std::function<void(State &)> bridge);
  Memory *Run(State &state, addr_t address, Memory *memory = nullptr);
  Memory *Dispatch(State &state, addr_t address, Memory *memory);
  bool HasGuestTrace(addr_t address) const noexcept;
 private:
  std::map<addr_t, Entry> traces_;
  std::map<addr_t, std::function<void(State &)>> imports_;
};
}  // namespace recomp

// Explicit call protocol for pre-inlining lifted call sites. No host exception
// represents a guest transfer. An abnormal result must be returned immediately
// by the caller before it resets a local RETURN_PC or executes more guest code.
extern "C" Memory *__bunker_guest_call(State &, addr_t argument_pc, Memory *,
                                      addr_t expected_return_pc, addr_t caller_sp,
                                      recomp::Entry direct_entry) noexcept;
extern "C" uint32_t __bunker_guest_transfer_pending(State &) noexcept;

extern "C" uint64_t __remill_aarch64_load_exclusive(State &, addr_t, uint64_t size, uint64_t acquire);
extern "C" uint32_t __remill_aarch64_store_exclusive(State &, addr_t, uint64_t value, uint64_t size, uint64_t release);
extern "C" void __remill_aarch64_clear_exclusive(State &);
extern "C" void __remill_aarch64_load_exclusive_pair(State &, addr_t, uint64_t element_size, uint64_t acquire, uint64_t *first, uint64_t *second);
extern "C" uint32_t __remill_aarch64_store_exclusive_pair(State &, addr_t, uint64_t first, uint64_t second, uint64_t element_size, uint64_t release);
