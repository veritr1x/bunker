#include <cfenv>
#include "signal_sleep.h"
#include "signal_delivery.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <stdexcept>
#include <string>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <time.h>
#endif
using namespace bunker::windows;
namespace {
std::atomic<unsigned>checks{0};thread_local int guest_error;SignalSleeps*provider;
constexpr addr_t kErrno=0x7ffe40000000ULL;
void Check(bool x,const char*m){if(!x){std::fprintf(stderr,"usleep check:%s\n",m);std::abort();}++checks;}
uint64_t Now(){
#ifdef _WIN32
 using Query=VOID(WINAPI*)(PULONGLONG);
 auto address=GetProcAddress(GetModuleHandleW(L"kernelbase.dll"),"QueryUnbiasedInterruptTimePrecise");
 Query query=nullptr;static_assert(sizeof(query)==sizeof(address));std::memcpy(&query,&address,sizeof(query));
 Check(query!=nullptr,"independent actual Windows unbiased precise clock");
 ULONGLONG t;query(&t);return uint64_t(t)*100;
#else
 timespec t{};Check(!clock_gettime(CLOCK_MONOTONIC,&t),"independent monotonic reference");return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;
#endif
}
bool Executable(addr_t a){for(auto&t:kTraces)if(t.address==a)return true;return false;}
void*Resolve(const char*n){if(!std::strcmp(n,"__errno"))return reinterpret_cast<void*>(kErrno);return reinterpret_cast<void*>(provider->Marker(n));}
struct Harness {
 recomp::Runtime runtime;SignalHost model;SignalDelivery*delivery=nullptr;
 SignalSleeps::Admission policy=[](uint64_t){return SignalHost::Bit(10);};
 SignalSleeps sleeps;elf_image image{};alignas(16)std::array<uint8_t,131072>stack{};
 unsigned delivered=0;uint32_t*counter=nullptr;addr_t normal=0,handler=0;
 Harness():sleeps(model,[]{return uint64_t(1);},[this](const auto&d){Check(delivery!=nullptr,"real bounded handler binding");++delivered;return delivery->Deliver(d);},[this](auto token){return policy(token);}){
  provider=&sleeps;Check(!model.RegisterThread(1)&&!model.BindCurrent(1),"actual caller owns signal model");
  sleeps.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,sizeof(e));});sleeps.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
  Check(!elf_load(USLEEP_LIBRARY,0x5b000000,Resolve,&image),"same strict NDK object loaded");handler=Symbol("sleep_handler");normal=Symbol("sleep_return");counter=reinterpret_cast<uint32_t*>(elf_symbol(&image,"sleep_handlers"));Check(counter!=nullptr,"actual guest handler side effect storage");Action(0);
 }
 ~Harness(){
#ifdef _WIN32
  VirtualFree(image.base,0,MEM_RELEASE);
#else
  munmap(image.base,image.span);
#endif
  std::free(const_cast<uint8_t*>(image.file));
 }
 addr_t Symbol(const char*n){auto a=reinterpret_cast<addr_t>(elf_symbol(&image,n));Check(a&&Executable(a),"actual NDK translated entry");return a;}
 void Reset(){uint32_t zero=0;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(counter),&zero,4);delivered=0;}
 void Action(uint32_t flags,addr_t address=0){AndroidSignalAction a{};a.handler=address?address:handler;a.flags=flags;Check(!model.Action(10,&a,nullptr),"real disposition");}
 int Run(uint64_t us,int mode,int*error){State s{};s.gpr.x0.qword=us;s.gpr.x1.dword=mode;s.gpr.x2.qword=reinterpret_cast<addr_t>(error);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x123456789abcdef0ULL;SignalDelivery frame(runtime,Executable,normal,{reinterpret_cast<addr_t>(stack.data()),s.gpr.sp.qword});delivery=&frame;runtime.Run(s,Symbol("guest_sleep"));delivery=nullptr;Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0x123456789abcdef0ULL,"NDK SP/PC/savedGPR roundtrip");return int32_t(s.gpr.x0.dword);}
 uint32_t Exclusive(bool interrupt){alignas(64)uint64_t word=0x123456789abcdef0ULL;int result=42;uint32_t status=99;State s{};s.gpr.x0.qword=interrupt?200000:1000;s.gpr.x1.qword=reinterpret_cast<addr_t>(&word);s.gpr.x2.qword=reinterpret_cast<addr_t>(&result);s.gpr.x3.qword=reinterpret_cast<addr_t>(&status);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;SignalDelivery frame(runtime,Executable,normal,{reinterpret_cast<addr_t>(stack.data()),s.gpr.sp.qword});delivery=&frame;guest_error=731;std::thread sender;if(interrupt)sender=std::thread([&]{std::this_thread::sleep_for(std::chrono::milliseconds(10));Check(!model.Queue(1,10),"real signal interrupts exclusive sleep");});runtime.Run(s,Symbol("sleep_exclusive"));if(sender.joinable())sender.join();delivery=nullptr;Check(result==(interrupt?-1:0)&&guest_error==(interrupt?4:731)&&word==0x123456789abcdef0ULL,"exclusive caller result/errno/memory");return status;}
};
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 Harness h;
 if(argc>1){std::string mode=argv[1];if(mode=="excluded")h.policy=[](uint64_t){return uint64_t(0);};else h.policy=[](uint64_t)->uint64_t{throw 17;};Check(!h.model.Queue(1,10),"negative actual pending");int e=0;h.Run(1000,1,&e);return 2;}
 unsigned records=0;
 for(int mode:{0,1}){
  for(uint64_t us:{UINT64_C(0),UINT64_C(1),UINT64_C(3000),UINT64_C(1000000),UINT64_C(1000001),UINT64_C(0x100000001)}){int e=0;h.Reset();const auto start=Now();int r=h.Run(us,mode,&e);const auto elapsed=Now()-start;Check(r==0&&e==731&&!h.delivered&&elapsed>=uint64_t(uint32_t(us))*1000,"actual elapsed lower bound/success errno/low32/zero/one-second-plus");std::printf("normal mode=%d low32=%u return=0 errno=731 elapsed=%llu\n",mode,uint32_t(us),(unsigned long long)elapsed);++records;}
  for(int restart:{0,1}){h.Action(restart?0x10000000:0);h.Reset();std::thread sender([&]{std::this_thread::sleep_for(std::chrono::milliseconds(10));Check(!h.model.Queue(1,10),"actual asynchronous model queue");});int e=0;int r=h.Run(UINT64_C(0x1ffffffff),mode,&e);sender.join();Check(r==-1&&e==4&&h.delivered==1&&*h.counter==1,"actual translated handler EINTR independent of SA_RESTART");std::printf("interrupt mode=%d restart=%d low32=4294967295 return=-1 errno=4 handlers=1\n",mode,restart);++records;}
 }
 h.Action(0);h.Reset();uint64_t mask=SignalHost::Bit(10);Check(!h.model.Mask(1,0,&mask,nullptr),"block real signal");std::thread blocked([&]{std::this_thread::sleep_for(std::chrono::milliseconds(2));Check(!h.model.Queue(1,10),"blocked queue retained");});int e=0;auto start=Now();Check(!h.Run(20000,0,&e),"blocked signal does not interrupt");blocked.join();uint64_t pending=0;Check(Now()-start>=20000000&&e==731&&!h.delivered&&!h.model.Pending(1,&pending)&&(pending&mask),"blocked pending/full elapsed/errno retained");h.Action(0,1);Check(!h.model.Mask(1,1,&mask,nullptr),"unblock after real ignore clears pending");
 h.Reset();std::thread ignored([&]{std::this_thread::sleep_for(std::chrono::milliseconds(2));Check(!h.model.Queue(1,10),"ignored signal does not enqueue");});start=Now();Check(!h.Run(20000,1,&e),"ignored signal does not interrupt");ignored.join();Check(Now()-start>=20000000&&e==731&&!h.delivered,"ignored completion budget");h.Action(0);
 h.Reset();std::thread spurious([&]{for(unsigned i=0;i<12;++i){h.model.Wake(1)->Notify();std::this_thread::sleep_for(std::chrono::milliseconds(1));}});start=Now();Check(!h.Run(20000,1,&e),"spurious wake not interruption");spurious.join();Check(Now()-start>=20000000&&e==731&&!h.delivered,"spurious notifications don't shorten deadline");
 for(unsigned i=0;i<8;++i){h.Reset();Check(!h.model.Queue(1,10),"wake before entering wait");Check(h.Run(200000,i&1,&e)==-1&&e==4&&h.delivered==1&&*h.counter==1,"pre-enrollment actual handler not lost");}
 h.Reset();Check(h.Exclusive(false)==1,"established Runtime import boundary clears real LDXR/STXR even without handler");h.Reset();Check(h.Exclusive(true)==1&&h.delivered==1&&*h.counter==1,"interrupted import and real handler leave exclusive invalidated");
 // Mixed allowed+excluded pending must be rejected atomically before either
 // callback. The excluded arrival is forced inside the admission decision.
 AndroidSignalAction other{};other.handler=h.handler;Check(!h.model.Action(12,&other,nullptr),"second real disposition");SignalHost::Info a{},b{};a[20]=0x51;b[20]=0x7f;Check(!h.model.Queue(1,10,&a),"allowed first queue");std::promise<void>inside,queued;auto entered=inside.get_future();auto done=queued.get_future();std::thread racer([&]{entered.wait();Check(!h.model.Queue(1,12,&b),"excluded races inside admission");queued.set_value();});h.policy=[&](uint64_t){inside.set_value();done.wait();return SignalHost::Bit(10);};bool rejected=false;try{h.sleeps.USleep(1000);}catch(const std::runtime_error&x){rejected=std::strstr(x.what(),"outside admitted")!=nullptr;}racer.join();Check(rejected&&h.delivered==1&&SignalHost::NeedsPoll(h.model.Lookup(1)),"atomic mixed exclusion rejects before new dispatch");unsigned seen=0;for(int sig:{10,12}){auto r=h.model.DispatchOneAllowed(1,SignalHost::Bit(sig),[&](const auto&d)->std::optional<uint64_t>{Check(d.signal==sig&&d.info[20]==(sig==10?0x51:0x7f),"rejected pending siginfo remains exact");++seen;return{};});Check(!r.error&&r.handled,"retained signal separately inspected");}Check(seen==2&&!SignalHost::NeedsPoll(h.model.Lookup(1)),"both original queued signals retained until explicit inspection");
 h.policy=[](uint64_t)->uint64_t{errno=999;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);throw std::runtime_error("policy throw");};errno=78;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);try{h.sleeps.USleep(1);}catch(const std::runtime_error&){}Check(errno==78&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"throwing preconsume policy restores native errno/fenv");std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);h.policy=[](uint64_t){return uint64_t(0);};
 std::thread wrong([&]{bool denied=false;try{h.sleeps.USleep(0);}catch(const std::runtime_error&x){denied=std::strstr(x.what(),"foreign")!=nullptr;}Check(denied,"foreign native thread cannot use another bound lifetime");});wrong.join();Check(!h.model.DropThread(1),"actual retirement");bool stale=false;try{h.sleeps.USleep(0);}catch(const std::runtime_error&){stale=true;}Check(stale,"retired lifetime rejected");
 std::printf("USLEEP-HOST-SUCCESS records=%u checks=%u actual-frame-handlers/monotonic/exclusives/admission-race\n",records,checks.load());return 0;
}
