// Component-only initial GC registry and helper-shaped caller are TEST inputs.
// Real Pthreads lifecycle/provider and retained original GC coordinators/handlers
// execute. No original Unity trampoline, heap scanner, or game rendering claim.
#include "pthread_host.h"
#include "signal_host.h"
#include "signal_delivery.h"
#include "signal_futex.h"
#include "signal_sleep.h"
#include "semaphore_host.h"
#include "worker_signal_lifecycle.h"
#include "../whole/cooperative_poll.h"
#include "../whole/bridge.h"
#include <windows.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
extern "C" {
#define ORIGINAL(name) Memory *sub_##name(State&,addr_t,Memory*);
ORIGINAL(825aada0) ORIGINAL(825aad50) ORIGINAL(825aae3c)
ORIGINAL(825b2af4) ORIGINAL(825b2b4c) ORIGINAL(825b2c70)
ORIGINAL(825b2ca4) ORIGINAL(825b2f00) ORIGINAL(825b2da4)
ORIGINAL(825b2e84) ORIGINAL(825b3860) ORIGINAL(825beb3c)
#undef ORIGINAL
}
namespace {
using namespace bunker::windows;
std::atomic<unsigned> checks{0};
void Check(bool value,const char*why){++checks;if(!value){std::fprintf(stderr,"FOCUSED-ASSERTION: %s\n",why);throw std::runtime_error(why);}}
void Require(bool value,const char*why){if(!value)throw std::runtime_error(why);}
template<class F>void Reject(F&&f,const char*why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,why);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
template<class T>void Write(addr_t p,const T&v){recomp::WriteGuestMemory(p,&v,sizeof(v));}
constexpr addr_t kCreate=0x5d200000,kWorker=0x82556a94,kErrno=0x7ff400000000ULL;
constexpr addr_t kNested=0x5d200008;
constexpr addr_t kRecord=0x879b7000,kEpoch=0x879a6b08,kStopped=0x879a6b10,kAck=0x87cb1e68;
Memory*CountStop(State&,addr_t,Memory*);Memory*CountRestart(State&,addr_t,Memory*);
constexpr recomp::Trace originals[]={
#define ORIGINAL(name) {0x##name##ULL,sub_##name},
ORIGINAL(825aada0) ORIGINAL(825aad50) ORIGINAL(825aae3c)
{0x825b2af4ULL,CountStop}, ORIGINAL(825b2b4c) {0x825b2c70ULL,CountRestart},
ORIGINAL(825b2ca4) ORIGINAL(825b2f00) ORIGINAL(825b2da4)
ORIGINAL(825b2e84) ORIGINAL(825b3860) ORIGINAL(825beb3c)
#undef ORIGINAL
};

bool Translated(addr_t p){return p==kCreate||p==kWorker||p==kNested||std::any_of(std::begin(originals),std::end(originals),[&](const auto&t){return t.address==p;});}
bool Executable(addr_t p){return Translated(p);}
struct GameWorkerObservation {
  struct NativeEnvironment {
    DWORD last_error=GetLastError();int native_errno=errno;fenv_t environment{};
    NativeEnvironment(){std::fegetenv(&environment);}
    ~NativeEnvironment(){std::fesetenv(&environment);errno=native_errno;SetLastError(last_error);}
  };
  // Scalar only: no destructor or provider access at native TLS retirement.
  static uint64_t &Token(){static thread_local uint64_t token=0;return token;}
  static void Lifecycle(const char *phase,const bunker::windows::Pthreads::WorkerInfo &info){
    NativeEnvironment preserve;
    std::fprintf(stderr,"Game bootstrap: worker lifecycle phase=%s token=%#llx parent=%#llx native_tid=%u stack_low=%#llx stack_high=%#llx tls=%#llx; observation only\n",phase,(unsigned long long)info.token,(unsigned long long)info.parent_token,info.native_tid,(unsigned long long)info.stack_low,(unsigned long long)info.stack_high,(unsigned long long)info.tls_address);
  }
  static void Enter(const bunker::windows::Pthreads::WorkerInfo &info){NativeEnvironment preserve;Token()=info.token;Lifecycle("enter",info);}
  static void Retire(const bunker::windows::Pthreads::WorkerInfo &info,bunker::windows::Pthreads::WorkerRetirement reason){
    NativeEnvironment preserve;Lifecycle(reason==bunker::windows::Pthreads::WorkerRetirement::normal?"retire_normal":"retire_cancelled",info);
    if(Token()==info.token)Token()=0;
  }
  static uint64_t Wait(const char *phase,const char *name,const State &s){
    NativeEnvironment preserve;const auto token=Token();if(!token)return 0;
    std::fprintf(stderr,"Game bootstrap: worker wait phase=%s import=%s token=%#llx native_tid=%lu PC=%#llx SP=%#llx FP=%#llx LR=%#llx x0=%#llx x1=%#llx x2=%#llx; call observation, not blocked-state proof\n",phase,name,(unsigned long long)token,GetCurrentThreadId(),(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.sp.qword,(unsigned long long)s.gpr.x29.qword,(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,(unsigned long long)s.gpr.x2.qword);
    return token;
  }
  static void BeforeCreate(const State &s){
    NativeEnvironment preserve;
    if(s.gpr.x30.qword!=0x82556a64||s.gpr.x2.qword!=0x82556a94||!s.gpr.x3.qword)return;
    const auto record=s.gpr.x3.qword;Require(record<=UINT64_MAX-0x20,"observed thread record prefix overflow");
    // Only initialized fields in the binary-proved 0x68-byte allocation. Read
    // before Create: the child may immediately free the nested 0x18 payload.
    const auto callback=Read<addr_t>(record+0x10),payload=Read<addr_t>(record+0x18);
    std::fprintf(stderr,"Game bootstrap: original worker create witness LR=%#llx entry=%#llx record=%#llx callback=%#llx payload=%#llx; before child start\n",(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x2.qword,(unsigned long long)record,(unsigned long long)callback,(unsigned long long)payload);
    if(callback==0x82557c80&&payload){
      Require(payload<=UINT64_MAX-0x18,"observed thread payload overflow");
      const auto owner=Read<addr_t>(payload),function=Read<addr_t>(payload+8),argument=Read<addr_t>(payload+16);
      std::fprintf(stderr,"Game bootstrap: original worker payload owner=%#llx function=%#llx argument=%#llx bytes=24; before child start, no post-create read\n",(unsigned long long)owner,(unsigned long long)function,(unsigned long long)argument);
    }
  }
};


#include "game_collector_delivery.h"
thread_local int guest_error=731;
struct Harness;Harness*host=nullptr;
Memory*Create(State&,addr_t,Memory*);Memory*Worker(State&,addr_t,Memory*);Memory*Nested(State&,addr_t,Memory*);
struct Harness {
  std::string mode;bool finalizer=false,timed=false,native_helper=false,ordinary=false;
  recomp::Runtime runtime;Pthreads threads{runtime,Translated};
  std::unique_ptr<GameCollectorDelivery> profile;
  SignalHost signals{[this](uint64_t token){if(profile)profile->Notify(token);},0x7ff600100000ULL};
  Semaphores sem{signals};
  SignalSleeps sleeps{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[](uint64_t){return uint64_t(0);}};
  alignas(16)std::array<uint8_t,128>event{};
  alignas(16)std::array<uint8_t,64>native_condition{},native_mutex{};
  alignas(16)std::array<uint64_t,13>creator{};
  alignas(16)std::array<uint64_t,3>payload{};
  uint64_t parent=0,target=0;std::atomic<unsigned>cycle{0},posts{0},stops{0},restarts{0},checkpoints{0},physical{0},environment_checks{0};
  std::array<std::promise<void>,2>entered,finished,proceed,suspended;
  std::promise<void>finish_reached,reacquire_ready,retired_ready,retired_release;
  std::atomic<bool>sender_certified{false},finish_returned{false},finish_published{false},reacquire_published{false},retired_published{false},main_mutex_released{false};
  std::atomic<unsigned>finish_calls{0},finish_environment_checks{0},queue_calls{0};
  std::array<std::atomic<bool>,2>published{};
  State interrupted{};AndroidTimespec request{};
  std::atomic<bool>notification_reacquire{false};
  addr_t Condition()const{return reinterpret_cast<addr_t>(native_helper?native_condition.data():event.data()+0x2c);}
  addr_t Mutex()const{return reinterpret_cast<addr_t>(native_helper?native_mutex.data():event.data()+4);}
  bool RaceTimeout()const{return mode=="race-timeout";}
  bool RaceReacquire()const{return mode=="race-reacquire";}
  bool RetireFirst()const{return mode=="bad-retired-send";}
  unsigned Cycles()const{return timed&&!ordinary&&!RaceTimeout()&&!RetireFirst()?2:1;}
  std::optional<uint64_t>Boundary(const SignalHost::Delivery&d){return profile->Deliver(d);}
  explicit Harness(std::string selected):mode(std::move(selected)),finalizer(mode=="finalizer"),timed(mode!="finalizer"&&mode!="untimed"&&mode!="native-untimed"&&mode!="race-reacquire"),native_helper(mode.find("native-")!=std::string::npos),ordinary(mode=="unknown"||mode=="opaque"||mode=="nested"){
    host=this;
    Check(VirtualAlloc(reinterpret_cast<void*>(0x87980000ULL),0x40000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87980000ULL),"TEST initial registry range");
    Check(VirtualAlloc(reinterpret_cast<void*>(0x87cb0000ULL),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87cb0000ULL),"TEST initial acknowledgment range");
    runtime.AddTraces(originals,std::size(originals));const recomp::Trace fixture[]={{kCreate,Create},{kWorker,Worker},{kNested,Nested}};runtime.AddTraces(fixture,3);
    auto error=[](int e){Write(reinterpret_cast<addr_t>(&guest_error),e);};threads.SetErrorSink(error);threads.Install();signals.SetErrorSink(error);sem.SetErrorSink(error);sleeps.SetErrorSink(error);
    parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"actual parent SignalHost identity");
    profile=std::make_unique<GameCollectorDelivery>(threads,signals,sem,runtime);
    const auto boundary=[this](const auto&d){return Boundary(d);};
    signals.Install(runtime,[this]{return threads.Self();},boundary,[]{return SignalHost::SenderIdentity{int32_t(GetCurrentProcessId()),10000};});sem.Install(runtime,[this]{return threads.Self();},boundary);sleeps.Install(runtime);
    runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
    Check(!threads.MutexInit(reinterpret_cast<void*>(Mutex()),nullptr)&&!threads.CondInit(reinterpret_cast<void*>(Condition()),nullptr),"real condition/mutex initialized");
    if(finalizer)Write<addr_t>(0x879a7a40,reinterpret_cast<addr_t>(event.data()));
    else Write<addr_t>(0x879a7a40,0x1111111111111111ULL);
    payload={reinterpret_cast<addr_t>(this),finalizer?0x825c3ed0ULL:0x8258aa94ULL,finalizer?0ULL:reinterpret_cast<addr_t>(event.data())};
    if(mode=="bad-function")payload[1]=0x8258aa98;
    if(mode=="bad-owner")payload[0]=0;
    if(mode=="bad-argument")payload[2]=0;
    creator[2]=0x82557c80;creator[3]=reinterpret_cast<addr_t>(payload.data());
    if(mode=="bad-wrapper")creator[2]=0x82557c84;
    Write<uint32_t>(0x879a62a0,1);Write<uint8_t>(0x879a62a8,1);Write<uint64_t>(kEpoch,0);Write<uint64_t>(kStopped,0);
    Write<int32_t>(0x87984e14,30);Write<int32_t>(0x87984e18,24);Write<int32_t>(0x87984e10,1);
    Write<addr_t>(0x879a7788,0x825b2af4);Write<addr_t>(0x879a7758,0x825b2c70);
    Write<uint64_t>(0x879a6b18,~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24)));
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=signal==30?0x10000004:0x10000000;action.mask=mask;Check(!signals.Action(signal,&action,nullptr),"original-shaped dispositions");}
    Check(!sem.Init(kAck,0,0),"real original acknowledgment semaphore");
  }
  void Observed(const Pthreads::WaitContext&context){
    const auto n=cycle.load();if(!n||context.token!=target)return;
    ++checkpoints;
    Check(context.active_state==recomp::CurrentExecutionState()&&threads.Self()==target,"observer runs on actual provider State/owner");
    Check(context.condition==reinterpret_cast<void*>(Condition())&&context.mutex==reinterpret_cast<void*>(Mutex()),"actual provider object pair retained");
    if(context.phase==Pthreads::WaitPhase::MutexReacquire){notification_reacquire=true;if(RaceReacquire()&&!reacquire_published.exchange(true))reacquire_ready.set_value();}
    if(context.phase==Pthreads::WaitPhase::ConditionReleased&&!published[n-1].exchange(true)){
      interrupted=*context.active_state;
      Check(timed?context.original_deadline==reinterpret_cast<AndroidTimespec*>(interrupted.gpr.sp.qword):!context.original_deadline,"actual timed/untimed provider shape");
      entered[n-1].set_value();
    }
  }
  void Checkpoint(const std::function<void(const Pthreads::WaitContext&)>&original,const Pthreads::WaitContext&context){
    GameWorkerObservation::NativeEnvironment restore;
    std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);const int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x82550574);
    original(context);
    Check(errno==EDOM&&GetLastError()==0x82550574&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"actual collector checkpoint preserves native errno/last-error/FENV");++environment_checks;
    Observed(context);
  }
  void Finish(const std::function<void(const Pthreads::WaitContext&)>&original,const Pthreads::WaitContext&context){
    GameWorkerObservation::NativeEnvironment restore;
    Check(context.token==target&&context.active_state==recomp::CurrentExecutionState()&&threads.Self()==target,"real finish executes on pinned current waiter State");
    Check(context.condition==reinterpret_cast<void*>(Condition())&&context.mutex==reinterpret_cast<void*>(Mutex()),"real finish retains actual condition/mutex identities");
    const bool raced=(RaceTimeout()&&context.phase==Pthreads::WaitPhase::ConditionReleased)||(RaceReacquire()&&context.phase==Pthreads::WaitPhase::MutexReacquire&&sender_certified);
    if(raced&&!finish_published.exchange(true)){
      Check(sender_certified,"sender was actually certified before provider finish");
      if(RaceTimeout()){AndroidTimespec now{};Check(!Pthreads::ClockGetTime(0,&now)&&(now.seconds>request.seconds||(now.seconds==request.seconds&&now.nanoseconds>=request.nanoseconds)),"actual absolute deadline expired before Queue");}
      finish_reached.set_value();
    }
    std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);const int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x82550164);
    if(original)original(context);
    Check(errno==EDOM&&GetLastError()==0x82550164&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"actual collector finish preserves native errno/last-error/FENV");++finish_environment_checks;
    ++finish_calls;
    if(raced)finish_returned=true;
    if(RetireFirst()&&context.phase==Pthreads::WaitPhase::ConditionReleased&&!retired_published.exchange(true)){retired_ready.set_value();retired_release.get_future().get();}
  }
  Memory*Body(State&s,Memory*m){
    const auto initial=s;AndroidThreadAttr attr{};
    Check(threads.Self()==target&&profile->Owns(target)&&!threads.GetAttr(target,&attr),"actual entered lifecycle owns worker and stack");
    const auto high=attr.stack_base+attr.stack_size;
    Write<addr_t>(kRecord,0);Write<uint64_t>(kRecord+8,target);Write<uint64_t>(kRecord+0x10,0);Write<addr_t>(kRecord+0x18,high);Write<uint32_t>(kRecord+0x20,2);Write<addr_t>(kRecord+0x28,high);
    uint32_t hash=uint32_t(target>>8)^uint32_t(target);hash^=hash>>16;Write<addr_t>(0x879a6b28+(hash&255)*8,kRecord);
    for(unsigned n=0;n<Cycles();++n){
      proceed[n].get_future().get();cycle=n+1;
      Check(!threads.MutexLock(reinterpret_cast<void*>(Mutex())),"waiter owns real mutex before wait");
      s=initial;
      for(unsigned i=0;i<31;++i){const uint64_t value=0x1234000000000000ULL+i*0x10101ULL;std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,&value,8);}
      for(unsigned i=0;i<32;++i)for(unsigned b=0;b<16;++b)reinterpret_cast<uint8_t*>(&s.simd.v[i])[b]=uint8_t(i*7+b);
      s.gpr.sp.qword=initial.gpr.sp.qword-(native_helper?0x50:0x70);s.gpr.x29.qword=s.gpr.sp.qword+(native_helper?0x40:0x60);
      s.gpr.x30.qword=native_helper?(timed?0x82550164:0x82550174):(timed?0x82550574:0x825505d8);s.gpr.pc.qword=timed?0x7ffc60000028ULL:0x7ffc60000020ULL;
      s.gpr.x0.qword=Condition();s.gpr.x1.qword=Mutex();s.gpr.x2.qword=timed?s.gpr.sp.qword:finalizer?0:1;
      if(timed){Check(!Pthreads::ClockGetTime(0,&request),"actual realtime deadline read");request.nanoseconds+=500000000;if(request.nanoseconds>=1000000000){++request.seconds;request.nanoseconds-=1000000000;}Write<AndroidTimespec>(s.gpr.sp.qword,request);}
      if(mode=="bad-LR"||mode=="unknown")s.gpr.x30.qword=0x82550578;
      if(mode=="bad-FP"||mode=="bad-native-FP")s.gpr.x29.qword+=16;
      if(mode=="bad-request"){Write<AndroidTimespec>(s.gpr.sp.qword+16,request);s.gpr.x2.qword+=16;}
      if(mode=="bad-TLS"||mode=="bad-native-TLS")s.sr.tpidr_el0.qword+=16;
      std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);errno=EDOM;SetLastError(0x82550574);
      const auto start=std::chrono::steady_clock::now();
      {GameCollectorDelivery::Opaque opaque(mode=="opaque"||mode=="bad-opaque-send");profile->WithWait(timed?"pthread_cond_timedwait":"pthread_cond_wait",s,[&]{runtime.Dispatch(s,threads.Marker(timed?"pthread_cond_timedwait":"pthread_cond_wait"),m);});}
      const auto elapsed=std::chrono::steady_clock::now()-start;
      Check(int32_t(s.gpr.x0.dword)==(timed&&!n&&!ordinary?110:0),"actual timeout/notification result preserved");
      std::fprintf(stderr,"OUTER-RUNTIME-NATIVE-OBSERVATION errno=%d last_error=%lu rounding=%d flags=%d; dispatcher clears FP flags before imports, no whole-dispatch preservation contract\n",errno,GetLastError(),std::fegetround(),std::fetestexcept(FE_ALL_EXCEPT));
      if(timed){Check(!std::memcmp(&request,reinterpret_cast<void*>(s.gpr.sp.qword),sizeof(request)),"original request bytes unchanged");if(!n&&!ordinary)Check(elapsed>=std::chrono::milliseconds(500)&&elapsed<std::chrono::seconds(3),"handler duration consumes original deadline");}
      for(unsigned i=1;i<31;++i){uint64_t a=0,b=0;std::memcpy(&a,reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,8);std::memcpy(&b,reinterpret_cast<uint8_t*>(&interrupted.gpr)+i*16+8,8);Check(a==b,"original handlers restore interrupted GPR");}
      Check(!std::memcmp(&s.simd,&interrupted.simd,sizeof(s.simd)),"original handlers restore all32Q");
      Check(!std::memcmp(&s.fpcr,&interrupted.fpcr,sizeof(s.fpcr))&&!std::memcmp(&s.fpsr,&interrupted.fpsr,sizeof(s.fpsr))&&!std::memcmp(&s.sr,&interrupted.sr,sizeof(s.sr)),"interrupted guest FPCR/FPSR/status/TLS preserved");
      Check(s.gpr.sp.qword==interrupted.gpr.sp.qword&&s.gpr.pc.qword==interrupted.gpr.x30.qword,"exact helper stack and return restored");
      Check(Read<uint64_t>(kRecord+0x10)==(ordinary?0:uint64_t((n+1)*2+1)),"original record epoch matches real collector activity");
      Check(!threads.MutexUnlock(reinterpret_cast<void*>(Mutex())),"real mutex reacquired before return");
      finished[n].set_value();
    }
    s=initial;s.gpr.x0.qword=0x1234;s.gpr.pc.qword=s.gpr.x30.qword;return m;
  }
  Memory*PLT(State&s,Memory*m,const char*name){
    addr_t marker=0;if(!std::strcmp(name,"__errno"))marker=kErrno;else if(!std::strncmp(name,"sem_",4))marker=sem.Marker(name);else if(!std::strcmp(name,"pthread_kill")||!std::strcmp(name,"sigsuspend"))marker=signals.Marker(name);else if(!std::strcmp(name,"usleep"))marker=sleeps.Marker(name);else marker=threads.Marker(name);s.gpr.pc.qword=marker;
    auto invoke=[&]{runtime.Dispatch(s,marker,m);};
    if(!std::strcmp(name,"pthread_kill"))profile->Send(s,[&]{
      if(s.gpr.x1.dword==30&&(RaceTimeout()||RaceReacquire())){sender_certified=true;if(RaceReacquire()){Check(!threads.MutexUnlock(reinterpret_cast<void*>(Mutex())),"real owning coordinator releases mutex after certification");main_mutex_released=true;}finish_reached.get_future().get();Check(!finish_returned,"provider finish cannot retire sender-certified request before Queue");}
      ++queue_calls;std::fprintf(stderr,"ACTUAL-SIGNAL-QUEUE signal=%u\n",s.gpr.x1.dword);invoke();
    });
    else if(!std::strcmp(name,"sigsuspend")){const auto n=cycle.load();if(n&&!suspended_done[n-1].exchange(true))suspended[n-1].set_value();profile->WithWait(name,s,invoke);}
    else if(!std::strcmp(name,"sem_post")){profile->BeforePost(s);++physical;invoke();profile->AfterPost(s);++posts;}
    else invoke();
    return m;
  }
  std::array<std::atomic<bool>,2>suspended_done{};
  void Run(){
    Check(!threads.Run(kCreate),"creator-shaped call invokes actual Pthreads Create");
    for(unsigned n=0;n<Cycles();++n){
      proceed[n].set_value();entered[n].get_future().get();
      Check(!threads.MutexLock(reinterpret_cast<void*>(Mutex())),"provider actually released guest mutex");
      if(ordinary){uint64_t pending=1;Check(!signals.Pending(target,&pending)&&!pending&&!SignalHost::NeedsPoll(signals.Lookup(target)),"unknown helper has no pending collector signal");Check(!threads.CondWake(reinterpret_cast<void*>(Condition()),false),"ordinary unknown helper uses real condition notification");std::this_thread::sleep_for(std::chrono::milliseconds(15));Check(!threads.MutexUnlock(reinterpret_cast<void*>(Mutex())),"ordinary notifier releases real mutex");finished[n].get_future().get();continue;}
      if(mode.rfind("bad-",0)==0){std::fprintf(stderr,"EXPECT-PRODUCTION-REJECTION %s\n",mode.c_str());std::fflush(stderr);}
      if(RaceReacquire()){Check(!threads.CondWake(reinterpret_cast<void*>(Condition()),false),"actual notifier releases condition into contended reacquisition");reacquire_ready.get_future().get();}
      if(RetireFirst())retired_ready.get_future().get();
      threads.Run(0x825aad50);Check(Read<uint64_t>(kEpoch)==uint64_t((n+1)*2)&&Read<uint64_t>(kStopped)==1,"original coordinator stopped world");suspended[n].get_future().get();
      if(timed&&!n&&!RaceTimeout())std::this_thread::sleep_for(std::chrono::milliseconds(600));
      threads.Run(0x825aae3c);
      if((!timed||n)&&!RaceReacquire()){Check(!threads.CondWake(reinterpret_cast<void*>(Condition()),false),"real condition notification");std::this_thread::sleep_for(std::chrono::milliseconds(15));}
      if(!main_mutex_released)Check(!threads.MutexUnlock(reinterpret_cast<void*>(Mutex())),"notifier releases pinned mutex");
      finished[n].get_future().get();
    }
    addr_t result=0;Check(!threads.Join(target,&result)&&result==0x1234,"actual worker join/TLS retirement");
    Check(posts==(ordinary?0:Cycles()*2)&&physical==(ordinary?0:Cycles()*2)&&stops==(ordinary?0:Cycles())&&restarts==(ordinary?0:Cycles()),"only real collector requests invoke original handlers and posts");
    Check((notification_reacquire||RaceTimeout())&&environment_checks>=Cycles(),"provider observed real mutex reacquisition and externally invoked checkpoint environment preservation");
    Check(finish_calls>=Cycles()*2&&finish_environment_checks==finish_calls,"provider invoked both real finish boundaries with native environment preservation");
    if(RaceTimeout()||RaceReacquire())Check(finish_published&&finish_returned&&queue_calls==2,"certified request survives real provider-finish race with only original stop/restart queue calls");
    int32_t value=-1;Check(!sem.GetValue(kAck,&value)&&!value,"original coordinators consumed genuine posts");
    Check(!threads.Shutdown(),"actual worker drain");profile->CloseAfterShutdown();profile.reset();
    Check(!threads.CondDestroy(reinterpret_cast<void*>(Condition()))&&!threads.MutexDestroy(reinterpret_cast<void*>(Mutex()))&&!sem.Destroy(kAck),"real wait resources destroyed after join");
    Check(!threads.ReleaseCurrent()&&!signals.DropThread(parent),"parent signal/TLS owner retired");
    std::printf("MANAGED-WORKER-ORIGINAL-GC-PASS mode=%s cycles=%u posts=%u stops=%u restarts=%u physical=%u checks=%u State=%zu Memory64=%zu checkpoint_env=%u FPCR_FPSR=%u finish_calls=%u finish_env=%u\n",mode.c_str(),Cycles(),posts.load(),stops.load(),restarts.load(),physical.load(),checks.load(),sizeof(State),sizeof(addr_t),environment_checks.load(),Cycles(),finish_calls.load(),finish_environment_checks.load());
  }
};
Memory*Create(State&s,addr_t,Memory*m){const auto saved=s.gpr.x30.qword;s.gpr.x0.qword=reinterpret_cast<addr_t>(&host->target);s.gpr.x1.qword=0;s.gpr.x2.qword=kWorker;s.gpr.x3.qword=reinterpret_cast<addr_t>(host->creator.data());s.gpr.x30.qword=0x82556a64;s.gpr.pc.qword=host->threads.Marker("pthread_create");host->profile->WithCreate(s,[&](State&inner){host->runtime.Dispatch(inner,host->threads.Marker("pthread_create"),m);});s.gpr.x30.qword=saved;s.gpr.pc.qword=saved;return m;}
Memory*Worker(State&s,addr_t,Memory*m){if(host->mode=="nested"){s.gpr.x0.qword=host->threads.Run(kNested);s.gpr.pc.qword=s.gpr.x30.qword;return m;}return host->Body(s,m);}
Memory*Nested(State&s,addr_t,Memory*m){return host->Body(s,m);}
Memory*CountStop(State&s,addr_t address,Memory*m){++host->stops;return sub_825b2af4(s,address,m);}
Memory*CountRestart(State&s,addr_t address,Memory*m){++host->restarts;return sub_825b2c70(s,address,m);}
[[noreturn]]void Unsupported(const char*name){std::fprintf(stderr,"TEST-only unsupported original path: %s\n",name);std::abort();}
}
extern "C" {
void __real__ZN6bunker7windows8Pthreads12SetWaitHooksENS1_9WaitHooksE(bunker::windows::Pthreads*,bunker::windows::Pthreads::WaitHooks);
void __wrap__ZN6bunker7windows8Pthreads12SetWaitHooksENS1_9WaitHooksE(bunker::windows::Pthreads*self,bunker::windows::Pthreads::WaitHooks hooks){auto original=hooks.checkpoint;hooks.checkpoint=[original](const auto&context){host->Checkpoint(original,context);};auto finish=hooks.finish;hooks.finish=[finish](const auto&context){host->Finish(finish,context);};__real__ZN6bunker7windows8Pthreads12SetWaitHooksENS1_9WaitHooksE(self,std::move(hooks));}
#define PLT(address,name) Memory *sub_##address(State&s,addr_t,Memory*m){return host->PLT(s,m,name);}
PLT(820ca520,"__errno") PLT(820ca660,"pthread_self") PLT(820caa50,"sem_timedwait")
PLT(820cb330,"sigsuspend") PLT(820cb440,"pthread_kill") PLT(820cbcf0,"sem_wait")
PLT(820cbdc0,"clock_gettime") PLT(820cbdf0,"sem_getvalue") PLT(820cc110,"sem_post") PLT(820cc140,"usleep")
#undef PLT
Memory*sub_820cbb10(State&,addr_t,Memory*){Unsupported("original abort");}
Memory*sub_825a66a4(State&,addr_t,Memory*){Unsupported("original diagnostic logging");}
Memory*sub_825b3020(State&,addr_t,Memory*){Unsupported("original unexpected reinitialization");}
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(20));std::fputs("managed GC fixture watchdog\n",stderr);std::_Exit(98);}).detach();try{Harness h(argc==2?argv[1]:"timed");h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"managed GC fixture: %s\n",e.what());std::_Exit(91);}}
