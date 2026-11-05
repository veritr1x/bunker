// TEST registry/caller/role setup only. Retained original GC coordinators and
// handlers, real Pthreads lifetimes, actual NDK poll and SocketTransport execute.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <windows.h>
#include "socket_transport.h"
#include "socket_transport_cases.h"
#include "pthread_host.h"
#include "signal_host.h"
#include "signal_delivery.h"
#include "signal_futex.h"
#include "signal_sleep.h"
#include "semaphore_host.h"
#include "worker_signal_lifecycle.h"
#include "../whole/cooperative_poll.h"
#include "../fastaes/elfload.h"
#include "traces.h"
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
template<class F>void Reject(F&&invoke,const char*why){bool rejected=false;try{invoke();}catch(const std::exception&){rejected=true;}Check(rejected,why);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
template<class T>void Write(addr_t p,const T&v){recomp::WriteGuestMemory(p,&v,sizeof(v));}
constexpr addr_t kCreate=0x5e100000,kWorker=0x70383624,kSetup=0x5e100010,kAck=0x87cb1e68,kEpoch=0x879a6b08,kStopped=0x879a6b10;
constexpr recomp::Trace originals[]={
#define ORIGINAL(name) {0x##name##ULL,sub_##name},
ORIGINAL(825aada0) ORIGINAL(825aad50) ORIGINAL(825aae3c)
ORIGINAL(825b2af4) ORIGINAL(825b2b4c) ORIGINAL(825b2c70)
ORIGINAL(825b2ca4) ORIGINAL(825b2f00) ORIGINAL(825b2da4)
ORIGINAL(825b2e84) ORIGINAL(825b3860) ORIGINAL(825beb3c)
#undef ORIGINAL
};
bool Translated(addr_t p){return p==kCreate||p==kWorker||p==kSetup||std::any_of(std::begin(originals),std::end(originals),[&](const auto&t){return t.address==p;})||std::any_of(std::begin(kTraces),std::end(kTraces),[&](const auto&t){return t.address==p;});}
bool Executable(addr_t p){return Translated(p);}
struct GameWorkerObservation {
  using NativeEnvironment=struct Environment{int error=errno;DWORD last=GetLastError();fenv_t f{};Environment(){std::fegetenv(&f);}~Environment(){std::fesetenv(&f);errno=error;SetLastError(last);}};
  static void Lifecycle(const char*,const Pthreads::WorkerInfo&){}
  static void Enter(const Pthreads::WorkerInfo&){}
  static void Retire(const Pthreads::WorkerInfo&,Pthreads::WorkerRetirement){}
  static void BeforeCreate(const State&){}
};
#include "game_collector_delivery.h"
#include "game_unity_main_collector.h"
#include "game_unity_worker_collector.h"
#include "game_socket_wait.h"
enum class Role{Ordinary,Worker,Main};
struct Harness;Harness*host=nullptr;
Memory*Create(State&,addr_t,Memory*);Memory*Target(State&,addr_t,Memory*);Memory*Setup(State&,addr_t,Memory*);
struct Harness {
  Role role;recomp::Runtime runtime;Pthreads threads{runtime,Translated};FileSystem files;SocketTransport sockets{files};
  std::unique_ptr<GameCollectorDelivery> ordinary;std::unique_ptr<GameUnityMainCollector> main_profile;std::unique_ptr<GameUnityWorkerCollector> workers;std::unique_ptr<GameSocketWaitCollector> socket_profile;
  SignalHost signals{[this](uint64_t token){if(main_profile&&main_profile->Owns(token))main_profile->Notify(token);else if(workers&&workers->Owns(token))workers->Notify(token);else if(ordinary)ordinary->Notify(token);}};
  Semaphores sem{signals};SignalSleeps sleeps{signals,[this]{return threads.Self();},[this](const auto&d){return Boundary(d);},[](uint64_t){return uint64_t(0);}};
  elf_image image{};addr_t entry=0;uint64_t parent=0,target=0;addr_t record=0;
  int listener=-1,client=-1,accepted=-1;std::atomic<unsigned>cycle{0},posts{0},stops{0},restarts{0},copied{0},returned{0},before{0},after{0},late30{0},late24{0};
  std::array<std::promise<void>,2>entered,finished,proceed,suspend_ready;std::array<std::atomic<unsigned>,2>suspends{};std::promise<void>attached,late_checked;std::atomic<bool>checked_late{false};State interrupted{};
  std::function<void(State&)>nested_control;unsigned negative_controls=0;
  static void*Resolve(const char*name){try{return reinterpret_cast<void*>(host->files.Marker(name));}catch(const std::invalid_argument&){return reinterpret_cast<void*>(host->sockets.Marker(name));}}
  std::optional<uint64_t>Boundary(const SignalHost::Delivery&d){if(d.signal==30){++stops;if(d.info[100]==30)++late30;}else{++restarts;if(d.info[100]==24)++late24;}if(main_profile->Owns(d.token))return main_profile->Deliver(d);if(workers->Owns(d.token))return workers->Deliver(d);return ordinary->Deliver(d);}
  explicit Harness(Role selected):role(selected){
    host=this;Check(VirtualAlloc(reinterpret_cast<void*>(0x87980000ULL),0x40000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87980000ULL),"TEST initial registry range");Check(VirtualAlloc(reinterpret_cast<void*>(0x87cb0000ULL),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x87cb0000ULL),"TEST initial ack range");
    runtime.AddTraces(originals,std::size(originals));runtime.AddTraces(kTraces,std::size(kTraces));const recomp::Trace fixtures[]={{kCreate,Create},{kWorker,Target},{kSetup,Setup}};runtime.AddTraces(fixtures,3);
    auto error=[this](int e){files.SetError(e);};threads.SetErrorSink(error);threads.Install();signals.SetErrorSink(error);sem.SetErrorSink(error);sleeps.SetErrorSink(error);parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"actual parent signal lifetime");
    workers=std::make_unique<GameUnityWorkerCollector>(threads,signals,sem,runtime);GameCollectorDelivery::WorkerExtension extension;
    extension.prepare=[this](const auto&i,auto&l){workers->Prepare(i,l);};extension.enter=[this](const auto&i){workers->Enter(i);};extension.before_tls=[this](const auto&i){workers->BeforeTls(i);};extension.retire=[this](const auto&i,auto reason){workers->Retire(i,reason);};extension.owns=[this](auto token){return workers->Owns(token);};extension.checkpoint=[this](const auto&c){workers->Checkpoint(c);};
    ordinary=std::make_unique<GameCollectorDelivery>(threads,signals,sem,runtime,std::move(extension));main_profile=std::make_unique<GameUnityMainCollector>(threads,signals,sem,runtime);
    // Explicit TEST site policy for this actual NDK object's caller. Production
    // defaults to the separately pinned original Unity return-site inventory.
    socket_profile=std::make_unique<GameSocketWaitCollector>(threads,*ordinary,*main_profile,*workers,[](const std::string&name,const State&s){return name=="poll"&&s.gpr.x30.qword>=0x7b000000&&s.gpr.x30.qword<0x7b010000;});
    sockets.SetWaitObserver([this](const auto&o){
      try{
      if(!o.state)return SocketTransport::WaitDecision{};
      const auto n=cycle.load();
      if(n&&o.phase==SocketTransport::WaitPhase::Copied){interrupted=*o.state;++copied;entered[n-1].set_value();if(n==1){SignalHost::Info info{};info[100]=99;Check(!signals.Queue(target,24,&info),"TEST control restart retained before genuine stop");}}
      if(n==1&&o.phase==SocketTransport::WaitPhase::Copied)Controls(o);
      const auto decision=socket_profile->Observe(o);
      // The controlled provider boundary calls its persistent owner's genuine
      // Deliver directly; its handled result is the actual completed stop.
      if(decision.handled)++stops;
      if(n&&o.phase==SocketTransport::WaitPhase::BeforeNativeWait){++before;if(n==2&&!checked_late.exchange(true)){Check(!decision.handled&&SignalHost::NeedsPoll(signals.Lookup(target))&&stops==1,"late30 survives phase exit until next genuine epoch");late_checked.set_value();}}
      if(n&&o.phase==SocketTransport::WaitPhase::AfterNativeWait)++after;
      if(n&&o.phase==SocketTransport::WaitPhase::Returned){++returned;if(n==1){SignalHost::Info a{},b{};a[100]=24;b[100]=30;Check(!signals.Queue(target,24,&a)&&!signals.Queue(target,30,&b),"TEST late pair queued at actual Returned before phase revocation");}}
      return decision;
      }catch(const std::exception&e){std::fprintf(stderr,"socket GC observer phase=%u operation=%u PC=%#llx LR=%#llx: %s\n",unsigned(o.phase),unsigned(o.operation),(unsigned long long)(o.state?o.state->gpr.pc.qword:0),(unsigned long long)(o.state?o.state->gpr.x30.qword:0),e.what());throw;}
    });
    const DescriptorImportInterceptor intercept=[this](const std::string&name,State&s,const std::function<void()>&invoke){socket_profile->WithSocketWait(name,s,invoke);};files.Install(runtime,intercept);sockets.Install(runtime,intercept);
    const auto boundary=[this](const auto&d){return Boundary(d);};signals.Install(runtime,[this]{return threads.Self();},boundary,[]{return SignalHost::SenderIdentity{int32_t(GetCurrentProcessId()),10000};});sem.Install(runtime,[this]{return threads.Self();},boundary);sleeps.Install(runtime);
    Check(!elf_load(SOCKET_LIBRARY,0x7b000000,Resolve,&image),"actual NDK caller ELF loaded with real socket imports");entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_socket_operation"));Check(entry!=0,"actual NDK dispatcher symbol");
    Write<uint32_t>(0x879a62a0,1);Write<uint8_t>(0x879a62a8,1);Write<uint64_t>(kEpoch,0);Write<uint64_t>(kStopped,0);Write<int32_t>(0x87984e14,30);Write<int32_t>(0x87984e18,24);Write<int32_t>(0x87984e10,1);Write<addr_t>(0x879a7788,0x825b2af4);Write<addr_t>(0x879a7758,0x825b2c70);Write<uint64_t>(0x879a6b18,~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24)));
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));for(int signal:{30,24}){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=signal==30?0x10000004:0x10000000;action.mask=mask;Check(!signals.Action(signal,&action,nullptr),"actual original-shaped dispositions");}Check(!sem.Init(kAck,0,0),"actual ack semaphore");
    listener=sockets.Socket(2,1,0);Check(listener>=0,"actual TCP listener socket");std::array<uint8_t,16>address{};address[0]=2;address[4]=127;address[7]=1;Check(!sockets.Bind(listener,reinterpret_cast<addr_t>(address.data()),16)&&!sockets.Listen(listener,1),"actual native loopback bind/listen");uint32_t length=16;Check(!sockets.Name(listener,reinterpret_cast<addr_t>(address.data()),reinterpret_cast<addr_t>(&length),false),"actual assigned loopback endpoint");client=sockets.Socket(2,1,0);Check(client>=0&&!sockets.Connect(client,reinterpret_cast<addr_t>(address.data()),16),"actual TCP client connects");accepted=sockets.Accept(listener,0,0);Check(accepted>=0,"actual accepted descriptor retained by poll");
  }
  void Controls(const SocketTransport::WaitObservation&o){
    GameSocketWaitContext::NativeEnvironment restore;using C=GameSocketWaitContext;
    AndroidThreadAttr attr{};Check(!threads.GetAttr(target,&attr),"negative controls use actual target bounds");const auto low=attr.stack_base,high=attr.stack_base+attr.stack_size;
    const C::Observation copy{o.state,o.descriptor,C::Operation::Poll,C::Phase::Copied,o.request_identity,o.retained_request,o.finite,o.deadline_nanoseconds};auto before=copy;before.phase=C::Phase::BeforeNativeWait;
    const auto state=*o.state;const auto allow=[](const std::string&,const State&){return true;};const auto decline=[]()->C::Decision{return{};};
    std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);const int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x70b4a1b8);
    auto exercise=[&](uint64_t token,addr_t bottom,addr_t tls){C c(*o.state,"poll",token,bottom,high,tls,role==Role::Main,allow);c.Observe(copy,decline);Reject([&]{c.Observe(before,[&]()->C::Decision{c.Validate(threads,signals);return{};});},"foreign owner/TLS/insufficient stack rejected before delivery");++negative_controls;};
    exercise(target+1,low,state.sr.tpidr_el0.qword);exercise(target,low,state.sr.tpidr_el0.qword+16);exercise(target,state.gpr.sp.qword-8192,state.sr.tpidr_el0.qword);
    {C c(*o.state,"poll",target,low,high,state.sr.tpidr_el0.qword,role==Role::Main,allow);c.Observe(copy,decline);Reject([&]{c.Observe(copy,decline);},"duplicate copied observation rejected");auto changed=before;++changed.deadline_nanoseconds;Reject([&]{c.Observe(changed,decline);},"changed immutable deadline rejected");changed=before;++changed.descriptor;Reject([&]{c.Observe(changed,decline);},"changed retained descriptor rejected");changed=before;changed.phase=C::Phase::AfterNativeWait;Reject([&]{c.Observe(changed,decline);},"AfterNativeWait without actual Before rejected");negative_controls+=4;}
    {C c(*o.state,"poll",target,low,high,state.sr.tpidr_el0.qword,role==Role::Main,allow);auto changed=copy;State foreign=state;changed.state=&foreign;Reject([&]{c.Observe(changed,decline);},"foreign observed State rejected");changed=copy;changed.request_identity=reinterpret_cast<const void*>(1);Reject([&]{c.Observe(changed,decline);},"resource identity not owned by retained request rejected");negative_controls+=2;}
    {C c(*o.state,"poll",target,low,high,state.sr.tpidr_el0.qword,role==Role::Main,{});bool dispatched=false;c.Observe(copy,decline);const auto decision=c.Observe(before,[&]()->C::Decision{dispatched=true;return{true,true};});Check(!decision.handled&&!dispatched&&SignalHost::NeedsPoll(signals.Lookup(target)),"unlisted production site retains real pending signal without dispatch");++negative_controls;}
    {C::NativeEnvironment exclusive_environment;C c(*o.state,"poll",target,low,high,state.sr.tpidr_el0.qword,role==Role::Main,allow);c.Observe(copy,decline);recomp::PollRequest request;bool delivered=false;recomp::PollBinding binding(request,[&](State&,recomp::PollSite,const auto&){delivered=true;},[&](const auto&context){return c.Admit(context);});request.Request();alignas(16)uint64_t value=7;__remill_aarch64_load_exclusive(*o.state,reinterpret_cast<addr_t>(&value),8,0);const auto saved=*o.state;c.Observe(before,[&]()->C::Decision{__bunker_guest_poll_slow(o.state,o.state->gpr.pc.qword,C::kOrdinal,o.state->gpr.pc.qword);return{};});Check(!delivered&&__bunker_guest_poll_requested()&&!std::memcmp(&saved,o.state,sizeof(State)),"missing original sender certificate defers actual slow poll without State/request mutation");Check(!__remill_aarch64_store_exclusive(*o.state,reinterpret_cast<addr_t>(&value),9,8,0)&&value==9,"declined socket poll preserves actual exclusive reservation");++negative_controls;}
    nested_control=[&](State&nested){C c(nested,"poll",target,low,high,nested.sr.tpidr_el0.qword,role==Role::Main,allow);auto observed=copy;observed.state=&nested;c.Observe(observed,decline);observed.phase=C::Phase::BeforeNativeWait;Reject([&]{c.Observe(observed,[&]()->C::Decision{c.Validate(threads,signals);return{};});},"nested Runtime parent roots are not admitted");++negative_controls;};
    State nested=state;nested.gpr.x30.qword=0xfeedffff;runtime.Run(nested,kSetup);nested_control={};
    Check(!std::memcmp(&state,o.state,sizeof(State)),"all1200 State bytes unchanged by declined contexts");Check(errno==EDOM&&GetLastError()==0x70b4a1b8&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"rejected context callbacks preserve native environment");
  }
  void RegisterTarget(State&s){
    AndroidThreadAttr attr{};Check(!threads.GetAttr(target,&attr),"actual target stack attributes");const auto high=attr.stack_base+attr.stack_size;record=role==Role::Main?0x879a7330:0x879b7000;
    Write<addr_t>(record,0);Write<uint64_t>(record+8,target);Write<uint64_t>(record+0x10,0);Write<addr_t>(record+0x18,high-16);Write<uint32_t>(record+0x20,role==Role::Main?6:2);Write<addr_t>(record+0x28,role==Role::Main?0x1111111111111111ULL:high);Write<addr_t>(0x879a6ac0,role==Role::Main?high:0x1111111111111111ULL);
    uint32_t hash=uint32_t(target>>8)^uint32_t(target);hash^=hash>>16;Write<addr_t>(0x879a6b28+(hash&255)*8,record);Check(s.sr.tpidr_el0.qword!=0,"actual target materialized TLS");attached.set_value();
  }
  Memory*Body(State&s,Memory*m){
    const auto original=s;RegisterTarget(s);
    for(unsigned n=0;n<2;++n){proceed[n].get_future().get();cycle=n+1;s=original;
      for(unsigned i=0;i<31;++i){const uint64_t value=0xa123000000000000ULL+i*0x10101;std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+i*16+8,&value,8);}for(unsigned i=0;i<32;++i)for(unsigned b=0;b<16;++b)reinterpret_cast<uint8_t*>(&s.simd.v[i])[b]=uint8_t(i*7+b);
      SocketTransport::PollFd pollfd{accepted,1,0};uint64_t args[6]={reinterpret_cast<addr_t>(&pollfd),1,5000,0,0,0};int error=0;s.gpr.sp.qword=original.gpr.sp.qword-64;s.gpr.x29.qword=s.gpr.sp.qword+32;s.gpr.x30.qword=original.gpr.x30.qword;s.gpr.x0.dword=NET_POLL;s.gpr.x1.qword=reinterpret_cast<addr_t>(args);s.gpr.x2.dword=n;s.gpr.x3.qword=reinterpret_cast<addr_t>(&error);s.gpr.pc.qword=entry;
      runtime.Dispatch(s,entry,m);Check(int64_t(s.gpr.x0.qword)==-1&&error==4,"actual NDK poll returns EINTR after genuine original stop/restart");Check(Read<uint64_t>(record+0x10)==uint64_t((n+1)*2+1),"original resumed record epoch updated");Check(s.gpr.sp.qword==original.gpr.sp.qword-64,"actual NDK function restores original caller SP");finished[n].set_value();
    }
    s=original;s.gpr.x0.qword=0x1234;s.gpr.pc.qword=s.gpr.x30.qword;return m;
  }
  Memory*PLT(State&s,Memory*m,const char*name){
    addr_t marker=0;if(!std::strcmp(name,"__errno"))marker=files.Marker(name);else if(!std::strncmp(name,"sem_",4))marker=sem.Marker(name);else if(!std::strcmp(name,"pthread_kill")||!std::strcmp(name,"sigsuspend"))marker=signals.Marker(name);else if(!std::strcmp(name,"usleep"))marker=sleeps.Marker(name);else marker=threads.Marker(name);s.gpr.pc.qword=marker;
    auto send=[&]{runtime.Dispatch(s,marker,m);};
    if(!std::strcmp(name,"pthread_kill")){if(main_profile->Owns(s.gpr.x0.qword))main_profile->Send(s,send);else if(workers->Owns(s.gpr.x0.qword))workers->Send(s,send);else ordinary->Send(s,send);}
    else if(!std::strcmp(name,"sigsuspend")){const auto n=cycle.load()-1;if(++suspends[n]==2)suspend_ready[n].set_value();if(main_profile->Owns(threads.Self()))main_profile->WithWait(name,s,send);else if(workers->Owns(threads.Self()))workers->WithWait(name,s,send);else ordinary->WithWait(name,s,send);}
    else if(!std::strcmp(name,"sem_post")){if(main_profile->Owns(threads.Self()))main_profile->BeforePost(s);else if(workers->Owns(threads.Self()))workers->BeforePost(s);else ordinary->BeforePost(s);send();if(main_profile->Owns(threads.Self()))main_profile->AfterPost(s);else if(workers->Owns(threads.Self()))workers->AfterPost(s);else ordinary->AfterPost(s);++posts;}
    else send();
    return m;
  }
  void Run(){
    std::thread external;
    if(role==Role::Main)external=std::thread([this]{try{target=threads.Self();Check(!signals.RegisterThread(target,parent)&&!signals.BindCurrent(target),"real external signal owner");threads.Run(kSetup);main_profile->AttachCurrent(target,parent);Check(threads.Run(kWorker)==0x1234,"real external NDK worker return");main_profile->DetachCurrent();Check(!threads.ReleaseCurrent()&&!signals.DropThread(target),"actual external owner retirement");}catch(const std::exception&e){std::fprintf(stderr,"socket main target:%s\n",e.what());std::_Exit(93);}});
    else Check(!threads.Run(kCreate),"actual Pthreads worker creation");
    attached.get_future().get();
    for(unsigned n=0;n<2;++n){proceed[n].set_value();entered[n].get_future().get();if(n)late_checked.get_future().get();threads.Run(0x825aad50);Check(Read<uint64_t>(kEpoch)==uint64_t((n+1)*2)&&Read<uint64_t>(kStopped)==1,"genuine original stop coordinator epoch/world");suspend_ready[n].get_future().get();threads.Run(0x825aae3c);finished[n].get_future().get();}
    if(external.joinable())external.join();else{addr_t result=0;Check(!threads.Join(target,&result)&&result==0x1234,"actual prepared worker join/retire");}
    Check(posts==4&&stops==2&&restarts>=4&&checked_late&&late24==1,"genuine original acknowledgments and retained late requests");Check(copied==2&&returned==2&&before>=2,"actual NDK poll copies/returns and waits");int32_t value=-1;Check(!sem.GetValue(kAck,&value)&&!value,"original coordinators consumed actual posts");
    Check(!files.Close(accepted)&&!files.Close(client)&&!files.Close(listener),"actual shared socket descriptors close");socket_profile.reset();main_profile->Close();workers->Close();Check(!threads.Shutdown(),"actual native worker drain");ordinary->CloseAfterShutdown();ordinary.reset();workers.reset();main_profile.reset();Check(!sem.Destroy(kAck)&&!threads.ReleaseCurrent()&&!signals.DropThread(parent),"all owners retire before dependencies");
    std::printf("SOCKET-WAIT-ORIGINAL-GC-PASS role=%u cycles=2 posts=%u stops=%u restarts=%u checks=%u copied=%u returned=%u before=%u after=%u actual_NDK_calls=2 forms=2 negative_controls=%u\n",unsigned(role),posts.load(),stops.load(),restarts.load(),checks.load(),copied.load(),returned.load(),before.load(),after.load(),negative_controls);
  }
};
Memory*Create(State&s,addr_t,Memory*m){const auto saved=s.gpr.x30.qword;s.gpr.x0.qword=reinterpret_cast<addr_t>(&host->target);s.gpr.x1.qword=0;s.gpr.x2.qword=kWorker;s.gpr.x3.qword=reinterpret_cast<addr_t>(host);s.gpr.x30.qword=0x704389a8;s.gpr.pc.qword=host->threads.Marker("pthread_create");auto invoke=[&](State&state){host->ordinary->WithCreate(state,[&](State&inner){host->runtime.Dispatch(inner,host->threads.Marker("pthread_create"),m);});};if(host->role==Role::Worker)host->workers->WithCreate(s,invoke);else invoke(s);s.gpr.x30.qword=saved;s.gpr.pc.qword=saved;return m;}
Memory*Target(State&s,addr_t,Memory*m){return host->Body(s,m);}
Memory*Setup(State&s,addr_t,Memory*m){if(host->nested_control)host->nested_control(s);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
[[noreturn]]void Unsupported(const char*name){std::fprintf(stderr,"socket GC TEST unexpected original error path:%s\n",name);std::abort();}
}
extern "C" {
#define PLT(address,name) Memory*sub_##address(State&s,addr_t,Memory*m){return host->PLT(s,m,name);}
PLT(820ca520,"__errno") PLT(820ca660,"pthread_self") PLT(820caa50,"sem_timedwait") PLT(820cb330,"sigsuspend") PLT(820cb440,"pthread_kill") PLT(820cbcf0,"sem_wait") PLT(820cbdc0,"clock_gettime") PLT(820cbdf0,"sem_getvalue") PLT(820cc110,"sem_post") PLT(820cc140,"usleep")
#undef PLT
Memory*sub_820cbb10(State&,addr_t,Memory*){Unsupported("abort");}Memory*sub_825a66a4(State&,addr_t,Memory*){Unsupported("diagnostic");}Memory*sub_825b3020(State&,addr_t,Memory*){Unsupported("reinitialization");}
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(60));std::fputs("socket GC component watchdog\n",stderr);std::_Exit(98);}).detach();try{Check(argc==2,"explicit component role");const unsigned role=unsigned(std::strtoul(argv[1],nullptr,10));Check(role<3,"known component role");Harness h(static_cast<Role>(role));h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"socket GC fixture:%s\n",e.what());std::_Exit(91);}}
