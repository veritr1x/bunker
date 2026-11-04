#include <cfenv>
#include "signal_nanosleep.h"
#include "../whole/bridge.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#include <sys/uio.h>
#include <unistd.h>
#endif
namespace bunker::windows {
namespace {
struct Timespec {int64_t seconds,nanoseconds;};
static_assert(sizeof(Timespec)==16&&alignof(Timespec)==8&&offsetof(Timespec,nanoseconds)==8);
constexpr uint64_t kUserLimit=UINT64_C(1)<<48,kUntagMask=UINT64_C(0x00ffffffffffffff);
struct Environment {
 int error=errno;fenv_t environment{};bool handled=false;
#ifdef _WIN32
 DWORD last_error=GetLastError();
#endif
 Environment(){std::fegetenv(&environment);}
 ~Environment(){std::fesetenv(&environment);
  if(handled)if(auto*s=recomp::CurrentExecutionState()){const int modes[]={FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO};std::fesetround(modes[s->fpcr.rmode]);}
  errno=error;
#ifdef _WIN32
  SetLastError(last_error);
#endif
 }
};
int RangeError(addr_t address){
 const auto low=address&kUntagMask;
 if(!address||low>=kUserLimit||sizeof(Timespec)>kUserLimit-low)return 14;
 if(address!=low)throw std::runtime_error("unsupported nanosleep tagged-address ABI profile");
 return 0;
}
bool ReadRequest(addr_t address,Timespec&value){
 bool okay=false;uint64_t unsupported=0;
 recomp::WithGuestMemoryRead([&]{
#ifdef _WIN32
  SIZE_T bytes=0;const auto success=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),&value,sizeof(value),&bytes);
  if(success&&bytes==sizeof(value)){okay=true;return;}
  const auto error=GetLastError();
  if(error==ERROR_PARTIAL_COPY||error==ERROR_NOACCESS||error==ERROR_INVALID_ADDRESS)return;
  unsupported=error?error:UINT64_MAX;
#else
  iovec local{&value,sizeof(value)},remote{reinterpret_cast<void*>(address),sizeof(value)};
  const auto bytes=process_vm_readv(getpid(),&local,1,&remote,1,0);
  if(bytes==ssize_t(sizeof(value))){okay=true;return;}
  if(bytes>=0||errno==EFAULT)return;
  unsupported=errno?uint64_t(errno):UINT64_MAX;
#endif
 });
 if(unsupported)throw std::runtime_error("unsupported nanosleep fault-safe read API failure "+std::to_string(unsupported));
 return okay;
}
bool WriteRemaining(addr_t address,const Timespec&value){
 if(RangeError(address))return false;
 bool okay=false;uint64_t unsupported=0;
 recomp::WithGuestMemoryWrite(address,sizeof(value),[&]{
#ifdef _WIN32
  // Require writable pages before using the debugger-safe copy API. A read-only
  // guest buffer is an EFAULT, not permission to temporarily change protection.
  auto cursor=address;const auto end=address+sizeof(value);
  while(cursor<end){MEMORY_BASIC_INFORMATION region{};
   if(!VirtualQuery(reinterpret_cast<const void*>(cursor),&region,sizeof(region))||region.State!=MEM_COMMIT||(region.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return;
   const auto protection=region.Protect&0xff;
   if(protection!=PAGE_READWRITE&&protection!=PAGE_WRITECOPY&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return;
   const auto high=reinterpret_cast<addr_t>(region.BaseAddress)+region.RegionSize;
   if(high<=cursor)return;
   cursor=high<end?high:end;
  }
  SIZE_T bytes=0;const auto success=WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),&value,sizeof(value),&bytes);
  if(success&&bytes==sizeof(value)){okay=true;return;}
  const auto error=GetLastError();
  if(error==ERROR_PARTIAL_COPY||error==ERROR_NOACCESS||error==ERROR_INVALID_ADDRESS)return;
  unsupported=error?error:UINT64_MAX;
#else
  iovec local{const_cast<Timespec*>(&value),sizeof(value)},remote{reinterpret_cast<void*>(address),sizeof(value)};
  const auto bytes=process_vm_writev(getpid(),&local,1,&remote,1,0);
  if(bytes==ssize_t(sizeof(value))){okay=true;return;}
  if(bytes>=0||errno==EFAULT)return;
  unsupported=errno?uint64_t(errno):UINT64_MAX;
#endif
 });
 if(unsupported)throw std::runtime_error("unsupported nanosleep fault-safe write API failure "+std::to_string(unsupported));
 return okay;
}
uint64_t ActiveNanoseconds(){
#ifdef _WIN32
 using Query=VOID(WINAPI*)(PULONGLONG);
 static const auto query=[] {
  auto address=GetProcAddress(GetModuleHandleW(L"kernelbase.dll"),"QueryUnbiasedInterruptTimePrecise");
  Query function=nullptr;static_assert(sizeof(function)==sizeof(address));std::memcpy(&function,&address,sizeof(function));return function;
 }();
 if(!query)throw std::runtime_error("unsupported nanosleep: Windows10 precise active-monotonic clock is unavailable");
 ULONGLONG ticks=0;query(&ticks);
 if(ticks>UINT64_MAX/100)throw std::overflow_error("nanosleep active-monotonic clock overflow");
 return uint64_t(ticks)*100;
#else
 timespec now{};if(clock_gettime(CLOCK_MONOTONIC,&now))throw std::runtime_error("nanosleep native CLOCK_MONOTONIC failed");
 if(now.tv_sec<0||now.tv_nsec<0||now.tv_nsec>=1000000000||uint64_t(now.tv_sec)>UINT64_MAX/1000000000)throw std::overflow_error("nanosleep monotonic clock range");
 const auto whole=uint64_t(now.tv_sec)*1000000000;
 if(whole>UINT64_MAX-uint64_t(now.tv_nsec))throw std::overflow_error("nanosleep monotonic clock sum overflow");
 return whole+uint64_t(now.tv_nsec);
#endif
}
constexpr uint64_t DurationBits(int64_t seconds,int64_t nanos){
 constexpr auto maximum=uint64_t(INT64_MAX),scale=UINT64_C(1000000000);
 // Android time64.h timespec64_to_ns clamps at KTIME_SEC_MAX itself.
 return uint64_t(seconds)>=maximum/scale?maximum:uint64_t(seconds)*scale+uint64_t(nanos);
}
static_assert(DurationBits(9223372035,999999999)==UINT64_C(9223372035999999999));
static_assert(DurationBits(9223372036,0)==uint64_t(INT64_MAX));
static_assert(DurationBits(INT64_MAX,999999999)==uint64_t(INT64_MAX));
uint64_t Deadline(const Timespec&request){
 constexpr auto maximum=uint64_t(INT64_MAX);
 const auto start=ActiveNanoseconds();if(start>maximum)throw std::overflow_error("nanosleep clock outside signed ktime profile");
 const auto duration=DurationBits(request.seconds,request.nanoseconds);
 return duration>maximum-start?maximum:start+duration;
}
}
SignalNanoSleeps::SignalNanoSleeps(SignalHost&s,SignalHost::Current current,SignalHost::Boundary boundary,Admission admission,addr_t marker):signals_(s),current_(std::move(current)),boundary_(std::move(boundary)),admission_(std::move(admission)),marker_base_(marker){
 if(!current_||!boundary_||!admission_||!marker||marker%8)throw std::invalid_argument("nanosleep requires explicit current/boundary/admission and aligned marker");
}
addr_t SignalNanoSleeps::Marker(const std::string&name)const{if(name!="nanosleep")throw std::invalid_argument("unsupported nanosleep import: "+name);return marker_base_;}
int32_t SignalNanoSleeps::NanoSleep(addr_t request,addr_t remaining){
 Environment preserve;auto fail=[&](int error)->int32_t{if(!error_sink_)throw std::runtime_error("nanosleep failure without guest errno sink");error_sink_(error);return -1;};
 Timespec value{};const bool copied=!RangeError(request)&&ReadRequest(request,value);
 if(observer_)observer_({request,remaining,copied,copied?value.seconds:0,copied?value.nanoseconds:0});
 if(!copied)return fail(14);
 if(value.seconds<0||value.nanoseconds<0||value.nanoseconds>=1000000000)return fail(22);
 const auto token=current_();auto retained=signals_.Lookup(token);auto wake=signals_.Wake(token);
 if(!retained||!wake)throw std::runtime_error("unsupported nanosleep without live signal lifetime");
 if(signals_.DispatchOneAllowed(token,0,{}).error)throw std::runtime_error("unsupported nanosleep on unbound or foreign signal owner");
 const auto deadline=Deadline(value);
 for(;;){
  const auto generation=wake->Generation(),allowed=admission_(token);
  bool remainder_fault=false,expired_with_remainder=false;std::exception_ptr copy_failure;
  const auto result=signals_.DispatchOneAdmitted(token,allowed,[&](const SignalHost::Delivery&delivery){
   // The kernel copies relative remainder before returning to the real handler.
   // Snapshot it before a handler that can itself wait or overwrite this buffer.
   if(remaining){
    try{const auto now=ActiveNanoseconds();expired_with_remainder=now>=deadline;
     if(!expired_with_remainder){const auto left=deadline-now;Timespec rest{int64_t(left/1000000000),int64_t(left%1000000000)};remainder_fault=!WriteRemaining(remaining,rest);}
    }catch(...){copy_failure=std::current_exception();}
   }
   return boundary_(delivery); // A failed remainder copy never swallows a signal.
  });
  if(result.error==95)throw std::runtime_error("unsupported nanosleep eligible signal outside admitted provider phase");
  if(result.error)throw std::runtime_error("unsupported nanosleep signal ownership or delivery boundary");
  if(result.handled){preserve.handled=true;if(copy_failure)std::rethrow_exception(copy_failure);if(expired_with_remainder)return 0;return fail(remainder_fault?14:4);}
  const auto now=ActiveNanoseconds();if(now>=deadline)return 0;
  // Keep the same fixed active deadline, but bound each native relative wait.
  // condition_variable may internally add its own differently biased clock;
  // a saturated multi-century budget must not overflow that native addition.
  const auto left=deadline-now;
  wake->WaitRelative(generation,std::chrono::nanoseconds(left>1000000000?1000000000:left));
 }
}
void SignalNanoSleeps::Install(recomp::Runtime&runtime){
 if(installed_||!error_sink_)throw std::logic_error("nanosleep install requires one complete errno-bound provider");
 auto bridge=recomp::MakeBridge<int32_t(addr_t,addr_t)>([this](auto request,auto remaining){return NanoSleep(request,remaining);});
 runtime.AddImport(marker_base_,[bridge](State&s){try{bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"signal nanosleep: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fputs("signal nanosleep: unknown exception\n",stderr);std::fflush(stderr);std::abort();}});installed_=true;
}
}
