#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "libc.h"
#include "libc_wall_time_detail.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <chrono>
#include <vector>
static bunker::windows::LibC *provider;
static thread_local int32_t guest_error;
static void *Resolve(const char *name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);return reinterpret_cast<void*>(provider->Marker(name));}
static int64_t NativeMicroseconds(){FILETIME value{};GetSystemTimePreciseAsFileTime(&value);ULARGE_INTEGER ticks{};ticks.LowPart=value.dwLowDateTime;ticks.HighPart=value.dwHighDateTime;return static_cast<int64_t>((static_cast<__int128>(ticks.QuadPart)-INT64_C(116444736000000000))/10);}
int main(){try{
 std::atomic<unsigned> checks{0};auto Check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
 bunker::windows::LibC libc;provider=&libc;libc.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&e,4);});recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(0x7ffc00000000ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});elf_image image{};
 Check(!elf_load(WALL_LIBRARY,0x58000000,Resolve,&image),"actual NDK timeval fixture loads");
 Check(libc.Marker("gettimeofday")==libc.Marker("sysconf")+8,"wall-time marker is append-only");
 const uint64_t cases[]={0,1,9,10,9999999,10000000,UINT32_MAX,UINT64_C(116444736000000000)-10000001,UINT64_C(116444736000000000)-1,UINT64_C(116444736000000000),UINT64_C(116444736000000001),UINT64_C(116444736009999999),UINT64_C(1)<<63,UINT64_MAX};
 for(auto ticks:cases){__int128 delta=static_cast<__int128>(ticks)-INT64_C(116444736000000000);auto seconds=delta/10000000,remainder=delta%10000000;if(remainder<0){--seconds;remainder+=10000000;}const auto value=bunker::windows::libc_detail::UnixTimeval(ticks);Check(value.seconds==seconds&&value.microseconds==remainder/10,"FILETIME epoch/subsecond conversion handles full unsigned range and dates before1970");}
 struct Guard{uint64_t before=0x1122334455667788ULL;bunker::windows::libc_detail::Timeval value{};uint64_t after=0x8877665544332211ULL;};
 auto Run=[&](Guard &out,int indirect){alignas(16)std::array<uint8_t,65536> stack{};State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(&out.value);state.gpr.x1.dword=indirect;state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;
  runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_wall_time")));Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK time call preserves PC/SP");Check(state.gpr.x0.qword==(uint64_t(123)<<32)&&guest_error==123,"successful real time query preserves actual guest errno");
  Check(out.before==0x1122334455667788ULL&&out.after==0x8877665544332211ULL&&out.value.microseconds>=0&&out.value.microseconds<1000000,"16-byte Android timeval publication and canaries");};
 for(int indirect=0;indirect<2;++indirect)for(unsigned n=0;n<32;++n){Guard out;auto before=NativeMicroseconds();Run(out,indirect);auto after=NativeMicroseconds();auto value=out.value.seconds*1000000+out.value.microseconds;Check(value>=before&&value<=after,"actual Android time value is bracketed by independent native UTC samples");}
 Guard prior,next;Run(prior,0);std::this_thread::sleep_for(std::chrono::milliseconds(30));Run(next,1);Check(next.value.seconds*1000000+next.value.microseconds>prior.value.seconds*1000000+prior.value.microseconds,"real wall clock progresses");
 Guard tracked;auto changed=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked.value),8,[&]{libc.GetTimeOfDay(reinterpret_cast<addr_t>(&tracked.value),0);});Check(changed.status==1,"same-value seconds still publish through tracked writes");
 for(auto shape:{std::pair<addr_t,addr_t>{0,0},{reinterpret_cast<addr_t>(&tracked.value),1}}){bool rejected=false;try{libc.GetTimeOfDay(shape.first,shape.second);}catch(const std::runtime_error&){rejected=true;}Check(rejected,"unimplemented optional output/timezone shapes fail explicitly");}
 std::vector<std::thread> threads;std::atomic<unsigned> failures{0};for(unsigned n=0;n<4;++n)threads.emplace_back([&,n]{try{for(unsigned i=0;i<16;++i){Guard out;Run(out,(n+i)%2);}}catch(...){++failures;}});for(auto &thread:threads)thread.join();Check(!failures,"concurrent queries retain independent guest errno and output");
 std::printf("Windows gettimeofday: %u checks passed; 130 actual NDK calls, real UTC microseconds, signed64 epoch conversion, guards/errno/tracked output/threads\n",checks.load());return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"gettimeofday gate failed: %s\n",e.what());return 1;}}
