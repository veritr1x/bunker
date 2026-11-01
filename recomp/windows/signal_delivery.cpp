#include "signal_delivery.h"
#include <stdexcept>

namespace bunker::windows {
SignalDelivery::SignalDelivery(recomp::Runtime &runtime,std::function<bool(addr_t)> executable,
                               addr_t normal_return_entry,Bounds registered_stack)
    :runtime_(runtime),executable_(std::move(executable)),return_entry_(normal_return_entry),
     stack_(registered_stack),owner_(std::this_thread::get_id()) {
  if(!executable_||!return_entry_||(return_entry_&3)||!executable_(return_entry_)||
      !stack_.low||stack_.high<=stack_.low)throw std::invalid_argument("invalid signal delivery stack/return entry");
}
std::optional<uint64_t> SignalDelivery::Deliver(const SignalHost::Delivery &delivery){
  using namespace recomp::signal_frame;
  if(owner_!=std::this_thread::get_id())throw std::invalid_argument("signal frame delivery on wrong native worker");
  auto *interrupted=recomp::CurrentExecutionState();
  if(!interrupted)throw std::invalid_argument("signal frame delivery outside materialized guest execution");
  if(!delivery.action.handler||!executable_(delivery.action.handler)||
      (delivery.action.flags&~uint32_t(4|0x10000000)))throw std::invalid_argument("unsupported signal disposition at frame boundary");
  Metadata saved=metadata_;
  Metadata context=saved;context.mask=delivery.saved_mask;context.siginfo=delivery.info;
  Request request{stack_,stack_,interrupted->gpr.sp.qword,delivery.action.handler,return_entry_,
                  delivery.signal,bool(delivery.action.flags&4)};
  const auto image=Serialize(*interrupted,context,request);
  // Materialize every interrupted register into actual registered guest-stack
  // bytes before running the handler. There is no global lock across Run.
  __remill_aarch64_clear_exclusive(*interrupted);
  recomp::WriteGuestMemory(image.base,image.bytes.data(),image.bytes.size());
  State handler=image.handler_state;
  metadata_.pstate=image.handler_pstate;
  try{
    runtime_.Run(handler,delivery.action.handler);
    if(handler.gpr.pc.qword!=return_entry_||handler.gpr.sp.qword!=image.base)
      throw std::runtime_error("signal handler did not return through its bounded frame boundary");
    auto bytes=image.bytes;
    recomp::ReadGuestMemory(bytes.data(),image.base,bytes.size());
    const auto restored=Restore({image.base,bytes.data(),bytes.size()},image.base,stack_,*interrupted);
    if(restored.state.gpr.pc.qword!=interrupted->gpr.pc.qword)
      throw std::invalid_argument("signal context PC redirection is unsupported by translated continuation");
    constexpr uint64_t nzcv=0xf0000000ULL;
    if((restored.metadata.pstate&~nzcv)!=(saved.pstate&~nzcv)||
        restored.metadata.altstack.pointer!=saved.altstack.pointer||
        restored.metadata.altstack.size!=saved.altstack.size||restored.metadata.altstack.flags!=saved.altstack.flags)
      throw std::invalid_argument("signal context changes unsupported PSTATE or alternate stack policy");
    *interrupted=restored.state;metadata_=restored.metadata;
    return restored.metadata.mask;
  }catch(...){metadata_=saved;throw;}
}
}  // namespace bunker::windows
