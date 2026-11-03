#include <cfenv>
#include "signal_sleep.h"
#include "../whole/bridge.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif
namespace bunker::windows {
namespace {
uint64_t ActiveNanoseconds(){
#ifdef _WIN32
 // Unlike biased interrupt time/QPC, this budget excludes sleep/hibernation.
 using Query=VOID(WINAPI*)(PULONGLONG);
 static const auto query=[] {
  // Microsoft's API metadata includes KernelBase; current Windows exports
  // this precise query there without a Kernel32 forwarding export.
  auto address=GetProcAddress(GetModuleHandleW(L"kernelbase.dll"),"QueryUnbiasedInterruptTimePrecise");
  Query function=nullptr;static_assert(sizeof(function)==sizeof(address));
  std::memcpy(&function,&address,sizeof(function));return function;
 }();
 if(!query)throw std::runtime_error("unsupported usleep: Windows10 precise active-monotonic clock is unavailable");
 ULONGLONG ticks=0;query(&ticks);
 if(ticks>UINT64_MAX/100)throw std::overflow_error("usleep active-monotonic clock overflow");
 return uint64_t(ticks)*100;
#else
 timespec now{};if(clock_gettime(CLOCK_MONOTONIC,&now))throw std::runtime_error("usleep native CLOCK_MONOTONIC failed");
 if(now.tv_sec<0||now.tv_nsec<0||now.tv_nsec>=1000000000||uint64_t(now.tv_sec)>UINT64_MAX/1000000000)throw std::overflow_error("usleep monotonic clock range");
 const auto whole=uint64_t(now.tv_sec)*1000000000;
 if(whole>UINT64_MAX-uint64_t(now.tv_nsec))throw std::overflow_error("usleep monotonic clock sum overflow");
 return whole+uint64_t(now.tv_nsec);
#endif
}
struct Environment {
 int error=errno;fenv_t environment{};bool handled=false;
#ifdef _WIN32
 DWORD last_error=GetLastError();
#endif
 Environment(){std::fegetenv(&environment);}
 ~Environment(){std::fesetenv(&environment);
  // Match the established poll scope: real signal context edits remain in
  // State; reapply the current guest rounding mode after restoring host flags.
  if(handled)if(auto*s=recomp::CurrentExecutionState()){const int modes[]={FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO};std::fesetround(modes[s->fpcr.rmode]);}
  errno=error;
#ifdef _WIN32
  SetLastError(last_error);
#endif
 }
};
}
SignalSleeps::SignalSleeps(SignalHost&s,SignalHost::Current c,SignalHost::Boundary b,Admission a,addr_t marker):signals_(s),current_(std::move(c)),boundary_(std::move(b)),admission_(std::move(a)),marker_base_(marker){
 if(!current_||!admission_||marker%8)throw std::invalid_argument("usleep needs explicit current/admission and aligned marker");
}
addr_t SignalSleeps::Marker(const std::string&name)const{if(name!="usleep")throw std::invalid_argument("unsupported sleep import: "+name);return marker_base_;}
int32_t SignalSleeps::USleep(uint32_t microseconds){
 Environment preserve;const auto token=current_();auto retained=signals_.Lookup(token);auto wake=signals_.Wake(token);
 if(!retained||!wake)throw std::runtime_error("unsupported usleep without live signal lifetime");
 // Zero allowed bits validates actual bound-thread ownership without consuming.
 if(signals_.DispatchOneAllowed(token,0,{}).error)throw std::runtime_error("unsupported usleep on unbound or foreign signal owner");
 const uint64_t start=ActiveNanoseconds(),duration=uint64_t(microseconds)*1000;
 if(duration>UINT64_MAX-start)throw std::overflow_error("usleep deadline overflow");
 const auto deadline=start+duration;
 for(;;){
  const auto generation=wake->Generation();const auto allowed=admission_(token);
  const auto result=signals_.DispatchOneAdmitted(token,allowed,boundary_);
  if(result.error==95)throw std::runtime_error("unsupported usleep eligible signal outside admitted provider phase");
  if(result.error)throw std::runtime_error("unsupported usleep signal ownership or delivery boundary");
  if(result.handled){preserve.handled=true;if(!error_sink_)throw std::runtime_error("usleep interrupted without guest errno sink");error_sink_(4);return -1;}
  const auto now=ActiveNanoseconds();if(now>=deadline)return 0;
  // The relative wait may wake spuriously or on any mask/state change. Only
  // the fixed active-monotonic budget decides completion; no rearming drift.
  wake->WaitRelative(generation,std::chrono::nanoseconds(deadline-now));
 }
}
void SignalSleeps::Install(recomp::Runtime&runtime){
 if(installed_||!error_sink_)throw std::logic_error("usleep install requires one complete errno-bound provider");
 auto bridge=recomp::MakeBridge<int32_t(uint32_t)>([this](auto value){return USleep(value);});
 runtime.AddImport(marker_base_,[bridge](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"signal sleep usleep: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fputs("signal sleep usleep: unknown exception\n",stderr);std::fflush(stderr);std::abort();}});installed_=true;
}
}
