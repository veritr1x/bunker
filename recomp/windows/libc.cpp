#include "libc.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace bunker::windows {
namespace {
thread_local int guest_error;
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
  "fmod", "fmodf", "remainderf", "nearbyintf", "ldexp", "ldexpf", "scalbn", "frexpf", "modf", "modff"
};
bool Space(int c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
int Lower(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
int Upper(int c) { return c >= 'a' && c <= 'z' ? c - 32 : c; }
int Digit(int c) { if(c>='0'&&c<='9')return c-'0';c=Lower(c);return c>='a'&&c<='z'?c-'a'+10:99; }
int CompareCase(const char *a,const char *b,uint64_t count) {
  for(uint64_t i=0;i<count;++i) { int x=Lower(static_cast<unsigned char>(a[i])),y=Lower(static_cast<unsigned char>(b[i]));if(x!=y)return x-y;if(!x)return 0; }return 0;
}
uint64_t Length(const char *s,uint64_t n) {uint64_t i=0;while(i<n&&s[i])++i;return i;}
template <typename F,typename... A> auto Math(F function,A... args) {
  errno=0;auto result=function(args...);return std::make_pair(result,errno);
}
}
LibC::LibC(Runner runner,addr_t base):runner_(std::move(runner)),marker_base_(base) {
  if((base&7)||base>UINT64_MAX-sizeof(imports)/sizeof(*imports)*8)throw std::invalid_argument("invalid libc marker base");
  BuildEnvironment();
}
int LibC::Error()const{return guest_error;}
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
    try{bridge(state);}catch(...){Fatal(name);}
  });
}
void *LibC::Malloc(uint64_t size){
  if(size>INT64_MAX){Fail(12);return nullptr;}auto p=std::malloc(static_cast<size_t>(size?size:1));if(!p)Fail(12);return p;
}
void *LibC::Calloc(uint64_t n,uint64_t size){
  if(size&&n>uint64_t(INT64_MAX)/size){Fail(12);return nullptr;}uint64_t total=n*size;
  auto p=std::calloc(1,static_cast<size_t>(total?total:1));if(!p)Fail(12);return p;
}
void LibC::Free(void *p){
  if(!p)return;std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=aligned_.find(p);
  if(i==aligned_.end())std::free(p);else{std::free(i->second.base);aligned_.erase(i);}
}
void *LibC::AlignedAllocate(uint64_t alignment,uint64_t size,bool set_errno){
  if(!alignment||(alignment&(alignment-1))){if(set_errno)Fail(22);return nullptr;}
  alignment=std::max<uint64_t>(alignment,16);
  if(alignment>uint64_t(INT64_MAX)||size>uint64_t(INT64_MAX)-alignment){if(set_errno)Fail(12);return nullptr;}
  void *base=std::malloc(static_cast<size_t>((size?size:1)+alignment));
  if(!base){if(set_errno)Fail(12);return nullptr;}
  auto p=reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(base)+alignment-1)&~uintptr_t(alignment-1));
  try{std::lock_guard<std::recursive_mutex> lock(mutex_);aligned_.emplace(p,Aligned{base,size,alignment});}
  catch(...){std::free(base);if(set_errno)Fail(12);return nullptr;}return p;
}
void *LibC::Memalign(uint64_t alignment,uint64_t size){return AlignedAllocate(alignment,size,true);}
int LibC::PosixMemalign(void **out,uint64_t alignment,uint64_t size){
  if(!out||alignment<sizeof(void*)||(alignment&(alignment-1)))return 22;
  auto p=AlignedAllocate(alignment,size,false);if(!p)return 12;*out=p;return 0;
}
void *LibC::Realloc(void *p,uint64_t size){
  if(!p)return Malloc(size);if(!size){Free(p);return nullptr;}if(size>INT64_MAX){Fail(12);return nullptr;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=aligned_.find(p);
  if(i!=aligned_.end()){
    const auto old=i->second;auto q=AlignedAllocate(old.alignment,size,true);if(!q)return nullptr;
    std::memcpy(q,p,static_cast<size_t>(std::min(size,old.size)));Free(p);return q;
  }
  auto q=std::realloc(p,static_cast<size_t>(size));if(!q)Fail(12);return q;
}
uint64_t LibC::ParseInteger(const char *text,char **end,int base,bool is_signed){
  if(end)*end=const_cast<char*>(text);
  if(!text||base<0||base==1||base>36){Fail(22);return 0;}
  const char *p=text;while(Space(static_cast<unsigned char>(*p)))++p;
  bool negative=*p=='-';if(*p=='-'||*p=='+')++p;
  if((base==0||base==16)&&p[0]=='0'&&(p[1]=='x'||p[1]=='X')&&Digit(static_cast<unsigned char>(p[2]))<16){base=16;p+=2;}
  // Modern Bionic also accepts the C23 binary prefix. Never use host Windows long.
  if((base==0||base==2)&&p[0]=='0'&&(p[1]=='b'||p[1]=='B')&&p[2]>='0'&&p[2]<='9'){base=2;p+=2;}
  if(!base)base=*p=='0'?8:10;
  const uint64_t limit=is_signed?(negative?UINT64_C(1)<<63:uint64_t(INT64_MAX)):UINT64_MAX;
  uint64_t value=0;bool any=false,overflow=false;
  for(int digit;(digit=Digit(static_cast<unsigned char>(*p)))<base;++p){
    any=true;if(value>(limit-unsigned(digit))/unsigned(base))overflow=true;
    else if(!overflow)value=value*unsigned(base)+unsigned(digit);
  }
  if(!any)return 0;if(end)*end=const_cast<char*>(p);
  if(overflow){Fail(34);return is_signed&&negative?UINT64_C(1)<<63:limit;}
  return negative?uint64_t(0)-value:value;
}
void LibC::BuildEnvironment(){
  environment_text_.clear();environment_pointers_.clear();environment_text_.reserve(environment_.size());
  for(const auto &v:environment_)environment_text_.push_back(v.first+'='+v.second);
  for(auto &v:environment_text_)environment_pointers_.push_back(v.data());environment_pointers_.push_back(nullptr);environment_slot_=environment_pointers_.data();
}
void LibC::SetEnvironment(std::map<std::string,std::string> values){
  for(auto &v:values)if(v.first.empty()||v.first.find('=')!=std::string::npos||v.first.find('\0')!=std::string::npos||v.second.find('\0')!=std::string::npos)throw std::invalid_argument("invalid virtual environment");
  std::lock_guard<std::recursive_mutex> lock(mutex_);environment_=std::move(values);BuildEnvironment();
}
char *LibC::Getenv(const char *name){
  if(!name)return nullptr;std::lock_guard<std::recursive_mutex> lock(mutex_);auto i=environment_.find(name);return i==environment_.end()?nullptr:i->second.data();
}
int LibC::Setenv(const char *name,const char *value,int overwrite){
  if(!name||!*name||std::strchr(name,'=')||!value){Fail(22);return -1;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);if(!overwrite&&environment_.count(name))return 0;
  environment_[name]=value;BuildEnvironment();return 0;
}
int LibC::Unsetenv(const char *name){
  if(!name||!*name||std::strchr(name,'=')){Fail(22);return -1;}
  std::lock_guard<std::recursive_mutex> lock(mutex_);environment_.erase(name);BuildEnvironment();return 0;
}
int LibC::RegisterExit(addr_t callback,addr_t argument,addr_t dso,bool plain){
  if(!runner_||!callback){Fail(22);return -1;}std::lock_guard<std::recursive_mutex> lock(mutex_);
  try{exits_.push_back({callback,argument,dso,plain,false});}catch(...){Fail(12);return -1;}return 0;
}
void LibC::Finalize(addr_t dso){
  for(;;){Exit entry{};bool found=false;{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    for(auto i=exits_.rbegin();i!=exits_.rend();++i)if(!i->called&&(!dso||i->dso==dso)){i->called=true;entry=*i;found=true;break;}
  }if(!found)return;runner_(entry.callback,entry.plain?std::vector<addr_t>{}:std::vector<addr_t>{entry.argument});}
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
  Add<void*(void*,const void*,uint64_t)>(runtime,"memcpy",[](auto d,auto s,auto n){return std::memcpy(d,s,n);});
  Add<void*(void*,const void*,uint64_t)>(runtime,"memmove",[](auto d,auto s,auto n){return std::memmove(d,s,n);});
  Add<void*(void*,int32_t,uint64_t)>(runtime,"memset",[](auto d,auto c,auto n){return std::memset(d,c,n);});
  Add<int32_t(const void*,const void*,uint64_t)>(runtime,"memcmp",[](auto a,auto b,auto n){return std::memcmp(a,b,n);});
  Add<const void*(const void*,int32_t,uint64_t)>(runtime,"memchr",[](auto p,auto c,auto n){return std::memchr(p,c,n);});
  Add<const void*(const void*,int32_t,uint64_t)>(runtime,"memrchr",[](auto p,auto c,auto n)->const void*{auto b=static_cast<const unsigned char*>(p);while(n)if(b[--n]==static_cast<unsigned char>(c))return b+n;return nullptr;});
  Add<uint64_t(const char*)>(runtime,"strlen",[](auto s){return uint64_t(std::strlen(s));});
  Add<uint64_t(const char*,uint64_t)>(runtime,"strnlen",[](auto s,auto n){return Length(s,n);});
  for(auto name:{"strcmp","strcoll"})Add<int32_t(const char*,const char*)>(runtime,name,[](auto a,auto b){return std::strcmp(a,b);});
  Add<int32_t(const char*,const char*,uint64_t)>(runtime,"strncmp",[](auto a,auto b,auto n){return std::strncmp(a,b,n);});
  Add<char*(char*,const char*)>(runtime,"strcpy",[](auto a,auto b){return std::strcpy(a,b);});
  Add<char*(char*,const char*,uint64_t)>(runtime,"strncpy",[](auto a,auto b,auto n){return std::strncpy(a,b,n);});
  Add<char*(char*,const char*)>(runtime,"strcat",[](auto a,auto b){return std::strcat(a,b);});
  Add<char*(char*,const char*,uint64_t)>(runtime,"strncat",[](auto a,auto b,auto n){return std::strncat(a,b,n);});
  Add<uint64_t(char*,const char*,uint64_t)>(runtime,"strlcpy",[](auto d,auto s,auto n){auto length=std::strlen(s);if(n){auto copy=std::min<uint64_t>(length,n-1);std::memcpy(d,s,copy);d[copy]=0;}return uint64_t(length);});
  Add<uint64_t(char*,const char*,uint64_t)>(runtime,"strxfrm",[](auto d,auto s,auto n){auto length=std::strlen(s);if(n>length)std::memcpy(d,s,length+1);return uint64_t(length);});
  Add<const char*(const char*,int32_t)>(runtime,"strchr",[](auto s,auto c){return std::strchr(s,c);});
  Add<const char*(const char*,int32_t)>(runtime,"strrchr",[](auto s,auto c){return std::strrchr(s,c);});
  Add<const char*(const char*,const char*)>(runtime,"strstr",[](auto s,auto t){return std::strstr(s,t);});
  Add<const char*(const char*,const char*)>(runtime,"strpbrk",[](auto s,auto t){return std::strpbrk(s,t);});
  Add<uint64_t(const char*,const char*)>(runtime,"strspn",[](auto s,auto t){return uint64_t(std::strspn(s,t));});
  Add<uint64_t(const char*,const char*)>(runtime,"strcspn",[](auto s,auto t){return uint64_t(std::strcspn(s,t));});
  for(auto name:{"strdup","strndup"}){
    auto dup=[this](const char*s,uint64_t n)->char*{auto length=Length(s,n);auto d=static_cast<char*>(Malloc(length+1));if(d){std::memcpy(d,s,length);d[length]=0;}return d;};
    if(std::strcmp(name,"strdup")==0)Add<char*(const char*)>(runtime,name,[dup](auto s){return dup(s,UINT64_MAX);});
    else Add<char*(const char*,uint64_t)>(runtime,name,dup);
  }
  Add<char*(char*,const char*,char**)>(runtime,"strtok_r",[](char*s,const char*sep,char**save)->char*{
    if(!s)s=*save;if(!s)return nullptr;s+=std::strspn(s,sep);if(!*s){*save=s;return nullptr;}char *end=s+std::strcspn(s,sep);if(*end)*end++=0;*save=end;return s;});
  Add<int32_t(const char*,const char*)>(runtime,"strcasecmp",[](auto a,auto b){return CompareCase(a,b,UINT64_MAX);});
  Add<int32_t(const char*,const char*,uint64_t)>(runtime,"strncasecmp",CompareCase);
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
  Add<double(const char*,char**)>(runtime,"strtod",[this](auto s,auto e){auto r=Math([](auto a,auto b){return std::strtod(a,b);},s,e);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<float(const char*,char**)>(runtime,"strtof",[this](auto s,auto e){auto r=Math([](auto a,auto b){return std::strtof(a,b);},s,e);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<double(const char*)>(runtime,"atof",[this](auto s){auto r=Math([](auto a){return std::strtod(a,nullptr);},s);if(r.second)Fail(r.second==ERANGE?34:22);return r.first;});
  Add<char*(const char*)>(runtime,"getenv",[this](auto n){return Getenv(n);});
  Add<int32_t(const char*,const char*,int32_t)>(runtime,"setenv",[this](auto n,auto v,auto o){return Setenv(n,v,o);});
  Add<int32_t(const char*)>(runtime,"unsetenv",[this](auto n){return Unsetenv(n);});
  Add<int32_t(addr_t,addr_t,addr_t)>(runtime,"__cxa_atexit",[this](auto c,auto a,auto d){return RegisterExit(c,a,d);});
  Add<void(addr_t)>(runtime,"__cxa_finalize",[this](auto d){Finalize(d);});
  Add<int32_t(addr_t)>(runtime,"atexit",[this](auto c){return RegisterExit(c,0,0,true);});
  Add<void()>(runtime,"__stack_chk_fail",[this]{Fatal("stack protector check failed");});
  Add<void()>(runtime,"abort",[this]{Fatal("abort");});
  Add<void(int32_t)>(runtime,"exit",[this](auto code){Finalize();std::exit(code);});
  Add<void(const char*)>(runtime,"android_set_abort_message",[this](auto s){std::lock_guard<std::recursive_mutex> lock(mutex_);abort_message_=s?s:"";});
  Add<uint64_t()>(runtime,"__ctype_get_mb_cur_max",[]{return UINT64_C(1);});
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
  Add<float(float,int32_t*)>(runtime,"frexpf",[](auto x,auto p){return std::frexp(x,p);});
  Add<double(double,double*)>(runtime,"modf",[](auto x,auto p){return std::modf(x,p);});
  Add<float(float,float*)>(runtime,"modff",[](auto x,auto p){return std::modf(x,p);});
  installed_=true;
}
}  // namespace bunker::windows
