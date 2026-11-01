#pragma once
#include "signal_host.h"
#include <set>
namespace bunker::windows {
struct AndroidSemaphore {uint32_t opaque[4];};
struct AndroidSemaphoreTime {int64_t seconds,nanoseconds;};
static_assert(sizeof(AndroidSemaphore)==16&&alignof(AndroidSemaphore)==4);
class Semaphores {
 public:
  explicit Semaphores(SignalHost&,addr_t marker_base=0x7ff600200000ULL);
  int Init(addr_t semaphore,int shared,uint32_t value);
  int Destroy(addr_t semaphore);
  int Post(addr_t semaphore);
  int TryWait(addr_t semaphore);
  int GetValue(addr_t semaphore,int32_t *out);
  int Wait(addr_t semaphore,uint64_t token,const SignalHost::Boundary&);
  int TimedWait(addr_t semaphore,addr_t guest_deadline,uint64_t token,const SignalHost::Boundary&);
  void Install(recomp::Runtime&,SignalHost::Current,SignalHost::Boundary);
  addr_t Marker(const std::string&)const;
  void SetErrorSink(std::function<void(int)> sink){error_sink_=std::move(sink);}
 private:
  struct Semaphore;
  std::shared_ptr<Semaphore> Find(addr_t);
  int WaitImpl(const std::shared_ptr<Semaphore>&,uint64_t,const SignalHost::Boundary&,std::optional<std::chrono::system_clock::time_point>);
  int SyscallError(int);
  std::mutex registry_;std::map<addr_t,std::shared_ptr<Semaphore>> semaphores_;
  SignalHost &signals_;std::function<void(int)> error_sink_;addr_t marker_base_;bool installed_=false;
};
}
