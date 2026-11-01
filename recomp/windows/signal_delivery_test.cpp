#include "../whole/cooperative_poll.h"
#include "signal_delivery.h"
#include "semaphore_host.h"
#include "signal_delivery_fixture.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>

using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
thread_local uint64_t token;
thread_local int guest_error;
thread_local SignalDelivery *boundary;
SignalHost *signals;Semaphores *semaphores;
constexpr addr_t kErrno=0x7ff500000000ULL,kSelf=kErrno+8,kReturn=0xfeedffff;
void Check(bool value,const char *why){++checks;if(!value){std::fprintf(stderr,"signal delivery check: %s\n",why);std::abort();}}
void *Resolve(const char *name){
  if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);
  if(!std::strcmp(name,"pthread_self"))return reinterpret_cast<void*>(kSelf);
  try{return reinterpret_cast<void*>(signals->Marker(name));}catch(const std::invalid_argument&){}
  return reinterpret_cast<void*>(semaphores->Marker(name));
}
bool Executable(addr_t address){for(auto &trace:kTraces)if(trace.address==address)return true;return false;}
template<class T>void Publish(volatile T &target,T value){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&target),&value,sizeof(value));}
}
int main(){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(40));std::fputs("signal delivery watchdog\n",stderr);std::_Exit(95);}).detach();
  recomp::PollRequest request;
  SignalHost model([&](uint64_t target){if(target==2)request.Request();});
  Semaphores sem(model);signals=&model;semaphores=&sem;
  Check(!model.RegisterThread(1)&&!model.BindCurrent(1)&&!model.RegisterThread(2,1),"stable controller/worker tokens");token=1;
  recomp::Runtime runtime;
  auto deliver=[](const SignalHost::Delivery &d){if(!boundary)throw std::invalid_argument("no signal frame binding on current worker");return boundary->Deliver(d);};
  model.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,sizeof(e));});
  sem.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,sizeof(e));});
  model.Install(runtime,[]{return token;},deliver);sem.Install(runtime,[]{return token;},deliver);
  runtime.AddImport(kErrno,[](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
  runtime.AddImport(kSelf,[](State &s){s.gpr.x0.qword=token;});
  runtime.AddTraces(kTraces,std::size(kTraces));
  elf_image image{};Check(!elf_load(SIGNAL_DELIVERY_LIBRARY,0x5c000000,Resolve,&image),"real NDK handler/loop ELF load");
  auto symbol=[&](const char *name,bool entry=true){auto address=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(address&&(!entry||Executable(address)),"verified guest symbol/translated entry");return address;};
  const auto install=symbol("delivery_install"),loop=symbol("delivery_loop"),head=symbol("delivery_loop_head",false),normal_return=symbol("delivery_return_boundary");
  alignas(16)std::array<uint8_t,131072> stack{};
  const auto low=reinterpret_cast<addr_t>(stack.data()),high=low+stack.size();
  alignas(16)DeliveryReport report{};
  const auto ack=reinterpret_cast<addr_t>(report.acknowledgment);
  Check(!sem.Init(ack,0,0),"real Android opaque acknowledgment semaphore");
  State setup{};setup.gpr.x0.qword=reinterpret_cast<addr_t>(&report);setup.gpr.sp.qword=high;setup.gpr.pc.qword=install;setup.gpr.x30.qword=kReturn;
  runtime.Run(setup,install);Check(!setup.gpr.x0.qword&&setup.gpr.sp.qword==high,"NDK installs actual stop/restart dispositions");
  SignalDelivery outside(runtime,Executable,normal_return,{low,high});
  SignalHost::Delivery fake{};
  bool rejected=false;try{outside.Deliver(fake);}catch(const std::invalid_argument&){rejected=true;}
  Check(rejected,"delivery outside Runtime context rejected");
  alignas(16)std::array<uint64_t,4> roots{{1,2,3,4}};
  alignas(16)std::array<uint64_t,6> output{};
  alignas(16)std::array<uint64_t,8> tls{{0x12345678}};
  const auto root=reinterpret_cast<addr_t>(roots.data());
  State state{};state.gpr.x0.qword=root;state.gpr.x1.qword=reinterpret_cast<addr_t>(output.data());
  state.gpr.x2.qword=reinterpret_cast<addr_t>(&report.done);state.gpr.x20.qword=root;
  uint64_t lanes[]={root,root};std::memcpy(&state.simd.v[31],lanes,16);
  state.gpr.sp.qword=high;state.gpr.pc.qword=loop;state.gpr.x30.qword=kReturn;
  state.sr.tpidr_el0.qword=reinterpret_cast<addr_t>(tls.data());state.sr.tpidrro_el0.qword=0xaabbccdd;
  state.fpcr.rmode=kFPURoundUpInf;state.sr.ioc=1;state.sr.idc=1;
  std::promise<void> ready;auto started=ready.get_future();
  std::atomic<uint64_t> callbacks{0},nested_frames{0};
  std::thread worker([&]{
    token=2;guest_error=71;errno=63;
    Check(!model.BindCurrent(2),"worker owns signal policy");
    SignalDelivery execution(runtime,Executable,normal_return,{low,high});boundary=&execution;
    recomp::PollBinding binding(request,[&](State &s,recomp::PollSite,const std::vector<State*> &frames){
      ++callbacks;Check(&s==&state&&frames.size()==1&&frames[0]==&state,"loop poll materializes current worker State");
      auto result=model.DispatchOne(2,[&](const SignalHost::Delivery &d){
        Check(d.token==token,"signal executes on its original worker");
        ++nested_frames;return deliver(d);
      });
      Check(!result.error,"queued signal dispatch at cooperative boundary");
    });
    std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
    ready.set_value();runtime.Run(state,loop);
    Check(guest_error==71&&errno==63,"handler and nested waits preserve virtual errno; poll contains host errno");
    Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"nested frame delivery restores native worker fenv");
    boundary=nullptr;
  });
  started.wait();
  uint64_t previous=0;
  constexpr unsigned cycles=16;
  for(unsigned cycle=0;cycle<cycles;++cycle){
    Publish(report.world_stopped,uint64_t(1));Check(!model.Queue(2,30),"request stop during translated execution");
    auto wait_ack=[&]{auto now=std::chrono::system_clock::now().time_since_epoch();AndroidSemaphoreTime deadline{std::chrono::duration_cast<std::chrono::seconds>(now).count()+3,0};Check(!sem.TimedWait(ack,reinterpret_cast<addr_t>(&deadline),1,{}),"bounded stop/resume acknowledgment");};
    wait_ack();DeliveryReport snapshot{};recomp::ReadGuestMemory(&snapshot,reinterpret_cast<addr_t>(&report),sizeof(snapshot));
    Check(snapshot.stops==cycle+1&&snapshot.restarts==cycle,"exactly one stop acknowledgment before restart");
    Check(snapshot.worker_token==2&&snapshot.tls==reinterpret_cast<addr_t>(tls.data()),"handler sees original pthread identity and guest TLS");
    Check(snapshot.root==(root^((snapshot.counter&1)?8:0))&&snapshot.vector_root[0]==root&&snapshot.vector_root[1]==root,"live GPR and SIMD roots present in stack ucontext");
    Check(snapshot.counter>=previous&&(cycle==0||snapshot.counter>0),"interrupted active loop counter coherent");previous=snapshot.counter;
    Check(snapshot.interrupted_pc==(snapshot.counter?head:loop),"signal frame contains exact interrupted guest PC");
    Check(snapshot.interrupted_sp==high-(snapshot.counter?32:0)&&snapshot.frame<snapshot.interrupted_sp,"signal frame below exact interrupted SP");
    Check(snapshot.handler_sp>=low&&snapshot.handler_sp<snapshot.frame&&snapshot.handler_fp>=low&&snapshot.handler_fp<=snapshot.frame,"actual handler frame and FP are on original registered guest stack");
    Check(snapshot.error_before==71,"handler receives interrupted virtual errno");
    // Reads/writes and semaphore operations progress while the target is inside
    // its actual translated stop handler waiting in sigsuspend.
    Publish(report.world_stopped,uint64_t(0));Check(!model.Queue(2,24),"queue restart to nested target handler");
    wait_ack();recomp::ReadGuestMemory(&snapshot,reinterpret_cast<addr_t>(&report),sizeof(snapshot));
    Check(snapshot.restarts==cycle+1&&snapshot.error_after==4,"restart caught on target and sigsuspend reports EINTR");
  }
  Publish(report.done,uint64_t(1));worker.join();
  Check(state.gpr.sp.qword==high&&state.gpr.pc.qword==kReturn,"interrupted loop resumes and returns normally after all cycles");
  Check(state.gpr.x21.qword>0&&output[0]==(root^((state.gpr.x21.qword&1)?8:0))&&output[2]==root&&output[3]==root,"resumed guest consumes preserved live register roots");
  Check(state.sr.tpidr_el0.qword==reinterpret_cast<addr_t>(tls.data())&&state.sr.tpidrro_el0.qword==0xaabbccdd&&state.fpcr.rmode==kFPURoundUpInf&&state.sr.ioc&&state.sr.idc,"TLS/FPCR/FPSR restored after nested signal frames");
  Check(callbacks>=cycles&&nested_frames==cycles,"all stops delivered through actual compiler/runtime poll boundary");
  Check(!sem.Destroy(ack)&&!model.DropThread(2),"worker/semaphore lifetime cleanup");
  std::printf("Combined signal delivery: %u checks, %u same-worker stop/restart cycles, NDK handlers and real stack frames; no production GC integration.\n",checks.load(),cycles);
}
