#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <stdexcept>
#include <thread>
namespace {
static_assert(sizeof(State)==1200&&alignof(State)==16);
std::atomic<unsigned> checks{0},calls{0};
thread_local int32_t guest_error=0;
thread_local unsigned sink_calls=0;
addr_t yield_marker=0;
bunker::windows::LibC*provider=nullptr;
void Check(bool yes,const char*why){++checks;if(!yes)throw std::runtime_error(why);}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);return reinterpret_cast<void*>(provider->Marker(name));}
}
// Seed at the genuine registered import boundary, after Runtime scaffolding.
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*runtime,addr_t marker,std::function<void(State&)> callback){
 if(marker==yield_marker){auto original=std::move(callback);callback=[original=std::move(original)](State&s){
   std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);const int flags=std::fetestexcept(FE_ALL_EXCEPT);
   errno=EDOM;SetLastError(0x72416001);original(s);
   Check(errno==EDOM,"registered callback restores native errno");Check(GetLastError()==0x72416001,"registered callback restores native LastError");Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"registered callback restores nonzero floating environment");
 };}
 RealAddImport(runtime,marker,std::move(callback));
}
int main(){try{
 recomp::Runtime runtime;bunker::windows::LibC libc;provider=&libc;yield_marker=libc.Marker("sched_yield");
 Check(yield_marker==libc.Marker("difftime")+8,"new yield marker appended after complete old prefix");
 libc.SetErrorSink([](int e){guest_error=e;++sink_calls;});libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(0x7ffc00000000ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
 elf_image image{};Check(!elf_load(YIELD_LIBRARY,0x7a000000,Resolve,&image),"actual NDK caller loaded");const addr_t entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_sched_yield"));Check(entry!=0,"actual NDK export");
 auto exercise=[&](int worker){
  for(int mode=0;mode<2;++mode)for(int n=0;n<8;++n){
   struct Output {uint64_t before=0x1122334455667788ULL;struct {int32_t status=-77,error=-88;int64_t widened=-99;}value;uint64_t after=0x8877665544332211ULL;} output;
   alignas(16)std::array<unsigned char,65536>stack{};State s{};const int sentinel=1000+worker*100+n;guest_error=-777;sink_calls=0;
   s.gpr.x0.dword=mode;s.gpr.x1.dword=sentinel;s.gpr.x2.qword=reinterpret_cast<addr_t>(&output.value);s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
   std::array<unsigned char,16>v;v.fill(0xd9);std::memcpy(&s.simd.v[31],v.data(),16);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;auto*memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);
   Check(runtime.Run(s,entry,memory)==memory,"opaque Memory64 identity");++calls;
   Check(output.value.status==0&&output.value.widened==0&&s.gpr.x0.qword==0,"signed32 yield status and NDK int64 widening");
   Check(output.value.error==sentinel&&guest_error==sentinel&&sink_calls==0&&libc.Error()==0,"success preserves guest errno and never calls failure sink");
   Check(output.before==0x1122334455667788ULL&&output.after==0x8877665544332211ULL,"NDK result canaries");
   Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"guest return PC SP and saved 64-bit registers");
   Check(!std::memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"full1200 State SIMD128/high cell preserved");
  }
 };
 exercise(0);std::exception_ptr errors[2];std::thread workers[2];for(unsigned i=0;i<2;++i)workers[i]=std::thread([&,i]{try{exercise(int(i)+1);}catch(...){errors[i]=std::current_exception();}});for(auto&t:workers)t.join();for(auto&e:errors)if(e)std::rethrow_exception(e);
 Check(calls==48,"main and two genuine worker threads repeated direct/indirect yields");
 std::printf("SCHED-YIELD-PASS checks=%u NDK_calls=%u workers=2 State=1200 Memory64=1\n",checks.load(),calls.load());return 0;
}catch(const std::exception&e){std::fprintf(stderr,"sched_yield: %s\n",e.what());return 1;}}
