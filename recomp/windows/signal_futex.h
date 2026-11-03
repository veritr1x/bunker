#pragma once
#include "signal_host.h"
#include <memory>
namespace bunker::windows {
// One explicit virtual process's private futex namespace. Must outlive imports
// and callers; all waits/handlers must finish before destruction. No word pin
// persists after comparison: a private key remains numeric VA, even if unmapped.
class SignalFutexes {
 public:
  // Runs outside queue/memory/model locks, only after matching WAIT enrolled.
  // Read-only policy; no guest execution or queue/mask changes. A zero policy
  // is the actual bootstrap profile: no new provider root/safepoint admission.
  using Admission=std::function<uint64_t(uint64_t)>;
  using Observe=std::function<void(const State&,uint64_t)>;
  SignalFutexes(SignalHost&,SignalHost::Current,SignalHost::Boundary,Admission,
                addr_t marker_base=0x7ff600400000ULL);
  ~SignalFutexes();
  SignalFutexes(const SignalFutexes&)=delete;
  SignalFutexes&operator=(const SignalFutexes&)=delete;
  void SetErrorSink(std::function<void(int)>);
  // Android LP64 public number is long64, decoded by the kernel's low32.
  // Only low32 nr98: low32 op==0x80 with timeout0, or op==0x81. The observer
  // still receives the original unmodified raw64 X0 and all other registers.
  // WAKE ignores timeout/uaddr2/val3. WAIT ignores uaddr2/val3. Other shapes
  // stop explicitly. Alignment precedes fixed untagged lower48 range policy;
  // tagged-address ABI is unsupported, never silently untagged.
  int64_t Syscall(int64_t number,addr_t address,int32_t operation,uint32_t value,
                  addr_t timeout,addr_t address2,uint32_t value3);
  addr_t Marker(const std::string&)const;
  // Observer executes before the operation with actual original X0..X6/stack
  // and token; empty observer emits a compact native-thread/register witness.
  void Install(recomp::Runtime&,Observe observer={});
 private:
  struct Impl;std::unique_ptr<Impl> impl_;
};
}
