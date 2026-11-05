#pragma once
#include "jni_host.h"
#include <cstdint>
#include <exception>
#include <functional>
#include <memory>
#include <string>

namespace bunker::windows {
// Real asynchronous HandlerThread queues and a nominal frame clock for this
// Windows port. The clock is not an observation of Android or DWM vsync.
class AndroidChoreographer {
 public:
  struct ClockSample {
    int64_t monotonic_ns = 0;
    uint32_t refresh_numerator = 0, refresh_denominator = 0;
  };
  struct Event {
    std::string operation;
    std::u16string thread_name;
    int32_t what = 0;
    int64_t frame_time_ns = 0;
  };
  struct Config {
    using WorkerLease=std::shared_ptr<void>;
    // Capture the actual creator's thread/signal context before starting the
    // native worker. The lease is passive owned data, never a borrowed local.
    std::function<WorkerLease(const std::u16string&)> prepare_worker;
    // Enter runs on the new native worker before any service JNI use. The
    // owner attaches this actual thread to Host/VM and registers its actual
    // Pthreads/Signal context here. Exit releases that context and detaches.
    std::function<void(const std::u16string&,const WorkerLease&)> enter_worker;
    std::function<void(const WorkerLease&)> exit_worker;
    // Must report an observed Windows refresh ratio and a real monotonic
    // timestamp. Frame delivery uses bounded CV waits on the nominal period.
    std::function<ClockSample()> read_frame_clock;
    std::function<void(const Event&)> observer;
    // Notification after native worker failure, outside all service locks.
    // CheckHealthy/Stop also expose the same failure to the owning caller.
    std::function<void(std::exception_ptr)> failure;
  };
  AndroidChoreographer(jni::Host&, Config);
  ~AndroidChoreographer();
  AndroidChoreographer(const AndroidChoreographer&) = delete;
  AndroidChoreographer& operator=(const AndroidChoreographer&) = delete;
  void CheckHealthy() const;
  // Bind the actual already-attached lifecycle worker to an owned Looper.
  // wake_owner may run on a sender: it must only enqueue a native owner-FIFO
  // task, return false if stopping, and never invoke Pump synchronously.
  void PrepareCurrentLooper(const std::u16string& name,std::function<bool()> wake_owner);
  void PumpCurrentLooper();
  // Actual owner-thread cleanup, while its JNI context is still attached.
  // Cancel its queue and release this mapping before service Stop/teardown.
  void ReleaseCurrentLooper();
  // Owner-side quiescence fence: stop acceptance, cancel pending callbacks and
  // join every owned real worker before proxy, Host, runner or modules retire.
  // Externally-owned prepared Loopers must first ReleaseCurrentLooper.
  void Stop();
 private:
  struct Shared;
  std::shared_ptr<Shared> state_;
};
}  // namespace bunker::windows
