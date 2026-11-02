#pragma once
#include "pthread_host.h"
#include "signal_host.h"
#include "../whole/cooperative_poll.h"
#include <atomic>

namespace bunker::windows {
// Optional worker ownership only. No poll binding, delivery or GC registration.
class WorkerSignalLifecycle {
 public:
  enum class Phase { preparing,prepared,entered,finishing,retiring,retired,cancelled };
  class Context {
   public:
    const Pthreads::WorkerInfo &PreparedWorker() const noexcept {return prepared_;}
    uint32_t NativeThreadId() const noexcept {return native_tid_.load();}
    Phase CurrentPhase() const noexcept {return phase_.load();}
    const SignalHost::ThreadRef &SignalThread() const noexcept {return thread_;}
    const std::shared_ptr<SignalWake> &Wake() const noexcept {return wake_;}
    recomp::PollRequest &PollRequests() noexcept {return request_;}
   private:
    friend class WorkerSignalLifecycle;
    Pthreads::WorkerInfo prepared_{};
    std::atomic<uint32_t> native_tid_{0};
    std::atomic<Phase> phase_{Phase::preparing};
    std::atomic<uint64_t> users_{0};
    SignalHost::ThreadRef thread_;
    std::shared_ptr<SignalWake> wake_;
    recomp::PollRequest request_;
    std::thread::id creator_,owner_;
    bool registered_=false;
  };
  using ContextRef=std::shared_ptr<Context>;
  class Use {
   public:
    Use()=default;
    ~Use();
    Use(Use&&) noexcept;
    Use &operator=(Use&&) noexcept;
    Use(const Use&)=delete;
    Use &operator=(const Use&)=delete;
   private:
    friend class WorkerSignalLifecycle;
    explicit Use(ContextRef context):context_(std::move(context)){}
    void Release() noexcept;
    ContextRef context_;
  };
  explicit WorkerSignalLifecycle(SignalHost&);
  ~WorkerSignalLifecycle();
  WorkerSignalLifecycle(const WorkerSignalLifecycle&)=delete;
  WorkerSignalLifecycle &operator=(const WorkerSignalLifecycle&)=delete;
  // Take once and install before the first Create attempt. Wrappers may compose
  // checks/observation; cancellation must still reach the returned retire hook.
  Pthreads::WorkerLifecycleHooks TakeHooks();
  // Lookup/AcquireUse take the adapter ledger mutex. Never call them from a
  // PollBinding Admission policy (which forbids locks); capture the context/use
  // before that phase and let admission read owner-local published metadata.
  ContextRef Lookup(uint64_t token) const;
  // Same actual worker only, including genuine guest TLS callbacks. A future
  // delivery/frame owner must retain this guard until its checked return.
  Use AcquireUse(uint64_t token);
  // Call after actual Pthreads::Shutdown. UI/UnityMain registrations are separate.
  // Seals captured hooks before their SignalHost dependency can be destroyed.
  void CloseAfterShutdown();
 private:
  struct Shared;
  std::shared_ptr<Shared> shared_;
};
}  // namespace bunker::windows
