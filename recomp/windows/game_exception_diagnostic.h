#pragma once
#include "../whole/runtime.h"
#include <windows.h>
#include <cerrno>
#include <cfenv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>

// Observation only. ReportNull retains the existing terminal behavior; Raise
// calls its configured original entry without correcting control transfer.
class GameExceptionDiagnostic {
 public:
  using Entry=Memory*(*)(State&,addr_t,Memory*);
  static void ConfigureRaise(Entry original,bool enabled){
    if(!original)throw std::invalid_argument("Raise observer original entry absent");
    raise_entry_=original;raise_enabled_=enabled;
  }
  static Memory* Raise(State&s,addr_t pc,Memory*m){
    if(!raise_enabled_)return raise_entry_(s,pc,m);
    const auto lr=s.gpr.x30.qword,sp=s.gpr.sp.qword,entry_pc=s.gpr.pc.qword,x21=s.gpr.x21.qword,object=s.gpr.x0.qword;
    const addr_t header=object>=0x60?object-0x60:0;
    Observe([&]{
      std::fprintf(stderr,"Game exception diagnostic: original Raise ENTER argumentPC=%#llx StatePC=%#llx LR=%#llx SP=%#llx X21=%#llx unwind_object=%#llx header=%#llx Memory=%p; observation only\n",U(pc),U(entry_pc),U(lr),U(sp),U(x21),U(object),U(header),static_cast<void*>(m));
      RaiseGot();Header("Raise entry original unwind-object-minus60 candidate",header);
    });
    Memory*result=raise_entry_(s,pc,m);
    Observe([&]{
      std::fprintf(stderr,"Game exception diagnostic: original Raise RETURN entryLR=%#llx StatePC=%#llx X30=%#llx SP=%#llx X21=%#llx reason_X0=%#llx different_return_PC=%d original_header=%#llx Memory=%p; original result, no dispatch/transfer correction\n",U(lr),U(s.gpr.pc.qword),U(s.gpr.x30.qword),U(s.gpr.sp.qword),U(s.gpr.x21.qword),U(s.gpr.x0.qword),s.gpr.pc.qword!=lr,U(header),static_cast<void*>(result));
      RaiseGot();Header("Raise return SAME original header candidate",header);
    });
    return result;
  }
  static void ReportNull(const State&s)noexcept{
    Observe([&]{
      std::fprintf(stderr,"Game exception diagnostic: terminal null target native_tid=%lu StatePC=%#llx LR=%#llx SP=%#llx FP=%#llx; read-only observation, fatal behavior retained\n",GetCurrentThreadId(),U(s.gpr.pc.qword),U(s.gpr.x30.qword),U(s.gpr.sp.qword),U(s.gpr.x29.qword));
      Globals();Registers(s);Frames(s);Stack(s);
      uint64_t caller=0;const auto fp=s.gpr.x29.qword;
      const auto sp=s.gpr.sp.qword;const bool frame=!(sp&15)&&sp<=std::numeric_limits<addr_t>::max()-32&&fp==sp+16;
      const bool known=frame&&Read(fp+8,&caller,8);
      std::fprintf(stderr,"Game exception diagnostic: wrapper saved callerLR exact_frame=%d readable=%d value=%#llx; attribution requires original wrapper context\n",frame,known,U(caller));
      const bool wrapper=frame&&s.gpr.pc.qword==0&&s.gpr.x30.qword==0x8260df44;
      const char*x19_label=wrapper&&known&&caller==0x8260d628?"X19 candidate; saved caller matches original d608 header convention":"X19 unclassified candidate";
      const char*x8_label=wrapper&&known&&caller==0x8260dee0?"X8 candidate; saved caller matches original std-terminate caught-header convention":"X8 unclassified candidate";
      Header(x19_label,s.gpr.x19.qword);
      if(wrapper&&known&&caller==0x8260def0)std::fprintf(stderr,"Game exception diagnostic: saved caller matches original std-terminate global-handler branch; X8=%#llx is global-address candidate, not a caught-exception header\n",U(s.gpr.x8.qword));
      else Header(x8_label,s.gpr.x8.qword);
    });
  }
  static void ReportJavaFailureFrames(const State&s)noexcept{
    Observe([&]{
      std::fprintf(stderr,"Game exception diagnostic: Java Locale failure PC=%#llx LR=%#llx SP=%#llx FP=%#llx; read-only bounded frame candidates\n",U(s.gpr.pc.qword),U(s.gpr.x30.qword),U(s.gpr.sp.qword),U(s.gpr.x29.qword));
      Frames(s,12);
    });
  }
 private:
  struct NativeEnvironment {
    int native_errno=errno;DWORD last_error=GetLastError();std::fenv_t environment{};
    NativeEnvironment(){std::fegetenv(&environment);}
    ~NativeEnvironment(){std::fesetenv(&environment);errno=native_errno;SetLastError(last_error);}
  };
  template<class F>static void Observe(F&&f)noexcept{
    NativeEnvironment preserve;
    try{f();std::fflush(stderr);}catch(...){std::fprintf(stderr,"Game exception diagnostic: observation unavailable; original execution retained\n");}
  }
  static unsigned long long U(uint64_t v){return static_cast<unsigned long long>(v);}
  static bool Read(addr_t address,void*out,size_t size)noexcept{
    if(!address||size>256||address>std::numeric_limits<addr_t>::max()-size)return false;
    bool ok=false;
    try{recomp::WithGuestMemoryRead([&]{SIZE_T got=0;ok=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),out,size,&got)&&got==size;});}catch(...){return false;}
    return ok;
  }
  static void Globals(){
    uint64_t got=0,handler=0;const bool got_ok=Read(0x87408e50,&got,8),handler_ok=Read(0x87985200,&handler,8);
    std::fprintf(stderr,"Game exception diagnostic: GOT[87408e50] readable=%d value=%#llx global[87985200] readable=%d value=%#llx; values valid only when readable\n",got_ok,U(got),handler_ok,U(handler));
  }
  static void RaiseGot(){
    uint64_t value=0;const bool ok=Read(0x8740b950,&value,8);
    std::fprintf(stderr,"Game exception diagnostic: Raise GOT[8740b950] readable=%d value=%#llx; value valid only when readable\n",ok,U(value));
  }
  static void Registers(const State&s){
    const auto*base=reinterpret_cast<const uint8_t*>(&s.gpr.x0);
    for(unsigned i=0;i<31;++i){uint64_t value=0;std::memcpy(&value,base+i*16,8);std::fprintf(stderr,"Game exception diagnostic: X%u=%#llx\n",i,U(value));}
  }
  static void Frames(const State&s,unsigned limit=4){
    auto fp=s.gpr.x29.qword;const auto sp=s.gpr.sp.qword;
    for(unsigned depth=0;depth<limit;++depth){
      if((fp&15)||fp<sp||fp-sp>65536){std::fprintf(stderr,"Game exception diagnostic: frame depth=%u stopped outside bounded SP window\n",depth);return;}
      uint64_t pair[2]{};if(!Read(fp,pair,sizeof(pair))){std::fprintf(stderr,"Game exception diagnostic: frame depth=%u address=%#llx unreadable\n",depth,U(fp));return;}
      std::fprintf(stderr,"Game exception diagnostic: frame depth=%u address=%#llx savedFP=%#llx savedLR=%#llx; bounded bytes, not unwind proof\n",depth,U(fp),U(pair[0]),U(pair[1]));
      if(pair[0]<=fp){return;}
      fp=pair[0];
    }
  }
  static void Header(const char*label,addr_t address){
    uint64_t words[16]{};const bool ok=Read(address,words,sizeof(words));
    std::fprintf(stderr,"Game exception diagnostic: header %s address=%#llx readable=%d bytes=128; candidate, not ownership/type proof\n",label,U(address),ok);
    if(!ok)return;
    for(unsigned j=0;j<16;++j)std::fprintf(stderr,"Game exception diagnostic: header offset=%#x value=%#llx\n",j*8,U(words[j]));
    TypeInfo(words[1]);
  }
  static void Stack(const State&s){
    uint64_t words[8]{};const bool ok=Read(s.gpr.sp.qword,words,sizeof(words));
    std::fprintf(stderr,"Game exception diagnostic: terminal SP words readable=%d bytes=64\n",ok);
    if(ok)for(unsigned j=0;j<8;++j)std::fprintf(stderr,"Game exception diagnostic: SP+%#x=%#llx\n",j*8,U(words[j]));
  }
  static void TypeInfo(addr_t address){
    uint64_t words[2]{};if(!Read(address,words,sizeof(words))){std::fprintf(stderr,"Game exception diagnostic: typeinfo candidate=%#llx unreadable\n",U(address));return;}
    char text[97]{};unsigned count=0;bool terminated=false,readable=true;
    for(;count<96;++count){char c=0;if(words[1]>std::numeric_limits<addr_t>::max()-count||!Read(words[1]+count,&c,1)){readable=false;break;}if(!c){terminated=true;break;}text[count]=(c>=32&&c<127)?c:'.';}
    std::fprintf(stderr,"Game exception diagnostic: typeinfo candidate=%#llx vtable=%#llx nameptr=%#llx bounded_name=[%s] bytes=%u readable=%d terminated=%d; no demangling/type assertion\n",U(address),U(words[0]),U(words[1]),text,count,readable,terminated);
  }
  inline static Entry raise_entry_=nullptr;
  inline static bool raise_enabled_=false;
};
