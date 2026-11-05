#include "libc.h"
#include "libc_inet_pton_cases.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstring>
#include <iterator>
#include <limits>
#include <stdexcept>
namespace {
static_assert(sizeof(State)==1200&&alignof(State)==16);
unsigned checks=0,calls=0,sink_calls=0;int guest_error=123;addr_t marker=0;bunker::windows::LibC*provider=nullptr;std::function<void(State&)> installed;
void Check(bool yes,const char*why){++checks;if(!yes)throw std::runtime_error(why);}
void*Resolve(const char*name){return reinterpret_cast<void*>(provider->Marker(name));}
}
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*r,addr_t m,std::function<void(State&)>callback){if(m==marker){installed=callback;auto original=std::move(callback);callback=[original=std::move(original)](State&s){std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x70b4b574);original(s);Check(errno==EDOM&&GetLastError()==0x70b4b574,"real callback native errno/LastError");Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"real callback nonzero FENV");};}RealAddImport(r,m,std::move(callback));}
int main(){try{
 std::setvbuf(stdout,nullptr,_IONBF,0);recomp::Runtime runtime;bunker::windows::LibC libc;provider=&libc;marker=libc.Marker("inet_pton");Check(marker==libc.Marker("sched_yield")+8,"only appended marker after old prefix");libc.SetErrorSink([](int e){guest_error=e;++sink_calls;});libc.Install(runtime);Check(bool(installed),"captured genuine installed boundary");runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};Check(!elf_load(INET_LIBRARY,0x7c000000,Resolve,&image),"actual NDK inet caller loaded");auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_inet_pton"));Check(entry!=0,"real NDK export");
 for(unsigned i=0;i<INET_CASE_COUNT;++i)for(unsigned mode=0;mode<2;++mode){InetBytes output;std::memset(&output,0xa5,sizeof(output));guest_error=123;sink_calls=0;State s{};alignas(16)std::array<unsigned char,65536>stack{};s.gpr.x0.qword=uint64_t(int64_t(inet_cases[i].family));s.gpr.x1.qword=reinterpret_cast<addr_t>(inet_cases[i].input);s.gpr.x2.qword=reinterpret_cast<addr_t>(output.bytes+16);s.gpr.x3.dword=mode;s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;std::array<unsigned char,16>v;v.fill(0xd9);std::memcpy(&s.simd.v[31],v.data(),16);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;auto*memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);Check(runtime.Run(s,entry,memory)==memory,"opaque Memory64 identity");++calls;int64_t result=static_cast<int64_t>(s.gpr.x0.qword);Check(result>=-1&&result<=1,"NDK signed32 result int64 widening");Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"NDK PCSP and high64 saved regs");Check(!std::memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200/SIMD128/highcell");Check(sink_calls==(result<0?1u:0u)&&guest_error==(result<0?97:123),"guest EAFNOSUPPORT exactlyonce onlyunsupportedfamily");InetRecord(i,mode,int(result),guest_error,&output);}
 auto direct=[&](int family,const char*input,addr_t output){State s{};s.gpr.x0.qword=uint64_t(int64_t(family));s.gpr.x1.qword=reinterpret_cast<addr_t>(input);s.gpr.x2.qword=output;installed(s);return static_cast<int32_t>(s.gpr.x0.dword);};
 std::array<unsigned char,48>alias;alias.fill(0xa5);std::memcpy(alias.data()+8,"127.0.0.1",10);Check(direct(2,reinterpret_cast<char*>(alias.data()+8),reinterpret_cast<addr_t>(alias.data()+8))==1&&alias[8]==127&&alias[9]==0&&alias[10]==0&&alias[11]==1&&alias[12]=='0',"input-outputalias parsed from snapshot before4bytepublication");
 SYSTEM_INFO info{};GetSystemInfo(&info);const size_t page=info.dwPageSize;auto*pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,page*2,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(pages!=nullptr,"real pages");
 for(int family:{2,10}){const char*input=family==2?"192.0.2.1":"2001:db8::1";size_t size=family==2?4:16;for(size_t offset:{size_t(1),page-size}){std::memset(pages,0xa5,page*2);Check(direct(family,input,reinterpret_cast<addr_t>(pages+offset))==1,"unaligned and exactpageend valid output");Check(pages[offset-1]==0xa5&&pages[offset+size]==0xa5,"exactbinarysize canaries");}
 }
 VirtualFree(pages,0,MEM_RELEASE);std::printf("INET-PTON-PASS checks=%u NDK_calls=%u forms=2 State=1200 Memory64=1 networkRequests=0\n",checks,calls);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"inet_pton fixture: %s\n",e.what());return 1;}}
