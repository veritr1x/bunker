#include "libc.h"
#include "libc_process_detail.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <memory>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#include <unistd.h>
#endif

namespace {
std::atomic<unsigned> checks{0};
void Check(bool value,const char *why){if(!value){std::fprintf(stderr,"process clock check failed: %s\n",why);std::exit(1);}++checks;}
bunker::windows::LibC *provider;
thread_local int32_t guest_errno;
void *Resolve(const char *name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);try{return reinterpret_cast<void*>(provider->Marker(name));}catch(...){std::fprintf(stderr,"unknown process fixture import: %s\n",name);return nullptr;}}
int64_t NativeClock(){
#ifdef _WIN32
  FILETIME c{},e{},k{},u{};if(!GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u))throw std::runtime_error("independent GetProcessTimes failed");
  ULARGE_INTEGER kernel{},user{};kernel.LowPart=k.dwLowDateTime;kernel.HighPart=k.dwHighDateTime;user.LowPart=u.dwLowDateTime;user.HighPart=u.dwHighDateTime;
  return static_cast<int64_t>((static_cast<unsigned __int128>(kernel.QuadPart)+user.QuadPart)/10);
#else
  timespec ts{};if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&ts))throw std::runtime_error("independent native process CPU query failed");return int64_t(ts.tv_sec)*1000000+ts.tv_nsec/1000;
#endif
}
void BusyForCpu(int64_t microseconds){
  const auto start=NativeClock(),deadline=start+microseconds;
  const auto wall_deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  volatile uint64_t value=7;
  while(NativeClock()<deadline){for(unsigned i=0;i<100000;++i)value=value*UINT64_C(2862933555777941757)+3037000493;if(std::chrono::steady_clock::now()>=wall_deadline)throw std::runtime_error("CPU progress exceeded watchdog");}
}
}
int main(int argc,char **){
  std::thread([]{std::this_thread::sleep_for(std::chrono::seconds(25));std::fputs("process clock watchdog\n",stderr);std::_Exit(95);}).detach();
  bunker::windows::LibC libc;provider=&libc;recomp::Runtime runtime;libc.Install(runtime);
  libc.SetErrorSink([](int e){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_errno),&e,sizeof(e));});
  runtime.AddImport(0x7ffc00000000ULL,[](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno);});runtime.AddTraces(kTraces,std::size(kTraces));
  elf_image image{};Check(!elf_load(PROCESS_LIBRARY,0x6c000000,Resolve,&image),"actual NDK process/sysconf fixture loads");
  auto run=[&](const char *name,std::initializer_list<addr_t> args){alignas(16) std::array<uint8_t,65536> stack{};State s{};Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3};size_t i=0;for(auto a:args)(s.gpr.*registers[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK process caller preserves PC/SP");return static_cast<int64_t>(s.gpr.x0.qword);};
  if(argc>1){
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
    int32_t observed=0;run("guest_process_sysconf",{6,0,17,reinterpret_cast<addr_t>(&observed)});return 99;
  }
  Check(run("guest_process_contract",{})==1000000,"actual Android CLOCKS_PER_SEC is one million");
  Check(libc.Marker("malloc")==0x7ffb00000000ULL&&libc.Marker("clock")==libc.Marker("uselocale")+8&&libc.Marker("sysconf")==libc.Marker("clock")+8,"new libc markers are append-only");
  const uint64_t values[]={0,1,4,5,9,10,11,9999999,10000000,UINT32_MAX,UINT64_C(1)<<32,UINT64_C(1)<<63,UINT64_MAX};
  for(auto kernel:values)for(auto user:values){const auto expected=static_cast<uint64_t>((static_cast<unsigned __int128>(kernel)+user)/10);Check(bunker::windows::libc_detail::CpuMicroseconds(kernel,user)==static_cast<int64_t>(expected),"100ns conversion handles carries and64-bit extreme sums");}
  unsigned known=0;
#define BUNKER_SYSCONF_NAME(symbol,value) Check(bunker::windows::libc_detail::AndroidSysconfName(value),"pinned known Android sysconf classified");++known;
#include "libc_sysconf_names.inc"
#undef BUNKER_SYSCONF_NAME
  Check(known==148,"all exact Android13 sysconf names classified");
  for(auto name:{INT32_MIN,-1,86,87,88,89,90,91,92,93,94,95,158,INT32_MAX})Check(!bunker::windows::libc_detail::AndroidSysconfName(name),"unassigned Android sysconf names remain invalid");
  for(auto name:{0,6,85,96,98,157}){bool rejected=false;try{libc.Sysconf(name);}catch(const std::runtime_error &e){rejected=std::string(e.what())=="unsupported Android sysconf name: "+std::to_string(name);}Check(rejected,"valid unimplemented sysconf is decisive");}
#ifdef _WIN32
  SYSTEM_INFO info{};GetSystemInfo(&info);const int64_t pagesize=info.dwPageSize,cpus=GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
#else
  const int64_t pagesize=::sysconf(_SC_PAGESIZE),cpus=::sysconf(_SC_NPROCESSORS_ONLN);
#endif
  Check(pagesize>0&&cpus>0,"independent real page size and online CPU count");
  int ndk_calls=1;
  for(int indirect=0;indirect<2;++indirect){
    for(auto name:{39,40,97}){int32_t observed=0;Check(run("guest_process_sysconf",{static_cast<addr_t>(name),static_cast<addr_t>(indirect),123,reinterpret_cast<addr_t>(&observed)})==(name==97?cpus:pagesize)&&observed==123,"NDK query uses real native value and preserves errno");++ndk_calls;}
    for(auto name:{-1,86,95,158,INT32_MIN,INT32_MAX}){int32_t observed=0;Check(run("guest_process_sysconf",{static_cast<uint32_t>(name),static_cast<addr_t>(indirect),123,reinterpret_cast<addr_t>(&observed)})==-1&&observed==22,"NDK invalid name returns signed64 minus1/EINVAL");++ndk_calls;}
    for(int repeat=0;repeat<8;++repeat){guest_errno=51;const auto before=NativeClock(),value=run("guest_process_clock",{static_cast<addr_t>(indirect)}),after=NativeClock();Check(value>=before&&value<=after&&guest_errno==51,"actual NDK clock is bracketed by independent CPU samples");++ndk_calls;}
  }
  auto before=run("guest_process_clock",{0});BusyForCpu(30000);auto after=run("guest_process_clock",{1});const auto busy_ticks=after-before;ndk_calls+=2;Check(busy_ticks>=30000,"CPU busy work advances actual process clock");
  before=run("guest_process_clock",{0});const auto wall=std::chrono::steady_clock::now();std::this_thread::sleep_for(std::chrono::milliseconds(150));after=run("guest_process_clock",{1});const auto sleep_ticks=after-before;ndk_calls+=2;const auto wall_elapsed=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-wall).count();Check(after>=before&&sleep_ticks<wall_elapsed/2,"sleep does not become process CPU time");
  before=run("guest_process_clock",{0});std::thread cpu_worker([]{BusyForCpu(30000);});cpu_worker.join();after=run("guest_process_clock",{1});const auto worker_ticks=after-before;ndk_calls+=2;Check(worker_ticks>=30000,"other native worker CPU contributes to process total");
  std::atomic<bool> go{false};std::atomic<unsigned> ready{0};std::vector<std::thread> workers;
  for(unsigned n=0;n<8;++n)workers.emplace_back([&,n]{guest_errno=100+int32_t(n);++ready;while(!go)std::this_thread::yield();int32_t observed=0;auto value=run("guest_process_sysconf",{97,n%2,static_cast<addr_t>(100+n),reinterpret_cast<addr_t>(&observed)});Check(value==cpus&&observed==int32_t(100+n)&&guest_errno==int32_t(100+n),"simultaneous real CPU queries preserve independent guest errno");auto ticks=run("guest_process_clock",{n%2});Check(ticks>=0&&guest_errno==int32_t(100+n),"simultaneous process CPU clocks preserve thread-local errno");});
  while(ready<8)std::this_thread::yield();
  go=true;
  for(auto &worker:workers)worker.join();
  ndk_calls+=16;
  Check(libc.ProcessClock()>=0&&libc.Sysconf(39)==pagesize&&libc.Sysconf(40)==pagesize&&libc.Sysconf(97)==cpus,"direct provider uses same real process/system values");
  std::printf("Bionic process clock/sysconf: %u checks; %d actual NDK direct/indirect calls; pages=%lld onlineCPUs=%lld; CPU busy/sleep/worker evidence\n",checks.load(),ndk_calls,static_cast<long long>(pagesize),static_cast<long long>(cpus));
  std::printf("Observed process CPU microseconds: busy=%lld sleep=%lld sleep-wall=%lld worker=%lld\n",static_cast<long long>(busy_ticks),static_cast<long long>(sleep_ticks),static_cast<long long>(wall_elapsed),static_cast<long long>(worker_ticks));
}
