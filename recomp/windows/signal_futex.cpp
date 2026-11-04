#include <cfenv>
#include "signal_futex.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <list>
#include <limits>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
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
struct Timeout {int64_t seconds,nanoseconds;};
static_assert(sizeof(Timeout)==16&&offsetof(Timeout,nanoseconds)==8);
int TimeoutRangeError(addr_t address){
 const auto low=address&kUntagMask;
 if(low>=kUserLimit||sizeof(Timeout)>kUserLimit-low)return 14;
 if(address!=low)throw std::runtime_error("unsupported syscall98 tagged timeout-address ABI profile");
 return 0;
}
bool ReadTimeout(addr_t address,Timeout&value){
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
 if(unsupported)throw std::runtime_error("unsupported futex timeout native fault-safe read API failure "+std::to_string(unsupported));
 return okay;
}
uint64_t ActiveNanoseconds(){
#ifdef _WIN32
 // Same qualified active-monotonic budget as SignalSleeps: sleep/hibernate
 // time is excluded. Resolve only the actual documented KernelBase export.
 using Query=VOID(WINAPI*)(PULONGLONG);
 static const auto query=[] {
  auto address=GetProcAddress(GetModuleHandleW(L"kernelbase.dll"),"QueryUnbiasedInterruptTimePrecise");
  Query function=nullptr;static_assert(sizeof(function)==sizeof(address));
  std::memcpy(&function,&address,sizeof(function));return function;
 }();
 if(!query)throw std::runtime_error("unsupported timed futex: Windows10 precise active-monotonic clock is unavailable");
 ULONGLONG ticks=0;query(&ticks);
 if(ticks>UINT64_MAX/100)throw std::overflow_error("futex active-monotonic clock overflow");
 return uint64_t(ticks)*100;
#else
 timespec now{};if(clock_gettime(CLOCK_MONOTONIC,&now))throw std::runtime_error("futex native CLOCK_MONOTONIC failed");
 if(now.tv_sec<0||now.tv_nsec<0||now.tv_nsec>=1000000000||uint64_t(now.tv_sec)>UINT64_MAX/1000000000)throw std::overflow_error("futex monotonic clock range");
 const auto whole=uint64_t(now.tv_sec)*1000000000;
 if(whole>UINT64_MAX-uint64_t(now.tv_nsec))throw std::overflow_error("futex monotonic clock sum overflow");
 return whole+uint64_t(now.tv_nsec);
#endif
}
uint64_t MakeDeadline(const Timeout&timeout){
 constexpr auto maximum=uint64_t(INT64_MAX),scale=UINT64_C(1000000000);
 const auto start=ActiveNanoseconds();
 if(start>maximum)throw std::overflow_error("futex active-monotonic clock outside signed ktime profile");
 // Linux timespec64_to_ktime/ktime_add_safe saturate valid large values.
 const auto seconds=uint64_t(timeout.seconds),nanos=uint64_t(timeout.nanoseconds);
 const auto duration=seconds>=maximum/scale?maximum:
    (seconds*scale>maximum-nanos?maximum:seconds*scale+nanos);
 return duration>maximum-start?maximum:start+duration;
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
 std::function<void(int)>error_sink;WaitObserver wait_observer;addr_t marker;bool installed=false,closing=false;
 Dispatcher dispatcher;
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
 void ObserveWait(const WaitObservation&observation){
  if(wait_observer){Environment preserve;wait_observer(observation);}
 }
 SignalHost::Dispatch Dispatch(uint64_t token,uint64_t allowed,const SignalHost::Boundary&wrapped){
  return dispatcher?dispatcher(token,allowed,wrapped):signals.DispatchOneAdmitted(token,allowed,wrapped);
 }
 int64_t TimedWait(addr_t address,uint32_t expected,uint64_t token,uint64_t deadline,Environment&environment,WaitObservation&observation){
  auto fail=[&](int error){observation.error=error;return Fail(error);};
  auto retained=signals.Lookup(token);auto wake=signals.Wake(token);
  if(!retained||!wake)throw std::runtime_error("futex timed wait lost actual signal lifetime");
  auto ticket=std::make_shared<Ticket>();ticket->key=address;ticket->wake=wake;
  int setup_error=0;
  {std::lock_guard lock(mutex);uint32_t word=0;
   if(!ReadWord(address,word))setup_error=14;
   else if(word!=expected)setup_error=11;
   else{
    auto inserted=queues.try_emplace(address);
    try{inserted.first->second.push_back(ticket);}catch(...){if(inserted.second&&inserted.first->second.empty())queues.erase(inserted.first);throw;}
    ticket->linked=true;
   }
  }
  if(setup_error)return fail(setup_error);
  Registration registration{*this,ticket};
  for(;;){
   const auto generation=wake->Generation();bool expired=false;
   {std::lock_guard lock(mutex);
    // A genuine Wake selected under this same lock wins, even if the clock
    // has since passed the deadline. Otherwise retire before timeout return.
    if(ticket->woken)return 0;
    if(ActiveNanoseconds()>=deadline){RemoveLocked(ticket);expired=true;}
   }
   if(expired)return fail(110);
   const auto allowed=admission(token);
   {std::lock_guard lock(mutex);
    if(ticket->woken)return 0;
    if(ActiveNanoseconds()>=deadline){RemoveLocked(ticket);expired=true;}
   }
   if(expired)return fail(110);
   enum class Cause {None,Wake,Timeout,Interrupt};Cause cause=Cause::None;
   const auto result=Dispatch(token,allowed,[&](const auto&delivery){
    {std::lock_guard lock(mutex);
     // Latch the syscall's outcome before the actual caught handler. Linux
     // may still deliver a pending handler before returning a wake/timeout
     // result to userspace. Handler duration cannot change this selection.
     cause=ticket->woken?Cause::Wake:
         ActiveNanoseconds()>=deadline?Cause::Timeout:Cause::Interrupt;
     RemoveLocked(ticket);
    }
    if(!boundary)throw std::runtime_error("unsupported futex caught handler without qualified boundary");
    auto restored=boundary(delivery);environment.handled=true;return restored;
   });
   if(result.error){
    {std::lock_guard lock(mutex);
     if(ticket->woken)return 0;
     // Rejected admission consumed no signal. A deadline reached during the
     // eligibility check can retire the wait while leaving that signal pending.
     if(result.error==95&&ActiveNanoseconds()>=deadline){RemoveLocked(ticket);expired=true;}
    }
    if(expired)return fail(110);
    if(result.error==95)throw std::runtime_error("unsupported futex eligible signal outside admitted provider phase");
    throw std::runtime_error("unsupported futex signal ownership or handler boundary");
   }
   if(result.handled){
    if(cause==Cause::Wake)return 0;
    if(cause==Cause::Timeout)return fail(110);
    if(cause!=Cause::Interrupt)throw std::logic_error("timed futex handler without selected cause");
    // Timed FUTEX_WAIT uses ERESTART_RESTARTBLOCK: caught handlers produce
    // EINTR even with SA_RESTART. No relative timeout rearm after the handler.
    return fail(4);
   }
   {std::lock_guard lock(mutex);if(ticket->woken)return 0;}
   const auto now=ActiveNanoseconds();if(now>=deadline)continue;
   // Bound native duration arithmetic while the one fixed active deadline,
   // not channel notifications or spurious wakeups, decides completion.
   const auto remaining=std::min<uint64_t>(deadline-now,UINT64_C(1000000000));
   wake->WaitRelative(generation,std::chrono::nanoseconds(remaining));
  }
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
    const auto result=Dispatch(token,allowed,[&](const auto&delivery){
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
void SignalFutexes::SetWaitObserver(WaitObserver observer){
 WaitObserver retired;
 {std::lock_guard lock(impl_->mutex);
  if(impl_->closing||impl_->callers)throw std::logic_error("futex wait observer requires quiescent calls");
  retired=std::move(impl_->wait_observer);impl_->wait_observer=std::move(observer);
 }
 // Captured resources in the previous callback retire outside the queue lock.
}
void SignalFutexes::SetDispatcher(Dispatcher dispatcher){
 Dispatcher retired;
 {std::lock_guard lock(impl_->mutex);
  if(impl_->closing||impl_->callers)throw std::logic_error("futex dispatcher requires quiescent calls");
  retired=std::move(impl_->dispatcher);impl_->dispatcher=std::move(dispatcher);
 }
 // Captured resources in the previous callback retire outside the queue lock.
}
addr_t SignalFutexes::Marker(const std::string&name)const{if(name!="syscall")throw std::invalid_argument("unsupported private futex import: "+name);return impl_->marker;}
int64_t SignalFutexes::Syscall(int64_t number,addr_t address,int32_t operation,uint32_t value,addr_t timeout,addr_t address2,uint32_t value3){
 Environment environment;Impl::Call call(*impl_);(void)address2;(void)value3;
 if(uint32_t(number)!=98)throw std::runtime_error("unsupported Android syscall low32 number outside98");
 if(operation!=0x80&&operation!=0x81)throw std::runtime_error("unsupported syscall98 outside private WAIT/WAKE");
 if(operation==0x80&&timeout){
  WaitObservation observation;observation.timeout_pointer=timeout;
  auto finish=[&](int64_t result,int error=0){observation.phase=WaitPhase::Return;observation.result=result;observation.error=error?error:observation.error;impl_->ObserveWait(observation);return result;};
  if(const auto error=TimeoutRangeError(timeout))return finish(impl_->Fail(error),error);
  Timeout snapshot{};if(!ReadTimeout(timeout,snapshot))return finish(impl_->Fail(14),14);
  observation.seconds=snapshot.seconds;observation.nanoseconds=snapshot.nanoseconds;observation.copied=true;
  const bool valid=snapshot.seconds>=0&&snapshot.nanoseconds>=0&&snapshot.nanoseconds<1000000000;
  if(valid){observation.deadline_nanoseconds=MakeDeadline(snapshot);observation.deadline_valid=true;}
  impl_->ObserveWait(observation);
  if(!valid)return finish(impl_->Fail(22),22);
  if(const auto error=KeyError(address))return finish(impl_->Fail(error),error);
  const auto token=impl_->Current();
  return finish(impl_->TimedWait(address,value,token,observation.deadline_nanoseconds,environment,observation));
 }
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
