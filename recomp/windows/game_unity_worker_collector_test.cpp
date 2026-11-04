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
void Check(bool value,const char*why){++checks;if(!value)throw std::runtime_error(why);}
void Require(bool value,const char*why){if(!value)throw std::runtime_error(why);}
template<class F>void Reject(F&&f,const char*why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,why);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
template<class T>void Write(addr_t p,const T&v){recomp::WriteGuestMemory(p,&v,sizeof(v));}
constexpr addr_t kCreate=0x5d100000,kWorker=0x70383624,kErrno=0x7ff400000000ULL;
constexpr addr_t kRecord=0x879b7000,kEpoch=0x879a6b08,kStopped=0x879a6b10,kAck=0x87cb1e68;
constexpr recomp::Trace originals[]={
#define ORIGINAL(name) {0x##name##ULL,sub_##name},
ORIGINAL(825aada0) ORIGINAL(825aad50) ORIGINAL(825aae3c)
ORIGINAL(825b2af4) ORIGINAL(825b2b4c) ORIGINAL(825b2c70)
ORIGINAL(825b2ca4) ORIGINAL(825b2f00) ORIGINAL(825b2da4)
ORIGINAL(825b2e84) ORIGINAL(825b3860) ORIGINAL(825beb3c)
#undef ORIGINAL
};
bool Translated(addr_t p){return p==kCreate||p==kWorker||std::any_of(std::begin(originals),std::end(originals),[&](const auto&t){return t.address==p;});}
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

#include "game_unity_worker_collector.h"
#include "game_collector_delivery.h"
thread_local int guest_error=731;
struct Harness;Harness*host=nullptr;
Memory*Create(State&,addr_t,Memory*);Memory*Worker(State&,addr_t,Memory*);
struct Harness {
  recomp::Runtime runtime;Pthreads threads{runtime,Translated};
  std::unique_ptr<GameUnityWorkerCollector> profile;
  std::unique_ptr<GameCollectorDelivery> old;
  SignalHost signals{[this](auto token){if(profile&&profile->Owns(token))profile->Notify(token);else if(old)old->Notify(token);},0x7ff600100000ULL};
  Semaphores sem{signals};
  SignalFutexes futex{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[this](auto token){return profile->FutexAdmission(token);}};
  SignalSleeps sleeps{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[](uint64_t){return uint64_t(0);}};
  uint64_t parent=0,target=0;std::atomic<unsigned> cycle{0},posts{0},restarts{0},stops{0},sends30{0},sends24{0},seen_late30{0},seen_late24{0},seen_control24{0},copied{0},returned{0},control_copies{0},control_returns{0},restored_bindings{0};int control_error=0;
  std::array<std::promise<void>,2> entered,finished,proceed,suspend_ready;
  std::array<std::atomic<unsigned>,2> suspend_entries{};
  std::promise<void> attached,late_checked;std::atomic<bool> late_published{false};
  WorkerSignalLifecycle::ContextRef context;State interrupted{};
  std::optional<uint64_t> Boundary(const SignalHost::Delivery&d){
    if(d.signal==30){++stops;if(d.info[100]==30)++seen_late30;}
    else if(d.signal==24){++restarts;if(d.info[100]==24)++seen_late24;if(d.info[100]==99)++seen_control24;}
    return profile->Owns(d.token)?profile->Deliver(d):old->Deliver(d);
  }
  Harness(){
    host=this;Check(VirtualAlloc(reinterpret_cast<void*>(0x87980000ULL),0x40000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87980000ULL),"TEST registry globals reserved exactly");
    Check(VirtualAlloc(reinterpret_cast<void*>(0x87cb0000ULL),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87cb0000ULL),"TEST ack globals reserved exactly");
    runtime.AddTraces(originals,std::size(originals));const recomp::Trace fixture[]={{kCreate,Create},{kWorker,Worker}};runtime.AddTraces(fixture,2);
    auto error=[](int e){Write(reinterpret_cast<addr_t>(&guest_error),e);};threads.SetErrorSink(error);threads.Install();signals.SetErrorSink(error);sem.SetErrorSink(error);futex.SetErrorSink(error);sleeps.SetErrorSink(error);
    parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"actual parent signal owner");
    profile=std::make_unique<GameUnityWorkerCollector>(threads,signals,sem,runtime);
    GameCollectorDelivery::WorkerExtension extension;
    extension.prepare=[this](const auto&i,auto&lifecycle){profile->Prepare(i,lifecycle);context=lifecycle.Lookup(i.token);};
    extension.enter=[this](const auto&i){profile->Enter(i);};
    extension.before_tls=[this](const auto&i){profile->BeforeTls(i);context->PollRequests().Request();};
    extension.retire=[this](const auto&i,auto reason){profile->Retire(i,reason);if(reason==Pthreads::WorkerRetirement::normal){Check(__bunker_guest_poll_requested()!=0,"new nested binding restores actual old binding before old retirement");++restored_bindings;}};
    extension.owns=[this](auto token){return profile->Owns(token);};extension.checkpoint=[this](const auto&c){profile->Checkpoint(c);};
    old=std::make_unique<GameCollectorDelivery>(threads,signals,sem,runtime,std::move(extension));
    const auto boundary=[this](const auto&d){return Boundary(d);};
    signals.Install(runtime,[this]{return threads.Self();},boundary,[]{return SignalHost::SenderIdentity{int32_t(GetCurrentProcessId()),10000};});
    sem.Install(runtime,[this]{return threads.Self();},boundary);futex.Install(runtime,[](const State&,uint64_t){});sleeps.Install(runtime);
    futex.SetDispatcher([this](auto token,auto allowed,const auto&boundary){auto result=profile->DispatchFutex(token,allowed,boundary);if(cycle==2&&!late_published.exchange(true)){Check(!result.handled&&SignalHost::NeedsPoll(signals.Lookup(token)),"late30/24 retained before new original epoch certification");Check(stops==1&&restarts==2&&!seen_late30&&!seen_late24,"late pair not prematurely delivered");late_checked.set_value();}return result;});
    futex.SetWaitObserver([this](const auto&observation){profile->ObserveFutex(observation);if(observation.phase==SignalFutexes::WaitPhase::Copied){if(cycle){++copied;interrupted=*recomp::CurrentExecutionState();entered[cycle.load()-1].set_value();}else ++control_copies;}else if(cycle){++returned;Check(observation.result==-1&&observation.error==4,"real timed futex reports EINTR after actual handler");}else{++control_returns;Check(observation.result==-1&&observation.error==control_error,"ordinary forwarded timeout/error result preserved");}});
    runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
    // TEST initial registry only; original coordinator/handlers own all later
    // epoch/world/ack transitions. Ordinary+28 is used; global main bound poisoned.
    Write<uint32_t>(0x879a62a0,1);Write<uint8_t>(0x879a62a8,1);Write<uint64_t>(kEpoch,0);Write<uint64_t>(kStopped,0);
    Write<int32_t>(0x87984e14,30);Write<int32_t>(0x87984e18,24);Write<int32_t>(0x87984e10,1);
    Write<addr_t>(0x879a7788,0x825b2af4);Write<addr_t>(0x879a7758,0x825b2c70);
    Write<uint64_t>(0x879a6b18,~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24)));
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=signal==30?0x10000004:0x10000000;action.mask=mask;Check(!signals.Action(signal,&action,nullptr),"actual original-shaped signal disposition");}
    Check(!sem.Init(kAck,0,0),"real original ack semaphore initialized");
  }
  Memory*Target(State&s,Memory*m){
    const auto top=s.gpr.sp.qword,return_pc=s.gpr.x30.qword;Check(threads.Self()==target&&target!=parent&&profile->Owns(target),"actual Pthreads prepared Unity entry reaches entered profile");
    AndroidThreadAttr attr{};Check(!threads.GetAttr(target,&attr)&&attr.stack_base&&attr.stack_size,"actual prepared worker owns stack");const auto high=attr.stack_base+attr.stack_size;
    Check(context&&context->CurrentPhase()==WorkerSignalLifecycle::Phase::entered&&context->NativeThreadId()==GetCurrentThreadId()&&context->PreparedWorker().tls_address==s.sr.tpidr_el0.qword,"actual prepared context/TLS/native identity");
    Write<addr_t>(kRecord,0);Write<uint64_t>(kRecord+8,target);Write<uint64_t>(kRecord+0x10,0);Write<addr_t>(kRecord+0x18,high);Write<uint32_t>(kRecord+0x20,2);Write<addr_t>(kRecord+0x28,high);Write<addr_t>(0x879a6ac0,0x1111111111111111ULL);
    uint32_t hash=uint32_t(target>>8)^uint32_t(target);hash^=hash>>16;Write<addr_t>(0x879a6b28+(hash&255)*8,kRecord);
    // Real provider forwarding controls. The retained known24 is consumed only
    // later by the genuine original nested sigsuspend after certified stop30.
    SignalHost::Info control24{};control24[100]=99;Check(!signals.Queue(target,24,&control24),"TEST known24 queued before ordinary forwarding controls");
    const auto initial=s;
    auto forward=[&](int64_t seconds,int64_t nanoseconds,int error,bool shape){
      s=initial;s.gpr.sp.qword=top-32;s.gpr.x30.qword=shape?0x708f2f14:0x704c155c;s.gpr.pc.qword=futex.Marker("syscall");s.gpr.x0.qword=98;s.gpr.x1.qword=kRecord+0x58;s.gpr.x2.qword=0x80;s.gpr.x3.qword=0;s.gpr.x4.qword=s.gpr.sp.qword;s.gpr.x5.qword=0;s.gpr.x6.qword=0;
      const int64_t request[2]={seconds,nanoseconds};recomp::WriteGuestMemory(s.gpr.sp.qword,request,sizeof(request));control_error=error;guest_error=731;
      profile->WithSyscall(s,[&]{runtime.Dispatch(s,futex.Marker("syscall"),m);});
      Check(int32_t(s.gpr.x0.qword)==-1&&guest_error==error,"nonadmitted actual provider operation preserves errno/result");Check(!stops&&!restarts&&SignalHost::NeedsPoll(signals.Lookup(target)),"ordinary provider operation retains known24 without handler/ack");
    };
    forward(0,1000000,110,true);forward(0,1000000000,22,true);
    Write<uint32_t>(kRecord+0x58,1);forward(4294967,295000000,11,true);Write<uint32_t>(kRecord+0x58,0);
    forward(0,0,110,false);s=initial;
    const Pthreads::WaitContext checkpoint{target,&s,nullptr,nullptr,nullptr,Pthreads::WaitPhase::ConditionReleased};profile->Checkpoint(checkpoint);Check(SignalHost::NeedsPoll(signals.Lookup(target))&&!seen_control24,"nonphase checkpoint retains known24 without consuming it");
    Check(control_copies==4&&control_returns==4,"four real ordinary provider calls each copy and return exactly once");attached.set_value();
    for(unsigned n=0;n<2;++n){
      proceed[n].get_future().get();cycle=n+1;guest_error=731;
      for(unsigned i=0;i<31;++i){const uint64_t v=0x1234000000000000ULL+i*0x10101ULL;std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,&v,8);}
      for(unsigned i=0;i<32;++i)for(unsigned b=0;b<16;++b)reinterpret_cast<uint8_t*>(&s.simd.v[i])[b]=uint8_t(i*7+b);
      s.gpr.sp.qword=top-32;s.gpr.x29.qword=top-16;s.gpr.x30.qword=0x708f2f14;s.gpr.pc.qword=futex.Marker("syscall");s.gpr.x0.qword=98;s.gpr.x1.qword=kRecord+0x58;s.gpr.x2.qword=0x80;s.gpr.x3.qword=0;s.gpr.x4.qword=s.gpr.sp.qword;s.gpr.x5.qword=0;s.gpr.x6.qword=0;
      const int64_t request[2]={4294967,295000000};recomp::WriteGuestMemory(s.gpr.sp.qword,request,sizeof(request));Write<addr_t>(s.gpr.sp.qword+16,0x704c155c);
      if(!n){
        auto bad=s;bad.gpr.x30.qword=0x70383878;Check(!GameUnityWorkerCollector::Shape(bad),"wrong helper LR is outside bounded worker shape");
        {GameUnityWorkerCollector::Opaque opaque(true);Check(!profile->FutexAdmission(target),"opaque scope cannot grant receiver admission");}
        const auto deferred=profile->DispatchFutex(target,SignalHost::Bit(30),boundary_placeholder);Check(!deferred.error&&!deferred.handled,"dispatcher defers without live syscall phase");
      }
      profile->WithSyscall(s,[&]{runtime.Dispatch(s,futex.Marker("syscall"),m);});
      Check(int32_t(s.gpr.x0.qword)==-1&&guest_error==4,"real timed futex returns EINTR after genuine stop");
      for(unsigned i=1;i<31;++i){uint64_t actual=0,expected=0;std::memcpy(&actual,reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,8);std::memcpy(&expected,reinterpret_cast<const uint8_t*>(&interrupted.gpr)+i*16+8,8);Check(actual==expected,"genuine nested original handlers restore interrupted GPR");}
      Check(!std::memcmp(&s.simd,&interrupted.simd,sizeof(s.simd)),"genuine handlers restore all32Q");Check(s.gpr.sp.qword==top-32&&s.gpr.pc.qword==0x708f2f14,"timed futex restores exact helper SP/PC");
      Check(Read<uint64_t>(kRecord+0x10)==uint64_t((n+1)*2+1),"original second post followed by E|1 store");finished[n].set_value();
    }
    s.gpr.sp.qword=top;s.gpr.x30.qword=return_pc;s.gpr.pc.qword=return_pc;s.gpr.x0.qword=0x1234;return m;
  }
  const SignalHost::Boundary boundary_placeholder=[](const auto&)->std::optional<uint64_t>{throw std::runtime_error("TEST unexpected provider boundary");};
  Memory*PLT(State&s,Memory*m,const char*name){
    addr_t marker=0;if(!std::strcmp(name,"__errno"))marker=kErrno;else if(!std::strncmp(name,"sem_",4))marker=sem.Marker(name);else if(!std::strcmp(name,"pthread_kill")||!std::strcmp(name,"sigsuspend"))marker=signals.Marker(name);else if(!std::strcmp(name,"usleep"))marker=sleeps.Marker(name);else marker=threads.Marker(name);s.gpr.pc.qword=marker;
    if(!std::strcmp(name,"pthread_kill")){if(s.gpr.x1.dword==30)++sends30;else if(s.gpr.x1.dword==24)++sends24;profile->Send(s,[&]{runtime.Dispatch(s,marker,m);});}
    else if(!std::strcmp(name,"sigsuspend")){const auto n=cycle.load()-1;if(++suspend_entries[n]==2)suspend_ready[n].set_value();profile->WithWait(name,s,[&]{runtime.Dispatch(s,marker,m);});}
    else if(!std::strcmp(name,"sem_post")){profile->BeforePost(s);runtime.Dispatch(s,marker,m);profile->AfterPost(s);++posts;}
    else{runtime.Dispatch(s,marker,m);}
    return m;
  }
  void Run(){
    Check(threads.Run(kCreate)==0,"actual Pthreads Create succeeds through composed create witness");attached.get_future().get();
    for(unsigned n=0;n<2;++n){
      if(n){SignalHost::Info late24{},late30{};late24[100]=24;late30[100]=30;Check(!signals.Queue(target,24,&late24)&&!signals.Queue(target,30,&late30),"TEST late bits queued as stimuli only");}
      proceed[n].set_value();entered[n].get_future().get();if(n)late_checked.get_future().get();threads.Run(0x825aad50);
      Check(Read<uint64_t>(kEpoch)==uint64_t((n+1)*2)&&Read<uint64_t>(kStopped)==1,"original coordinator advances epoch/world");suspend_ready[n].get_future().get();threads.Run(0x825aae3c);finished[n].get_future().get();
    }
    addr_t result=0;Check(!threads.Join(target,&result)&&result==0x1234,"actual prepared worker completes TLS/retire/Join");Check(!profile->Owns(target)&&restored_bindings==1,"real retirement revoked worker and restored predecessor binding");
    Check(posts==4&&stops==2&&restarts>=2&&sends30>=2&&sends24>=2&&seen_late30==1&&seen_late24==1&&seen_control24==1,"two genuine protocol cycles with original posts and retained late bits");Check(copied==2&&returned==2,"each real provider copies once and returns once with fixed deadline");
    int32_t count=-1;Check(!sem.GetValue(kAck,&count)&&count==0,"original coordinators consumed actual ack posts");
    profile->Close();Check(!threads.Shutdown(),"actual Pthreads shutdown after worker join");old->CloseAfterShutdown();old.reset();profile.reset();Check(!sem.Destroy(kAck)&&!threads.ReleaseCurrent()&&!signals.DropThread(parent),"parent providers close after actual worker retirement");
    std::printf("UNITY-WORKER-ORIGINAL-GC-SUCCESS cycles=2 posts=%u stops=%u restarts=%u checks=%u copied=%u returned=%u restored_bindings=%u forwarding_controls=%u",posts.load(),stops.load(),restarts.load(),checks.load(),copied.load(),returned.load(),restored_bindings.load(),control_returns.load());std::putchar(10);
  }
};
Memory*Create(State&s,addr_t,Memory*m){const auto saved=s.gpr.x30.qword;s.gpr.x0.qword=reinterpret_cast<addr_t>(&host->target);s.gpr.x1.qword=0;s.gpr.x2.qword=kWorker;s.gpr.x3.qword=reinterpret_cast<addr_t>(host);s.gpr.x30.qword=0x704389a8;s.gpr.pc.qword=host->threads.Marker("pthread_create");host->profile->WithCreate(s,[&](State&state){host->old->WithCreate(state,[&](State&inner){host->runtime.Dispatch(inner,host->threads.Marker("pthread_create"),m);});});s.gpr.x30.qword=saved;s.gpr.pc.qword=saved;return m;}
Memory*Worker(State&s,addr_t,Memory*m){return host->Target(s,m);}
[[noreturn]]void Unsupported(const char*name){std::fprintf(stderr,"TEST-only unsupported original abort/reinit path: %s\n",name);std::abort();}
}
extern "C" {
#define PLT(address,name) Memory *sub_##address(State&s,addr_t,Memory*m){return host->PLT(s,m,name);}
PLT(820ca520,"__errno") PLT(820ca660,"pthread_self") PLT(820caa50,"sem_timedwait")
PLT(820cb330,"sigsuspend") PLT(820cb440,"pthread_kill") PLT(820cbcf0,"sem_wait")
PLT(820cbdc0,"clock_gettime") PLT(820cbdf0,"sem_getvalue") PLT(820cc110,"sem_post") PLT(820cc140,"usleep")
#undef PLT
Memory *sub_820cbb10(State&,addr_t,Memory*){Unsupported("original abort");}
Memory *sub_825a66a4(State&,addr_t,Memory*){Unsupported("original diagnostic logging");}
Memory *sub_825b3020(State&,addr_t,Memory*){Unsupported("original unexpected reinitialization");}
}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(40));std::fputs("worker GC component watchdog\n",stderr);std::_Exit(98);}).detach();try{Harness h;h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"worker GC fixture: %s\n",e.what());std::_Exit(91);}}
