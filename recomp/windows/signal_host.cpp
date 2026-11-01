#include "signal_host.h"
#include "../whole/bridge.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

namespace bunker::windows {
namespace {
constexpr uint32_t kSiginfo=4,kRestart=0x10000000,kOnStack=0x08000000;
constexpr uint64_t kUnblockable=(1ULL<<8)|(1ULL<<18);
constexpr uint64_t kAndroidTimer=1ULL<<31,kAndroidUnblocked=0xffULL<<32;
const char *const imports[]={"sigaction","pthread_sigmask","sigprocmask","pthread_kill","sigsuspend","sigpending","sigemptyset","sigfillset","sigaddset","sigdelset","sigismember"};
template<class T>T Read(addr_t address){T value{};recomp::ReadGuestMemory(&value,address,sizeof(value));return value;}
template<class T>void Write(addr_t address,const T&value){recomp::WriteGuestMemory(address,&value,sizeof(value));}
}
uint64_t SignalWake::Generation(){std::lock_guard lock(mutex_);return generation_;}
void SignalWake::Notify(){std::lock_guard lock(mutex_);++generation_;condition_.notify_all();}
bool SignalWake::Wait(uint64_t generation,std::optional<std::chrono::system_clock::time_point> deadline){
  std::unique_lock lock(mutex_);auto changed=[&]{return generation_!=generation;};
  if(deadline)return condition_.wait_until(lock,*deadline,changed);
  condition_.wait(lock,changed);return true;
}
struct SignalHost::Thread {
  uint64_t token,mask=0,pending=0;bool alive=true;
  std::thread::id owner;
  std::array<Info,32> info{};
  std::atomic<bool> poll{false};
  std::shared_ptr<SignalWake> wake=std::make_shared<SignalWake>();
};
SignalHost::SignalHost(Notify notify,addr_t base):request_poll_(std::move(notify)),marker_base_(base){if(base&7)throw std::invalid_argument("signal marker alignment");}
uint64_t SignalHost::Bit(int signal){return signal>0&&signal<=64?1ULL<<(signal-1):0;}
void SignalHost::Publish(const ThreadRef&t){t->poll.store(t->alive&&bool(t->pending&~t->mask),std::memory_order_release);}
void SignalHost::NotifyAfterUnlock(const ThreadRef&t){t->wake->Notify();if(request_poll_&&NeedsPoll(t))request_poll_(t->token);}
bool SignalHost::NeedsPoll(const ThreadRef&t)noexcept{return t&&t->poll.load(std::memory_order_acquire);}
SignalHost::ThreadRef SignalHost::Lookup(uint64_t token){std::lock_guard lock(mutex_);auto i=threads_.find(token);return i==threads_.end()?nullptr:i->second;}
std::shared_ptr<SignalWake> SignalHost::Wake(uint64_t token){auto thread=Lookup(token);return thread?thread->wake:nullptr;}
int SignalHost::RegisterThread(uint64_t token,uint64_t parent){
  std::lock_guard lock(mutex_);if(!token||threads_.count(token))return 22;
  uint64_t mask=kAndroidTimer;if(parent){auto i=threads_.find(parent);if(i==threads_.end()||!i->second->alive)return 3;mask=i->second->mask;}
  auto t=std::make_shared<Thread>();t->token=token;t->mask=mask;threads_.emplace(token,std::move(t));return 0;
}
int SignalHost::BindCurrent(uint64_t token){
  std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;
  auto &t=*i->second;if(t.owner!=std::thread::id{}&&t.owner!=std::this_thread::get_id())return 16;t.owner=std::this_thread::get_id();return 0;
}
int SignalHost::DropThread(uint64_t token){
  ThreadRef t;{std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;
    t=i->second;t->alive=false;t->pending=0;Publish(t);}
  NotifyAfterUnlock(t);return 0;
}
int SignalHost::Action(int signal,const AndroidSignalAction *set,AndroidSignalAction *old){
  const AndroidSignalAction desired=set?*set:AndroidSignalAction{};
  if(signal<=0||signal>=32||signal==9||signal==19)return signal>=32&&signal<=64?38:22;
  // Threads start with SS_DISABLE and no sigaltstack API is installed. A
  // registered SA_ONSTACK action therefore uses the ordinary stack.
  if(set&&(desired.flags&~(kSiginfo|kRestart|kOnStack)))return 38;
  if(set&&desired.handler>1&&(desired.handler&3))return 22;
  std::lock_guard lock(mutex_);if(old)*old=actions_[signal];
  if(set){actions_[signal]=desired;actions_[signal].padding=0;actions_[signal].mask&=~kUnblockable;
    if(desired.handler==1)for(auto &[id,t]:threads_){t->pending&=~Bit(signal);Publish(t);}}
  return 0;
}
int SignalHost::Mask(uint64_t token,int how,const uint64_t *set,uint64_t *old){
  uint64_t requested=set?*set:0;
  ThreadRef t;{std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;t=i->second;
    if(set&&(how<0||how>2))return 22;if(old)*old=t->mask;
    if(set){
      uint64_t value=requested&~kUnblockable;
      // Android13 libc reserves32 for POSIX timers and33..40 for runtimes.
      value=how==1?(value&~kAndroidTimer)|kAndroidUnblocked:(value|kAndroidTimer)&~kAndroidUnblocked;
      t->mask=how==0?t->mask|value:how==1?t->mask&~value:value;Publish(t);
    }}
  if(set)NotifyAfterUnlock(t);return 0;
}
int SignalHost::Pending(uint64_t token,uint64_t *out){
  if(!out)return 14;std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;*out=i->second->pending&i->second->mask;return 0;
}
int SignalHost::Queue(uint64_t token,int signal,const Info *info){
  if(signal<0||signal>64)return 22;
  ThreadRef t;{std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;t=i->second;
    if(!signal)return 0;if(signal>=32||signal==9||signal==19)return 38;
    if(actions_[signal].handler==0)return 38; // Default termination/stop policy is not implemented.
    if(actions_[signal].handler==1)return 0;
    if(!(t->pending&Bit(signal))){t->info[signal]=info?*info:Info{};const uint32_t number=signal;std::memcpy(t->info[signal].data(),&number,4);}
    t->pending|=Bit(signal);Publish(t);}
  NotifyAfterUnlock(t);return 0;
}
SignalHost::Dispatch SignalHost::DispatchOne(uint64_t token,const Boundary &boundary){return DispatchImpl(token,boundary,{});}
SignalHost::Dispatch SignalHost::DispatchImpl(uint64_t token,const Boundary &boundary,std::optional<uint64_t> saved_override){
  ThreadRef t;Delivery delivery{};uint64_t old;
  {std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return {3};t=i->second;
    if(t->owner!=std::this_thread::get_id())return {1};
    uint64_t eligible=t->pending&~t->mask;if(!eligible){Publish(t);return {};}
    int signal=1;while(!(eligible&Bit(signal)))++signal;
    auto action=actions_[signal];if(action.handler<=1)return {38};if(!boundary)return {38};
    old=t->mask;delivery={token,signal,action,t->info[signal],saved_override.value_or(old)};
    t->pending&=~Bit(signal);t->mask=(old|action.mask|Bit(signal))&~kUnblockable;Publish(t);
  }
  std::optional<uint64_t> restored;
  try{restored=boundary(delivery);}catch(...){
    {std::lock_guard lock(mutex_);t->mask=old;Publish(t);}NotifyAfterUnlock(t);throw;
  }
  {std::lock_guard lock(mutex_);t->mask=restored.value_or(delivery.saved_mask)&~kUnblockable;Publish(t);}
  NotifyAfterUnlock(t);return {0,true,bool(delivery.action.flags&kRestart)};
}
int SignalHost::Suspend(uint64_t token,uint64_t temporary,const Boundary &boundary){
  ThreadRef t;uint64_t old;
  {std::lock_guard lock(mutex_);auto i=threads_.find(token);if(i==threads_.end()||!i->second->alive)return 3;t=i->second;
    if(t->owner!=std::this_thread::get_id())return 1;old=t->mask;
    // Bionic sigsuspend64 applies the same reserved-signal filtering as a
    // SIG_SETMASK request, before the kernel removes SIGKILL/SIGSTOP.
    t->mask=((temporary&~kUnblockable)|kAndroidTimer)&~kAndroidUnblocked;Publish(t);}
  NotifyAfterUnlock(t);
  try{for(;;){auto generation=t->wake->Generation();auto delivered=DispatchImpl(token,boundary,old);
    if(delivered.error){std::lock_guard lock(mutex_);t->mask=old;Publish(t);return delivered.error;}
    if(delivered.handled)return 4;
    t->wake->Wait(generation);
  }}catch(...){std::lock_guard lock(mutex_);t->mask=old;Publish(t);throw;}
}
int SignalHost::SyscallError(int error){if(error&&error_sink_)error_sink_(error);return error?-1:0;}
addr_t SignalHost::Marker(const std::string &name)const{for(size_t i=0;i<std::size(imports);++i)if(name==imports[i])return marker_base_+i*8;throw std::invalid_argument("unsupported signal import: "+name);}
addr_t SignalHost::ProcessMarker(const std::string &name)const{
  for(auto process:{"sigaction","sigemptyset","sigfillset","sigaddset","sigdelset","sigismember"})if(name==process)return Marker(name);
  throw std::invalid_argument("thread signal import outside process-only subset: "+name);
}
void SignalHost::InstallProcess(recomp::Runtime &runtime){
  if(process_installed_)throw std::logic_error("signal process imports already installed");
  auto add=[&](const char *name,auto bridge){runtime.AddImport(ProcessMarker(name),[name,bridge](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"signal process %s: %s\n",name,e.what());std::abort();}catch(...){std::abort();}});};
  add("sigaction",recomp::MakeBridge<int32_t(int32_t,addr_t,addr_t)>([this](auto sig,auto set,auto old){AndroidSignalAction a{},previous{};if(set)a=Read<AndroidSignalAction>(set);int e=Action(sig,set?&a:nullptr,old?&previous:nullptr);if(!e&&old)Write(old,previous);return SyscallError(e);}));
  for(auto name:{"sigemptyset","sigfillset"})add(name,recomp::MakeBridge<int32_t(addr_t)>([this,name](auto out){if(!out)return SyscallError(22);Write(out,std::string(name)=="sigemptyset"?uint64_t(0):UINT64_MAX);return 0;}));
  for(auto name:{"sigaddset","sigdelset","sigismember"})add(name,recomp::MakeBridge<int32_t(addr_t,int32_t)>([this,name](auto out,auto sig){if(!out||!Bit(sig))return SyscallError(22);auto value=Read<uint64_t>(out);if(!std::strcmp(name,"sigismember"))return int(bool(value&Bit(sig)));value=std::strcmp(name,"sigaddset")?value&~Bit(sig):value|Bit(sig);Write(out,value);return 0;}));
  process_installed_=true;
}
void SignalHost::Install(recomp::Runtime &runtime,Current current,Boundary boundary){
  if(installed_||!current)throw std::logic_error("signal imports need one explicit current-token binding");
  if(!process_installed_)InstallProcess(runtime);
  auto add=[&](const char *name,auto bridge){runtime.AddImport(Marker(name),[name,bridge](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"signal foundation %s: %s\n",name,e.what());std::abort();}catch(...){std::abort();}});};
  for(auto name:{"pthread_sigmask","sigprocmask"})add(name,recomp::MakeBridge<int32_t(int32_t,addr_t,addr_t)>([this,current,name](auto how,auto set,auto old){uint64_t value=set?Read<uint64_t>(set):0,previous=0;int e=Mask(current(),how,set?&value:nullptr,old?&previous:nullptr);if(!e&&old)Write(old,previous);return std::string(name)=="pthread_sigmask"?e:SyscallError(e);}));
  add("pthread_kill",recomp::MakeBridge<int32_t(uint64_t,int32_t)>([this](auto token,auto sig){return Queue(token,sig);}));
  add("sigsuspend",recomp::MakeBridge<int32_t(addr_t)>([this,current,boundary](auto mask){return SyscallError(mask?Suspend(current(),Read<uint64_t>(mask),boundary):14);}));
  add("sigpending",recomp::MakeBridge<int32_t(addr_t)>([this,current](auto out){uint64_t pending=0;int e=out?Pending(current(),&pending):14;if(!e)Write(out,pending);return SyscallError(e);}));
  installed_=true;
}
}  // namespace bunker::windows
