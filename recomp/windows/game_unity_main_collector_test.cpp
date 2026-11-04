// Component-only GC globals/caller: genuine retained original coordinators and
// handlers execute; this fixture does not initialize or render the real game.
#include "pthread_host.h"
#include "signal_host.h"
#include "signal_delivery.h"
#include "signal_nanosleep.h"
#include "signal_sleep.h"
#include "semaphore_host.h"
#include "../whole/cooperative_poll.h"
#include "../whole/bridge.h"
#include <windows.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
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
void Check(bool okay,const char*why){++checks;if(!okay)throw std::runtime_error(why);}
template<class F>void Reject(F&&f,const char*why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,why);}
template<class T>T Read(addr_t p){T value{};recomp::ReadGuestMemory(&value,p,sizeof(value));return value;}
template<class T>void Write(addr_t p,const T&value){recomp::WriteGuestMemory(p,&value,sizeof(value));}
constexpr addr_t kSetup=0x5d000000,kSleepEntry=0x5d000010,kErrno=0x7ff400000000ULL;
constexpr addr_t kRecord=0x879a7330,kEpoch=0x879a6b08,kStopped=0x879a6b10,kAck=0x87cb1e68;
constexpr recomp::Trace originals[]={
#define ORIGINAL(name) {0x##name##ULL,sub_##name},
ORIGINAL(825aada0) ORIGINAL(825aad50) ORIGINAL(825aae3c)
ORIGINAL(825b2af4) ORIGINAL(825b2b4c) ORIGINAL(825b2c70)
ORIGINAL(825b2ca4) ORIGINAL(825b2f00) ORIGINAL(825b2da4)
ORIGINAL(825b2e84) ORIGINAL(825b3860) ORIGINAL(825beb3c)
#undef ORIGINAL
};
bool Translated(addr_t p){return p==kSetup||p==kSleepEntry||std::any_of(std::begin(originals),std::end(originals),[&](const auto&t){return t.address==p;});}
bool Executable(addr_t p){return Translated(p);}
#include "game_unity_main_collector.h"
thread_local int guest_error=731;
struct Harness;
Harness*host=nullptr;
Memory *Setup(State&s,addr_t,Memory*m){s.gpr.pc.qword=s.gpr.x30.qword;return m;}
Memory *SleepEntry(State&,addr_t,Memory*);
struct Harness {
  recomp::Runtime runtime;
  Pthreads threads{runtime,Translated};
  std::unique_ptr<GameUnityMainCollector> profile;
  SignalHost signals{[this](auto token){if(profile&&profile->Owns(token))profile->Notify(token);}};
  Semaphores sem{signals};
  SignalNanoSleeps nano{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[this](auto token){return profile->NanoSleepAdmission(token);}};
  SignalSleeps sleeps{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[](uint64_t){return uint64_t(0);}};
  uint64_t parent=0,target=0;std::atomic<unsigned> cycle{0},posts{0},restarts{0},stops{0},sends30{0},sends24{0},seen_late30{0},seen_late24{0};
  std::array<std::promise<void>,2> entered,finished,proceed,suspend_ready;
  std::array<std::atomic<unsigned>,2> suspend_entries{};
  std::promise<void> attached,late_checked;
  std::atomic<bool> late_published{false};
  State interrupted{};
  std::optional<uint64_t> Boundary(const SignalHost::Delivery&d){
    if(d.signal==30){++stops;if(d.info[100]==30)++seen_late30;}
    else if(d.signal==24){++restarts;if(d.info[100]==24)++seen_late24;}
    return profile->Deliver(d);
  }
  Harness(){
    host=this;Check(VirtualAlloc(reinterpret_cast<void*>(0x87980000ULL),0x40000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87980000ULL),"TEST original-GC data range reserved exactly");
    Check(VirtualAlloc(reinterpret_cast<void*>(0x87cb0000ULL),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87cb0000ULL),"TEST original acknowledgment range reserved exactly");
    runtime.AddTraces(originals,std::size(originals));const recomp::Trace fixture[]={{kSetup,Setup},{kSleepEntry,SleepEntry}};runtime.AddTraces(fixture,2);
    auto error=[](int e){Write(reinterpret_cast<addr_t>(&guest_error),e);};threads.SetErrorSink(error);threads.Install();signals.SetErrorSink(error);sem.SetErrorSink(error);nano.SetErrorSink(error);sleeps.SetErrorSink(error);
    parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"actual parent SignalHost identity");
    profile=std::make_unique<GameUnityMainCollector>(threads,signals,sem,runtime);
    const auto boundary=[this](const auto&d){return Boundary(d);};
    signals.Install(runtime,[this]{return threads.Self();},boundary,[]{return SignalHost::SenderIdentity{int32_t(GetCurrentProcessId()),10000};});
    sem.Install(runtime,[this]{return threads.Self();},boundary);nano.Install(runtime);sleeps.Install(runtime);
    nano.SetDispatcher([this](auto token,auto allowed,const auto&boundary){auto result=profile->DispatchNanoSleep(token,allowed,boundary);if(cycle==2&&!late_published.exchange(true)){Check(!result.handled&&SignalHost::NeedsPoll(signals.Lookup(token)),"late30/24 remain pending before new original epoch certification");Check(stops==1&&restarts==1&&!seen_late30&&!seen_late24,"late pair not delivered before new epoch");late_checked.set_value();}return result;});
    nano.SetRequestObserver([this](const auto&value){Check(value.copied&&value.remaining==0&&value.seconds==0&&value.nanoseconds==500000000,"actual NanoSleep copied TEST helper-shaped request");interrupted=*recomp::CurrentExecutionState();entered[cycle.load()-1].set_value();});
    runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
    // Explicit TEST initial state only. Epoch/world transitions after this
    // point are performed by the retained original coordinators, never host ack.
    Write<uint32_t>(0x879a62a0,1);Write<uint8_t>(0x879a62a8,1);Write<uint64_t>(kEpoch,0);Write<uint64_t>(kStopped,0);
    Write<int32_t>(0x87984e14,30);Write<int32_t>(0x87984e18,24);Write<int32_t>(0x87984e10,1);
    Write<addr_t>(0x879a7788,0x825b2af4);Write<addr_t>(0x879a7758,0x825b2c70);
    Write<uint64_t>(0x879a6b18,~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24)));
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=signal==30?0x10000004:0x10000000;action.mask=mask;Check(!signals.Action(signal,&action,nullptr),"actual original-shaped thunk disposition installed");}
    Check(!sem.Init(kAck,0,0),"real original ack semaphore initialized for component");
  }
  void Target(){
    target=threads.Self();Check(target!=parent,"external std::thread gets actual distinct Pthreads token");Check(!signals.RegisterThread(target,parent)&&!signals.BindCurrent(target),"actual external signal lifetime bound");
    threads.Run(kSetup);AndroidThreadAttr attr{};Check(!threads.GetAttr(target,&attr)&&attr.stack_base&&attr.stack_size,"actual owned external guest stack allocated by Pthreads");
    const auto high=attr.stack_base+attr.stack_size;
    Write<addr_t>(kRecord,0);Write<uint64_t>(kRecord+8,target);Write<uint64_t>(kRecord+0x10,0);Write<addr_t>(kRecord+0x18,high-16);Write<uint32_t>(kRecord+0x20,6);
    Write<addr_t>(kRecord+0x28,0x1111111111111111ULL);Write<addr_t>(0x879a6ac0,high); // Poison ordinary bound: actual main profile must use global.
    uint32_t hash=uint32_t(target>>8)^uint32_t(target);hash^=hash>>16;Write<addr_t>(0x879a6b28+(hash&255)*8,kRecord);
    profile->AttachCurrent(target,parent);Check(profile->Owns(target),"explicit attached external owner is live");Reject([&]{profile->AttachCurrent(target,parent);},"duplicate external attachment rejected");attached.set_value();
    for(unsigned n=0;n<2;++n){proceed[n].get_future().get();cycle=n+1;guest_error=731;const auto result=threads.Run(kSleepEntry);Check(int32_t(result)==-1&&guest_error==4,"original caught stop returns genuine NanoSleep EINTR");Check(Read<uint64_t>(kRecord+0x10)==uint64_t((n+1)*2+1),"original second post followed by actual E|1 store");finished[n].set_value();}
    Check(!SignalHost::NeedsPoll(signals.Lookup(target)),"no target model signals lost at retirement");profile->DetachCurrent();Check(!profile->Owns(target),"real external detach revokes profile owner");Check(!threads.ReleaseCurrent()&&!signals.DropThread(target),"external Pthreads and SignalHost lifetimes retired on owner");
  }
  Memory *PLT(State&s,Memory*m,const char*name){
    addr_t marker=0;
    if(!std::strcmp(name,"__errno"))marker=kErrno;
    else if(!std::strncmp(name,"sem_",4))marker=sem.Marker(name);
    else if(!std::strcmp(name,"pthread_kill")||!std::strcmp(name,"sigsuspend"))marker=signals.Marker(name);
    else if(!std::strcmp(name,"usleep"))marker=sleeps.Marker(name);
    else marker=threads.Marker(name);
    s.gpr.pc.qword=marker;
    if(!std::strcmp(name,"pthread_kill")){if(s.gpr.x1.dword==30)++sends30;else if(s.gpr.x1.dword==24)++sends24;profile->Send(s,[&]{runtime.Dispatch(s,marker,m);});}
    else if(!std::strcmp(name,"sigsuspend")){
      const auto n=cycle.load()-1;
      if(++suspend_entries[n]==n+1)suspend_ready[n].set_value();
      profile->WithWait(name,s,[&]{runtime.Dispatch(s,marker,m);});
    }
    else if(!std::strcmp(name,"sem_post")){profile->BeforePost(s);runtime.Dispatch(s,marker,m);profile->AfterPost(s);++posts;}
    else runtime.Dispatch(s,marker,m);
    return m;
  }
  void Run(){
    Reject([&]{profile->AttachCurrent(parent,parent);},"parent cannot masquerade as distinct external UnityMain");
    std::thread child([this]{try{Target();}catch(const std::exception&e){std::fprintf(stderr,"target fixture: %s\n",e.what());std::_Exit(93);}});
    attached.get_future().get();
    for(unsigned n=0;n<2;++n){
      if(n){SignalHost::Info info24{},info30{};info24[100]=24;info30[100]=30;Check(!signals.Queue(target,24,&info24)&&!signals.Queue(target,30,&info30),"TEST late original-number pair queued as model stimuli only");}
      proceed[n].set_value();entered[n].get_future().get();if(n)late_checked.get_future().get();
      const auto stopped=threads.Run(0x825aad50);(void)stopped;
      Check(Read<uint64_t>(kEpoch)==uint64_t((n+1)*2)&&Read<uint64_t>(kStopped)==1,"original stop coordinator advanced epoch and stopped world");
      // Deterministic TEST scheduling only: cycle2 consumes its retained late24
      // while the original world is still stopped, then waits again for the
      // actual original resume send. No host post/epoch/world mutation.
      suspend_ready[n].get_future().get();
      threads.Run(0x825aae3c);Check(Read<uint64_t>(kStopped)==0,"original resume coordinator cleared worldStopped");finished[n].get_future().get();
    }
    child.join();Check(posts==4&&stops==2&&restarts>=2,"two genuine stop cycles produced exactly four original posts and nested restarts");Check(sends30>=2&&sends24>=2,"original sender instructions reached real SignalHost kill bridges");Check(seen_late30==1&&seen_late24==1,"retained late info delivered once after new epoch certification");
    int32_t count=-1;Check(!sem.GetValue(kAck,&count)&&count==0,"actual original coordinators consumed their acknowledgments");
    profile->Close();profile.reset();Check(!sem.Destroy(kAck)&&!threads.Shutdown()&&!threads.ReleaseCurrent()&&!signals.DropThread(parent),"parent providers close after genuine external retirement");
    std::printf("EXTERNAL-UNITYMAIN-ORIGINAL-GC-SUCCESS cycles=2 posts=%u stops=%u restarts=%u checks=%u actual-external-thread/current-polled-original-code/physical31GPR32Q/main-global-bound\n",posts.load(),stops.load(),restarts.load(),checks.load());
  }
};
Memory *SleepEntry(State&s,addr_t,Memory*m){
  const auto top=s.gpr.sp.qword,return_pc=s.gpr.x30.qword;
  for(unsigned i=0;i<31;++i){const uint64_t value=0x1234000000000000ULL+i*0x10101ULL;std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,&value,8);}
  for(unsigned i=0;i<32;++i)for(unsigned b=0;b<16;++b)reinterpret_cast<uint8_t*>(&s.simd.v[i])[b]=uint8_t(i*7+b);
  s.gpr.sp.qword=top-32;s.gpr.x0.qword=s.gpr.sp.qword;s.gpr.x1.qword=0;s.gpr.x29.qword=top-16;s.gpr.x30.qword=0x70383878;s.gpr.pc.qword=host->nano.Marker("nanosleep");
  const int64_t request[2]={0,500000000};recomp::WriteGuestMemory(s.gpr.sp.qword,request,sizeof(request));Write<addr_t>(s.gpr.sp.qword+16,return_pc);
  host->profile->WithNanoSleep(s,[&]{host->runtime.Dispatch(s,host->nano.Marker("nanosleep"),m);});
  for(unsigned i=1;i<31;++i){uint64_t value=0;std::memcpy(&value,reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,8);uint64_t expected=0;std::memcpy(&expected,reinterpret_cast<const uint8_t*>(&host->interrupted.gpr)+i*16+8,8);Check(value==expected,"actual original nested handlers restored interrupted GPR");}
  Check(!std::memcmp(&s.simd,&host->interrupted.simd,sizeof(s.simd)),"actual nested original handlers restored all32Q");
  Check(s.gpr.sp.qword==top-32&&s.gpr.pc.qword==0x70383878,"actual NanoSleep preserved helper continuation SP/PC");s.gpr.sp.qword=top;s.gpr.x30.qword=return_pc;s.gpr.pc.qword=return_pc;return m;
}
[[noreturn]]void Unsupported(const char*name){std::fprintf(stderr,"TEST-only unsupported original error/reinitialization path: %s\n",name);std::abort();}
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
int main(){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(45));std::fputs("external original GC component watchdog\n",stderr);std::_Exit(98);}).detach();
  try{Harness h;h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"external original GC fixture: %s\n",e.what());std::_Exit(91);}
}
