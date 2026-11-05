#include "libc.h"
#include "libc_scan_profiles_cases.h"
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
unsigned checks=0,calls=0;int32_t guest_error=123;unsigned sink_calls=0;addr_t scanner=0;bunker::windows::LibC*provider=nullptr;
void Check(bool v,const char*why){++checks;if(!v)throw std::runtime_error(why);}
void*Resolve(const char*name){return reinterpret_cast<void*>(provider->Marker(name));}
}
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*r,addr_t marker,std::function<void(State&)>callback){if(marker==scanner){auto original=std::move(callback);callback=[original=std::move(original)](State&s){std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x704624b4);original(s);Check(errno==EDOM&&GetLastError()==0x704624b4,"actual scanner callback restores native errno/LastError");Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"actual scanner callback restores nonzero FENV");};}RealAddImport(r,marker,std::move(callback));}
int main(){try{
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);std::setvbuf(stdout,nullptr,_IONBF,0);
 recomp::Runtime runtime;bunker::windows::LibC libc;provider=&libc;scanner=libc.Marker("sscanf");libc.SetErrorSink([](int e){guest_error=e;++sink_calls;});libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};Check(!elf_load(SCAN_LIBRARY,0x7b000000,Resolve,&image),"actual NDK scanf caller loaded");auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_scan_profiles"));Check(entry!=0,"actual NDK sixGP caller export");
 for(unsigned n=0;n<SCAN_CASE_COUNT;++n){ScanBuffers out;ScanInitialize(&out);guest_error=123;sink_calls=0;State s{};alignas(16)std::array<unsigned char,65536>stack{};s.gpr.x0.qword=reinterpret_cast<addr_t>(scan_cases[n].input);s.gpr.x1.qword=reinterpret_cast<addr_t>(scan_formats[scan_cases[n].format]);s.gpr.x2.qword=reinterpret_cast<addr_t>(out.bytes[0]+8);s.gpr.x3.qword=reinterpret_cast<addr_t>(out.bytes[1]+8);s.gpr.x4.qword=reinterpret_cast<addr_t>(out.bytes[2]+8);s.gpr.x5.qword=reinterpret_cast<addr_t>(out.bytes[3]+8);s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;std::array<unsigned char,16>v;v.fill(0xd9);std::memcpy(&s.simd.v[31],v.data(),16);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;auto*memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);Check(runtime.Run(s,entry,memory)==memory,"opaque Memory64 identity");++calls;const auto status=static_cast<int64_t>(s.gpr.x0.qword);Check(status>=-1&&status<=4,"NDK signed status widening");Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"NDK PCSP and saved high64");Check(!std::memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200/SIMD128/highcells");Check(sink_calls==(guest_error==123?0:1),"guest errno only published on old integer overflow");ScanRecord(n,int(status),guest_error,&out);}
 auto scan=[&](const char*input,const char*format,addr_t a=1,addr_t b=1,addr_t c=1,addr_t d=1){return libc.Scan(input,format,a,b,c,d);};
 bool failed=false;try{scan(reinterpret_cast<const char*>(1),"%s");}catch(const std::exception&){failed=true;}Check(failed,"unsupported format rejects before invalid input access");
 failed=false;try{scan(nullptr,scan_formats[0]);}catch(const std::exception&){failed=true;}Check(failed,"null input range guard");
 Check(scan(":",scan_formats[0])==0,"unassigned invalid outputs never accessed");std::array<char,16>partial{};Check(scan("abc",scan_formats[0],reinterpret_cast<addr_t>(partial.data()))==1&&!std::strcmp(partial.data(),"abc"),"only first assigned output used");
 std::array<unsigned char,80>alias;alias.fill(0xa5);std::memcpy(alias.data()+8,"http:tail",10);std::array<char,32>rest{};Check(scan(reinterpret_cast<char*>(alias.data()+8),scan_formats[0],reinterpret_cast<addr_t>(alias.data()+8),reinterpret_cast<addr_t>(rest.data()))==2&&!std::strcmp(reinterpret_cast<char*>(alias.data()+8),"http")&&!std::strcmp(rest.data(),"tail"),"input and outputs snapshot alias before publication");
 std::array<char,64>format{};std::strcpy(format.data(),scan_formats[0]);std::array<char,32>tail{};Check(scan("abc:tail",format.data(),reinterpret_cast<addr_t>(format.data()),reinterpret_cast<addr_t>(tail.data()))==2&&!std::strcmp(format.data(),"abc")&&!std::strcmp(tail.data(),"tail"),"format-output alias snapshot");
 SYSTEM_INFO info{};GetSystemInfo(&info);size_t page=info.dwPageSize;auto*pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,page*3,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Check(pages!=nullptr,"real page allocations");DWORD inaccessible=0;Check(VirtualProtect(pages+page*2,page,PAGE_NOACCESS,&inaccessible)!=FALSE,"guaranteed inaccessible third page");
 for(DWORD protection:{DWORD(PAGE_READONLY),DWORD(PAGE_NOACCESS),DWORD(PAGE_READWRITE|PAGE_GUARD)}){std::memset(pages,0xa5,page*2);DWORD old=0;Check(VirtualProtect(pages+page,page,protection,&old)!=FALSE,"set real output protections");failed=false;try{scan("abc:tail",scan_formats[0],reinterpret_cast<addr_t>(pages+page));}catch(const std::exception&){failed=true;}Check(failed,"assigned invalid output fails closed");MEMORY_BASIC_INFORMATION region{};Check(VirtualQuery(pages+page,&region,sizeof(region))&&region.Protect==protection,"guard protection not consumed");Check(VirtualProtect(pages+page,page,PAGE_READWRITE,&old)!=FALSE,"restore page protection");Check(pages[page]==0xa5,"failed assigned output unchanged");}
 for(addr_t ptr:{addr_t(0),addr_t(1),std::numeric_limits<addr_t>::max()-1,reinterpret_cast<addr_t>(pages+page*2-2)}){failed=false;try{scan("abc:tail",scan_formats[0],ptr);}catch(const std::exception&){failed=true;}Check(failed,"null overflow or crossing-unmapped assigned output guarded");}
 std::memset(pages,0xa5,page*2);Check(scan("abc:tail",scan_formats[0],reinterpret_cast<addr_t>(pages+page-4),reinterpret_cast<addr_t>(pages+page))==2&&!std::strcmp(reinterpret_cast<char*>(pages+page-4),"abc")&&!std::strcmp(reinterpret_cast<char*>(pages+page),"tail"),"exact-fit scanset including NUL at page boundary");VirtualFree(pages,0,MEM_RELEASE);
 std::printf("SCAN-PROFILES-PASS checks=%u NDK_calls=%u formats=4 old_integer=1 State=1200 Memory64=1\n",checks,calls);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"scan fixture: %s\n",e.what());return 1;}}
