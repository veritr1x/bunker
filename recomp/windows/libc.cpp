#include "libc.h"
#include "../whole/bridge.h"
#include "provider_memory.h"
#include "libc_process_detail.h"
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <type_traits>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#include <time.h>
#endif

namespace bunker::windows {
namespace pm=provider_memory;
namespace {
thread_local int guest_error;
std::atomic<uint64_t> next_locale_owner{1};
thread_local std::map<uint64_t, addr_t> current_locales;
constexpr addr_t global_locale = UINT64_MAX;
const char *const imports[] = {
  "malloc", "calloc", "realloc", "free", "memalign", "posix_memalign", "aligned_alloc",
  "memcpy", "memmove", "memset", "memcmp", "memchr", "memrchr",
  "strlen", "strnlen", "strcmp", "strncmp", "strcpy", "strncpy", "strcat", "strncat", "strlcpy",
  "strchr", "strrchr", "strstr", "strpbrk", "strspn", "strcspn", "strdup", "strndup", "strtok_r",
  "strcasecmp", "strncasecmp", "strcoll", "strxfrm",
  "isalnum", "isalpha", "isblank", "iscntrl", "isdigit", "isgraph", "islower", "isprint", "ispunct", "isspace", "isupper", "isxdigit", "tolower", "toupper",
  "strtol", "strtoul", "strtoll", "strtoull", "atoi", "atol", "atoll", "strtod", "strtof", "atof",
  "getenv", "setenv", "unsetenv", "__cxa_atexit", "__cxa_finalize", "atexit",
  "__stack_chk_fail", "abort", "exit", "android_set_abort_message", "__ctype_get_mb_cur_max",
  "sin", "sinf", "cos", "cosf", "tan", "tanf", "asin", "asinf", "acos", "acosf", "atan", "atanf", "atan2", "atan2f",
  "exp", "expf", "exp2f", "log", "logf", "log10", "log10f", "log2f", "logb", "pow", "powf", "sqrt", "sqrtf", "hypot",
  "fmod", "fmodf", "remainderf", "nearbyintf", "ldexp", "ldexpf", "scalbn", "frexpf", "modf", "modff", "getpagesize",
  "newlocale", "freelocale", "uselocale", "clock", "sysconf"
};
bool Space(int c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
int Lower(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
int Upper(int c) { return c >= 'a' && c <= 'z' ? c - 32 : c; }
int Digit(int c) { if(c>='0'&&c<='9')return c-'0';c=Lower(c);return c>='a'&&c<='z'?c-'a'+10:99; }
int CompareCase(const char *a,const char *b,uint64_t count) {
  for(uint64_t i=0;i<count;++i) { int x=Lower(static_cast<unsigned char>(a[i])),y=Lower(static_cast<unsigned char>(b[i]));if(x!=y)return x-y;if(!x)return 0; }return 0;
}
template <typename F,typename... A> auto Math(F function,A... args) {
  errno=0;auto result=function(args...);return std::make_pair(result,errno);
}
template <typename T> auto ParseFloating(const char *input,char **end){
  auto text=pm::String(input);char *finish=nullptr;
  auto result=Math([&]{
    if constexpr(std::is_same_v<T,float>)return std::strtof(text.c_str(),&finish);
    else return std::strtod(text.c_str(),&finish);
  });
  if(end)pm::Write(end,const_cast<char*>(input+(finish-text.c_str())));return result;
}
}
LibC::LibC(Runner runner,addr_t base):runner_(std::move(runner)),marker_base_(base) {
  if((base&7)||base>UINT64_MAX-sizeof(imports)/sizeof(*imports)*8)throw std::invalid_argument("invalid libc marker base");
  locale_owner_=next_locale_owner.fetch_add(1);
  if(!locale_owner_)throw std::overflow_error("locale provider identity exhausted");
  BuildEnvironment();
}
LibC::~LibC(){
  for(const auto &entry:locales_)Free(entry.second.storage);
  current_locales.erase(locale_owner_);
  recomp::InvalidateGuestMemory(pm::Address(&environment_slot_),sizeof(environment_slot_));
  Free(environment_array_);for(auto text:environment_strings_)Free(text);
}
addr_t LibC::NewLocale(int32_t mask,const char *name,addr_t /*base*/){
  // Android 13 LC_ALL_MASK excludes the LC_ALL pseudo-category bit (6).
  // Bionic ignores base, even for a zero category mask, and allocates afresh.
  if((uint32_t(mask)&~UINT32_C(0x1fbf))||!name){Fail(22);return 0;}
  auto text=pm::String(name);
  if(text!=""&&text!="C"&&text!="POSIX"&&text!="C.UTF-8"&&text!="en_US.UTF-8"){
    Fail(2);return 0;
  }
  const uint64_t maximum=(text.empty()||text.find("UTF-8")!=std::string::npos)?4:1;
  auto storage=static_cast<uint64_t*>(Malloc(sizeof(uint64_t)));
  if(!storage)return 0;
  try{
    pm::Write(storage,maximum);
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    locales_.emplace(pm::Address(storage),Locale{storage,true});
  }catch(const std::bad_alloc&){Free(storage);Fail(12);return 0;}
  catch(...){Free(storage);throw;}
  return pm::Address(storage);
}
void LibC::FreeLocale(addr_t locale){
  if(!locale)return;
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  auto found=locales_.find(locale);
  if(found==locales_.end()||!found->second.active)
    throw std::invalid_argument("freelocale requires an active locale owned by this provider");
  // Quarantine backing storage until shutdown: stale handles never alias a
  // newly created locale. The public API rejects the retired identity.
  recomp::InvalidateGuestMemory(locale,sizeof(uint64_t));
  found->second.active=false;
}
addr_t LibC::UseLocale(addr_t locale){
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if(locale&&locale!=global_locale){
    auto found=locales_.find(locale);
    if(found==locales_.end()||!found->second.active)
      throw std::invalid_argument("uselocale requires an active locale owned by this provider");
  }
  auto old=current_locales.find(locale_owner_);
  const addr_t previous=old==current_locales.end()?global_locale:old->second;
  if(locale)current_locales[locale_owner_]=locale;
  return previous;
}
uint64_t LibC::LocaleMbCurMax(){
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  const auto locale=UseLocale(0);
  // Android starts in C.UTF-8; no host process locale is consulted or changed.
  if(locale==global_locale)return 4;
  auto found=locales_.find(locale);
  if(found==locales_.end()||!found->second.active)
    throw std::invalid_argument("current locale has been retired");
  return pm::Read(found->second.storage);
}
int LibC::Error()const{return guest_error;}
int64_t LibC::ProcessClock(){
#ifdef _WIN32
  FILETIME created{},exited{},kernel{},user{};
  if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user)){
    const auto error=GetLastError();Fail(error==ERROR_ACCESS_DENIED?13:error==ERROR_INVALID_PARAMETER?22:error==ERROR_NOT_ENOUGH_MEMORY?12:error==ERROR_NOT_SUPPORTED?95:5);return -1;
  }
  const uint64_t kernel_ticks=uint64_t(kernel.dwHighDateTime)<<32|kernel.dwLowDateTime;
  const uint64_t user_ticks=uint64_t(user.dwHighDateTime)<<32|user.dwLowDateTime;
  return libc_detail::CpuMicroseconds(kernel_ticks,user_ticks);
#else
  timespec value{};
  if(::clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&value)){Fail(errno?errno:5);return -1;}
  if(value.tv_sec<0||value.tv_nsec<0||value.tv_nsec>=1000000000){Fail(5);return -1;}
  if(uint64_t(value.tv_sec)>uint64_t(INT64_MAX)/1000000){Fail(75);return -1;}
  const auto whole=uint64_t(value.tv_sec)*1000000,fraction=uint64_t(value.tv_nsec)/1000;
  if(whole>uint64_t(INT64_MAX)-fraction){Fail(75);return -1;}
  return static_cast<int64_t>(whole+fraction);
#endif
}
int64_t LibC::Sysconf(int32_t name){
  if(name!=39&&name!=40&&name!=97){
    if(libc_detail::AndroidSysconfName(name))throw std::runtime_error("unsupported Android sysconf name: "+std::to_string(name));
    Fail(22);return -1;
  }
#ifdef _WIN32
  if(name==39||name==40){SYSTEM_INFO info{};GetSystemInfo(&info);if(!info.dwPageSize){Fail(5);return -1;}return info.dwPageSize;}
  const auto count=GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
  if(!count){const auto error=GetLastError();Fail(error==ERROR_ACCESS_DENIED?13:error==ERROR_INVALID_PARAMETER?22:error==ERROR_NOT_ENOUGH_MEMORY?12:error==ERROR_NOT_SUPPORTED?95:5);return -1;}
  return count;
#else
  errno=0;const auto value=::sysconf(name==97?_SC_NPROCESSORS_ONLN:_SC_PAGESIZE);
  if(value<=0){Fail(errno?errno:5);return -1;}return static_cast<int64_t>(value);
#endif
}
void LibC::Fail(int error)noexcept{guest_error=error;if(error_sink_)try{error_sink_(error);}catch(...){}}
[[noreturn]] void LibC::Fatal(const char *why)noexcept{
  std::fprintf(stderr,"Bunker guest libc fatal: %s\n",why);
  try { std::lock_guard<std::recursive_mutex> lock(mutex_);
    if(!abort_message_.empty())std::fprintf(stderr,"%s\n",abort_message_.c_str());
  } catch (...) {}
  std::abort();
}
addr_t LibC::Marker(const std::string &name)const{
  if(name=="environ")return reinterpret_cast<addr_t>(&environment_slot_);
  for(size_t i=0;i<sizeof(imports)/sizeof(*imports);++i)if(name==imports[i])return marker_base_+i*8;
  throw std::invalid_argument("unsupported libc import: "+name);
}
template <typename Signature,typename F>void LibC::Add(recomp::Runtime &runtime,const char *name,F function){
  auto bridge=recomp::MakeBridge<Signature>(std::move(function));
  runtime.AddImport(Marker(name),[this,bridge=std::move(bridge),name](State &state){
    try{bridge(state);}
    catch(const std::exception &error){
      std::fprintf(stderr,"Bunker guest libc import %s failed: %s\n",name,error.what());
      std::fprintf(stderr,"  guest-pc=%#llx return=%#llx x0=%#llx x1=%#llx x2=%#llx x3=%#llx\n",
        static_cast<unsigned long long>(state.gpr.pc.qword),static_cast<unsigned long long>(state.gpr.x30.qword),
        static_cast<unsigned long long>(state.gpr.x0.qword),static_cast<unsigned long long>(state.gpr.x1.qword),
        static_cast<unsigned long long>(state.gpr.x2.qword),static_cast<unsigned long long>(state.gpr.x3.qword));
      Fatal(name);
    }
    catch(...){
      std::fprintf(stderr,"Bunker guest libc import %s failed: non-standard C++ exception\n",name);
      Fatal(name);
    }
  });
}
void *LibC::Malloc(uint64_t size){
  if(size>INT64_MAX){Fail(12);return nullptr;}auto p=pm::Allocate(static_cast<size_t>(size));if(!p)Fail(12);return p;
}
void *LibC::Calloc(uint64_t n,uint64_t size){
  if(size&&n>uint64_t(INT64_MAX)/size){Fail(12);return nullptr;}uint64_t total=n*size;
  auto p=Malloc(total);if(p)pm::Fill(p,0,static_cast<size_t>(total?total:1));return p;
}
void LibC::Free(void *p){
  if(!p)return;std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=aligned_.find(p);
  if(i==aligned_.end())pm::Free(p);else{pm::Free(i->second.base);aligned_.erase(i);}
}
void *LibC::AlignedAllocate(uint64_t alignment,uint64_t size,bool set_errno){
  if(!alignment||(alignment&(alignment-1))){if(set_errno)Fail(22);return nullptr;}
  alignment=std::max<uint64_t>(alignment,16);
  if(alignment>uint64_t(INT64_MAX)||size>uint64_t(INT64_MAX)-alignment){if(set_errno)Fail(12);return nullptr;}
  void *base=pm::Allocate(static_cast<size_t>((size?size:1)+alignment));
  if(!base){if(set_errno)Fail(12);return nullptr;}
  auto p=reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(base)+alignment-1)&~uintptr_t(alignment-1));
  try{std::lock_guard<std::recursive_mutex> lock(mutex_);aligned_.emplace(p,Aligned{base,size,alignment});}
  catch(...){pm::Free(base);if(set_errno)Fail(12);return nullptr;}return p;
}
void *LibC::Memalign(uint64_t alignment,uint64_t size){return AlignedAllocate(alignment,size,true);}
int LibC::PosixMemalign(void **out,uint64_t alignment,uint64_t size){
  if(!out||alignment<sizeof(void*)||(alignment&(alignment-1)))return 22;
  auto p=AlignedAllocate(alignment,size,false);if(!p)return 12;pm::Write(out,p);return 0;
}
void *LibC::Realloc(void *p,uint64_t size){
  if(!p)return Malloc(size);if(!size){Free(p);return nullptr;}if(size>INT64_MAX){Fail(12);return nullptr;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=aligned_.find(p);
  if(i!=aligned_.end()){
    const auto old=i->second;auto q=AlignedAllocate(old.alignment,size,true);if(!q)return nullptr;
    try{pm::Copy(q,p,static_cast<size_t>(std::min(size,old.size)));}
    catch(const std::bad_alloc&){Free(q);Fail(12);return nullptr;}
    Free(p);return q;
  }
  auto q=pm::Reallocate(p,static_cast<size_t>(size));if(!q)Fail(12);return q;
}
uint64_t LibC::ParseInteger(const char *text,char **end,int base,bool is_signed){
  if(end)pm::Write(end,const_cast<char*>(text));
  if(!text||base<0||base==1||base>36){Fail(22);return 0;}
  const auto snapshot=pm::String(text);const char *p=snapshot.c_str();while(Space(static_cast<unsigned char>(*p)))++p;
  bool negative=*p=='-';if(*p=='-'||*p=='+')++p;
  if((base==0||base==16)&&p[0]=='0'&&(p[1]=='x'||p[1]=='X')&&Digit(static_cast<unsigned char>(p[2]))<16){base=16;p+=2;}
  // Target Android 13/API 33: only hex/octal prefixes. Binary prefixes were
  // added in Android 14/API 34, so "0b2" consumes just its leading zero here.
  if(!base)base=*p=='0'?8:10;
  const uint64_t limit=is_signed?(negative?UINT64_C(1)<<63:uint64_t(INT64_MAX)):UINT64_MAX;
  uint64_t value=0;bool any=false,overflow=false;
  for(int digit;(digit=Digit(static_cast<unsigned char>(*p)))<base;++p){
    any=true;if(value>(limit-unsigned(digit))/unsigned(base))overflow=true;
    else if(!overflow)value=value*unsigned(base)+unsigned(digit);
  }
  if(!any)return 0;if(end)pm::Write(end,const_cast<char*>(text+(p-snapshot.c_str())));
  if(overflow){Fail(34);return is_signed&&negative?UINT64_C(1)<<63:limit;}
  return negative?uint64_t(0)-value:value;
}
void LibC::BuildEnvironment(){
  std::vector<char*> next;
  char **array=nullptr;
  try{
    next.reserve(environment_.size()+1);
    for(const auto &entry:environment_){
      auto value=entry.first+'='+entry.second;auto text=static_cast<char*>(Malloc(value.size()+1));
      if(!text)throw std::bad_alloc();next.push_back(text);
      recomp::WriteGuestMemory(pm::Address(text),value.c_str(),value.size()+1);
    }
    next.push_back(nullptr);array=static_cast<char**>(Malloc(next.size()*sizeof(char*)));
    if(!array)throw std::bad_alloc();
    recomp::WriteGuestMemory(pm::Address(array),next.data(),next.size()*sizeof(char*));next.pop_back();
  }catch(...){Free(array);for(auto p:next)Free(p);throw;}
  pm::Write(&environment_slot_,array);
  auto previous=environment_array_;environment_array_=array;environment_strings_.swap(next);
  Free(previous);for(auto text:next)Free(text);
}
void LibC::SetEnvironment(std::map<std::string,std::string> values){
  for(auto &v:values)if(v.first.empty()||v.first.find('=')!=std::string::npos||v.first.find('\0')!=std::string::npos||v.second.find('\0')!=std::string::npos)throw std::invalid_argument("invalid virtual environment");
  std::lock_guard<std::recursive_mutex> lock(mutex_);environment_=std::move(values);BuildEnvironment();
}
char *LibC::Getenv(const char *name){
  if(!name)return nullptr;auto key=pm::String(name);std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=environment_.find(key);
  return i==environment_.end()?nullptr:environment_strings_[std::distance(environment_.begin(),i)]+key.size()+1;
}
int LibC::Setenv(const char *name,const char *value,int overwrite){
  if(!name||!value){Fail(22);return -1;}auto key=pm::String(name),text=pm::String(value);
  if(key.empty()||key.find('=')!=std::string::npos){Fail(22);return -1;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);if(!overwrite&&environment_.count(key))return 0;
  environment_[key]=std::move(text);BuildEnvironment();return 0;
}
int LibC::Unsetenv(const char *name){
  if(!name){Fail(22);return -1;}auto key=pm::String(name);
  if(key.empty()||key.find('=')!=std::string::npos){Fail(22);return -1;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);environment_.erase(key);BuildEnvironment();return 0;
}
int LibC::RegisterExit(addr_t callback,addr_t argument,addr_t dso,bool plain){
  if(!runner_||!callback){Fail(22);return -1;}std::lock_guard<std::recursive_mutex> lock(mutex_);
  try{exits_.push_back({callback,argument,dso,plain,false});}catch(...){Fail(12);return -1;}return 0;
}
void LibC::Finalize(addr_t dso){
  for(;;){Exit entry{};bool found=false;{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    for(auto i=exits_.rbegin();i!=exits_.rend();++i)if(!i->called&&(!dso||i->dso==dso)){i->called=true;entry=*i;found=true;break;}
  }if(!found)return;
    try{runner_(entry.callback,entry.plain?std::vector<addr_t>{}:std::vector<addr_t>{entry.argument});}
    catch(...){
      char context[224];
      std::snprintf(context,sizeof(context),"__cxa_finalize callback=%#llx argument=%#llx dso=%#llx filter=%#llx%s: ",
        static_cast<unsigned long long>(entry.callback),static_cast<unsigned long long>(entry.argument),
        static_cast<unsigned long long>(entry.dso),static_cast<unsigned long long>(dso),entry.plain?" plain-atexit":"");
      try{throw;}catch(const std::exception &error){throw std::runtime_error(std::string(context)+error.what());}
      catch(...){throw std::runtime_error(std::string(context)+"non-standard C++ exception");}
    }
  }
}
void LibC::Install(recomp::Runtime &runtime){
  if(installed_)throw std::logic_error("libc imports already installed");
  Add<void*(uint64_t)>(runtime,"malloc",[this](auto n){return Malloc(n);});
  Add<void*(uint64_t,uint64_t)>(runtime,"calloc",[this](auto n,auto s){return Calloc(n,s);});
  Add<void*(void*,uint64_t)>(runtime,"realloc",[this](auto p,auto n){return Realloc(p,n);});
  Add<void(void*)>(runtime,"free",[this](auto p){Free(p);});
  Add<void*(uint64_t,uint64_t)>(runtime,"memalign",[this](auto a,auto n){return Memalign(a,n);});
  Add<int32_t(void**,uint64_t,uint64_t)>(runtime,"posix_memalign",[this](auto p,auto a,auto n){return PosixMemalign(p,a,n);});
  Add<void*(uint64_t,uint64_t)>(runtime,"aligned_alloc",[this](auto a,auto n)->void*{if(!a||n%a){Fail(22);return nullptr;}return Memalign(a,n);});
  for(auto name:{"memcpy","memmove"})Add<void*(void*,const void*,uint64_t)>(runtime,name,pm::Copy);
  Add<void*(void*,int32_t,uint64_t)>(runtime,"memset",pm::Fill);
  Add<int32_t(const void*,const void*,uint64_t)>(runtime,"memcmp",[](auto a,auto b,auto n){if(!n)return 0;auto x=pm::Bytes(a,n),y=pm::Bytes(b,n);return std::memcmp(x.data(),y.data(),n);});
  Add<const void*(const void*,int32_t,uint64_t)>(runtime,"memchr",[](auto p,auto c,auto n)->const void*{if(!n)return nullptr;auto bytes=pm::Bytes(p,n);auto found=static_cast<const unsigned char*>(std::memchr(bytes.data(),c,n));return found?static_cast<const unsigned char*>(p)+(found-bytes.data()):nullptr;});
  Add<const void*(const void*,int32_t,uint64_t)>(runtime,"memrchr",[](auto p,auto c,auto n)->const void*{auto bytes=pm::Bytes(p,n);while(n)if(bytes[--n]==static_cast<unsigned char>(c))return static_cast<const unsigned char*>(p)+n;return nullptr;});
  Add<uint64_t(const char*)>(runtime,"strlen",[](auto s){return uint64_t(pm::String(s).size());});
  Add<uint64_t(const char*,uint64_t)>(runtime,"strnlen",[](auto s,auto n){return uint64_t(pm::String(s,n).size());});
  for(auto name:{"strcmp","strcoll"})Add<int32_t(const char*,const char*)>(runtime,name,[](auto a,auto b){auto x=pm::String(a),y=pm::String(b);return std::strcmp(x.c_str(),y.c_str());});
  Add<int32_t(const char*,const char*,uint64_t)>(runtime,"strncmp",[](auto a,auto b,auto n){auto x=pm::String(a,n),y=pm::String(b,n);return std::strncmp(x.c_str(),y.c_str(),n);});
  Add<char*(char*,const char*)>(runtime,"strcpy",[](auto a,auto b){auto text=pm::String(b);recomp::WriteGuestMemory(pm::Address(a),text.c_str(),text.size()+1);return a;});
  Add<char*(char*,const char*,uint64_t)>(runtime,"strncpy",[](auto a,auto b,auto n){auto text=pm::String(b,n);std::vector<char> result(n,0);if(!text.empty())std::memcpy(result.data(),text.data(),text.size());recomp::WriteGuestMemory(pm::Address(a),result.data(),n);return a;});
  Add<char*(char*,const char*)>(runtime,"strcat",[](auto a,auto b){auto prefix=pm::String(a),text=pm::String(b);recomp::WriteGuestMemory(pm::Address(a)+prefix.size(),text.c_str(),text.size()+1);return a;});
  Add<char*(char*,const char*,uint64_t)>(runtime,"strncat",[](auto a,auto b,auto n){auto prefix=pm::String(a),text=pm::String(b,n);recomp::WriteGuestMemory(pm::Address(a)+prefix.size(),text.c_str(),text.size()+1);return a;});
  Add<uint64_t(char*,const char*,uint64_t)>(runtime,"strlcpy",[](auto d,auto s,auto n){auto text=pm::String(s);auto length=text.size();if(n){text.resize(std::min<uint64_t>(length,n-1));recomp::WriteGuestMemory(pm::Address(d),text.c_str(),text.size()+1);}return uint64_t(length);});
  Add<uint64_t(char*,const char*,uint64_t)>(runtime,"strxfrm",[](auto d,auto s,auto n){auto text=pm::String(s);if(n>text.size())recomp::WriteGuestMemory(pm::Address(d),text.c_str(),text.size()+1);return uint64_t(text.size());});
  Add<const char*(const char*,int32_t)>(runtime,"strchr",[](auto s,auto c){auto text=pm::String(s);return pm::Locate(s,text,std::strchr(text.c_str(),c));});
  Add<const char*(const char*,int32_t)>(runtime,"strrchr",[](auto s,auto c){auto text=pm::String(s);return pm::Locate(s,text,std::strrchr(text.c_str(),c));});
  Add<const char*(const char*,const char*)>(runtime,"strstr",[](auto s,auto t){auto text=pm::String(s),needle=pm::String(t);return pm::Locate(s,text,std::strstr(text.c_str(),needle.c_str()));});
  Add<const char*(const char*,const char*)>(runtime,"strpbrk",[](auto s,auto t){auto text=pm::String(s),set=pm::String(t);return pm::Locate(s,text,std::strpbrk(text.c_str(),set.c_str()));});
  Add<uint64_t(const char*,const char*)>(runtime,"strspn",[](auto s,auto t){auto text=pm::String(s),set=pm::String(t);return uint64_t(std::strspn(text.c_str(),set.c_str()));});
  Add<uint64_t(const char*,const char*)>(runtime,"strcspn",[](auto s,auto t){auto text=pm::String(s),set=pm::String(t);return uint64_t(std::strcspn(text.c_str(),set.c_str()));});
  for(auto name:{"strdup","strndup"}){
    auto dup=[this](const char*s,uint64_t n)->char*{auto text=pm::String(s,n);auto d=static_cast<char*>(Malloc(text.size()+1));if(d)recomp::WriteGuestMemory(pm::Address(d),text.c_str(),text.size()+1);return d;};
    if(std::strcmp(name,"strdup")==0)Add<char*(const char*)>(runtime,name,[dup](auto s){return dup(s,UINT64_MAX);});
    else Add<char*(const char*,uint64_t)>(runtime,name,dup);
  }
  Add<char*(char*,const char*,char**)>(runtime,"strtok_r",[](char*s,const char*sep,char**save)->char*{
    if(!s)s=pm::Read(save);if(!s)return nullptr;auto text=pm::String(s),set=pm::String(sep);
    size_t start=std::strspn(text.c_str(),set.c_str());if(start==text.size()){pm::Write(save,s+start);return nullptr;}
    size_t end=start+std::strcspn(text.c_str()+start,set.c_str());bool delimiter=end<text.size();
    if(delimiter)pm::Write(s+end,char(0));pm::Write(save,s+end+size_t(delimiter));return s+start;});
  Add<int32_t(const char*,const char*)>(runtime,"strcasecmp",[](auto a,auto b){auto x=pm::String(a),y=pm::String(b);return CompareCase(x.c_str(),y.c_str(),UINT64_MAX);});
  Add<int32_t(const char*,const char*,uint64_t)>(runtime,"strncasecmp",[](auto a,auto b,auto n){auto x=pm::String(a,n),y=pm::String(b,n);return CompareCase(x.c_str(),y.c_str(),n);});
  for(auto name:{"isalnum","isalpha","isblank","iscntrl","isdigit","isgraph","islower","isprint","ispunct","isspace","isupper","isxdigit"}){
    Add<int32_t(int32_t)>(runtime,name,[name](int32_t c){bool lower=c>='a'&&c<='z',upper=c>='A'&&c<='Z',digit=c>='0'&&c<='9',graph=c>=33&&c<=126;
      if(!std::strcmp(name,"isalnum"))return int(lower||upper||digit);if(!std::strcmp(name,"isalpha"))return int(lower||upper);
      if(!std::strcmp(name,"isblank"))return int(c==' '||c=='\t');if(!std::strcmp(name,"iscntrl"))return int((c>=0&&c<32)||c==127);
      if(!std::strcmp(name,"isdigit"))return int(digit);if(!std::strcmp(name,"isgraph"))return int(graph);
      if(!std::strcmp(name,"islower"))return int(lower);if(!std::strcmp(name,"isprint"))return int(c>=32&&c<=126);
      if(!std::strcmp(name,"ispunct"))return int(graph&&!lower&&!upper&&!digit);if(!std::strcmp(name,"isspace"))return int(Space(c));
      if(!std::strcmp(name,"isupper"))return int(upper);return int(Digit(c)<16);
    });
  }
  Add<int32_t(int32_t)>(runtime,"tolower",Lower);Add<int32_t(int32_t)>(runtime,"toupper",Upper);
  for(auto name:{"strtol","strtoll","strtoul","strtoull"})Add<uint64_t(const char*,char**,int32_t)>(runtime,name,[this,name](auto s,auto e,auto b){return ParseInteger(s,e,b,std::strcmp(name,"strtoul")&&std::strcmp(name,"strtoull"));});
  Add<int32_t(const char*)>(runtime,"atoi",[this](auto s){return static_cast<int32_t>(ParseInteger(s,nullptr,10,true));});
  for(auto name:{"atol","atoll"})Add<uint64_t(const char*)>(runtime,name,[this](auto s){return ParseInteger(s,nullptr,10,true);});
  Add<double(const char*,char**)>(runtime,"strtod",[this](auto s,auto e){auto r=ParseFloating<double>(s,e);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<float(const char*,char**)>(runtime,"strtof",[this](auto s,auto e){auto r=ParseFloating<float>(s,e);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<double(const char*)>(runtime,"atof",[this](auto s){auto r=ParseFloating<double>(s,nullptr);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<char*(const char*)>(runtime,"getenv",[this](auto n){return Getenv(n);});
  Add<int32_t(const char*,const char*,int32_t)>(runtime,"setenv",[this](auto n,auto v,auto o){return Setenv(n,v,o);});
  Add<int32_t(const char*)>(runtime,"unsetenv",[this](auto n){return Unsetenv(n);});
  Add<int32_t(addr_t,addr_t,addr_t)>(runtime,"__cxa_atexit",[this](auto c,auto a,auto d){return RegisterExit(c,a,d);});
  Add<void(addr_t)>(runtime,"__cxa_finalize",[this](auto d){Finalize(d);});
  Add<int32_t(addr_t)>(runtime,"atexit",[this](auto c){return RegisterExit(c,0,0,true);});
  Add<void()>(runtime,"__stack_chk_fail",[this]{Fatal("stack protector check failed");});
  Add<void()>(runtime,"abort",[this]{Fatal("abort");});
  Add<void(int32_t)>(runtime,"exit",[this](auto code){Finalize();std::exit(code);});
  Add<void(const char*)>(runtime,"android_set_abort_message",[this](auto s){auto message=s?pm::String(s):std::string();std::lock_guard<std::recursive_mutex> lock(mutex_);abort_message_=std::move(message);});
  Add<uint64_t()>(runtime,"__ctype_get_mb_cur_max",[this]{return LocaleMbCurMax();});
#define MATH1(name,type) Add<type(type)>(runtime,#name,[this](type x){auto r=Math([](type v){return ::name(v);},x);if(r.second)Fail(r.second==EDOM?33:34);return r.first;})
#define MATH2(name,type) Add<type(type,type)>(runtime,#name,[this](type x,type y){auto r=Math([](type a,type b){return ::name(a,b);},x,y);if(r.second)Fail(r.second==EDOM?33:34);return r.first;})
  MATH1(sin,double);MATH1(sinf,float);MATH1(cos,double);MATH1(cosf,float);MATH1(tan,double);MATH1(tanf,float);
  MATH1(asin,double);MATH1(asinf,float);MATH1(acos,double);MATH1(acosf,float);MATH1(atan,double);MATH1(atanf,float);
  MATH2(atan2,double);MATH2(atan2f,float);MATH1(exp,double);MATH1(expf,float);MATH1(exp2f,float);
  MATH1(log,double);MATH1(logf,float);MATH1(log10,double);MATH1(log10f,float);MATH1(log2f,float);MATH1(logb,double);
  MATH2(pow,double);MATH2(powf,float);MATH1(sqrt,double);MATH1(sqrtf,float);MATH2(hypot,double);
  MATH2(fmod,double);MATH2(fmodf,float);MATH2(remainderf,float);MATH1(nearbyintf,float);
#undef MATH1
#undef MATH2
  Add<double(double,int32_t)>(runtime,"ldexp",[this](auto x,auto n){auto r=Math([](double a,int b){return std::ldexp(a,b);},x,n);if(r.second)Fail(34);return r.first;});
  Add<float(float,int32_t)>(runtime,"ldexpf",[this](auto x,auto n){auto r=Math([](float a,int b){return std::ldexp(a,b);},x,n);if(r.second)Fail(34);return r.first;});
  Add<double(double,int32_t)>(runtime,"scalbn",[this](auto x,auto n){auto r=Math([](double a,int b){return std::scalbn(a,b);},x,n);if(r.second)Fail(34);return r.first;});
  Add<float(float,int32_t*)>(runtime,"frexpf",[](auto x,auto p){int32_t exponent;auto fraction=std::frexp(x,&exponent);pm::Write(p,exponent);return fraction;});
  Add<double(double,double*)>(runtime,"modf",[](auto x,auto p){double integral;auto fraction=std::modf(x,&integral);pm::Write(p,integral);return fraction;});
  Add<float(float,float*)>(runtime,"modff",[](auto x,auto p){float integral;auto fraction=std::modf(x,&integral);pm::Write(p,integral);return fraction;});
  Add<int32_t()>(runtime,"getpagesize",[this]{
#ifdef _WIN32
    SYSTEM_INFO info{};GetSystemInfo(&info);const uint64_t size=info.dwPageSize;
#else
    const auto size=::sysconf(_SC_PAGESIZE);
#endif
    if(!(size>0&&size<=INT32_MAX))Fatal("invalid host memory page size");return static_cast<int32_t>(size);
  });
  Add<addr_t(int32_t,const char*,addr_t)>(runtime,"newlocale",[this](auto mask,auto name,auto base){return NewLocale(mask,name,base);});
  Add<void(addr_t)>(runtime,"freelocale",[this](auto locale){FreeLocale(locale);});
  Add<addr_t(addr_t)>(runtime,"uselocale",[this](auto locale){return UseLocale(locale);});
  Add<int64_t()>(runtime,"clock",[this]{return ProcessClock();});
  Add<int64_t(int32_t)>(runtime,"sysconf",[this](auto name){return Sysconf(name);});
  installed_=true;
}
}  // namespace bunker::windows
