#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif
namespace {
std::atomic<unsigned> checks{0},calls{0};
bunker::windows::LibC *provider;
thread_local int32_t guest_errno;
void Check(bool value,const char *why){if(!value){std::fprintf(stderr,"PID check failed: %s\n",why);std::abort();}++checks;}
void *Resolve(const char *name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);return reinterpret_cast<void*>(provider->Marker(name));}
uint64_t NativePid(){
#ifdef _WIN32
 return GetCurrentProcessId();
#else
 return static_cast<uint64_t>(::getpid());
#endif
}
struct Result {int32_t first,second,error,reserved;int64_t widened;};
struct Guard {uint64_t before=UINT64_C(0x123456789abcdef0);Result result{0,0,0,0x6543210,0};uint64_t after=UINT64_C(0xfedcba9876543210);};
}
int main(){
 const auto native=NativePid();Check(native>0&&native<=uint64_t(INT32_MAX),"real native PID fits Android pid_t");
 const auto expected=static_cast<int32_t>(native);
 bunker::windows::LibC libc;provider=&libc;
 libc.SetErrorSink([](int error){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_errno),&error,sizeof(error));});
 recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(0x7ffc00000000ULL,[](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno);});
 elf_image image{};Check(!elf_load(PID_LIBRARY,0x59000000,Resolve,&image),"actual NDK PID fixture loads");
 Check(libc.Marker("getpid")==libc.Marker("gettimeofday")+8,"PID marker appends after wall-time provider");
 errno=137;Check(libc.ProcessId()==static_cast<int32_t>(native)&&errno==137,"native PID adapter preserves native errno");
 auto Run=[&](int indirect,int sentinel){
  Guard out;alignas(16)std::array<uint8_t,65536> stack{};State s{};
  s.gpr.x0.qword=reinterpret_cast<addr_t>(&out.result);s.gpr.x1.dword=indirect;s.gpr.x2.dword=sentinel;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
  s.gpr.x19.qword=UINT64_C(0xf0123456789abcde);s.gpr.x29.qword=UINT64_C(0xe0123456789abcdf);
  runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_pid")));calls+=2;
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK call preserves PC/SP");
  Check(s.gpr.x19.qword==UINT64_C(0xf0123456789abcde)&&s.gpr.x29.qword==UINT64_C(0xe0123456789abcdf),"NDK call preserves callee registers");
  Check(s.gpr.x0.qword==native&&out.result.first==expected&&out.result.second==expected&&out.result.widened==static_cast<int64_t>(native),"direct/indirect signed32 PID and sign-extension match independent native PID");
  Check(out.result.error==sentinel&&guest_errno==sentinel,"successful PID calls preserve actual guest errno");
  Check(out.before==UINT64_C(0x123456789abcdef0)&&out.after==UINT64_C(0xfedcba9876543210)&&out.result.reserved==0x6543210,"guest result canaries and padding preserved");
 };
 for(int indirect=0;indirect<2;++indirect)for(int i=0;i<16;++i)Run(indirect,100+i);
 std::vector<std::thread> threads;
 for(int n=0;n<4;++n)threads.emplace_back([&,n]{for(int i=0;i<16;++i)Run((n+i)%2,200+n);Check(libc.ProcessId()==expected,"all real native threads observe the process PID");});
 for(auto &thread:threads)thread.join();
 alignas(16)std::array<uint8_t,65536> stack{};State s{};s.gpr.x0.qword=UINT64_MAX;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
 runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_pid_return")));++calls;
 Check(s.gpr.x0.dword==native&&s.gpr.pc.qword==0xfeedffff,"actual NDK pid_t return consumes the signed32 result");
 Check(NativePid()==native,"independent native PID remains stable throughout test");
 std::printf("PID provider: %u checks passed; %u actual NDK getpid calls, direct/indirect/native comparison, signed32 ABI, guards/errno/threads\n",checks.load(),calls.load());
}
