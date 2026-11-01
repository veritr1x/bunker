#pragma once
// Pure Android AArch64 frame bytes. No delivery, sigreturn, or GC integration.
#include "runtime.h"
#include <array>
#include <cstdint>
#include <vector>

namespace recomp::signal_frame {
constexpr size_t kSiginfoSize=128,kUcontextSize=4560,kFrameSize=4688,kFrameRecordSize=16;
constexpr size_t kUcontextOffset=128,kMachineOffset=304,kFpsimdOffset=592,kFpsimdSize=528;
constexpr uint32_t kFpsimdMagic=0x46508001;
struct Bounds {addr_t low,high;}; // Half-open registered guest stack range.
struct AltStack {addr_t pointer=0;uint32_t flags=2;uint64_t size=0;};
struct Metadata {
  uint64_t pstate=0,mask=0,fault_address=0,uc_flags=0,uc_link=0;
  AltStack altstack;
  std::array<uint8_t,kSiginfoSize> siginfo{};
};
struct Request {
  Bounds interrupted_stack,delivery_stack;
  addr_t stack_top,handler,restorer;
  int32_t signal;
  bool siginfo_handler=true;
};
struct Image {
  addr_t base=0,frame_record=0,info=0,ucontext=0;
  std::vector<uint8_t> bytes;
  State handler_state{};
  uint64_t handler_pstate=0;
};
struct View {addr_t base;const uint8_t *bytes;size_t size;};
struct Restored {State state;Metadata metadata;};
Image Serialize(const State &,const Metadata &,const Request &);
// Baseline supplies TLS and Remill-only state not represented in ucontext.
// Parse/validation is transactional: neither the baseline nor bytes are changed.
Restored Restore(const View &,addr_t frame_base,Bounds allowed_saved_stack,const State &baseline);
}  // namespace recomp::signal_frame
