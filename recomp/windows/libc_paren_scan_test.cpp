#include "libc.h"
#include "libc_paren_scan_cases.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <iterator>
#include <stdexcept>
#include <thread>
namespace {
static_assert(sizeof(State)==1200&&alignof(State)==16);
static_assert(sizeof(int)==4&&sizeof(ParenScanBuffers)==80);
std::atomic<unsigned>checks{0},calls{0},bridges{0};
thread_local int guest_error=123;
addr_t scanner=0;bunker::windows::LibC*provider=nullptr;
void Check(bool value,const char*why){++checks;if(!value)throw std::runtime_error(why);}
void*Resolve(const char*name){return reinterpret_cast<void*>(provider->Marker(name));}
struct Fixture {
 recomp::Runtime runtime;elf_image image{};addr_t entry=0;
 int64_t Run(const char*input,unsigned profile,int*a,int*b,int*c,unsigned form){
  ++calls;State state{};alignas(16)std::array<unsigned char,65536>stack{};auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());
  state.gpr.x0.qword=reinterpret_cast<addr_t>(input);state.gpr.x1.dword=profile;state.gpr.x2.qword=reinterpret_cast<addr_t>(a);state.gpr.x3.qword=reinterpret_cast<addr_t>(b);state.gpr.x4.qword=reinterpret_cast<addr_t>(c);state.gpr.x5.dword=form;
  state.gpr.sp.qword=top;state.gpr.x30.qword=0xfeedffff;state.gpr.x19.qword=0xf123456789abcdefULL;state.gpr.x29.qword=0xe123456789abcdefULL;
  std::array<unsigned char,16>v;v.fill(0xd9);memcpy(&state.simd.v[31],v.data(),16);reinterpret_cast<unsigned char*>(&state)[1199]=0x6d;auto*memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);
  Check(runtime.Run(state,entry,memory)==memory,"actual NDK Memory64 identity");Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==top&&state.gpr.x19.qword==0xf123456789abcdefULL&&state.gpr.x29.qword==0xe123456789abcdefULL,"actual NDK PC/SP/saved high64 GPRs");Check(!memcmp(v.data(),&state.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&state)[1199]==0x6d,"actual NDK State1200/SIMD128/highcell");
  const auto result=static_cast<int64_t>(state.gpr.x0.qword);Check(result>=-1&&result<=3,"NDK signed int return extends to signed64");return result;
 }
};
}
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*r,addr_t marker,std::function<void(State&)>callback){if(marker==scanner){auto original=std::move(callback);callback=[original=std::move(original)](State&s){++bridges;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x70b5680c);original(s);Check(errno==EDOM&&GetLastError()==0x70b5680c,"actual installed scanner preserves native errno/LastError");Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"actual installed scanner preserves nondefault FENV");};}RealAddImport(r,marker,std::move(callback));}
int main(){try{
 setvbuf(stdout,nullptr,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);bunker::windows::LibC libc;provider=&libc;scanner=libc.Marker("sscanf");libc.SetErrorSink([](int error){guest_error=error;});Fixture fixture;libc.Install(fixture.runtime);fixture.runtime.AddTraces(kTraces,std::size(kTraces));Check(!elf_load(PAREN_SCAN_LIBRARY,0x7d000000,Resolve,&fixture.image),"actual NDK scanner ELF loads");fixture.entry=reinterpret_cast<addr_t>(elf_symbol(&fixture.image,"guest_paren_scan"));Check(fixture.entry!=0,"real variadic direct/pointer helper exists");
 unsigned observations=0;for(unsigned form=0;form<2;++form)for(unsigned n=0;n<PAREN_SCAN_CASE_COUNT;++n){const auto&test=paren_scan_cases[n];ParenScanBuffers out;ParenScanInitialize(&out);guest_error=123;auto result=fixture.Run(test.input,test.format,reinterpret_cast<int*>(out.slots[0]+8),reinterpret_cast<int*>(out.slots[1]+8),reinterpret_cast<int*>(out.slots[2]+8),form);ParenScanRecord(n,form,result,guest_error,&out);observations+=test.implementation_observation;}
 const auto canonical_calls=calls.load();
 for(unsigned form=0;form<2;++form){int value=0;guest_error=177;Check(fixture.Run("HTTP/1.2 345",0,&value,&value,&value,form)==3&&value==345&&guest_error==177,"same int output receives three assignments in conversion order");int a=7,b=9,c=11;Check(fixture.Run("HTTP/x",0,&a,&b,&c,form)==0&&a==7&&b==9&&c==11,"mismatch leaves complete unassigned int objects unchanged");}
 int value=17;
 auto assigned=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&value),4,[&]{Check(libc.Scan("(17)",paren_scan_formats[4],reinterpret_cast<addr_t>(&value),0,0,0)==1,"same value assigned once");});Check(assigned.status==1&&value==17,"same-value int32 publication invalidates actual exclusive reservation");
 auto unassigned=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&value),4,[&]{Check(libc.Scan("(x)",paren_scan_formats[4],reinterpret_cast<addr_t>(&value),0,0,0)==0,"mismatch count zero");});Check(unassigned.status==0&&value==17,"mismatch performs no tracked publication");
 for(const char*format:{"HTTP/%d.%d %d"," HTTP/%i.%d %d"," HTTP/%d.%d %d "," HTTP %4d"," (%u)","(%d)","(%u) "}){bool refused=false;try{libc.Scan("HTTP/1.1 200",format,reinterpret_cast<addr_t>(&value),0,0,0);}catch(const std::runtime_error&e){refused=std::string(e.what()).find("outside the exact qualified profiles")!=std::string::npos;}Check(refused,"unadmitted adjacent format rejected");}
 std::atomic<bool>parallel_ok{true};std::array<std::thread,4>workers;
 for(unsigned thread=0;thread<workers.size();++thread)workers[thread]=std::thread([&,thread]{try{for(unsigned n=0;n<4;++n){int major=0,minor=0,status=0;guest_error=210+thread;auto result=fixture.Run("(-1]",4,&major,&minor,&status,n&1);if(result!=1||uint32_t(major)!=0xffffffffU||minor!=0||status!=0||guest_error!=int(210+thread))parallel_ok=false;}}catch(...){parallel_ok=false;}});
 for(auto&worker:workers){worker.join();}Check(parallel_ok,"concurrent genuine NDK calls retain thread-local guest errno and outputs");Check(calls==bridges&&calls==canonical_calls+20,"each actual NDK entry traverses production installed typed sscanf bridge; all20 additional calls counted");
 printf("PAREN-SCAN-PASS checks=%u canonical_NDK_calls=%u actual_NDK_calls=%u implementation_observation_records=%u formats=5 forms=2 State=1200 Memory64=1\n",checks.load(),canonical_calls,calls.load(),observations);return 0;
}catch(const std::exception&e){fprintf(stderr,"HTTP scanner fixture: %s\n",e.what());return 1;}}
