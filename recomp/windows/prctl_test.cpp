#include "pthread_host.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <windows.h>
#include "../fastaes/elfload.h"
#include "traces.h"

using bunker::windows::Pthreads;
static Pthreads *provider;
static thread_local int guest_errno;
constexpr addr_t kErrno=0x7ffb00100000ULL,kObserve=0x7ffb00100008ULL;
static void *Resolve(const char *name){
  if(!std::strcmp(name,"__errno"))return reinterpret_cast<void*>(kErrno);
  if(!std::strcmp(name,"observe_native_name"))return reinterpret_cast<void*>(kObserve);
  return reinterpret_cast<void*>(provider->Marker(name));
}
static std::wstring Name(){
  using Get=HRESULT(WINAPI*)(HANDLE,PWSTR*);
  auto fn=reinterpret_cast<Get>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"GetThreadDescription"));
  PWSTR text=nullptr;
  if(!fn||FAILED(fn(GetCurrentThread(),&text)))throw std::runtime_error("independent GetThreadDescription failed");
  std::wstring copy(text);LocalFree(text);return copy;
}
int main(){
  unsigned checks=0;
  auto require=[&](bool good,const char *what){if(!good)throw std::runtime_error(what);++checks;};
  recomp::Runtime runtime;
  Pthreads host(runtime,[](addr_t p){for(const auto &t:kTraces)if(t.address==p)return true;return false;});
  provider=&host;host.SetErrorSink([](int e){guest_errno=e;});host.Install();runtime.AddTraces(kTraces,std::size(kTraces));
  runtime.AddImport(kErrno,[](State &s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_errno);});
  runtime.AddImport(kObserve,[](State &s){s.gpr.x0.qword=Name()==L"UnityWorker"?0x7711:0xbad;});
  elf_image image;require(elf_load(PRCTL_GUEST_IMAGE,0x5b000000,Resolve,&image)==0,"load actual NDK variadic callers");
  auto entry=[&](const char *name){auto p=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(p!=0,"NDK export");return p;};
  const auto call=entry("guest_prctl"),two=entry("guest_prctl_two"),pname=entry("guest_pthread_name"),worker=entry("guest_name_worker");
  constexpr uint64_t ok=uint64_t(123)<<32;
  auto named=[&](const char *text){return host.Run(call,{15,reinterpret_cast<addr_t>(text),0,0,0});};
  const auto token=host.Self();const auto tid=host.GetTid();
  require(named("UnityMain")==ok&&Name()==L"UnityMain","real reached PR_SET_NAME changes calling native thread");
  require(host.Self()==token&&host.GetTid()==tid,"name change preserves pthread and native thread identity");
  require(named("")==ok&&Name().empty(),"empty name clears actual thread description");
  require(named("123456789012345")==ok&&Name()==L"123456789012345","15-byte name accepted");
  require(named("1234567890123456-tail")==ok&&Name()==L"123456789012345","long prctl name silently truncates at15 bytes");
  require(host.Run(pname,{reinterpret_cast<addr_t>("1234567890123456-tail")})==(ok|34)&&Name()==L"123456789012345","pthread_setname_np retains ERANGE and errno unchanged");
  require(host.Run(two,{reinterpret_cast<addr_t>("TwoArgument")})==ok&&Name()==L"TwoArgument","true two-argument NDK variadic call");
  require(host.Run(call,{15,reinterpret_cast<addr_t>("IgnoredArgs"),0xfedcba9876543210ULL,1,~0ULL})==ok&&Name()==L"IgnoredArgs","kernel ignores unused PR_SET_NAME arguments without dereferencing");
  require(named("caf\xc3\xa9")==ok&&Name()==L"caf\u00e9","valid UTF8 maps exactly to native Unicode description");
  const char bad[]={char(0xff),0};
  require(named(bad)==((uint64_t(22)<<32)|0xffffffffU)&&Name()==L"caf\u00e9","unrepresentable Linux byte string explicitly fails EINVAL without renaming");
  require(named("12345678901234\xc3\xa9")==((uint64_t(22)<<32)|0xffffffffU)&&Name()==L"caf\u00e9","UTF8 split by byte truncation explicitly fails without loss");
  require(host.Run(call,{15,0,0,0,0})==((uint64_t(14)<<32)|0xffffffffU)&&Name()==L"caf\u00e9","null name returns-1/EFAULT without renaming");
  require(host.Run(call,{16,1,0,0,0})==((uint64_t(38)<<32)|0xffffffffU)&&Name()==L"caf\u00e9","unsupported PR_GET_NAME explicitly ENOSYS and never dereferences output");
  require(host.Run(call,{0xffffffffU,1,0,0,0})==((uint64_t(38)<<32)|0xffffffffU),"unknown option explicitly fails ENOSYS");
  auto *pages=static_cast<char*>(VirtualAlloc(nullptr,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(pages!=nullptr,"guarded name allocation");
  DWORD old;require(VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&old)!=0,"guarded source boundary");
  std::memcpy(pages+4096-15,"123456789012345",15);
  require(named(pages+4096-15)==ok&&Name()==L"123456789012345","exact15 nonterminated bytes never read inaccessible byte16");
  pages[4095]=0;require(named(pages+4095)==ok&&Name().empty(),"NUL at page boundary stops snapshot immediately");
  VirtualFree(pages,0,MEM_RELEASE);
  require(named("ParentMain")==ok,"restore parent thread test name");
  uint64_t child=0,result=0;require(host.Create(&child,nullptr,worker,reinterpret_cast<addr_t>("UnityWorker"))==0,"create actual translated worker");
  require(host.Join(child,&result)==0&&result==0x7711,"native GetThreadDescription independently sees translated worker name");
  require(Name()==L"ParentMain","worker name leaves parent unchanged");
  std::atomic<unsigned> failures{0};std::thread external([&]{
    if(host.Run(two,{reinterpret_cast<addr_t>("ExternalHost")})!=ok||Name()!=L"ExternalHost")++failures;
    if(host.ReleaseCurrent())++failures;
  });external.join();require(failures==0&&Name()==L"ParentMain","external calling thread uses its own native name and cleanup");
  require(host.Shutdown()==0&&host.ReleaseCurrent()==0,"provider worker and external lifecycle cleanup");
  std::printf("PR_SET_NAME: %u checks passed with actual NDK callers and native Windows descriptions\n",checks);
}
