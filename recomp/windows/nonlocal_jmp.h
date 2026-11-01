#pragma once
#include "../whole/runtime.h"
#include <array>
#include <functional>
#include <map>
#include <mutex>
#include <optional>
#include <exception>
#include <string>

namespace bunker::windows {
// Android 13 arm64, non-HWASan, PAC-disabled virtual CPU profile only.
// This adapter saves a real Bionic wire context; it does not implement native
// control transfer. Never pass this buffer to a Windows CRT setjmp/longjmp.
class NonlocalJumps {
 public:
  static constexpr size_t kJmpBytes=256,kSigJmpBytes=264,kWrittenBytes=200;
  struct Thread {uint64_t token=0,generation=0;addr_t stack_low=0,stack_high=0;};
  struct Region {addr_t low=0,high=0;uint64_t generation=0;};
  using Current=std::function<Thread()>;
  // Must return an owning region lifetime generation, not merely a VirtualQuery
  // mapping identity. Owner revokes/changes it on reuse. A custom arena mapping
  // cannot establish individual C subobject/frame lifetimes inside that arena.
  using Environment=std::function<std::optional<Region>(addr_t,size_t)>;
  using Mask=std::function<uint64_t()>;
  using Executable=std::function<bool(addr_t)>;
  struct Plan {
    uint64_t thread=0,thread_generation=0,environment_generation=0;
    addr_t environment=0,pc=0,sp=0;
    uint64_t scs_low=0;
    std::array<uint64_t,12> x19_x30{};
    std::array<uint64_t,8> d8_d15{};
    std::optional<uint64_t> mask;
    uint32_t value=1;
  };
  NonlocalJumps(Current,Environment,Mask,Executable,
                uint64_t cookie=RandomCookie(),addr_t marker_base=0x7ff460000000ULL);
  static uint64_t RandomCookie();
  void Save(State&,addr_t environment,int save_mask,size_t declared_size=kJmpBytes);
  Plan Inspect(const State&,addr_t environment,int value);
  // Pure state materialization for tests/future controlled dispatch. This does
  // not restore the signal mask or perform a nonlocal transfer.
  static State Materialize(const State &current,const Plan&);
  void Forget(addr_t environment);
  void DropThread(uint64_t token,uint64_t generation);
  addr_t Marker(const std::string&)const;
  void Install(recomp::Runtime&);
 private:
  struct Saved {Thread thread;Region region;size_t size;};
  std::pair<Thread,Region> Check(addr_t,size_t)const;
  [[noreturn]] static void Fatal(const char*,const State&,const std::exception&)noexcept;
  Current current_;Environment environment_;Mask mask_;Executable executable_;
  uint64_t cookie_;addr_t marker_base_;std::mutex mutex_;
  std::map<addr_t,Saved> saved_;bool installed_=false;
};
}  // namespace bunker::windows
