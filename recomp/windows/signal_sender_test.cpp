#include <cfenv>
#include "signal_host.h"
#include "signal_delivery.h"
#include "signal_sender_fixture.h"
#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
using namespace bunker::windows;
namespace {
unsigned checks=0;
void Check(bool value,const char *why){++checks;if(!value)throw std::runtime_error(why);}
template<class F> void Reject(F f,const char *why){bool rejected=false;try{f();}catch(...){rejected=true;}Check(rejected,why);}
constexpr addr_t kErrno=0x7ffc76000000ULL,kSelf=kErrno+8,kUid=kErrno+16,kCheckpoint=kErrno+24,kReturn=0xfeedffff;
constexpr uint64_t kToken=0x7ffa000000a0ULL;
bool Executable(addr_t p){for(const auto &t:kTraces)if(t.address==p)return true;return false;}
struct Harness;Harness *active;
void *Resolve(const char*);
struct Harness {
  recomp::Runtime runtime;
  LibC libc;
  SignalHost model;
  elf_image image{};
  alignas(16) std::array<uint8_t,131200> stack{};
  struct {uint64_t low=0x1122334455667788ULL;SenderReport value{};uint64_t high=0x8877665544332211ULL;} report;
  int guest_error=731,mode=0;
  uint32_t uid=0x12345678;
  unsigned snapshots=0;
  addr_t low=0,high=0,configure=0,invoke=0,checkpoint=0;
  std::unique_ptr<SignalDelivery> delivery;
  Harness(){
    active=this;stack.fill(0xa5);low=reinterpret_cast<addr_t>(stack.data())+64;high=low+131072;
    Check(!model.RegisterThread(kToken)&&!model.BindCurrent(kToken),"actual calling native thread owns test token");
    runtime.AddTraces(kTraces,std::size(kTraces));libc.Install(runtime);
    model.Install(runtime,[]{return kToken;},[this](const auto &d){return delivery->Deliver(d);},[this]{
      ++snapshots;AndroidSignalAction action{};uint64_t pending=0;
      Check(!model.Action(30,nullptr,&action)&&!model.Pending(kToken,&pending),"identity callback runs outside signal mutex");
      errno=123;std::fesetround(FE_DOWNWARD);std::feraiseexcept(FE_DIVBYZERO);
#ifdef _WIN32
      SetLastError(12345);
#endif
      if(mode==1)throw std::runtime_error("TEST sender snapshot exception");
      if(mode==2){std::fputs("TEST sender unknown snapshot exception\n",stderr);throw 7;}
      return SignalHost::SenderIdentity{mode==3?0:libc.ProcessId(),uid};
    });
    runtime.AddImport(kErrno,[this](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
    runtime.AddImport(kSelf,[](State &s){s.gpr.x0.qword=kToken;});
    runtime.AddImport(kUid,[this](State &s){s.gpr.x0.qword=uid;});
    runtime.AddImport(kCheckpoint,[this](State &s){try{
      const State saved=s;const auto result=model.DispatchOne(kToken,[this](const auto &d){return delivery->Deliver(d);});
      Check(!result.error&&result.handled,"actual pending delivery through same-worker signal frame");
      Check(!std::memcmp(&saved,&s,sizeof(s)),"signal restores complete interrupted State");
    }catch(const std::exception &e){std::fprintf(stderr,"sender checkpoint: %s\n",e.what());std::abort();}catch(...){std::abort();}});
    Check(!elf_load(SENDER_LIBRARY,0x5e000000,Resolve,&image),"actual NDK fixture loaded");
    auto symbol=[this](const char *name){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(p&&Executable(p),"translated NDK symbol");return p;};
    configure=symbol("sender_configure");invoke=symbol("sender_invoke");checkpoint=symbol("sender_checkpoint");
    delivery=std::make_unique<SignalDelivery>(runtime,Executable,symbol("sender_return_boundary"),SignalDelivery::Bounds{low,high});
    Check(Call(configure,reinterpret_cast<addr_t>(&report.value))==0,"actual NDK SA_SIGINFO registration");
  }
  ~Harness(){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.base),image.span);
#ifdef _WIN32
    if(image.base)VirtualFree(image.base,0,MEM_RELEASE);
#else
    if(image.base)munmap(image.base,image.span);
#endif
    std::free(const_cast<uint8_t*>(image.file));
  }
  uint64_t Call(addr_t entry,uint64_t x0=0,uint64_t x1=0,uint64_t x2=0){
    State state{};state.gpr.sp.qword=high;state.gpr.pc.qword=entry;state.gpr.x30.qword=kReturn;
    state.gpr.x0.qword=x0;state.gpr.x1.qword=x1;state.gpr.x2.qword=x2;
    Reg GPR::*regs[]={&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29};
    for(size_t i=0;i<std::size(regs);++i)(state.gpr.*regs[i]).qword=0x1144228800000000ULL+i;
    for(unsigned i=8;i<=15;++i){uint64_t v=0x9988112200000000ULL+i;std::memcpy(&state.simd.v[i],&v,8);}
    state.sr.tpidr_el0.qword=0x12345000;state.sr.tpidrro_el0.qword=0x55667788;state.fpcr.rmode=kFPURoundUpInf;
    runtime.Run(state,entry);
    Check(state.gpr.pc.qword==kReturn&&state.gpr.sp.qword==high,"NDK PC/SP return ABI");
    for(size_t i=0;i<std::size(regs);++i)Check((state.gpr.*regs[i]).qword==0x1144228800000000ULL+i,"NDK callee GP preservation");
    for(unsigned i=8;i<=15;++i){uint64_t v;std::memcpy(&v,&state.simd.v[i],8);Check(v==0x9988112200000000ULL+i,"NDK callee D low preservation");}
    Check(state.sr.tpidr_el0.qword==0x12345000&&state.sr.tpidrro_el0.qword==0x55667788&&state.fpcr.rmode==kFPURoundUpInf,"TLS/FP control preservation");
    for(size_t i=0;i<64;++i)Check(stack[i]==0xa5&&stack[stack.size()-1-i]==0xa5,"guest stack bounds canaries");
    Check(report.low==0x1122334455667788ULL&&report.high==0x8877665544332211ULL,"report write canaries");
    return state.gpr.x0.qword;
  }
  bool Pending(){uint64_t p=0;Check(!model.Pending(kToken,&p),"blocked pending query");return p||SignalHost::NeedsPoll(model.Lookup(kToken));}
  void Validate(uint32_t expected_uid){
    std::array<uint8_t,128> expected{};
    auto store=[&](size_t off,uint32_t v){for(size_t i=0;i<4;++i)expected[off+i]=uint8_t(v>>(8*i));};
    store(0,30);store(8,uint32_t(-6));store(16,uint32_t(libc.ProcessId()));store(20,expected_uid);
    Check(!std::memcmp(report.value.info,expected.data(),128),"exact NDK siginfo bytes and zero padding");
    Check(report.value.signal_number==30&&report.value.handler_error==731&&guest_error==731&&!report.value.caller_error_changed,"pthread/handler virtual errno preserved");
    Check(report.value.process_id==libc.ProcessId()&&report.value.real_uid==uid&&report.value.token==kToken,"handler reads same explicit virtual process identity");
    Check(report.value.handler_sp>=low&&report.value.handler_sp<high&&report.value.handler_fp>=low&&report.value.handler_fp<high,"actual NDK handler on owned guest stack");
  }
};
void *Resolve(const char *name){
  if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);
  if(!std::strcmp(name,"pthread_self"))return reinterpret_cast<void*>(kSelf);
  if(!std::strcmp(name,"getuid"))return reinterpret_cast<void*>(kUid);
  if(!std::strcmp(name,"test_sender_checkpoint"))return reinterpret_cast<void*>(kCheckpoint);
  if(!std::strcmp(name,"getpid"))return reinterpret_cast<void*>(active->libc.Marker(name));
  return reinterpret_cast<void*>(active->model.Marker(name));
}
void Direct(){
  SignalHost s;Check(!s.RegisterThread(1)&&!s.BindCurrent(1),"direct owner registered");AndroidSignalAction a{};a.handler=0x1000;a.flags=4;Check(!s.Action(30,&a,nullptr),"direct action");
  unsigned called=0;auto sender=[&]{++called;return SignalHost::SenderIdentity{123456,0xffffffff};};
  Check(s.ThreadKill(1,-1,sender)==22&&s.ThreadKill(1,65,sender)==22&&s.ThreadKill(999,30,sender)==3,"invalid direct statuses");
  Check(!s.ThreadKill(1,0,sender)&&s.ThreadKill(999,0,sender)==3,"signal0 only probes liveness");
  Check(s.ThreadKill(1,9,sender)==38&&s.ThreadKill(1,19,sender)==38&&s.ThreadKill(1,35,sender)==38&&s.ThreadKill(1,31,sender)==38&&!called,"unsupported paths do not snapshot");
  auto ignored=a;ignored.handler=1;Check(!s.Action(30,&ignored,nullptr)&&!s.ThreadKill(1,30,sender)&&!called,"ignored path does not snapshot");Check(!s.Action(30,&a,nullptr),"restore direct action");
  auto pending=[&]{uint64_t p=99;Check(!s.Pending(1,&p),"direct pending");return p||SignalHost::NeedsPoll(s.Lookup(1));};
  Reject([&]{s.ThreadKill(1,30,{});},"missing explicit snapshot rejected");
  for(int pid:{0,-1,INT32_MIN})Reject([&]{s.ThreadKill(1,30,[&]{return SignalHost::SenderIdentity{pid,42};});},"invalid explicit PID rejected");
  Reject([&]{s.ThreadKill(1,30,[]{throw std::runtime_error("direct failure");return SignalHost::SenderIdentity{};});},"snapshot exception propagates before queue");Check(!pending(),"failed identity did not queue");
  Check(!s.Queue(1,30),"legacy generic Queue unaffected");SignalHost::Info legacy{};Check(s.DispatchOne(1,[&](const auto&d)->std::optional<uint64_t>{legacy=d.info;return {};}).handled,"legacy direct dispatch");for(size_t i=0;i<128;++i)Check(legacy[i]==(i?0:30),"legacy generic info stays signo-only");
  errno=91;std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);
  Reject([&]{s.ThreadKill(1,30,[]{errno=123;std::fesetround(FE_DOWNWARD);std::feraiseexcept(FE_DIVBYZERO);throw 7;return SignalHost::SenderIdentity{};});},"unknown callback exception propagates before queue");
  Check(errno==91&&std::fegetround()==FE_UPWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INVALID&&!pending(),"snapshot failure restores native environment and pending");
#ifdef _WIN32
  SetLastError(8765);Reject([&]{s.ThreadKill(1,30,[]{SetLastError(123);throw 7;return SignalHost::SenderIdentity{};});},"Windows callback exception");Check(GetLastError()==8765,"callback restores Windows LastError");
#endif
  for(unsigned n=0;n<8;++n){uint64_t token=10+n;Check(!s.RegisterThread(token,1),"race target registration");std::promise<void> entered,removed;auto ready=entered.get_future(),gone=removed.get_future();std::thread remover([&]{ready.wait();Check(!s.DropThread(token),"concurrent real target retirement");removed.set_value();});const int result=s.ThreadKill(token,30,[&]{entered.set_value();gone.wait();return SignalHost::SenderIdentity{123456,9};});remover.join();Check(result==3&&!SignalHost::NeedsPoll(s.Lookup(token)),"final Queue revalidates lifetime and does not queue");}
  Check(!s.ThreadKill(1,30,[&]{Check(!s.Action(30,&ignored,nullptr),"disposition changes during unlocked snapshot");return SignalHost::SenderIdentity{123456,9};})&&!pending(),"final Queue respects now-ignored action");
}
}
int main(int argc,char **argv){
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
#endif
  try{
    Harness h;
    if(argc==2){h.mode=!std::strcmp(argv[1],"throw-standard")?1:!std::strcmp(argv[1],"throw-unknown")?2:3;h.Call(h.invoke,kToken,30,0);throw std::runtime_error("negative import returned");}
    for(unsigned mode=0;mode<2;++mode){const auto before=h.snapshots;
      for(const auto &item:std::array<std::pair<int32_t,int32_t>,4>{{{-1,22},{65,22},{9,38},{35,38}}})Check(h.Call(h.invoke,kToken,static_cast<uint64_t>(static_cast<int64_t>(item.first)),mode)==uint32_t(item.second),"NDK direct/indirect signed invalid status");
      Check(h.Call(h.invoke,999,30,mode)==3&&h.snapshots==before&&!h.Pending(),"NDK dead target status has no snapshot/queue");
      AndroidSignalAction ignored{};ignored.handler=1;Check(!h.model.Action(30,&ignored,nullptr),"install ignored disposition");Check(!h.Call(h.invoke,kToken,30,mode)&&h.snapshots==before&&!h.Pending(),"NDK ignored action no snapshot/queue");Check(!h.Call(h.configure,reinterpret_cast<addr_t>(&h.report.value)),"restore NDK disposition");
      Check(h.guest_error==731&&!h.report.value.caller_error_changed,"NDK error status leaves guest errno");
      Check(h.Call(h.invoke,kToken,0,mode)==0&&h.snapshots==before&&!h.Pending(),"NDK zero probe no snapshot/queue");Check(h.Call(h.invoke,kToken,30,mode)==0&&h.snapshots==before+1&&h.Pending(),"actual NDK pthread_kill queues explicit identity");Check(!h.Call(h.checkpoint)&&!h.Pending(),"NDK checkpoint drains actual signal");h.Validate(h.uid);std::printf("HOST mode=%u count=%u pid=%d uid=%u code=-6 raw=",mode,h.report.value.calls,h.report.value.process_id,h.uid);for(auto x:h.report.value.info)std::printf("%02x",x);std::putchar('\n');}
    for(uint32_t uid:{0U,1U,0x7fffffffU,0x80000000U,0xffffffffU}){h.uid=uid;Check(!h.Call(h.invoke,kToken,30,1)&&!h.Call(h.checkpoint),"UID wire edge actual NDK call/delivery");h.Validate(uid);}
    h.uid=17;Check(!h.Call(h.invoke,kToken,30,0),"first standard signal");h.uid=29;Check(!h.Call(h.invoke,kToken,30,1),"second coalesced standard signal");Check(!h.Call(h.checkpoint),"coalesced signal delivery");h.Validate(17);
    h.mode=1;Reject([&]{h.model.ThreadKill(kToken,30,[&]{throw std::runtime_error("TEST direct identity failure");return SignalHost::SenderIdentity{};});},"direct failed identity");Check(!h.Pending(),"direct failed identity leaves no pending");
    Direct();std::printf("SIGNAL-SENDER-HOST-SUCCESS checks=%u explicit-virtual-uid no-GC\n",checks);return 0;
  }catch(const std::exception&e){std::fprintf(stderr,"signal sender fixture: %s\n",e.what());return 1;}
}
