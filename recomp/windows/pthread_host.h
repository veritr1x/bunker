#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <initializer_list>
#include <memory>
#include <string>
#include <vector>
#include "../whole/runtime.h"
#include "android_types.h"

namespace bunker::windows {
// Android AArch64 wire types. Host Windows pthread/CRT layouts never escape.
struct AndroidThreadAttr {
  uint32_t flags = 0, padding = 0;
  uint64_t stack_base = 0, stack_size = 0, guard_size = 0;
  int32_t sched_policy = 0, sched_priority = 0;
  uint8_t reserved[16]{};
};
static_assert(sizeof(AndroidThreadAttr) == 56 && offsetof(AndroidThreadAttr, stack_base) == 8);
static_assert(offsetof(AndroidThreadAttr, sched_policy) == 32 && sizeof(AndroidTimespec) == 16);

// Must outlive its registered imports and workers. All guest callbacks execute
// translated traces via Runtime::Run, with their own State and per-thread stack.
// Invalid guest memory is outside this API's contract, as for native pthreads.
class Pthreads {
 public:
  Pthreads(recomp::Runtime &, std::function<bool(addr_t)> translated_entry,
           addr_t marker_base = 0x7ff900000000ULL,
           std::function<bool(addr_t)> tls_destructor_callable = {});
  ~Pthreads();
  Pthreads(const Pthreads &) = delete;
  Pthreads &operator=(const Pthreads &) = delete;
  void Install();
  void SetErrorSink(std::function<void(int)>);
  struct WorkerInfo {
    uint64_t token=0,parent_token=0;
    addr_t stack_low=0,stack_high=0,tls_address=0;
    uint32_t native_tid=0;  // Zero during creator-side preparation.
  };
  enum class WorkerRetirement { normal,cancelled };
  using WorkerLease=std::shared_ptr<void>;
  struct WorkerLifecycleHooks {
    std::function<WorkerLease(const WorkerInfo &)> prepare;
    std::function<void(const WorkerInfo &,const WorkerLease &)> enter,before_tls;
    std::function<void(const WorkerInfo &,const WorkerLease &,WorkerRetirement)> retire;
  };
  // Optional transport only; no signals/collector/Java records are synthesized.
  // Install once before the first Create attempt. All callbacks run without
  // provider locks. Prepare/creation cancellation run on the creator; enter,
  // enter-failure cancellation, before_tls and normal retire run on the child.
  // prepare may throw: retire(cancelled) then receives an empty lease and must
  // revoke any partial preparation by token. Lease destruction must be passive;
  // provider callbacks belong in explicit retire, never a shared_ptr destructor.
  void SetWorkerLifecycleHooks(WorkerLifecycleHooks);
  enum class WaitPhase { ConditionReleased, MutexReacquire };
  struct WaitContext {
    uint64_t token;
    State *active_state;
    void *condition, *mutex;
    const AndroidTimespec *original_deadline;
    WaitPhase phase;
  };
  struct WaitWake {
    std::function<uint64_t()> generation;
    std::function<void()> notify;
    // Must return if generation differs, including a change before enrollment.
    // Positive relative nanoseconds bound this call; zero permits infinity.
    std::function<void(uint64_t,uint64_t)> wait;
  };
  struct WaitHooks {
    std::function<std::shared_ptr<const WaitWake>(uint64_t)> acquire;
    std::function<void(const WaitContext &)> checkpoint;
  };
  // Optional condition-wait transport, immutable before the first Create or
  // CondWait attempt. Every configured waiter requires a complete live channel.
  // Callbacks run outside provider locks; checkpoint runs only on the waiter,
  // with its guest mutex released (possibly owned by another thread). It must
  // return normally; no pthread_exit/nonlocal transfer. Admission and physical
  // root publication belong to the caller, not this transport. No signal is
  // consumed or condition notification synthesized by a channel wake.
  // Hooks/channels must outlive workers; final payload destruction is passive.
  // Transport callbacks preserve native errno/fenv. A dispatch implementation
  // must scope its own native environment separately from guest context edits.
  void SetWaitHooks(WaitHooks);
  addr_t Marker(const std::string &) const;
  uint64_t Run(addr_t entry, std::initializer_list<addr_t> args = {});
  uint64_t Run(addr_t entry, const std::vector<addr_t> &args);
  // For callers that invoke Runtime themselves: register the actual guest stack
  // before imports need pthread_getattr_np. This is not the host native stack.
  void AttachCurrentStack(void *base, uint64_t size);
  // External native threads call this before exiting to run their guest TLS
  // destructors on the correct thread. pthread_create workers do so automatically.
  int ReleaseCurrent();
  // Stop new worker creation and wait for native workers, while keeping this
  // guest callback runner alive for dependent provider finalization.
  int Shutdown();
  uint64_t Self();
  // Native calling-thread ID, checked for Android pid_t width. This is not
  // the lifetime-unique opaque pthread_self token or a Linux process-group ID.
  int32_t GetTid();
  // Optional native-only lease for the closed owned-thread capability. WHO=0
  // is actual current; other values are native TIDs, never pthread tokens.
  // Empty means a known retired target or negative Android pid_t. Unowned
  // identifiers are unsupported, not evidence of foreign OS thread absence.
  class NativeThreadLease {
   public:
    NativeThreadLease()=default;
    explicit operator bool() const noexcept { return bool(storage_); }
    uintptr_t NativeHandleBits() const noexcept;
    uint32_t NativeTid() const noexcept;
   private:
    friend class Pthreads;
    struct Storage;
    explicit NativeThreadLease(std::shared_ptr<Storage> value):storage_(std::move(value)){}
    std::shared_ptr<Storage> storage_;
  };
  // Retains a real DuplicateHandle under registry/liveness protection. No
  // callbacks run while locked. Handle release preserves native errno/fenv/
  // LastError; callers must not close or mutate ownership of its borrowed bits.
  NativeThreadLease AcquireNativeThread(uint32_t who);
  // Bounded prctl: PR_SET_NAME only. Linux ignores the other variadic arguments.
  // The first 15 bytes are truncated before strict UTF-8 conversion to Windows.
  // Errors return -1 through the configured guest errno sink; no PID effects.
  int Prctl(int32_t option, const char *name);
  int Create(uint64_t *thread, const AndroidThreadAttr *, addr_t entry, addr_t arg);
  int Join(uint64_t thread, uint64_t *result);
  int Detach(uint64_t thread);
  [[noreturn]] void Exit(uint64_t result);
  int AttrInit(AndroidThreadAttr *);
  int AttrDestroy(AndroidThreadAttr *);
  int AttrSetDetach(AndroidThreadAttr *, int);
  int AttrSetStackSize(AndroidThreadAttr *, uint64_t);
  int AttrGetStack(const AndroidThreadAttr *, uint64_t *base, uint64_t *size);
  int GetAttr(uint64_t thread, AndroidThreadAttr *);
  int MutexAttrInit(int64_t *);
  int MutexAttrDestroy(int64_t *);
  int MutexAttrSetType(int64_t *, int);
  int MutexInit(void *, const int64_t *);
  int MutexDestroy(void *);
  int MutexLock(void *, bool try_only = false);
  int MutexUnlock(void *);
  int CondAttrInit(int64_t *);
  int CondAttrDestroy(int64_t *);
  int CondAttrSetClock(int64_t *, int);
  int CondInit(void *, const int64_t *);
  int CondDestroy(void *);
  int CondWake(void *, bool all);
  int CondWait(void *, void *mutex, const AndroidTimespec *deadline = nullptr);
  int Once(int32_t *, addr_t callback);
  int KeyCreate(int32_t *, addr_t destructor);
  int KeyDelete(int32_t);
  int SetSpecific(int32_t, uint64_t);
  uint64_t GetSpecific(int32_t);
  int RwInit(void *, const int64_t *);
  int RwDestroy(void *);
  int RwLock(void *, bool write);
  int RwUnlock(void *);
  int SetName(uint64_t, const char *);
  int Kill(uint64_t, int signal);
  static int ClockGetTime(int clock, AndroidTimespec *);
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
