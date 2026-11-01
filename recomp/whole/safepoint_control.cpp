#include "safepoint_control.h"
#include <cerrno>
#include <cfenv>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

namespace {
thread_local recomp::safepoint_proof::Control *current;
thread_local State *bound_state;
thread_local uint64_t handled, fast_calls;
}
namespace recomp::safepoint_proof {
uint64_t Control::Request() { return requested.fetch_add(1, std::memory_order_release) + 1; }
bool Control::Wait(uint64_t epoch, Snapshot &result, std::chrono::milliseconds timeout) {
  std::unique_lock lock(mutex);
  if (!condition.wait_for(lock, timeout, [&] { return parked >= epoch; })) return false;
  result = snapshot;
  return true;
}
void Control::Resume(uint64_t epoch) {
  std::lock_guard lock(mutex);
  if (epoch > parked) throw std::logic_error("resume before materialization acknowledgment");
  if (epoch > resumed) resumed = epoch;
  condition.notify_all();
}
Binding::Binding(Control &control, State &state) {
  if (current) throw std::logic_error("nested proof bindings are not supported");
  current = &control; bound_state = &state; handled = 0; fast_calls = 0;
}
Binding::~Binding() { current = nullptr; bound_state = nullptr; }
}

// No LTO: the optimizer of the lifted module sees opaque side effects, not a
// pure predicate. This conservative barrier can force spills on the fast path.
extern "C" __attribute__((noinline)) int32_t __bunker_poll_requested() {
  ++fast_calls;
  return current && current->requested.load(std::memory_order_acquire) > handled;
}
extern "C" __attribute__((noinline)) void __bunker_poll_slow(State *state, uint64_t site) {
  if (!current || state != bound_state) std::abort();
  auto &control = *current;
  const auto epoch = control.requested.load(std::memory_order_acquire);
  if (epoch <= handled) return;
  const int saved_errno = errno;
  fenv_t saved_fenv;
  std::fegetenv(&saved_fenv);
  {
    std::unique_lock lock(control.mutex);
    auto &snapshot = control.snapshot;
    std::memcpy(&snapshot.state, state, sizeof(State));
    snapshot.state_address = reinterpret_cast<addr_t>(state);
    snapshot.site = site; snapshot.epoch = epoch; snapshot.fast_calls = fast_calls;
    snapshot.worker = std::this_thread::get_id();
    snapshot.rounding = std::fegetround(); snapshot.exceptions = std::fetestexcept(FE_ALL_EXCEPT); snapshot.error = saved_errno;
    // Exercise host-side slow work disturbing errno/fenv. Neither change may
    // leak into the resumed guest or its calling host thread.
    errno = 123;
    std::fesetround(FE_TONEAREST); std::feclearexcept(FE_ALL_EXCEPT); std::feraiseexcept(FE_INVALID);
    control.parked = epoch;
    control.condition.notify_all();
    // wait releases this private controller lock. No guest-memory/provider
    // locks are acquired here, and no guest callback or signal is invoked.
    control.condition.wait(lock, [&] { return control.resumed >= epoch; });
  }
  std::fesetenv(&saved_fenv);
  errno = saved_errno;
  handled = epoch;
}
