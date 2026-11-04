#include <cfenv>
#include "signal_nanosleep.h"
#include "signal_delivery.h"
#include "../whole/bridge.h"
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
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <time.h>
#endif
using namespace bunker::windows;
namespace {
std::atomic<unsigned>checks{0};thread_local int guest_error;SignalNanoSleeps*provider;
constexpr addr_t kErrno=0x7ffe40000000ULL,kDelay=0x7ffe40000008ULL;
struct Time {int64_t seconds,nanoseconds;};static_assert(sizeof(Time)==16&&offsetof(Time,nanoseconds)==8);
void Check(bool value,const char*why){if(!value){std::fprintf(stderr,"nanosleep check:%s\n",why);std::abort();}++checks;}
uint64_t Now(){
#ifdef _WIN32
 using Query=VOID(WINAPI*)(PULONGLONG);auto address=GetProcAddress(GetModuleHandleW(L"kernelbase.dll"),"QueryUnbiasedInterruptTimePrecise");Query query=nullptr;static_assert(sizeof(query)==sizeof(address));std::memcpy(&query,&address,sizeof(query));Check(query!=nullptr,"actual unbiased precise Windows clock");ULONGLONG ticks=0;query(&ticks);return uint64_t(ticks)*100;
#else
 timespec now{};Check(!clock_gettime(CLOCK_MONOTONIC,&now),"actual monotonic clock");return uint64_t(now.tv_sec)*1000000000+now.tv_nsec;
#endif
}
bool Executable(addr_t address){for(const auto&trace:kTraces)if(trace.address==address)return true;return false;}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(name,"nanosleep_fixture_delay"))return reinterpret_cast<void*>(kDelay);return reinterpret_cast<void*>(provider->Marker(name));}
template<class T>T Read(addr_t address){T value{};recomp::ReadGuestMemory(&value,address,sizeof(value));return value;}
template<class T>void Write(addr_t address,const T&value){recomp::WriteGuestMemory(address,&value,sizeof(value));}
struct Harness {
 recomp::Runtime runtime;SignalHost model;SignalDelivery*delivery=nullptr;
 SignalNanoSleeps::Admission policy=[](uint64_t){return SignalHost::Bit(10);};
 std::function<void(const SignalNanoSleeps::Observation&)> observer;
 SignalNanoSleeps sleeps;elf_image image{};alignas(16)std::array<uint8_t,131072>stack{};
 addr_t counter=0,probe=0,delay=0,seen_seconds=0,seen_nanos=0,normal=0,handler=0;unsigned delivered=0,observations=0;SignalNanoSleeps::Observation last{};
 Harness():sleeps(model,[]{return uint64_t(1);},[this](const auto&info){Check(delivery!=nullptr,"actual bounded SignalDelivery handler");++delivered;return delivery->Deliver(info);},[this](auto token){return policy(token);}){
  provider=&sleeps;Check(!model.RegisterThread(1)&&!model.BindCurrent(1),"actual bound SignalHost lifetime");
  sleeps.SetErrorSink([](int value){Write(reinterpret_cast<addr_t>(&guest_error),value);});
  sleeps.SetRequestObserver([this](const auto&value){++observations;last=value;if(observer)observer(value);});
  sleeps.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
  // Explicit TEST-only native helper called by the actual translated handler;
  // the production provider never dispatches this or synthesizes its delay.
  runtime.AddImport(kDelay,recomp::MakeBridge<void()>([]{std::this_thread::sleep_for(std::chrono::milliseconds(60));}));
  Check(!elf_load(NANOSLEEP_IMAGE,0x5b000000,Resolve,&image),"strict NDK fixture loaded");
  counter=Data("nanosleep_handlers");probe=Data("nanosleep_remaining_probe");delay=Data("nanosleep_delay_handler");seen_seconds=Data("nanosleep_handler_seconds");seen_nanos=Data("nanosleep_handler_nanoseconds");normal=Symbol("nanosleep_return");handler=Symbol("nanosleep_handler");Action(0);
 }
 ~Harness(){
#ifdef _WIN32
  VirtualFree(image.base,0,MEM_RELEASE);
#else
  munmap(image.base,image.span);
#endif
  std::free(const_cast<uint8_t*>(image.file));
 }
 addr_t Data(const char*name){auto result=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(result!=0,"real NDK fixture storage");return result;}
 addr_t Symbol(const char*name){auto result=Data(name);Check(Executable(result),"real translated fixture function");return result;}
 void Reset(addr_t output=0,bool delayed=false){Write(counter,uint32_t(0));Write(probe,uint64_t(output));Write(delay,int32_t(delayed));Write(seen_seconds,int64_t(-9));Write(seen_nanos,int64_t(-9));delivered=0;observations=0;}
 void Action(uint32_t flags,addr_t entry=0){AndroidSignalAction action{};action.handler=entry?entry:handler;action.flags=flags;Check(!model.Action(10,&action,nullptr),"actual signal disposition");}
 int Run(addr_t request,addr_t remaining,int mode,int*error){State state{};state.gpr.x0.qword=request;state.gpr.x1.qword=remaining;state.gpr.x2.dword=mode;state.gpr.x3.qword=reinterpret_cast<addr_t>(error);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;state.gpr.x19.qword=0x123456789abcdef0ULL;SignalDelivery frame(runtime,Executable,normal,{reinterpret_cast<addr_t>(stack.data()),state.gpr.sp.qword});delivery=&frame;runtime.Run(state,Symbol("guest_nanosleep"));delivery=nullptr;Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&state.gpr.x19.qword==0x123456789abcdef0ULL,"NDK return SP/PC/callee register");return int32_t(state.gpr.x0.dword);}
 int Run(const Time*request,Time*remaining,int mode,int*error){return Run(reinterpret_cast<addr_t>(request),reinterpret_cast<addr_t>(remaining),mode,error);}
 std::thread Send(){return std::thread([this]{std::this_thread::sleep_for(std::chrono::milliseconds(10));Check(!model.Queue(1,10),"actual SignalHost signal queued");});}
};
struct Pages {
 uint8_t*base=nullptr;size_t page=4096;
 Pages(){
#ifdef _WIN32
  SYSTEM_INFO info{};GetSystemInfo(&info);page=info.dwPageSize;base=static_cast<uint8_t*>(VirtualAlloc(nullptr,page*2,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
#else
  base=static_cast<uint8_t*>(mmap(nullptr,page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));if(base==MAP_FAILED)base=nullptr;
#endif
  Check(base!=nullptr,"actual fault-test pages");
 }
 void Protect(bool read_only){
#ifdef _WIN32
  DWORD old=0;Check(VirtualProtect(base+page,page,read_only?PAGE_READONLY:PAGE_NOACCESS,&old)!=0,"real Windows read-only or guard buffer");
#else
  Check(!mprotect(base+page,page,read_only?PROT_READ:PROT_NONE),"real Linux read-only or guard buffer");
#endif
 }
 ~Pages(){
#ifdef _WIN32
  VirtualFree(base,0,MEM_RELEASE);
#else
  munmap(base,page*2);
#endif
 }
};
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
 Harness h;
 if(argc>1){if(!std::strcmp(argv[1],"excluded"))h.policy=[](uint64_t){return uint64_t(0);};else h.policy=[](uint64_t)->uint64_t{throw 17;};Check(!h.model.Queue(1,10),"negative real pending");Time request{0,20000000};int error=0;h.Run(&request,nullptr,0,&error);return 2;}
 unsigned records=0;
 for(int mode=0;mode<2;++mode){
  const Time durations[]={{0,0},{0,1},{0,1000},{0,2000000},{1,1}};
  for(unsigned i=0;i<std::size(durations);++i){Time rem{77,88};int error=0;h.Reset();const auto start=Now();auto result=h.Run(&durations[i],&rem,mode,&error);const auto elapsed=Now()-start;Check(!result&&error==731&&!h.delivered&&elapsed>=uint64_t(durations[i].seconds)*1000000000+durations[i].nanoseconds&&rem.seconds==77&&rem.nanoseconds==88,"normal elapsed lower bound/success errno/rem untouched");Check(h.observations==1&&h.last.copied&&h.last.request==reinterpret_cast<addr_t>(&durations[i])&&h.last.remaining==reinterpret_cast<addr_t>(&rem)&&h.last.seconds==durations[i].seconds&&h.last.nanoseconds==durations[i].nanoseconds,"one exact immutable request observation");std::printf("record normal mode=%d case=%u return=0 errno=731\n",mode,i);++records;}
  const Time invalid[]={{-1,0},{0,-1},{0,1000000000}};
  for(unsigned i=0;i<3;++i){Time rem{77,88};int error=0;h.Reset();Check(h.Run(&invalid[i],&rem,mode,&error)==-1&&error==22&&rem.seconds==77&&rem.nanoseconds==88&&!h.delivered&&h.observations==1&&h.last.copied,"invalid signed LP64 timespec returns EINVAL without output mutation");std::printf("record invalid mode=%d case=%u return=-1 errno=22\n",mode,i);++records;}
  for(unsigned i=0;i<2;++i){int error=0;h.Reset();Check(h.Run(addr_t(i),0,mode,&error)==-1&&error==14&&h.observations==1&&!h.last.copied&&!h.delivered,"null/unmapped request fault safe EFAULT and observed failed copy");std::printf("record fault mode=%d case=%u return=-1 errno=14\n",mode,i);++records;}
  for(int kind=0;kind<5;++kind){h.Action(kind==1?0x10000000:0);Time request{0,200000000},rem{77,88};if(kind==2)request.seconds=INT64_MAX;auto output=kind==2?addr_t(0):kind==3?addr_t(1):reinterpret_cast<addr_t>(kind==4?&request:&rem);h.Reset(kind==2||kind==3?0:output,kind==4);int error=0;auto sender=h.Send();const auto start=Now();const int result=h.Run(reinterpret_cast<addr_t>(&request),output,mode,&error);const auto elapsed=Now()-start;sender.join();const int expected=kind==3?14:4;Check(result==-1&&error==expected&&h.delivered==1&&Read<uint32_t>(h.counter)==1,"actual translated caught handler interrupts even SA_RESTART; bad rem EFAULT still dispatches handler");if(output&&kind!=3){auto value=Read<Time>(output);Check(value.seconds==0&&value.nanoseconds>0&&value.nanoseconds<200000000&&Read<int64_t>(h.seen_seconds)==value.seconds&&Read<int64_t>(h.seen_nanos)==value.nanoseconds,"remainder copied before actual handler and input/output alias supported");if(kind==4)Check(elapsed>=60000000&&uint64_t(value.nanoseconds)+elapsed>220000000,"handler delay does not subtract from prehandler remainder");}std::printf("record interrupt mode=%d kind=%d return=-1 errno=%d handlers=positive\n",mode,kind,expected);++records;}
 }
 int error=0;Time request{0,2000000};
 // Native unaligned copy, snapshot immutability and unused bad output pointer.
 std::array<uint8_t,24>unaligned{};std::memcpy(unaligned.data()+1,&request,sizeof(request));h.Reset();auto start=Now();Check(!h.Run(reinterpret_cast<addr_t>(unaligned.data()+1),1,1,&error)&&error==731&&Now()-start>=2000000,"unaligned request and invalid unused rem accepted on normal completion");
 request={0,20000000};h.Reset();h.observer=[&](const auto&info){Check(info.copied&&info.nanoseconds==20000000,"observer sees original snapshot before caller storage changes");Write(reinterpret_cast<addr_t>(&request),Time{0,0});};start=Now();Check(!h.Run(&request,nullptr,0,&error)&&Now()-start>=20000000,"request is not reread after observer/caller mutation");h.observer={};
 Pages pages;pages.Protect(false);h.Reset();Check(h.Run(reinterpret_cast<addr_t>(pages.base+pages.page-8),0,0,&error)==-1&&error==14&&!h.last.copied,"cross-page partial request snapshot rejected safely");
 for(bool readonly:{false,true}){if(readonly)pages.Protect(true);request={0,200000000};h.Reset();auto sender=h.Send();Check(h.Run(reinterpret_cast<addr_t>(&request),reinterpret_cast<addr_t>(pages.base+pages.page),1,&error)==-1&&error==14&&h.delivered==1,"guard/read-only remainder EFAULT still delivers actual handler");sender.join();}
 // Blocked, ignored and spurious wakeups never shorten the fixed budget.
 uint64_t mask=SignalHost::Bit(10);Check(!h.model.Mask(1,0,&mask,nullptr),"actual mask blocks signal");request={0,20000000};h.Reset();auto blocked=h.Send();start=Now();Check(!h.Run(&request,nullptr,0,&error)&&Now()-start>=20000000&&error==731&&!h.delivered,"blocked signal stays pending during complete delay");blocked.join();uint64_t pending=0;Check(!h.model.Pending(1,&pending)&&(pending&mask),"blocked original pending retained");h.Action(0,1);Check(!h.model.Mask(1,1,&mask,nullptr),"unblock after ignored disposition clears queue");h.Reset();auto ignored=h.Send();start=Now();Check(!h.Run(&request,nullptr,1,&error)&&Now()-start>=20000000&&error==731&&!h.delivered,"ignored signal doesn't interrupt");ignored.join();h.Action(0);
 h.Reset();std::thread spurious([&]{for(unsigned i=0;i<12;++i){h.model.Wake(1)->Notify();std::this_thread::sleep_for(std::chrono::milliseconds(1));}});start=Now();Check(!h.Run(&request,nullptr,1,&error)&&Now()-start>=20000000&&error==731&&!h.delivered,"spurious wakes don't restart or shorten original deadline");spurious.join();
 // A mixed excluded arrival is rejected atomically before either real signal.
 AndroidSignalAction other{};other.handler=h.handler;Check(!h.model.Action(12,&other,nullptr),"other real disposition");SignalHost::Info first{},second{};first[20]=0x51;second[20]=0x7f;Check(!h.model.Queue(1,10,&first),"allowed original signal queued");std::promise<void>inside,queued;auto entered=inside.get_future(),done=queued.get_future();std::thread racer([&]{entered.wait();Check(!h.model.Queue(1,12,&second),"excluded arrival inside policy decision");queued.set_value();});h.policy=[&](uint64_t){inside.set_value();done.wait();return SignalHost::Bit(10);};h.Reset();bool excluded=false;try{h.sleeps.NanoSleep(reinterpret_cast<addr_t>(&request),0);}catch(const std::runtime_error&e){excluded=std::strstr(e.what(),"outside admitted")!=nullptr;}racer.join();Check(excluded&&!h.delivered&&SignalHost::NeedsPoll(h.model.Lookup(1)),"mixed excluded pending rejected before any delivery");for(int signal:{10,12}){auto result=h.model.DispatchOneAllowed(1,SignalHost::Bit(signal),[&](const auto&info)->std::optional<uint64_t>{Check(info.info[20]==(signal==10?0x51:0x7f),"both excluded/allowed siginfo bytes retained");return{};});Check(!result.error&&result.handled,"retained signal inspected explicitly");}
 h.policy=[](uint64_t){return uint64_t(0);};errno=78;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
#ifdef _WIN32
 SetLastError(0x12345678);
#endif
 Check(!h.sleeps.NanoSleep(reinterpret_cast<addr_t>(&request),0)&&errno==78&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"native errno/fenv preserved after normal fixed-budget wait");
#ifdef _WIN32
 Check(GetLastError()==0x12345678,"native LastError preserved after normal wait");
#endif
 h.policy=[](uint64_t)->uint64_t{errno=999;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);throw std::runtime_error("TEST policy");};errno=78;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
#ifdef _WIN32
 SetLastError(0x12345678);
#endif
 try{h.sleeps.NanoSleep(reinterpret_cast<addr_t>(&request),0);}catch(const std::runtime_error&){}Check(errno==78&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"native errno/fenv preserved through exception");
#ifdef _WIN32
 Check(GetLastError()==0x12345678,"native LastError preserved through exception");
#endif
 std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);h.policy=[](uint64_t){return uint64_t(0);};
 std::thread foreign([&]{bool denied=false;try{h.sleeps.NanoSleep(reinterpret_cast<addr_t>(&request),0);}catch(const std::runtime_error&e){denied=std::strstr(e.what(),"foreign")!=nullptr;}Check(denied,"foreign native owner rejected");});foreign.join();Check(!h.model.DropThread(1),"actual lifetime retired");bool stale=false;try{h.sleeps.NanoSleep(reinterpret_cast<addr_t>(&request),0);}catch(const std::runtime_error&){stale=true;}Check(stale,"retired signal lifetime rejected");
 std::printf("NANOSLEEP-HOST-SUCCESS records=%u checks=%u actual-NDK/SignalDelivery/remainder/faults/active-monotonic\n",records,checks.load());
}
