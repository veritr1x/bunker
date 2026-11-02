#include "libc.h"
#include "tracked_memory_test.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "old_markers.h"
#include <array>
#include <atomic>
#include <clocale>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>
namespace {
std::atomic<unsigned>checks{0},calls{0},error_writes{0};bunker::windows::LibC*provider;
thread_local int32_t guest_error,expected_category;
thread_local addr_t expected_name;
constexpr addr_t kErrno=0x7ffc00000000ULL,kSetLocale=0x7ffc00000008ULL;
void Check(bool v,const char*w){if(!v){std::fprintf(stderr,"setlocale check failed: %s\n",w);std::abort();}++checks;}
void*Resolve(const char*n){if(!std::strcmp(n,"__errno"))return reinterpret_cast<void*>(kErrno);if(!std::strcmp(n,"setlocale"))return reinterpret_cast<void*>(kSetLocale);return reinterpret_cast<void*>(provider->Marker(n));}
struct Observation {const char*name=nullptr;uint64_t maximum=0;addr_t selection=0;int32_t error=0,reserved=0x7654321;};
struct Guard {uint64_t before=0x123456789abcdef0ULL;Observation result;uint64_t after=0xfedcba9876543210ULL;};
}
int main(){
 const char*host_query=std::setlocale(LC_ALL,nullptr);Check(host_query!=nullptr,"native CRT read-only locale query available");const std::string host_before=host_query;
 bunker::windows::LibC libc;provider=&libc;
 libc.SetErrorSink([](int error){++error_writes;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_error),&error,4);});
 recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 runtime.AddImport(kErrno,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});
 runtime.AddImport(kSetLocale,[&](State&s){Check(s.gpr.x0.dword==uint32_t(expected_category)&&s.gpr.x1.qword==expected_name,"actual NDK setlocale category W0 and name X1");auto x1=s.gpr.x1.qword,x2=s.gpr.x2.qword;runtime.Dispatch(s,libc.Marker("setlocale"),nullptr);++calls;Check(s.gpr.x1.qword==x1&&s.gpr.x2.qword==x2,"fixed bridge preserves other argument registers");});
 elf_image image{};Check(!elf_load(SETLOCALE_LIBRARY,0x5b000000,Resolve,&image),"strict NDK setlocale fixture loads");
 for(size_t i=0;i<std::size(kOldMarkers);++i)Check(libc.Marker(kOldMarkers[i])==0x7ffb00000000ULL+i*8,"every accepted marker unchanged including free and sscanf");
 Check(libc.Marker("setlocale")==libc.Marker("sscanf")+8,"setlocale is append-only");
 auto Run=[&](int32_t category,const char*name,int indirect,int sentinel,const char*canonical,uint64_t maximum,addr_t selection){
  alignas(16)std::array<uint8_t,65536>stack{};State s{};Guard out;
  expected_category=category;expected_name=reinterpret_cast<addr_t>(name);
  s.gpr.x0.qword=0xaabbccdd00000000ULL|uint32_t(category);s.gpr.x1.qword=reinterpret_cast<addr_t>(name);s.gpr.x2.dword=indirect;s.gpr.x3.dword=sentinel;s.gpr.x4.qword=reinterpret_cast<addr_t>(&out.result);
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x123456789abcdef0ULL;s.gpr.x29.qword=0x1122334455667788ULL;
  runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_setlocale")));
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK preserves PC/SP");
  Check(s.gpr.x19.qword==0x123456789abcdef0ULL&&s.gpr.x29.qword==0x1122334455667788ULL,"NDK preserves callee-saved registers");
  Check(s.gpr.x0.qword==reinterpret_cast<addr_t>(out.result.name),"installed bridge pointer result survives full64 ABI and actual caller");
  Check((!canonical&&!out.result.name)||(canonical&&out.result.name&&!std::strcmp(canonical,out.result.name)),"canonical readable static result or real null failure");
  Check(out.result.maximum==maximum&&out.result.selection==selection,"real NDK MB_CUR_MAX and uselocale reflect correct global/owned state");
  Check(out.before==0x123456789abcdef0ULL&&out.after==0xfedcba9876543210ULL&&out.result.reserved==0x7654321,"observation canaries/reserved bytes preserved");
  Check(out.result.error==guest_error,"real NDK errno observation agrees with actual provider error sink");return out.result;
 };
 const auto global=UINT64_MAX;
 auto initial=Run(6,nullptr,0,123,"C.UTF-8",4,global);Check(initial.error==123,"initial global query preserves errno");
 const char*utf8=initial.name;auto c_result=Run(6,"C",1,123,"C",1,global);const char*c_name=c_result.name;Check(c_result.error==123,"C switch preserves errno");
 for(int indirect=0;indirect<2;++indirect)for(int category=0;category<=12;++category){
  for(const char*name:{"C","POSIX","","C.UTF-8","en_US.UTF-8"}){
   const bool unicode=!*name||std::strstr(name,"UTF-8");auto before=error_writes.load();
   auto r=Run(category,name,indirect,123,unicode?"C.UTF-8":"C",unicode?4:1,global);
   Check(r.error==123&&error_writes.load()==before,"all valid names/categories leave guest errno untouched");
   Check(r.name==(unicode?utf8:c_name),"aliases use stable canonical result identity");
   auto q=Run(category,nullptr,1-indirect,124,unicode?"C.UTF-8":"C",unicode?4:1,global);
   Check(q.name==r.name&&q.error==124,"query never changes selection or errno");
  }
 }
 libc.SetLocale(6,"C");
 for(int32_t category:{INT32_MIN,-1,13,INT32_MAX})for(const char*name:{static_cast<const char*>(nullptr),reinterpret_cast<const char*>(1)}){
  auto before=error_writes.load();auto r=Run(category,name,1,125,nullptr,1,global);
  Check(r.error==22&&error_writes.load()==before+1,"invalid category sets EINVAL once before unreadable name access");Check(!std::strcmp(libc.SetLocale(6,nullptr),"C"),"invalid category preserves global mode");
 }
 for(const char*name:{"c","C.utf8","en_US","en-US.UTF-8","de_DE.UTF-8","this-is-not-a-locale"}){
  auto before=error_writes.load();auto r=Run(6,name,0,126,nullptr,1,global);Check(r.error==2&&error_writes.load()==before+1,"unknown exact spelling sets ENOENT once");Check(!std::strcmp(libc.SetLocale(6,nullptr),"C"),"unknown name preserves global mode");
 }
 libc.SetEnvironment({{"LANG","bad-host-profile"},{"LC_ALL","C"},{"LC_CTYPE","POSIX"}});
 Check(Run(6,"",0,127,"C.UTF-8",4,global).error==127,"Bionic empty alias ignores explicit virtual environment");
 Check(!std::strcmp(c_name,"C")&&!std::strcmp(utf8,"C.UTF-8")&&c_name!=utf8,"previous canonical strings remain readable after every later switch");
 auto owned_c=libc.NewLocale(0x1fbf,"C",0),owned_utf8=libc.NewLocale(0x1fbf,"C.UTF-8",0);Check(owned_c&&owned_utf8,"real owned C and UTF8 locale objects allocated");
 Check(libc.UseLocale(owned_c)==global,"select explicit owned C");
 Run(6,"C.UTF-8",1,128,"C.UTF-8",1,owned_c);Run(6,nullptr,0,129,"C.UTF-8",1,owned_c);
 Check(libc.UseLocale(owned_utf8)==owned_c,"select explicit owned UTF8");Run(6,"POSIX",0,130,"C",4,owned_utf8);Run(6,nullptr,1,131,"C",4,owned_utf8);
 auto empty_owned=libc.NewLocale(0x1fbf,"",owned_c);Check(empty_owned&&libc.UseLocale(empty_owned)==owned_utf8&&libc.LocaleMbCurMax()==4,"newlocale(empty) is fresh explicit UTF8 even while global C");
 Check(libc.UseLocale(global)==empty_owned&&libc.LocaleMbCurMax()==1,"return to global observes current C without changing object state");
 for(unsigned mode=0;mode<2;++mode){
  libc.SetLocale(6,mode?"C.UTF-8":"C");std::vector<std::thread>threads;
  for(unsigned n=0;n<9;++n){threads.emplace_back([&,n,mode]{
   if(n&1)Run(6,nullptr,0,139,mode?"C.UTF-8":"C",mode?4:1,global);
   Check(libc.UseLocale(0)==global,"new actual native thread starts in global locale");auto selected=n%3==0?global:n%3==1?owned_c:owned_utf8;
   if(selected!=global)Check(libc.UseLocale(selected)==global,"worker chooses its own object");
   for(unsigned i=0;i<4;++i){auto r=Run(6,nullptr,i&1,140+n,mode?"C.UTF-8":"C",selected==global?(mode?4:1):selected==owned_c?1:4,selected);Check(r.error==int(140+n),"actual worker errno remains thread-local");}
   if(selected!=global)Check(libc.UseLocale(global)==selected,"worker restores its own selection");
  });}
  for(auto&t:threads){t.join();}
  Check(libc.UseLocale(0)==global,"worker objects never change main selection");
 }
 // Synchronization, not timing, establishes process-wide global visibility.
 std::atomic<unsigned>phase{0};std::thread observer([&]{Check(libc.UseLocale(0)==global,"observer begins global");phase.store(1);while(phase.load()<2){std::this_thread::yield();}Run(6,nullptr,1,170,"C",1,global);phase.store(3);});
 while(phase.load()<1){std::this_thread::yield();}libc.SetLocale(6,"C");phase.store(2);while(phase.load()<3){std::this_thread::yield();}observer.join();
 bunker::windows::LibC other;Check(!std::strcmp(other.SetLocale(6,nullptr),"C.UTF-8")&&other.LocaleMbCurMax()==4,"separate virtual guest process stays initially UTF8");other.SetLocale(6,"C.UTF-8");Check(libc.LocaleMbCurMax()==1,"other provider changes cannot alter this process global");
 auto untouched=bunker::test::ReserveAcrossOperation(owned_c,8,[&]{libc.SetLocale(6,nullptr);libc.SetLocale(6,"");});Check(untouched.status==0,"query/global change never writes or retires owned locale metadata");
 Check(!std::strcmp(c_name,"C")&&!std::strcmp(utf8,"C.UTF-8"),"both canonical return lifetimes survive threads/provider operations");
 libc.FreeLocale(empty_owned);libc.FreeLocale(owned_c);libc.FreeLocale(owned_utf8);
 const char*host_after=std::setlocale(LC_ALL,nullptr);Check(host_after&&host_before==host_after,"host CRT process locale was never changed");
 std::printf("Bionic setlocale: %u checks passed; %u actual NDK calls; all categories/names/query/errors, immutable results, global versus owned/thread state, no host CRT mutation\n",checks.load(),calls.load());
}
