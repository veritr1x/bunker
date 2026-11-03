#include <cfenv>
#include "signal_futex.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <list>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/uio.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif
namespace bunker::windows {
namespace {
constexpr uint64_t kUserLimit=UINT64_C(1)<<48,kUntagMask=UINT64_C(0x00ffffffffffffff);
struct Environment {
 int error=errno;fenv_t environment{};bool handled=false;
#ifdef _WIN32
 DWORD last_error=GetLastError();
#endif
 Environment(){std::fegetenv(&environment);}
 ~Environment(){std::fesetenv(&environment);if(handled)if(auto*s=recomp::CurrentExecutionState()){const int modes[]={FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO};std::fesetround(modes[s->fpcr.rmode]);}errno=error;
#ifdef _WIN32
 SetLastError(last_error);
#endif
 }
};
int KeyError(addr_t address){
 if(address&3)return 22;
 const auto low=address&kUntagMask;
 // Fixed software virtual-user profile, not inferred native VMA or a claim
 // about the original device's VA_BITS/PR_TAGGED_ADDR_CTRL configuration.
 if(low>=kUserLimit||4>kUserLimit-low)return 14;
 if(address!=low)throw std::runtime_error("unsupported syscall98 tagged-address ABI profile");
 return 0;
}
bool ReadWord(addr_t address,uint32_t&value){
 bool okay=false;uint64_t unsupported=0;
 recomp::WithGuestMemoryRead([&]{
#ifdef _WIN32
  SIZE_T bytes=0;const BOOL success=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,sizeof(value),&bytes);
  if(success&&bytes==sizeof(value)){okay=true;return;}
  const auto error=GetLastError();
  if(error==ERROR_PARTIAL_COPY||error==ERROR_NOACCESS||error==ERROR_INVALID_ADDRESS)return;
  unsupported=error?error:UINT64_MAX;
#else
  iovec local{&value,sizeof(value)},remote{reinterpret_cast<void*>(address),sizeof(value)};
  const auto bytes=process_vm_readv(getpid(),&local,1,&remote,1,0);
  if(bytes==ssize_t(sizeof(value))){okay=true;return;}
  if(bytes>=0||errno==EFAULT)return;
  unsupported=errno?uint64_t(errno):UINT64_MAX;
#endif
 });
 if(unsupported)throw std::runtime_error("unsupported futex native fault-safe read API failure "+std::to_string(unsupported));
 return okay;
}
uint64_t NativeTid(){
#ifdef _WIN32
 return GetCurrentThreadId();
#else
 const auto tid=::syscall(SYS_gettid);if(tid<=0)throw std::runtime_error("futex observer native gettid failed");return uint64_t(tid);
#endif
}
}
struct SignalFutexes::Impl {
 struct Ticket {addr_t key;std::shared_ptr<SignalWake>wake;bool linked=false,woken=false;};
 SignalHost&signals;SignalHost::Current current;SignalHost::Boundary boundary;Admission admission;
 std::function<void(int)>error_sink;addr_t marker;bool installed=false,closing=false;
 std::mutex mutex;std::map<addr_t,std::list<std::shared_ptr<Ticket>>>queues;size_t callers=0;
 Impl(SignalHost&s,SignalHost::Current c,SignalHost::Boundary b,Admission a,addr_t m):signals(s),current(std::move(c)),boundary(std::move(b)),admission(std::move(a)),marker(m){if(!current||!admission||m%8)throw std::invalid_argument("futex provider requires explicit current/admission and aligned marker");}
 struct Call {
  Impl&p;explicit Call(Impl&owner):p(owner){std::lock_guard lock(p.mutex);if(p.closing)throw std::runtime_error("futex provider is closed");++p.callers;}
  ~Call(){std::lock_guard lock(p.mutex);if(!p.callers){std::fputs("futex active-call underflow\n",stderr);std::abort();}--p.callers;}
 };
 void RemoveLocked(const std::shared_ptr<Ticket>&ticket){
  if(!ticket->linked)return;
  auto it=queues.find(ticket->key);if(it==queues.end())throw std::logic_error("futex linked ticket has no queue");
  auto member=std::find(it->second.begin(),it->second.end(),ticket);if(member==it->second.end())throw std::logic_error("futex ticket missing from queue");
  it->second.erase(member);ticket->linked=false;if(it->second.empty())queues.erase(it);
 }
 struct Registration {
  Impl&p;std::shared_ptr<Ticket>ticket;
  ~Registration(){try{std::lock_guard lock(p.mutex);p.RemoveLocked(ticket);}catch(...){std::fputs("futex explicit ticket retirement failed\n",stderr);std::abort();}}
 };
 int64_t Fail(int error){if(!error_sink)throw std::logic_error("futex syscall error without guest errno sink");error_sink(error);return -1;}
 uint64_t Current(){const auto token=current();if(!signals.Lookup(token)||signals.DispatchOneAllowed(token,0,{}).error)throw std::runtime_error("unsupported futex call without actual bound current signal owner");return token;}
 int64_t Wake(addr_t address,uint32_t bits){
  int32_t requested;std::memcpy(&requested,&bits,sizeof(requested));const auto maximum=requested>0?uint64_t(requested):uint64_t(1);
  std::vector<std::shared_ptr<SignalWake>>notify;
  {std::lock_guard lock(mutex);auto it=queues.find(address);if(it==queues.end())return 0;
   notify.reserve(std::min<uint64_t>(it->second.size(),maximum));
   while(!it->second.empty()&&notify.size()<maximum){auto ticket=it->second.front();it->second.pop_front();ticket->linked=false;ticket->woken=true;notify.push_back(ticket->wake);}
   if(it->second.empty())queues.erase(it);
  }
  // Native channel notification only; selected flags/counts were committed
  // under the one queue lock. Never synthesize a guest word or signal/GC ack.
  for(auto&w:notify)w->Notify();
  return int64_t(notify.size());
 }
 int64_t Wait(addr_t address,uint32_t expected,uint64_t token,Environment&environment){
  auto retained=signals.Lookup(token);auto wake=signals.Wake(token);if(!retained||!wake)throw std::runtime_error("futex wait lost actual signal lifetime");
  for(;;){
   auto ticket=std::make_shared<Ticket>();ticket->key=address;ticket->wake=wake;
   int setup_error=0;
   {std::lock_guard lock(mutex);uint32_t word=0;
    // Lock order is queue -> Runtime memory. The readonly callback cannot
    // reenter a provider, write, wait, or invoke guest code.
    if(!ReadWord(address,word))setup_error=14;
    else if(word!=expected)setup_error=11;
    else{
     auto inserted=queues.try_emplace(address);
     try{inserted.first->second.push_back(ticket);}catch(...){if(inserted.second&&inserted.first->second.empty())queues.erase(inserted.first);throw;}
     ticket->linked=true;
    }
   }
   if(setup_error)return Fail(setup_error);
   Registration registration{*this,ticket};bool restart=false;
   for(;;){
    const auto generation=wake->Generation();
    {std::lock_guard lock(mutex);if(ticket->woken)return 0;}
    const auto allowed=admission(token);
    const auto result=signals.DispatchOneAdmitted(token,allowed,[&](const auto&delivery){
     // Linux withdraws the ticket before a caught handler. A genuine wake
     // which already selected this ticket still wins syscall success.
     {std::lock_guard lock(mutex);RemoveLocked(ticket);}
     if(!boundary)throw std::runtime_error("unsupported futex caught handler without qualified boundary");
     auto restored=boundary(delivery);environment.handled=true;return restored;
    });
    if(result.error){
     {std::lock_guard lock(mutex);if(ticket->woken)return 0;}
     if(result.error==95)throw std::runtime_error("unsupported futex eligible signal outside admitted provider phase");
     throw std::runtime_error("unsupported futex signal ownership or handler boundary");
    }
    if(result.handled){
     {std::lock_guard lock(mutex);if(ticket->woken)return 0;}
     if(!result.restart)return Fail(4);
     restart=true;break;
    }
    {std::lock_guard lock(mutex);if(ticket->woken)return 0;}
    wake->Wait(generation);
   }
   if(!restart)throw std::logic_error("futex retry without caught SA_RESTART handler");
   // Registration retires before the next iteration. Original expected stays
   // fixed: a handler changing the word yields EAGAIN on the fresh comparison.
  }
 }
};
SignalFutexes::SignalFutexes(SignalHost&s,SignalHost::Current c,SignalHost::Boundary b,Admission a,addr_t m):impl_(std::make_unique<Impl>(s,std::move(c),std::move(b),std::move(a),m)){}
SignalFutexes::~SignalFutexes(){std::lock_guard lock(impl_->mutex);impl_->closing=true;if(impl_->callers||!impl_->queues.empty()){std::fputs("futex provider destroyed before calls/handlers quiesced\n",stderr);std::abort();}}
void SignalFutexes::SetErrorSink(std::function<void(int)>sink){impl_->error_sink=std::move(sink);}
addr_t SignalFutexes::Marker(const std::string&name)const{if(name!="syscall")throw std::invalid_argument("unsupported private futex import: "+name);return impl_->marker;}
int64_t SignalFutexes::Syscall(int64_t number,addr_t address,int32_t operation,uint32_t value,addr_t timeout,addr_t address2,uint32_t value3){
 Environment environment;Impl::Call call(*impl_);(void)address2;(void)value3;
 if(uint32_t(number)!=98)throw std::runtime_error("unsupported Android syscall low32 number outside98");
 if(operation!=0x80&&operation!=0x81)throw std::runtime_error("unsupported syscall98 outside private WAIT/WAKE");
 if(operation==0x80&&timeout)throw std::runtime_error("unsupported private futex WAIT timeout profile");
 if(const auto error=KeyError(address))return impl_->Fail(error);
 const auto token=impl_->Current();if(operation==0x81)return impl_->Wake(address,value);
 return impl_->Wait(address,value,token,environment);
}
void SignalFutexes::Install(recomp::Runtime&runtime,Observe observer){
 if(impl_->installed||!impl_->error_sink)throw std::logic_error("futex install requires one complete errno-bound provider");
 auto bridge=recomp::MakeBridge<int64_t(int64_t,addr_t,int32_t,uint32_t,addr_t,addr_t,uint32_t)>([this](auto n,auto a,auto op,auto v,auto t,auto a2,auto v3){return Syscall(n,a,op,v,t,a2,v3);});
 runtime.AddImport(impl_->marker,[this,bridge,observer](State&s){try{
  {Environment observation;const auto token=impl_->current();if(observer)observer(s,token);else std::fprintf(stderr,"Futex syscall witness token=%#llx native_tid=%llu X0=%#llx X1=%#llx X2=%#llx X3=%#llx X4=%#llx X5=%#llx X6=%#llx SP=%#llx LR=%#llx; before operation\n",(unsigned long long)token,(unsigned long long)NativeTid(),(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,(unsigned long long)s.gpr.x2.qword,(unsigned long long)s.gpr.x3.qword,(unsigned long long)s.gpr.x4.qword,(unsigned long long)s.gpr.x5.qword,(unsigned long long)s.gpr.x6.qword,(unsigned long long)s.gpr.sp.qword,(unsigned long long)s.gpr.x30.qword);}
  bridge(s);
 }catch(const std::exception&e){std::fprintf(stderr,"private futex syscall: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fputs("private futex syscall: unknown exception\n",stderr);std::fflush(stderr);std::abort();}});impl_->installed=true;
}
}
