#define BSEARCH_DRIVER
#include "libc_bsearch_fixture.h"
#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#ifdef _WIN32
#include "pthread_host.h"
#endif
#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <vector>
namespace {
recomp::Runtime runtime,provider_runtime;elf_image image{};
thread_local int guest_errno;
bunker::windows::LibC*provider;
unsigned callbacks=0,bridge_checks=0,injection=0;
bool Translated(addr_t entry){for(const auto&t:kTraces)if(t.address==entry)return true;return false;}
void Check(bool b,const char*why){if(!b)throw std::runtime_error(why);}
addr_t Symbol(const char*name){auto value=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(value!=0,"strict fixture export exists");return value;}
void*Resolve(const char*name){if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(0x7ffd00000100ULL);return reinterpret_cast<void*>(provider->Marker(name));}
struct PortableRunner{
 alignas(16)std::array<uint8_t,1<<20>stack{};State*active=nullptr;
 uint64_t Run(addr_t entry,const std::vector<addr_t>&args){
  Check(Translated(entry),"bsearch TEST unknown callback target");State state{};if(active)state=*active;else state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());
  Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};Check(args.size()<=8,"bounded callback arguments");for(size_t n=0;n<args.size();++n)(state.gpr.*regs[n]).qword=args[n];
  state.gpr.x30.qword=0xfeedffff;auto sp=state.gpr.sp.qword;auto*previous=active;active=&state;
  try{runtime.Run(state,entry);}catch(...){active=previous;throw;}active=previous;
  Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==sp,"actual translated callback normal return/owned SP");return state.gpr.x0.qword;
 }
};
std::function<uint64_t(addr_t,const std::vector<addr_t>&)>run;
void Invoke(BSearchReport*r){Check(run(Symbol("bsearch_fixture_invoke"),{reinterpret_cast<addr_t>(r)})==0,"strict actual NDK ABI wrapper returns");}
}
int main(int argc,char**argv){try{
 const std::string mode=argc>1?argv[1]:"";
#ifdef _WIN32
 bunker::windows::Pthreads threads(runtime,Translated);
 run=[&](addr_t pc,const std::vector<addr_t>&args){return threads.Run(pc,args);};
#else
 auto portable=std::make_unique<PortableRunner>();
 run=[&](addr_t pc,const std::vector<addr_t>&args){return portable->Run(pc,args);};
#endif
 bunker::windows::LibC libc(mode=="missing-runner"?bunker::windows::LibC::Runner{}:bunker::windows::LibC::Runner{[&](addr_t pc,const std::vector<addr_t>&args)->uint64_t{
  ++callbacks;if(injection==1)throw std::runtime_error("TEST comparator runner exception");if(injection==2)throw 67;return run(pc,args);
 }});provider=&libc;libc.SetErrorSink([](int e){guest_errno=e;});libc.Install(provider_runtime);
 for(const char*name:{"bsearch","memcpy","memset"}){
  const auto marker=libc.Marker(name);const bool search=!std::strcmp(name,"bsearch");
  runtime.AddImport(marker,[marker,search](State&s){
   auto before=s;provider_runtime.Dispatch(s,marker,nullptr);
   if(search){
    Check(s.gpr.sp.qword==before.gpr.sp.qword,"provider callback leaves parent SP intact");
    const Reg GPR::*saved[]={&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29};
    for(auto reg:saved)Check((s.gpr.*reg).qword==(before.gpr.*reg).qword,"provider callback leaves parent callee GPR intact");
    for(unsigned n=8;n<16;++n){Check(!std::memcmp(&s.simd.v[n],&before.simd.v[n],8),"provider callback leaves parent D8-D15 intact");}++bridge_checks;
   }
  });
 }
 runtime.AddImport(0x7ffd00000100ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno);});runtime.AddTraces(kTraces,std::size(kTraces));
 Check(!elf_load(BSEARCH_LIBRARY,0x5d000000,Resolve,&image),"strict actual NDK caller image loads");
 if(!mode.empty()){
  uint32_t key=1,row=1;addr_t base=reinterpret_cast<addr_t>(&row),count=1,size=4,cmp=Symbol("bsearch_logged_comparator");
  if(mode=="span-overflow"){count=UINT64_MAX;size=2;}
  else if(mode=="pointer-overflow"){base=UINT64_MAX-3;count=2;size=4;}
  else if(mode=="unknown-target")cmp=0xdeadbeef;
  else if(mode=="zero-target")cmp=0;
  else if(mode=="throw-standard")injection=1;
  else if(mode=="throw-unknown")injection=2;
  else Check(mode=="missing-runner","known fixture negative mode");
  run(Symbol("bsearch_guest_raw"),{reinterpret_cast<addr_t>(&key),base,count,size,cmp});
  std::fprintf(stderr,"UNEXPECTED-BSEARCH-BOUNDARY-RETURN\n");return 40;
 }
 Check(!run(Symbol("bsearch_guest_empty"),{}),"zero count permits unused null pointers and no callback");Check(callbacks==0,"empty actual import invokes no translated comparator");
 Check(!libc.BinarySearch(nullptr,nullptr,0,UINT64_MAX,0)&&callbacks==0,"direct empty search touches no unused arguments");
 unsigned failed=0;for(bool overflow:{false,true})try{libc.BinarySearch(nullptr,reinterpret_cast<void*>(overflow?UINT64_MAX-3:16),overflow?2:UINT64_MAX,overflow?4:2,Symbol("bsearch_logged_comparator"));}catch(const std::overflow_error&){++failed;}
 Check(failed==2&&callbacks==0,"direct checked arithmetic fails before callback");
 int result=execute_bsearch_records(Invoke);if(result)return result;
#ifdef _WIN32
 threads.Shutdown();Check(!threads.ReleaseCurrent(),"real Pthreads caller TLS/stack release");
#endif
 std::printf("BSEARCH-HOST-SUCCESS callbacks=%u preserved_import_states=%u direct_overflow=2 empty=2 runner=%s\n",callbacks,bridge_checks,
#ifdef _WIN32
 "actual-Pthreads"
#else
 "portable-active-State-contract"
#endif
 );return 0;
}catch(const std::exception&e){std::fprintf(stderr,"bsearch fixture: %s\n",e.what());return 1;}}
