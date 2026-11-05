#include "pthread_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <time.h>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <limits>
#include <stdexcept>
static_assert(sizeof(State)==1200 && alignof(State)==16,"qualified State ABI");
using bunker::windows::Pthreads;
using bunker::windows::AndroidTimespec;
static Pthreads *provider;
static addr_t clock_marker=0;
static unsigned checks=0,calls=0;
static int guest_errno=0,sink_calls=0;
static void Check(bool v,const char *why){if(!v)throw std::runtime_error(why);++checks;}
static void *Resolve(const char *name){return reinterpret_cast<void*>(provider->Marker(name));}
// Test-only linker interposition: wrap the genuine registered callback, not Runtime dispatch scaffolding.
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime *runtime,addr_t marker,std::function<void(State&)> callback) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime *runtime,addr_t marker,std::function<void(State&)> callback){
 if(marker==clock_marker){
  auto original=std::move(callback);
  callback=[original=std::move(original)](State &state){
   std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);const int flags=std::fetestexcept(FE_ALL_EXCEPT);
   errno=EDOM;SetLastError(0x4bc0de01);original(state);
   Check(errno==EDOM,"actual callback preserves native errno");Check(GetLastError()==0x4bc0de01,"actual callback preserves native LastError");Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"actual callback preserves native floating environment");
  };
 }
 RealAddImport(runtime,marker,std::move(callback));
}
int main(){try{
 recomp::Runtime runtime;Pthreads host(runtime,[](addr_t entry){for(const auto&t:kTraces)if(t.address==entry)return true;return false;});provider=&host;
 host.SetErrorSink([](int e){guest_errno=e;++sink_calls;});clock_marker=host.Marker("clock_getres");host.Install();host.Self();runtime.AddTraces(kTraces,std::size(kTraces));
 elf_image image{};Check(!elf_load(PTHREAD_CLOCK_LIBRARY,0x78000000,Resolve,&image),"load frozen NDK clock caller");
 addr_t entries[]={reinterpret_cast<addr_t>(elf_symbol(&image,"pthread_clock_direct")),reinterpret_cast<addr_t>(elf_symbol(&image,"pthread_clock_indirect"))};Check(entries[0]&&entries[1],"real NDK direct and pointer exports");
 auto invoke=[&](unsigned mode,int id,addr_t output,int expected_error){
  guest_errno=12345;sink_calls=0;
  const auto result=static_cast<int32_t>(host.Run(entries[mode],{static_cast<uint64_t>(static_cast<int64_t>(id)),output}));++calls;
  Check(result==(expected_error?-1:0),"actual NDK return code");Check(guest_errno==(expected_error?expected_error:12345)&&sink_calls==(expected_error?1:0),"guest errno sink exactly once only on failure");return result;
 };
 SYSTEM_INFO info{};GetSystemInfo(&info);const size_t page=info.dwPageSize;auto *memory=static_cast<unsigned char*>(VirtualAlloc(nullptr,page*3,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(memory!=nullptr,"three real writable pages");
 for(unsigned mode=0;mode<2;++mode)for(int id=0;id<2;++id){
  timespec native{};Check(!::clock_getres(id,&native),"independent native Winpthreads resolution");AndroidTimespec expected{static_cast<int64_t>(native.tv_sec),static_cast<int64_t>(native.tv_nsec)};
  Check(expected.seconds>=0&&expected.nanoseconds>=0&&expected.nanoseconds<1000000000&&(expected.seconds||expected.nanoseconds),"native positive normalized resolution");
  for(size_t offset:std::array<size_t,4>{32,33,page-16,page-7}){
   std::memset(memory,0xa7,page*3);invoke(mode,id,reinterpret_cast<addr_t>(memory+offset),0);AndroidTimespec got{};std::memcpy(&got,memory+offset,16);Check(!std::memcmp(&got,&expected,16),"exact native resolution to Android16 output");
   bool intact=true;for(size_t n=0;n<page*3;++n)if((n<offset||n>=offset+16)&&memory[n]!=0xa7)intact=false;Check(intact,"exact16-byte output canaries including unaligned and page edges");
  }
  invoke(mode,id,0,0);
 }
 for(unsigned mode=0;mode<2;++mode){
  for(int id:std::array<int,5>{-1,2,7,std::numeric_limits<int>::min(),std::numeric_limits<int>::max()}){
   std::memset(memory,0x71,page*3);invoke(mode,id,reinterpret_cast<addr_t>(memory),22);Check(memory[0]==0x71&&memory[15]==0x71,"unsupported clock leaves output unchanged");invoke(mode,id,0,22);invoke(mode,id,1,22);
  }
  invoke(mode,1,1,14);invoke(mode,1,std::numeric_limits<addr_t>::max()-7,14);
  for(DWORD protection:std::array<DWORD,3>{PAGE_READONLY,PAGE_NOACCESS,PAGE_READWRITE|PAGE_GUARD}){
   std::memset(memory,0x6b,page*3);DWORD old=0;Check(VirtualProtect(memory+page,page,protection,&old)!=0,"set actual protected page");
   invoke(mode,1,reinterpret_cast<addr_t>(memory+page),14);invoke(mode,1,reinterpret_cast<addr_t>(memory+page-8),14);
   MEMORY_BASIC_INFORMATION region{};Check(VirtualQuery(memory+page,&region,sizeof(region))&&region.Protect==protection,"fault preflight leaves guard/protection unchanged");
   Check(VirtualProtect(memory+page,page,PAGE_READWRITE,&old)!=0,"restore protected page");bool intact=true;for(size_t n=0;n<page*3;++n)if(memory[n]!=0x6b)intact=false;Check(intact,"fault path has no partial output publication");
  }
 }
 Check(VirtualFree(memory,0,MEM_RELEASE)!=0,"release fixture pages");Check(host.ReleaseCurrent()==0,"release actual provider owner");
 std::printf("PTHREAD-CLOCK-PASS checks=%u ndk_calls=%u APIs=1 native_ids=2\n",checks,calls);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"pthread clock fixture: %s\n",e.what());return 1;}}
