#include "semaphore_host.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>

namespace bunker::windows {
namespace {constexpr uint32_t kMaximum=0x3fffffff;const char *const imports[]={"sem_init","sem_destroy","sem_post","sem_trywait","sem_getvalue","sem_wait","sem_timedwait"};}
struct Semaphores::Semaphore {
  std::mutex mutex;addr_t address=0;uint32_t count=0;bool dead=false;
  std::map<SignalWake*,std::pair<std::shared_ptr<SignalWake>,size_t>> waiters;
  void Publish(){const uint32_t wire=count?count<<1:waiters.empty()?0:0xfffffffe;recomp::WriteGuestMemory(address,&wire,4);}
};
Semaphores::Semaphores(SignalHost&s,addr_t base):signals_(s),marker_base_(base){if(base&7)throw std::invalid_argument("semaphore marker alignment");}
std::shared_ptr<Semaphores::Semaphore> Semaphores::Find(addr_t address){std::lock_guard lock(registry_);auto i=semaphores_.find(address);return i==semaphores_.end()?nullptr:i->second;}
int Semaphores::Init(addr_t address,int shared,uint32_t value){
  if(!address||(address&3)||value>kMaximum)return 22;if(shared)return 38;
  std::lock_guard lock(registry_);if(semaphores_.count(address))return 16;
  auto semaphore=std::make_shared<Semaphore>();semaphore->address=address;semaphore->count=value;
  AndroidSemaphore wire{};wire.opaque[0]=value<<1;
  recomp::InvalidateGuestMemory(address,sizeof(wire));recomp::WriteGuestMemory(address,&wire,sizeof(wire));
  semaphores_.emplace(address,std::move(semaphore));return 0;
}
int Semaphores::Destroy(addr_t address){
  std::unique_lock registry(registry_);auto i=semaphores_.find(address);if(i==semaphores_.end())return 22;auto s=i->second;
  {std::lock_guard lock(s->mutex);if(s->dead)return 22;if(!s->waiters.empty())return 16;s->dead=true;}
  semaphores_.erase(i);recomp::InvalidateGuestMemory(address,sizeof(AndroidSemaphore));return 0;
}
int Semaphores::Post(addr_t address){
  auto s=Find(address);if(!s)return 22;std::vector<std::shared_ptr<SignalWake>> wake;
  {std::lock_guard lock(s->mutex);if(s->dead)return 22;if(s->count==kMaximum)return 75;++s->count;s->Publish();
    for(auto &[key,value]:s->waiters)wake.push_back(value.first);}
  for(auto &event:wake)event->Notify();return 0;
}
int Semaphores::TryWait(addr_t address){auto s=Find(address);if(!s)return 22;std::lock_guard lock(s->mutex);if(s->dead)return 22;if(!s->count)return 11;--s->count;s->Publish();return 0;}
int Semaphores::GetValue(addr_t address,int32_t *out){if(!out)return 14;auto s=Find(address);if(!s)return 22;std::lock_guard lock(s->mutex);if(s->dead)return 22;*out=int32_t(s->count);return 0;}
int Semaphores::Wait(addr_t address,uint64_t token,const SignalHost::Boundary&boundary){auto s=Find(address);return s?WaitImpl(s,token,boundary,{}):22;}
int Semaphores::TimedWait(addr_t address,addr_t deadline,uint64_t token,const SignalHost::Boundary&boundary){
  // Android13 tries the token before dereferencing/validating the timespec.
  auto s=Find(address);if(!s)return 22;
  {std::lock_guard lock(s->mutex);if(s->dead)return 22;if(s->count){--s->count;s->Publish();return 0;}}
  if(!deadline)return 14;AndroidSemaphoreTime time{};recomp::ReadGuestMemory(&time,deadline,sizeof(time));
  if(time.nanoseconds<0||time.nanoseconds>=1000000000)return 22;if(time.seconds<0)return 110;
  using Clock=std::chrono::system_clock;
  const auto maximum=std::chrono::duration_cast<std::chrono::seconds>(Clock::duration::max()).count();
  if(time.seconds>maximum)return 75;
  const auto seconds=std::chrono::duration_cast<Clock::duration>(std::chrono::seconds(time.seconds));
  const auto nanos=std::chrono::duration_cast<Clock::duration>(std::chrono::nanoseconds(time.nanoseconds));
  if(seconds>Clock::duration::max()-nanos)return 75;
  return WaitImpl(s,token,boundary,Clock::time_point(seconds+nanos));
}
int Semaphores::WaitImpl(const std::shared_ptr<Semaphore>&s,uint64_t token,const SignalHost::Boundary&boundary,std::optional<std::chrono::system_clock::time_point> deadline){
  auto wake=signals_.Wake(token);if(!wake)return 3;
  {std::lock_guard lock(s->mutex);if(s->dead)return 22;auto &entry=s->waiters[wake.get()];entry.first=wake;++entry.second;s->Publish();}
  struct Scope{std::shared_ptr<Semaphore>s;SignalWake*key;~Scope(){std::lock_guard lock(s->mutex);auto i=s->waiters.find(key);if(i!=s->waiters.end()&&!--i->second.second)s->waiters.erase(i);s->Publish();}} scope{s,wake.get()};
  for(;;){
    auto generation=wake->Generation();
    {std::lock_guard lock(s->mutex);if(s->dead)return 22;if(s->count){--s->count;s->Publish();return 0;}}
    if(deadline&&std::chrono::system_clock::now()>=*deadline)return 110;
    auto delivered=signals_.DispatchOne(token,boundary);if(delivered.error)return delivered.error;
    // Linux futex waits with an absolute timeout use ERESTART_RESTARTBLOCK,
    // which becomes EINTR after a caught handler even with SA_RESTART.
    if(delivered.handled){if(!delivered.restart||deadline)return 4;continue;}
    wake->Wait(generation,deadline);
  }
}
int Semaphores::SyscallError(int error){if(error&&error_sink_)error_sink_(error);return error?-1:0;}
addr_t Semaphores::Marker(const std::string&name)const{for(size_t i=0;i<std::size(imports);++i)if(name==imports[i])return marker_base_+i*8;throw std::invalid_argument("unsupported semaphore import: "+name);}
void Semaphores::Install(recomp::Runtime &runtime,SignalHost::Current current,SignalHost::Boundary boundary){
  if(installed_||!current)throw std::logic_error("semaphore imports need explicit current binding");
  auto add=[&](const char*name,auto bridge){runtime.AddImport(Marker(name),[bridge,name](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"semaphore foundation %s: %s\n",name,e.what());std::abort();}catch(...){std::abort();}});};
  add("sem_init",recomp::MakeBridge<int32_t(addr_t,int32_t,uint32_t)>([this](auto p,auto shared,auto value){return SyscallError(Init(p,shared,value));}));
  add("sem_destroy",recomp::MakeBridge<int32_t(addr_t)>([this](auto p){return SyscallError(Destroy(p));}));
  add("sem_post",recomp::MakeBridge<int32_t(addr_t)>([this](auto p){return SyscallError(Post(p));}));
  add("sem_trywait",recomp::MakeBridge<int32_t(addr_t)>([this](auto p){return SyscallError(TryWait(p));}));
  add("sem_getvalue",recomp::MakeBridge<int32_t(addr_t,addr_t)>([this](auto p,auto out){int32_t value=0;int e=out?GetValue(p,&value):14;if(!e)recomp::WriteGuestMemory(out,&value,4);return SyscallError(e);}));
  add("sem_wait",recomp::MakeBridge<int32_t(addr_t)>([this,current,boundary](auto p){return SyscallError(Wait(p,current(),boundary));}));
  add("sem_timedwait",recomp::MakeBridge<int32_t(addr_t,addr_t)>([this,current,boundary](auto p,auto timeout){return SyscallError(TimedWait(p,timeout,current(),boundary));}));
  installed_=true;
}
}
