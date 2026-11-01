#include "signal_host.h"
#include "semaphore_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <future>
#include <stdexcept>
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};thread_local uint64_t token;thread_local int guest_error;
SignalHost *signals;Semaphores *semaphores;
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"signal/semaphore check: %s\n",why);std::abort();}}
void *Resolve(const char*name){if(!std::strcmp(name,"__errno"))return(void*)0x7ff600300000ULL;try{return(void*)signals->Marker(name);}catch(...){}return(void*)semaphores->Marker(name);}
uint64_t Mask(SignalHost&s,uint64_t t){uint64_t value=0;Check(!s.Mask(t,99,nullptr,&value),"mask query ignores how when no set");return value;}
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(40));std::fputs("signal/semaphore watchdog\n",stderr);std::_Exit(95);}).detach();
  {
    SignalHost process;recomp::Runtime calls;process.InstallProcess(calls);
    uint64_t masks[]={0x1122334455667788ULL,UINT64_MAX,0x8877665544332211ULL};
    State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(&masks[1]);state.gpr.x30.qword=0xfeedfff0;
    calls.Run(state,process.ProcessMarker("sigemptyset"));
    Check(!state.gpr.x0.qword&&!masks[1]&&masks[0]==0x1122334455667788ULL&&masks[2]==0x8877665544332211ULL,"process-only sigset subset writes exact Android mask without thread binding");
    bool rejected=false;try{process.ProcessMarker("pthread_kill");}catch(const std::invalid_argument&){rejected=true;}
    Check(rejected,"process-only lookup never advertises thread delivery imports");
  }
  std::atomic<unsigned> notifications{0};SignalHost *owner=nullptr;
  SignalHost model([&](uint64_t){++notifications;AndroidSignalAction a;Check(!owner->Action(30,nullptr,&a),"poll notification occurs after registry unlock");});owner=&model;
  Semaphores sem(model);signals=&model;semaphores=&sem;
  Check(!model.RegisterThread(1)&&!model.BindCurrent(1),"register and bind current virtual thread");token=1;
  auto initial=Mask(model,1);Check(initial==(1ULL<<31),"Android POSIX timer signal initially blocked");
  AndroidSignalAction action{};action.handler=0x1000;action.flags=4;
  Check(!model.Action(30,&action,nullptr),"GC SIGINFO disposition");
  auto alias_action=action;alias_action.handler=0x3000;Check(!model.Action(30,&alias_action,&alias_action)&&alias_action.handler==action.handler,"action input/output alias snapshots old value");
  AndroidSignalAction selected;model.Action(30,nullptr,&selected);Check(selected.handler==0x3000&&!model.Action(30,&action,nullptr),"aliased action still installs requested disposition");
  uint64_t alias_mask=SignalHost::Bit(30);Check(!model.Mask(1,0,&alias_mask,&alias_mask)&&alias_mask==initial&&Mask(model,1)==(initial|SignalHost::Bit(30)),"mask input/output alias retains requested new bits");
  Check(!model.Mask(1,2,&initial,nullptr),"restore initial mask after alias test");
  Check(model.Action(9,&action,nullptr)==22&&model.Queue(1,9)==38&&model.Queue(1,35)==38,"uncatchable/realtime delivery modes explicit");
  auto onstack=action;onstack.flags|=0x08000000;Check(!model.Action(30,&onstack,nullptr),"SA_ONSTACK registration with disabled alternate stack");
  Check(!model.Action(30,&action,nullptr),"restore ordinary disposition after onstack registration");
  auto unsupported=action;unsupported.flags|=0x40000000;Check(model.Action(30,&unsupported,nullptr)==38,"SA_NODEFER remains unsupported");
  Check(model.Queue(999,0)==3&&!model.Queue(1,0),"liveness uses stable thread tokens");
  uint64_t block=SignalHost::Bit(30);Check(!model.Mask(1,0,&block,nullptr),"block stop signal");
  SignalHost::Info info{},other{};info[16]=7;other[16]=9;
  Check(!model.Queue(1,30,&info)&&!model.Queue(1,30,&other),"pending standard signals coalesce");
  uint64_t pending=0;model.Pending(1,&pending);Check(pending==block&&!SignalHost::NeedsPoll(model.Lookup(1)),"blocked pending state suppresses runnable poll");
  Check(!model.RegisterThread(2,1),"child mask inherited");Check(Mask(model,2)==Mask(model,1),"child inherits mask but not pending");model.Pending(2,&pending);Check(!pending,"child starts with no pending signals");
  unsigned delivered=0;
  auto boundary=[&](const SignalHost::Delivery&d)->std::optional<uint64_t>{++delivered;Check(d.token==1&&d.signal==30&&d.info[16]==7,"coalescing retains first siginfo");auto active=Mask(model,1);Check(active&block,"automatic handler blocking");Check((active&(0xffULL<<32))==0&&(active&(1ULL<<31)),"sigsuspend filters Bionic reserved signals");Check(d.saved_mask==(initial|block),"sigsuspend frame saves original, not temporary mask");return {};};
  Check(model.Suspend(1,UINT64_MAX&~block,boundary)==4&&delivered==1,"queued-before-sigsuspend wakes and returns EINTR");
  Check(Mask(model,1)==(initial|block),"sigsuspend restores original mask");model.Pending(1,&pending);Check(!pending,"caught pending signal consumed");
  Check(!model.Mask(1,1,&block,nullptr),"unblock stop signal");Check(!model.Queue(1,30),"queued for explicit target dispatch");
  std::thread wrong([&]{Check(model.DispatchOne(1,boundary).error==1,"other thread cannot deliver target handler");});wrong.join();
  Check(SignalHost::NeedsPoll(model.Lookup(1)),"unmasked pending publishes acquire-visible poll request");
  Check(notifications.load()>0,"queue/unblock invokes parent poll notifier");
  auto thrown=[&](const SignalHost::Delivery&)->std::optional<uint64_t>{throw std::runtime_error("handler error");};
  bool caught=false;try{model.DispatchOne(1,thrown);}catch(const std::runtime_error&){caught=true;}Check(caught&&Mask(model,1)==initial,"throwing boundary restores mask");
  AndroidSignalAction ignored{};ignored.handler=1;Check(!model.Action(30,&ignored,nullptr)&&!model.Queue(1,30),"ignore disposition discards signals");
  Check(!SignalHost::NeedsPoll(model.Lookup(1)),"ignored signals do not interrupt waits");Check(!model.Action(30,&action,nullptr),"restore handler");
  Check(!model.DropThread(2)&&model.Queue(2,0)==3&&model.RegisterThread(2)==22,"dead token tombstone prevents ABA");
  AndroidSemaphore storage{};const addr_t address=(addr_t)&storage;
  Check(sem.Init(address,1,0)==38&&sem.Init(address,0,0x40000000)==22,"unsupported shared/value limits");Check(!sem.Init(address,0,1),"initialize semaphore");
  AndroidSemaphoreTime bad{0,1000000000},past{0,0},negative{-1,0};
  Check(!sem.TimedWait(address,(addr_t)&bad,1,boundary),"available token precedes deadline validation");
  Check(sem.TimedWait(address,(addr_t)&bad,1,boundary)==22&&sem.TimedWait(address,(addr_t)&past,1,boundary)==110&&sem.TimedWait(address,(addr_t)&negative,1,boundary)==110,"invalid/expired deadline semantics");
  Check(sem.TryWait(address)==11&&!sem.Post(address)&&!sem.TimedWait(address,0,1,boundary),"ready token avoids null deadline read");
  Check(!sem.Destroy(address)&&!sem.Init(address,0,0x3fffffff)&&sem.Post(address)==75,"overflow is truthful");Check(!sem.Destroy(address),"destroy maximum semaphore");
  for(unsigned restart=0;restart<2;++restart)for(unsigned timed=0;timed<2;++timed){
    Check(!sem.Init(address,0,0),"initialize interrupt test");uint64_t id=10+restart*2+timed;Check(!model.RegisterThread(id),"register blocking worker");
    auto a=action;a.flags=restart?0x10000000:0;Check(!model.Action(30,&a,nullptr),"restart disposition");
    std::promise<void> ready;auto started=ready.get_future();std::atomic<bool> handler_seen=false;std::atomic<int> result=-1;
    std::thread waiter([&]{Check(!model.BindCurrent(id),"worker owns boundary");ready.set_value();
      auto handler=[&](const SignalHost::Delivery&d)->std::optional<uint64_t>{Check(d.token==id,"interrupt on intended worker");int32_t value;Check(!sem.GetValue(address,&value),"semaphore lock released across callback");handler_seen=true;return {};};
      auto now=std::chrono::system_clock::now().time_since_epoch();AndroidSemaphoreTime until{std::chrono::duration_cast<std::chrono::seconds>(now).count()+2,0};
      result=timed?sem.TimedWait(address,(addr_t)&until,id,handler):sem.Wait(address,id,handler);
    });started.wait();std::this_thread::sleep_for(std::chrono::milliseconds(2));Check(!model.Queue(id,30),"interrupt blocked worker");
    while(!handler_seen)std::this_thread::yield();Check(!sem.Post(address),"post after handler");waiter.join();
    Check(result==(restart&&!timed?0:4),"untimed SA_RESTART retries; timed/nonrestart waits return EINTR");int32_t count=0;sem.GetValue(address,&count);Check(count==(restart&&!timed?0:1),"interrupt does not consume posted token");
    Check(!sem.Destroy(address)&&!model.DropThread(id),"cleanup interrupt worker");
  }
  // Stop-handler-shaped nesting: acknowledgment, sigsuspend for restart, then
  // resume acknowledgment. Pending stop requests during the callback survive.
  AndroidSemaphore acknowledgments{};addr_t ack=(addr_t)&acknowledgments;
  Check(!sem.Init(ack,0,0)&&!model.RegisterThread(80,1),"nested stop/restart test setup");
  auto stop_action=action;stop_action.flags=4|0x10000000;stop_action.mask=~SignalHost::Bit(24);
  auto restart_action=action;restart_action.handler=0x2000;restart_action.flags=0x10000000;
  Check(!model.Action(30,&stop_action,nullptr)&&!model.Action(24,&restart_action,nullptr),"nested stop/restart dispositions");
  std::atomic<unsigned> stops=0,restarts=0;std::promise<void> bound;auto bound_future=bound.get_future();
  SignalHost::Boundary nested;
  nested=[&](const SignalHost::Delivery&d)->std::optional<uint64_t>{
    if(d.signal==24){++restarts;return {};}
    if(++stops==1){
      Check(!sem.Post(ack),"stop acknowledgment callback has no semaphore/registry lock");
      Check(model.Suspend(80,~SignalHost::Bit(24),nested)==4,"explicit nested restart boundary");
      Check(!sem.Post(ack),"resume acknowledgment callback has no semaphore/registry lock");
    }
    return {};
  };
  std::thread stopping([&]{
    Check(!model.BindCurrent(80),"nested target bound");bound.set_value();
    Check(model.Suspend(80,initial,nested)==4,"outer suspend catches stop");
    Check(Mask(model,80)==initial&&SignalHost::NeedsPoll(model.Lookup(80)),"pending request during handler remains runnable after mask restore");
    Check(model.DispatchOne(80,nested).handled&&!SignalHost::NeedsPoll(model.Lookup(80)),"pending stop delivered after outer handler returns");
  });
  bound_future.wait();Check(!model.Queue(80,30),"send stop to target");
  Check(!sem.Wait(ack,1,{}),"wait for stop acknowledgment");
  Check(!model.Queue(80,30)&&!model.Queue(80,30)&&!model.Queue(80,24),"queue coalesced stop plus restart during stop handler");
  Check(!sem.Wait(ack,1,{}),"wait for resume acknowledgment");stopping.join();
  Check(stops==2&&restarts==1,"nested delivery and pending coalescence counts");
  Check(!sem.Destroy(ack)&&!model.DropThread(80),"nested stop/restart cleanup");
  // Isolated explicit nested Runtime boundary; no asynchronous hook installed.
  recomp::Runtime runtime;State *active=nullptr;alignas(16)std::array<uint8_t,65536> stack{};
  auto deliver=[&](const SignalHost::Delivery&d)->std::optional<uint64_t>{
    Check(active!=nullptr,"fixture supplies explicit materialized context");State handler=*active;
    handler.gpr.x0.qword=d.signal;handler.gpr.x1.qword=(addr_t)d.info.data();handler.gpr.x2.qword=0;handler.gpr.x30.qword=0xfeedfff0;
    auto previous=active;active=&handler;runtime.Run(handler,d.action.handler);active=previous;Check(handler.gpr.pc.qword==0xfeedfff0,"translated handler return");return {};
  };
  model.SetErrorSink([](int e){recomp::WriteGuestMemory((addr_t)&guest_error,&e,sizeof(e));});sem.SetErrorSink([](int e){recomp::WriteGuestMemory((addr_t)&guest_error,&e,sizeof(e));});
  model.Install(runtime,[]{return token;},deliver);sem.Install(runtime,[]{return token;},deliver);
  State invalid_set{};runtime.Run(invalid_set,model.Marker("sigemptyset"));
  Check(int32_t(invalid_set.gpr.x0.qword)==-1&&guest_error==22,"Bionic null sigset helper returns EINVAL");
  runtime.AddImport(0x7ff600300000ULL,[](State&s){s.gpr.x0.qword=(addr_t)&guest_error;});runtime.AddTraces(kTraces,std::size(kTraces));
  elf_image image{};Check(!elf_load(SIGNAL_HOST_LIBRARY,0x5a000000,Resolve,&image),"NDK ELF load");
  std::array<int64_t,64> actual{};State state{};state.gpr.x0.qword=1;state.gpr.x1.qword=(addr_t)actual.data();state.gpr.x30.qword=0xfeedfff0;state.gpr.sp.qword=(addr_t)(stack.data()+stack.size());
  active=&state;runtime.Run(state,(addr_t)elf_symbol(&image,"policy_guest"));active=nullptr;
  std::ifstream reference(SIGNAL_HOST_REFERENCE,std::ios::binary);int length=0;reference.read((char*)&length,4);std::array<int64_t,64> expected{};reference.read((char*)expected.data(),length*8);
  // Real glibc/QEMU rejects invalid nanoseconds before a ready token;
  // Android13 semaphore.cpp explicitly tries the token first.
  Check(expected[19]==-1&&expected[20]==22,"reference exposes glibc/Android invalid-deadline difference");
  expected[19]=expected[20]=0;
  Check(state.gpr.x0.qword==uint64_t(length)&&actual[0]==32&&actual[1]==8&&actual[2]==16,"Android layouts/result count");
  for(int i=3;i<length;++i){if(actual[i]!=expected[i])std::fprintf(stderr,"record%d actual%lld expected%lld\n",i,(long long)actual[i],(long long)expected[i]);Check(actual[i]==expected[i],"NDK policy/semantics match ARM64 QEMU");}
  std::printf("Signal/semaphore foundations: %u checks; NDK common policy matches QEMU plus source-verified Android fast path; no asynchronous delivery or GC integration.\n",checks.load());
}
