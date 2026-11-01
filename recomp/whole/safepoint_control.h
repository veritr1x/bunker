#pragma once
// Isolated cooperative-materialization experiment, not a signal/GC API.
#include <cfenv>
#include "runtime.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

namespace recomp::safepoint_proof {
struct Snapshot {
  State state{};
  addr_t state_address = 0;
  uint64_t site = 0, epoch = 0, fast_calls = 0;
  std::thread::id worker;
  int rounding = 0, exceptions = 0, error = 0;
};
class Control {
 public:
  uint64_t Request();
  bool Wait(uint64_t epoch, Snapshot &, std::chrono::milliseconds timeout);
  void Resume(uint64_t epoch);
  // Internal to this standalone experiment. Do not use from host providers.
  std::atomic<uint64_t> requested{0};
  std::mutex mutex;
  std::condition_variable condition;
  uint64_t parked = 0, resumed = 0;
  Snapshot snapshot;
};
class Binding {
 public:
  Binding(Control &, State &);
  ~Binding();
  Binding(const Binding &) = delete;
  Binding &operator=(const Binding &) = delete;
};
}  // namespace recomp::safepoint_proof
extern "C" int32_t __bunker_poll_requested();
extern "C" void __bunker_poll_slow(State *, uint64_t site);
