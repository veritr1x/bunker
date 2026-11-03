#pragma once
// Isolated signal policy foundation. No asynchronous/native signal delivery.
#include "../whole/runtime.h"
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <thread>

namespace bunker::windows {
class SignalWake {
 public:
  uint64_t Generation();
  bool WaitRelative(uint64_t generation,std::chrono::nanoseconds maximum);
  void Notify();
  bool Wait(uint64_t generation,std::optional<std::chrono::system_clock::time_point> deadline={});
 private:
  std::mutex mutex_;std::condition_variable condition_;uint64_t generation_=0;
};
struct AndroidSignalAction {uint32_t flags=0,padding=0;addr_t handler=0;uint64_t mask=0;addr_t restorer=0;};
static_assert(sizeof(AndroidSignalAction)==32);
struct AndroidSignalStack {addr_t pointer=0;int32_t flags=2;uint32_t padding=0;uint64_t size=0;};
static_assert(sizeof(AndroidSignalStack)==24&&alignof(AndroidSignalStack)==8);
static_assert(offsetof(AndroidSignalStack,flags)==8&&offsetof(AndroidSignalStack,size)==16);
class SignalHost {
 public:
  using Info=std::array<uint8_t,128>;
  struct StackRegion {addr_t low=0,high=0;uint64_t generation=0;};
  struct StackLease {StackRegion region;std::shared_ptr<void> lifetime;};
  using StackResolver=std::function<std::optional<StackRegion>(addr_t,size_t)>;
  using StackAcquire=std::function<std::optional<StackLease>(addr_t,size_t,uint64_t)>;
  struct StackSnapshot {AndroidSignalStack configured;std::optional<StackRegion> region;uint64_t epoch=0;};
  struct Delivery {uint64_t token;int signal;AndroidSignalAction action;Info info;uint64_t saved_mask;StackSnapshot stack;};
  // Return a mask only when an explicit user-context edit overrides restoration.
  using Boundary=std::function<std::optional<uint64_t>(const Delivery&)>;
  using Notify=std::function<void(uint64_t)>;
  using Current=std::function<uint64_t()>;
  struct SenderIdentity { int32_t process_id=0; uint32_t real_uid=0; };
  // Explicit virtual-process identity, never a pthread token/native target TID.
  // Must be read-only and preserve guest errno; captured owners outlive imports.
  // Called outside provider locks; native errno/fenv/LastError are restored.
  using SenderSnapshot=std::function<SenderIdentity()>;
  struct Dispatch {int error=0;bool handled=false,restart=false;};
  struct Thread;
  using ThreadRef=std::shared_ptr<Thread>;
  explicit SignalHost(Notify request_poll={},addr_t marker_base=0x7ff600100000ULL,
                      StackResolver stack_resolver={},StackAcquire stack_acquire={});
  // Primitive status returns are positive Android errno values; Install adapts
  // POSIX -1/errno versus pthread direct-error conventions. Lifecycle is explicit:
  // owner must DropThread on exit and keep this host alive through all callbacks.
  int RegisterThread(uint64_t token,uint64_t parent=0);
  int BindCurrent(uint64_t token);
  int DropThread(uint64_t token);
  ThreadRef Lookup(uint64_t token);
  static bool NeedsPoll(const ThreadRef&) noexcept;
  std::shared_ptr<SignalWake> Wake(uint64_t token);
  int Action(int signal,const AndroidSignalAction *set,AndroidSignalAction *old);
  int Mask(uint64_t token,int how,const uint64_t *set,uint64_t *old);
  int Pending(uint64_t token,uint64_t *out);
  // Typed arguments are host snapshots, not unvalidated guest pointers. The
  // import snapshots/tracks the real 24-byte ARM64 wire object separately.
  int AltStack(uint64_t token,addr_t current_sp,const AndroidSignalStack *set,AndroidSignalStack *old);
  StackSnapshot AlternateStack(uint64_t token);
  StackLease AcquireAlternateStack(uint64_t token,const StackSnapshot&);
  void RestoreAlternateStack(uint64_t token,addr_t restored_sp,const StackSnapshot&);
  static bool OnAlternateStack(const AndroidSignalStack&,addr_t sp);
  int Queue(uint64_t token,int signal,const Info *info=nullptr);
  // Optional pthread_kill profile. Invalid/zero/ignored paths do not snapshot;
  // identity failure throws before queue mutation, without a synthetic fallback.
  int ThreadKill(uint64_t token,int signal,const SenderSnapshot&);
  Dispatch DispatchOne(uint64_t token,const Boundary&);
  // Select only allowed unmasked pending signals, atomically before consuming.
  // Unallowed pending/info and global NeedsPoll remain intact; no predicate runs
  // under the signal mutex. Zero permits no delivery.
  Dispatch DispatchOneAllowed(uint64_t token,uint64_t allowed_signal_bits,const Boundary&);
  // Reject any eligible excluded signal with95 before selecting/consuming any.
  Dispatch DispatchOneAdmitted(uint64_t token,uint64_t allowed_signal_bits,const Boundary&);
  int Suspend(uint64_t token,uint64_t temporary_mask,const Boundary&); // positive EINTR normally
  // Dispositions and pure sigset helpers only; does not enable thread signals.
  void InstallProcess(recomp::Runtime&);
  addr_t ProcessMarker(const std::string&)const;
  // Empty sender retains the legacy bounded Queue siginfo profile unchanged.
  void Install(recomp::Runtime&,Current,Boundary,SenderSnapshot sender={});
  addr_t Marker(const std::string&)const;
  void SetErrorSink(std::function<void(int)> sink){error_sink_=std::move(sink);}
  static uint64_t Bit(int signal);
 private:
  Dispatch DispatchImpl(uint64_t,const Boundary&,std::optional<uint64_t> saved_override,uint64_t allowed_signal_bits=UINT64_MAX,bool reject_unallowed=false);
  void Publish(const ThreadRef&);
  void NotifyAfterUnlock(const ThreadRef&);
  int SyscallError(int);
  std::mutex mutex_;std::map<uint64_t,ThreadRef> threads_;
  std::array<AndroidSignalAction,32> actions_{};
  Notify request_poll_;std::function<void(int)> error_sink_;addr_t marker_base_;bool installed_=false,process_installed_=false;
  StackResolver stack_resolver_;StackAcquire stack_acquire_;
};
}  // namespace bunker::windows
