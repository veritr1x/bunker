#include "libc.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#ifdef _WIN32
#include <windows.h>
#endif
static unsigned checks;
static void check(bool value,const char *text){++checks;if(!value){std::fprintf(stderr,"libc check failed: %s\n",text);std::exit(1);}}
int main(int argc,char **argv){
  bunker::windows::LibC libc;recomp::Runtime runtime;libc.Install(runtime);int error=0;libc.SetErrorSink([&](int e){error=e;});
  if(argc>1){
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
    State s{};runtime.Run(s,libc.Marker(argv[1]));return 0;
  }
  check(!libc.Getenv("PATH"),"host environment is never inherited");
  libc.SetEnvironment({{"BUNKER","explicit"}});check(std::string(libc.Getenv("BUNKER"))=="explicit","explicit virtual environment");
  check(!libc.Setenv("BUNKER","retained",0)&&std::string(libc.Getenv("BUNKER"))=="explicit","setenv overwrite false");
  check(libc.Setenv("bad=name","x",1)==-1&&error==22,"invalid virtual environment fails");
  auto slot=reinterpret_cast<char***>(libc.Marker("environ"));check(*slot&&(*slot)[0]&&std::string((*slot)[0])=="BUNKER=explicit"&&!(*slot)[1],"environ is a guest-readable data export");
  auto p=static_cast<unsigned char*>(libc.Malloc(123));check(p&&!(reinterpret_cast<uintptr_t>(p)&15),"malloc16-byte alignment");std::memset(p,0xc3,123);
  check(!libc.Realloc(p,UINT64_MAX)&&error==12&&p[122]==0xc3,"failed realloc preserves original allocation");
  auto q=static_cast<unsigned char*>(libc.Realloc(p,2048));check(q&&q[0]==0xc3&&q[122]==0xc3,"realloc content");libc.Free(q);
  check(!libc.Calloc(UINT64_MAX,8)&&error==12,"calloc overflow");
  p=static_cast<unsigned char*>(libc.Calloc(31,7));for(unsigned i=0;i<217;++i)check(p[i]==0,"calloc clears all bytes");libc.Free(p);
  for(uint64_t alignment:{UINT64_C(16),UINT64_C(64),UINT64_C(4096)}){
    p=static_cast<unsigned char*>(libc.Memalign(alignment,513));check(p&&!(reinterpret_cast<uintptr_t>(p)&(alignment-1)),"aligned allocation");std::memset(p,0x97,513);
    q=static_cast<unsigned char*>(libc.Realloc(p,4097));check(q&&q[512]==0x97,"aligned realloc preserves data");libc.Free(q);
  }
  check(!libc.Memalign(1ULL<<63,1ULL<<63)&&error==12,"oversized aligned allocation cannot wrap");
  void *out=reinterpret_cast<void*>(0x1234);check(libc.PosixMemalign(&out,3,8)==22&&out==reinterpret_cast<void*>(0x1234),"invalid posix alignment leaves output unchanged");
  check(!libc.PosixMemalign(&out,64,31)&&!(reinterpret_cast<uintptr_t>(out)&63),"posix allocation freed by common free");libc.Free(out);
  // Logging's asprintf allocations use this same native malloc family.
  libc.Free(std::malloc(31));check(true,"common free accepts logging allocations");
  uint64_t seed=0x243f6a8885a308d3ULL;
  for(unsigned i=0;i<2000;++i){
    seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;char text[96];
    std::snprintf(text,sizeof(text),"%s%lluEND",i&1?"-":"",static_cast<unsigned long long>(seed));
    char *expected_end,*actual_end;errno=0;auto expected=std::strtoull(text,&expected_end,10);int expected_error=errno;
    auto actual=libc.ParseInteger(text,&actual_end,10,false);
    check(actual==expected&&actual_end-text==expected_end-text,"unsigned parser exact value/end pointer");
    errno=0;auto signed_expected=std::strtoll(text,&expected_end,10);expected_error=errno;
    actual=libc.ParseInteger(text,&actual_end,10,true);
    check(actual==static_cast<uint64_t>(signed_expected)&&actual_end-text==expected_end-text&&(!expected_error||error==34),"signed parser saturation and end pointer");
  }
  char *end;const char *binary="0b1011tail";check(libc.ParseInteger(binary,&end,0,false)==11&&end==binary+6,"Bionic binary prefix");
  for(unsigned mode=0;mode<4;++mode)for(unsigned negative=0;negative<2;++negative){
    State s{};s.fpcr.rmode=static_cast<FPURoundingMode>(mode);float value=negative?-1.25f:1.25f;std::memcpy(&s.simd.v[0],&value,4);
    runtime.Run(s,libc.Marker("nearbyintf"));float rounded;std::memcpy(&rounded,&s.simd.v[0],4);
    const float positive[]={1,2,1,1},minus[]={-1,-1,-2,-1};
    check(rounded==(negative?minus[mode]:positive[mode]),"imported nearbyintf follows guest rounding mode");
    check(!s.sr.ixc,"nearbyintf does not raise inexact");
  }
  check(libc.RegisterExit(1,2,3)==-1&&error==22,"callback registration requires a translated runner");
  std::vector<uint64_t> order;
  bunker::windows::LibC *active=nullptr;
  bunker::windows::LibC callbacks([&](addr_t entry,const std::vector<addr_t>&args){
    order.push_back(entry);if(entry==3){check(args.size()==1&&args[0]==33,"destructor argument");active->RegisterExit(4,44,1);active->Finalize(1);}else if(entry==9)check(args.empty(),"plain atexit has no argument");return 0;
  });active=&callbacks;
  callbacks.RegisterExit(1,11,1);callbacks.RegisterExit(2,22,2);callbacks.RegisterExit(3,33,1);callbacks.RegisterExit(9,0,0,true);
  callbacks.Finalize(1);check(order==std::vector<uint64_t>({3,4,1}),"DSO filtering/reverse order/reentrant registration and finalization");
  callbacks.Finalize(1);check(order.size()==3,"DSO destructors run once");callbacks.Finalize();check(order==std::vector<uint64_t>({3,4,1,9,2}),"global finalization includes plain and other DSO in reverse order");
  callbacks.Finalize();check(order.size()==5,"repeated global finalize does not rerun callbacks");
  bool rejected=false;try{libc.Marker("pthread_create");}catch(...){rejected=true;}check(rejected,"provider cannot claim another provider's imports");
  std::printf("Native Android-width libc: %u checks passed.\n",checks);
}
