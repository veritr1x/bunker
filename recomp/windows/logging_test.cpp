#include "logging.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#endif
static unsigned checks;
static void check(bool value,const char *why) {
  ++checks;if(!value){std::fprintf(stderr,"logging check failed: %s\n",why);std::exit(1);}
}
int main(int argc,char **) {
  bunker::windows::Logging log;
  recomp::Runtime runtime;log.Install(runtime);
  auto call=[&](const char *name,std::initializer_list<uint64_t> values) {
    State s{};Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};
    size_t i=0;for(auto value:values)(s.gpr.*registers[i++]).qword=value;
    s.gpr.x30.qword=0xfeedffff;runtime.Run(s,log.Marker(name));
    check(s.gpr.pc.qword==0xfeedffff,"import returns to guest LR");
    return static_cast<int32_t>(s.gpr.x0.qword);
  };
  auto ptr=[](auto value){return reinterpret_cast<uint64_t>(value);};
  if(argc>1){
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
    call("__android_log_assert",{ptr("condition"),ptr("tag"),ptr("fatal %d"),42});return 0;
  }
  std::string output,tag,text;int priority=0,error=0;
  log.SetOutput([&](std::string_view s){output.assign(s);return true;});
  log.SetLog([&](int p,std::string_view t,std::string_view s){priority=p;tag=t;text=s;return true;});
  log.SetErrorSink([&](int e){error=e;});
  char buffer[32];std::memset(buffer,0x55,sizeof(buffer));
  check(call("snprintf",{ptr(buffer),4,ptr("%s:%d"),ptr("hello"),123})==9&&std::string(buffer)=="hel"&&buffer[4]==0x55,"bounded write and full logical count");
  check(call("snprintf",{0,0,ptr("%d"),12345})==5,"size zero allows null destination");
  check(call("snprintf",{0,1,ptr("%d"),1})==-1&&error==22,"null writable destination fails EINVAL");
  for(const char *format:{"%n","%2$d","%Lf","%ls","%"}) {
    std::strcpy(buffer,"unchanged");
    check(call("sprintf",{ptr(buffer),ptr(format),0})==-1&&error==22&&std::string(buffer)=="unchanged","unsupported format checked before destination writes");
  }
  check(call("printf",{ptr("A%cB"),0})==3&&output==std::string("A\0B",3),"stdout preserves embedded NUL");
  check(call("puts",{ptr("line")})>=0&&output=="line\n","puts newline");
  check(call("__android_log_print",{4,ptr("tag"),ptr("x=%ld"),UINT64_C(0x100000000)})==1&&priority==4&&tag=="tag"&&text=="x=4294967296","Android log success is one and uses LP64");
  check(call("__android_log_write",{5,ptr("raw"),ptr("text")})==1&&priority==5&&tag=="raw"&&text=="text","unformatted log");
  log.SetLog([](int,std::string_view,std::string_view){return false;});
  check(call("__android_log_write",{4,0,ptr("filtered")})==-1&&error==1,"filtered Android log is -EPERM");
  log.SetOutput([](std::string_view){return false;});
  check(call("printf",{ptr("failure")})==-1&&error==5,"stdout sink failure");
  log.SetOutput([](std::string_view)->bool{throw std::runtime_error("sink");});
  check(call("printf",{ptr("throw")})==-1&&error==22,"sink exception cannot escape guest frame");
  check(call("fprintf",{123,ptr("file")})==-1&&error==38,"missing opaque FILE writer is ENOSYS");
  log.SetStream([&](addr_t stream,std::string_view s){check(stream==123,"opaque guest FILE forwarded");output=s;return s.size();});
  check(call("fprintf",{123,ptr("file:%d"),17})==7&&output=="file:17","FILE callback writes bytes");
  log.SetStream([](addr_t,std::string_view){return 0;});
  check(call("fprintf",{123,ptr("file")})==-1&&error==5,"short FILE write fails");
  char *allocated=reinterpret_cast<char *>(1);
  check(call("asprintf",{ptr(&allocated),ptr("%ld:%s"),UINT64_C(0x100000000),ptr("heap")})==15&&allocated&&std::string(allocated)=="4294967296:heap","asprintf host allocation");
  std::free(allocated);allocated=reinterpret_cast<char *>(1);
  check(call("asprintf",{ptr(&allocated),ptr("%n"),0})==-1&&!allocated,"asprintf failure clears result");
  uint64_t gp[]={UINT64_C(0x100000000),ptr("va")};
  struct {uint64_t stack,gr,vr;int32_t go,vo;} va={0,ptr(gp+2),0,-16,0};
  check(call("vasprintf",{ptr(&allocated),ptr("%ld:%s"),ptr(&va)})==13&&allocated&&std::string(allocated)=="4294967296:va","vasprintf consumes AAPCS64 save area");
  std::free(allocated);
  log.SetStream([&](addr_t stream,std::string_view s){check(stream==123,"va opaque guest FILE forwarded");output=s;return s.size();});
  check(call("vfprintf",{123,ptr("%ld:%s"),ptr(&va)})==13&&output=="4294967296:va","vfprintf uses guest va_list and opaque FILE callback");
  check(va.go==-16,"vfprintf leaves caller va_list unchanged");
  log.SetLog([&](int p,std::string_view t,std::string_view s){priority=p;tag=t;text=s;return true;});
  call("openlog",{ptr("ident"),0,0});call("syslog",{6,ptr("event:%d"),7});
  check(priority==6&&tag=="ident"&&text=="event:7","syslog forwards identity priority and formatted message");
  call("closelog",{});call("syslog",{6,ptr("next")});check(tag.empty()&&text=="next","closelog clears identity");
  bool rejected=false;try{log.Marker("swprintf");}catch(const std::invalid_argument&){rejected=true;}check(rejected,"wide formatting remains explicitly unresolved");
  std::printf("Logging provider: %u checks passed.\n",checks);
}
