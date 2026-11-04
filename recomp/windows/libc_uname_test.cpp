#include "libc.h"
#include "libc_uname_detail.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {
using bunker::windows::libc_detail::UnameFacts;
using bunker::windows::libc_detail::Utsname;
std::atomic<unsigned>checks{0},calls{0};
bunker::windows::LibC*provider=nullptr;
thread_local int32_t guest_error;
void Check(bool yes,const char*why){++checks;if(!yes){std::fprintf(stderr,"UNAME-CHECK-FAIL %s\n",why);std::abort();}}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);return reinterpret_cast<void*>(provider->Marker(name));}
template<class Function>Function Symbol(HMODULE module,const char*name){const auto address=GetProcAddress(module,name);Function result=nullptr;static_assert(sizeof(result)==sizeof(address));std::memcpy(&result,&address,sizeof(result));Check(result!=nullptr,"independent actual Windows API exists");return result;}
std::string Utf8(const std::wstring&text){if(text.empty())return {};const int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),int(text.size()),nullptr,0,nullptr,nullptr);Check(n>0,"independent UTF16 conversion size");std::string out(size_t(n),'\0');Check(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),int(text.size()),out.data(),n,nullptr,nullptr)==n,"independent UTF16 conversion");return out;}
std::string Name(COMPUTER_NAME_FORMAT which){DWORD size=0;const BOOL initial=GetComputerNameExW(which,nullptr,&size);if(initial&&which==ComputerNameDnsDomain&&size==0)return {};Check(!initial&&GetLastError()==ERROR_MORE_DATA&&size>0&&size<=65536,"independent Windows DNS name extent");std::vector<wchar_t>value(size);Check(GetComputerNameExW(which,value.data(),&size)!=FALSE,"independent Windows DNS query");return Utf8(std::wstring(value.data(),size));}
UnameFacts HostFacts(){
 using Version=LONG(WINAPI*)(OSVERSIONINFOW*);OSVERSIONINFOW version{};version.dwOSVersionInfoSize=sizeof(version);
 Check(Symbol<Version>(GetModuleHandleW(L"ntdll.dll"),"RtlGetVersion")(&version)==0&&version.dwPlatformId==VER_PLATFORM_WIN32_NT,"independent real Windows NT version");
 using Machines=BOOL(WINAPI*)(HANDLE,USHORT*,USHORT*);USHORT process=0,native=0;Check(Symbol<Machines>(GetModuleHandleW(L"kernel32.dll"),"IsWow64Process2")(GetCurrentProcess(),&process,&native)!=FALSE,"independent native OS machine query");
 std::string machine;
 switch(native){case IMAGE_FILE_MACHINE_AMD64:machine="x86_64";break;case IMAGE_FILE_MACHINE_I386:machine="x86";break;case IMAGE_FILE_MACHINE_ARM64:machine="aarch64";break;case IMAGE_FILE_MACHINE_ARMNT:machine="arm";break;case IMAGE_FILE_MACHINE_IA64:machine="ia64";break;default:Check(false,"independent machine is in explicit port catalog");}
 UnameFacts facts;facts.sysname="Windows_NT";facts.nodename=Name(ComputerNameDnsHostname);facts.release=std::to_string(version.dwMajorVersion)+"."+std::to_string(version.dwMinorVersion)+"."+std::to_string(version.dwBuildNumber);facts.version=version.szCSDVersion[0]?Utf8(version.szCSDVersion):"Build "+std::to_string(version.dwBuildNumber);facts.machine=machine;facts.domainname=Name(ComputerNameDnsDomain);return facts;
}
std::array<unsigned char,390>IndependentRecord(const UnameFacts&facts){
 std::array<unsigned char,390>out{};const std::string*fields[]={&facts.sysname,&facts.nodename,&facts.release,&facts.version,&facts.machine,&facts.domainname};
 for(unsigned i=0;i<6;++i){Check(fields[i]->size()<=64,"actual Windows fact representable in Bionic65-byte field");std::memcpy(out.data()+i*65,fields[i]->data(),fields[i]->size());}return out;
}
struct Result{int32_t result,error;int64_t widened;};
struct ResultGuard{uint64_t before=0x1122334455667788ULL;Result value{};uint64_t after=0x8877665544332211ULL;};
void PureControls(){
 static_assert(sizeof(Utsname)==390&&alignof(Utsname)==1);
 UnameFacts facts;facts.sysname="TEST_OS";facts.nodename="test-node";facts.release="1.2.3";facts.version="test-build";facts.machine="test-architecture";facts.domainname="";
 Utsname output;std::memset(&output,0xa5,sizeof(output));
 Check(bunker::windows::libc_detail::EncodeUname(facts,output)==0,"pure TEST facts encode; not game identity");
 const auto packed=IndependentRecord(facts);Check(!std::memcmp(&output,packed.data(),390),"all390 bytes fields/padding independently packed");
 auto before=output;facts.nodename=std::string(64,'a');Check(!bunker::windows::libc_detail::EncodeUname(facts,output)&&output.nodename[64]==0,"exact64 byte field fits");
 before=output;facts.nodename=std::string(65,'a');Check(bunker::windows::libc_detail::EncodeUname(facts,output)==75&&!std::memcmp(&output,&before,390),"65 bytes EOVERFLOW without partial record");
 facts.nodename=std::string(32,'a')+std::string(16,'\xc3');Check(bunker::windows::libc_detail::EncodeUname(facts,output)==84&&!std::memcmp(&output,&before,390),"invalid UTF8 EILSEQ without output");
 facts.nodename=std::string("bad\0name",8);Check(bunker::windows::libc_detail::EncodeUname(facts,output)==84&&!std::memcmp(&output,&before,390),"embeddedNUL is not silently truncated");
 facts.nodename.clear();Check(bunker::windows::libc_detail::EncodeUname(facts,output)==5&&!std::memcmp(&output,&before,390),"missing required real fact fails instead of fake identity");
 facts.nodename.clear();for(unsigned i=0;i<32;++i)facts.nodename+="\xc3\xa9";
 Check(!bunker::windows::libc_detail::EncodeUname(facts,output)&&output.nodename[64]==0,"64 multibyte UTF8 encoded bytes fit");before=output;facts.nodename+="a";
 Check(bunker::windows::libc_detail::EncodeUname(facts,output)==75&&!std::memcmp(&output,&before,390),"65 encoded UTF8 bytes overflow, not codepoint truncation");
 std::array<unsigned char,422>storage;storage.fill(0xb6);const auto original=storage;int error=0,sink_calls=0;
 std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);errno=EAGAIN;SetLastError(0x1234);
 const auto result=bunker::windows::libc_detail::UnameWithQuery(reinterpret_cast<addr_t>(storage.data()+16),[&](int value){error=value;++sink_calls;errno=E2BIG;SetLastError(0x5678);std::fesetround(FE_UPWARD);},[](UnameFacts&){errno=ERANGE;SetLastError(0x4321);std::feraiseexcept(FE_OVERFLOW);return 5;});
 Check(result==-1&&error==5&&sink_calls==1&&storage==original,"query failure propagates real error with no fake success/output");
 Check(errno==EAGAIN&&GetLastError()==0x1234&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INVALID,"query and error-sink native environment changes restored");
 error=0;sink_calls=0;const auto overflow=bunker::windows::libc_detail::UnameWithQuery(reinterpret_cast<addr_t>(storage.data()+16),[&](int value){error=value;++sink_calls;},[&](UnameFacts&value){value=facts;return 0;});
 Check(overflow==-1&&error==75&&sink_calls==1&&storage==original,"overlong query record never publishes success");
 sink_calls=0;bool publication_threw=false;errno=EAGAIN;SetLastError(0x6161);std::fesetround(FE_TOWARDZERO);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
 try{(void)bunker::windows::libc_detail::UnameWithQuery(reinterpret_cast<addr_t>(storage.data()+16),[&](int value){Check(value==5,"throwing sink receives original error");++sink_calls;errno=E2BIG;SetLastError(0x7171);std::fesetround(FE_UPWARD);std::feraiseexcept(FE_OVERFLOW);throw std::runtime_error("TEST uname sink");},[](UnameFacts&){return 5;});}
 catch(const std::runtime_error&exception){publication_threw=std::string(exception.what())=="TEST uname sink";}
 Check(publication_threw&&sink_calls==1&&storage==original,"publication exception propagates once without fake result or output");
 Check(errno==EAGAIN&&GetLastError()==0x6161&&std::fegetround()==FE_TOWARDZERO&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"native environment restored even while error publication throws");
 std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);
}
}
int main(){
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);PureControls();
 const auto expected=IndependentRecord(HostFacts());
 bunker::windows::LibC libc;provider=&libc;libc.SetErrorSink([](int value){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&value,4);});
 recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddImport(0x7ffc00000000ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
 elf_image image{};Check(!elf_load(UNAME_LIBRARY,0x5a000000,Resolve,&image),"actual NDK uname fixture loads");
 Check(libc.Marker("uname")&&libc.Marker("uname")==libc.Marker("readlink")+8,"uname marker appended without changing old namespace");
 auto invoke=[&](void*out,int indirect,int sentinel,int result,int error){
  ResultGuard observed;alignas(16)std::array<unsigned char,65536>stack{};alignas(16)std::array<unsigned char,64>token;token.fill(0x7a);const auto original=token;State s{};
  s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.dword=indirect;s.gpr.x2.dword=sentinel;s.gpr.x3.qword=reinterpret_cast<addr_t>(&observed.value);s.gpr.x19.qword=0xf0123456789abcdeULL;s.gpr.x29.qword=0xe0123456789abcdfULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
  auto*memory=reinterpret_cast<Memory*>(token.data());Check(runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_uname")),memory)==memory&&token==original,"actual NDK callback opaqueMemory64 preserved");++calls;
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK caller PC/SP restored");
  Check(s.gpr.x19.qword==0xf0123456789abcdeULL&&s.gpr.x29.qword==0xe0123456789abcdfULL,"NDK callee saved registers preserved");
  Check(observed.value.result==result&&observed.value.widened==result&&s.gpr.x0.qword==uint64_t(int64_t(result)),"actual signed32 status widened by NDK caller");
  Check(observed.value.error==error&&guest_error==error,"success preserves prior guest errno; failure publishes actual guest errno");
  Check(observed.before==0x1122334455667788ULL&&observed.after==0x8877665544332211ULL,"NDK status output canaries preserved");
 };
 for(int indirect=0;indirect<2;++indirect)for(unsigned offset:{32u,33u})for(int sentinel:{11,22}){
  std::array<unsigned char,456>buffer;buffer.fill(0xa5);const auto original=buffer;invoke(buffer.data()+offset,indirect,sentinel,0,sentinel);
  Check(!std::memcmp(buffer.data()+offset,expected.data(),390),"all390 actual host fields match independent real Windows queries");
  Check(!std::memcmp(buffer.data(),original.data(),offset)&&!std::memcmp(buffer.data()+offset+390,original.data()+offset+390,buffer.size()-offset-390),"only390 bytes written; unaligned Bionic struct supported");
 }
 SYSTEM_INFO system{};GetSystemInfo(&system);const auto page=system.dwPageSize;auto*pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,page*3,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));Check(pages!=nullptr&&page>=4096,"actual Windows boundary pages allocated");DWORD old=0;
 Check(VirtualProtect(pages+2*page,page,PAGE_NOACCESS,&old)!=FALSE,"real noaccess guard established");
 for(int indirect=0;indirect<2;++indirect){
  auto*out=pages+2*page-390;std::memset(out,0xa5,390);invoke(out,indirect,31,0,31);Check(!std::memcmp(out,expected.data(),390),"390-byte exact end of writable pages succeeds");
  invoke(nullptr,indirect,32,-1,14);invoke(reinterpret_cast<void*>(UINT64_MAX),indirect,33,-1,14);
  std::memset(out,0xa5,390);invoke(out+1,indirect,34,-1,14);Check(std::all_of(out,out+390,[](auto c){return c==0xa5;}),"crossing noaccess boundary EFAULT before publication on stable pages");
 }
 Check(VirtualProtect(pages,page,PAGE_READONLY,&old)!=FALSE,"actual read-only output page");
 for(int indirect=0;indirect<2;++indirect)invoke(pages,indirect,35,-1,14);
 Check(VirtualProtect(pages,page,PAGE_READWRITE|PAGE_GUARD,&old)!=FALSE,"actual guarded output page");
 for(int indirect=0;indirect<2;++indirect)invoke(pages,indirect,36,-1,14);
 MEMORY_BASIC_INFORMATION region{};Check(VirtualQuery(pages,&region,sizeof(region))==sizeof(region)&&(region.Protect&PAGE_GUARD),"failed probe never consumes PAGE_GUARD protection");
 Check(VirtualFree(pages,0,MEM_RELEASE)!=FALSE,"boundary allocation released");
 const uint64_t layout[]={390,1,0,65,130,195,260,325};
 for(unsigned index=0;index<8;++index){alignas(16)std::array<unsigned char,65536>stack{};State s{};s.gpr.x0.dword=index;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_uname_layout")));Check(s.gpr.x0.qword==layout[index]&&s.gpr.pc.qword==0xfeedffff,"executed actual NDK Bionic struct extent/offset constant");}
 std::vector<std::thread>threads;for(int n=0;n<2;++n)threads.emplace_back([&,n]{std::array<unsigned char,390>buffer{};invoke(buffer.data(),n,71+n,0,71+n);Check(!std::memcmp(buffer.data(),expected.data(),390),"real native thread queries actual same host with isolated guest errno");invoke(nullptr,1-n,81+n,-1,14);});for(auto&thread:threads)thread.join();
 std::printf("UNAME-PASS checks=%u NDK_calls=%u actual_host_fields=1 Bionic_bytes=390 native_layout_calls=8 identity_fabricated=0\n",checks.load(),calls.load());
}
