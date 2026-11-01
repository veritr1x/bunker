#include "libc.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

static unsigned checks;
static void check(bool result, const char *message) {
  ++checks;
  if (!result) { std::fprintf(stderr,"locale check failed: %s\n",message); std::exit(1); }
}
static bunker::windows::LibC *provider;
static thread_local int32_t guest_errno;
static thread_local const std::function<void(State&)> *trace_body;
static Memory *memory_trace(State &s,addr_t,Memory *m) {
  (*trace_body)(s);s.gpr.pc.qword=s.gpr.x30.qword;return m;
}
static void *resolve(const char *name) {
  if (!std::strcmp(name,"__errno")) return reinterpret_cast<void*>(0x7ffc00000000ULL);
  try { return reinterpret_cast<void*>(provider->Marker(name)); }
  catch (...) { std::fprintf(stderr,"unknown locale fixture import %s\n",name); return nullptr; }
}
int main() {
  bunker::windows::LibC libc;
  provider=&libc;
  libc.SetErrorSink([](int error){ recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&guest_errno),&error,sizeof(error)); });
  recomp::Runtime runtime;
  libc.Install(runtime);
  runtime.AddImport(0x7ffc00000000ULL,[](State &s){ s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno); });
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(*kTraces));
  elf_image image;
  if (elf_load(LOCALE_LIBRARY,0x6d000000,resolve,&image)) return 1;
  auto run=[&](const char *name,const std::vector<addr_t> &args) {
    auto stack=std::make_unique<uint8_t[]>(1<<18);
    State s{};
    Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};
    for(size_t i=0;i<args.size();++i)(s.gpr.*registers[i]).qword=args[i];
    s.gpr.sp.qword=(reinterpret_cast<addr_t>(stack.get())+(1<<18))&~addr_t(15);
    s.gpr.x30.qword=0xfeedffff;
    const auto sp=s.gpr.sp.qword;
    runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));
    check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==sp,"NDK returns with preserved stack");
    if (s.gpr.x0.qword) std::fprintf(stderr,"NDK locale fixture failed line %llu\n",static_cast<unsigned long long>(s.gpr.x0.qword));
    check(s.gpr.x0.qword==0,"actual NDK locale caller");
  };
  for(const char *name:{"C","POSIX","","C.UTF-8","en_US.UTF-8"})
    for(unsigned mask:{0U,1U,2U,0x1fbfU})
      run("guest_locale",{reinterpret_cast<addr_t>(name),mask,(!*name||std::strstr(name,"UTF-8"))?4U:1U});
  for(unsigned mask:{0x40U,0x2000U,0xffffffffU})
    run("guest_locale_invalid",{reinterpret_cast<addr_t>("C"),mask,22});
  run("guest_locale_invalid",{0,0x1fbf,22});
  for(const char *name:{"c","C.utf8","en_US","en-US.UTF-8","de_DE.UTF-8"})
    run("guest_locale_invalid",{reinterpret_cast<addr_t>(name),0x1fbf,2});
  check(libc.UseLocale(0)==UINT64_MAX&&libc.LocaleMbCurMax()==4,"main thread global UTF8 state");
  libc.FreeLocale(0);
  check(true,"null locale cleanup has no effect");
  const auto c=libc.NewLocale(0x1fbf,"C",0),utf8=libc.NewLocale(0x1fbf,"C.UTF-8",0);
  std::atomic<bool> good{true};
  std::vector<std::thread> threads;
  for(unsigned i=0;i<12;++i)threads.emplace_back([&,i]{
    const auto own=(i&1)?c:utf8;
    if(libc.UseLocale(0)!=UINT64_MAX||libc.UseLocale(own)!=UINT64_MAX)good=false;
    for(unsigned n=0;n<1000;++n)
      if(libc.UseLocale(0)!=own||libc.LocaleMbCurMax()!=((i&1)?1U:4U))good=false;
    if(libc.UseLocale(UINT64_MAX)!=own)good=false;
  });
  for(auto &thread:threads)thread.join();
  check(good,"12 real threads keep independent selections on shared locale objects");
  check(libc.UseLocale(0)==UINT64_MAX&&libc.LocaleMbCurMax()==4,"worker selections never change owner");
  recomp::Trace entry{0x6cf00000,memory_trace};runtime.AddTraces(&entry,1);
  std::function<void(State&)> reservation=[&](State &s){
    auto old=__remill_aarch64_load_exclusive(s,c,8,0);
    auto previous=libc.UseLocale(c);
    check(libc.LocaleMbCurMax()==1,"selected C metadata is readable");
    libc.UseLocale(previous);
    check(__remill_aarch64_store_exclusive(s,c,old,8,0)==0,"locale queries do not invalidate guest memory");
    old=__remill_aarch64_load_exclusive(s,c,8,0);
    std::thread retiring([&]{libc.FreeLocale(c);});retiring.join();
    check(__remill_aarch64_store_exclusive(s,c,old,8,0)==1,"locale retirement invalidates existing guest reservation");
  };
  trace_body=&reservation;State memory_state{};runtime.Run(memory_state,0x6cf00000);trace_body=nullptr;
  auto next=libc.NewLocale(0x1fbf,"C",0);
  check(next!=c,"retired locale identity is not reused");
  for(auto bad:{c,addr_t(0x1234),UINT64_MAX}) {
    bool rejected=false;try{libc.FreeLocale(bad);}catch(const std::invalid_argument&){rejected=true;}
    check(rejected,"foreign/retired/global freelocale is rejected");
  }
  bool rejected=false;try{libc.UseLocale(c);}catch(const std::invalid_argument&){rejected=true;}
  check(rejected,"retired uselocale is rejected");
  bunker::windows::LibC other;
  rejected=false;try{other.UseLocale(utf8);}catch(const std::invalid_argument&){rejected=true;}
  check(rejected&&other.UseLocale(0)==UINT64_MAX,"provider ownership is isolated");
  libc.FreeLocale(next);libc.FreeLocale(utf8);
  std::printf("Bionic locale adapter: %u checks; 29 translated NDK callers; 12 real isolated threads.\n",checks);
}
