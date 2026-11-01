#pragma once
// Bounded normal-return signal boundary, not complete POSIX signal delivery.
#include "signal_host.h"
#include "../whole/signal_frame.h"

namespace bunker::windows {
class SignalDelivery {
 public:
  using Bounds=recomp::signal_frame::Bounds;
  using Metadata=recomp::signal_frame::Metadata;
  SignalDelivery(recomp::Runtime &,std::function<bool(addr_t)> executable,
                 addr_t normal_return_entry,Bounds registered_stack);
  // Runs on the actual worker inside a materialized Runtime context. The
  // handler uses a separate State and a real frame below the interrupted SP.
  // Supports the registered normal stack and normal C return only. The return
  // entry is a verified translated control boundary, intercepted before its
  // instructions execute; no Linux rt_sigreturn syscall is claimed.
  std::optional<uint64_t> Deliver(const SignalHost::Delivery &);
  const Metadata &ThreadMetadata() const {return metadata_;}
 private:
  recomp::Runtime &runtime_;
  std::function<bool(addr_t)> executable_;
  addr_t return_entry_;
  Bounds stack_;
  Metadata metadata_;
  std::thread::id owner_;
};
}  // namespace bunker::windows
