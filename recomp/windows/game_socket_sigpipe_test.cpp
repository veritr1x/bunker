// TEST setup: isolated native main-thread/token/disposition. The actual NDK
// socket/send caller, installed providers and production policy execute.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <windows.h>
#include "socket_transport.h"
#include "socket_transport_cases.h"
#include "pthread_host.h"
#include "signal_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include "game_socket_sigpipe.h"

namespace {
using namespace bunker::windows;
unsigned checks=0,hooks=0,guarded_calls=0,ndk_calls=0;
std::array<addr_t,3> guarded_markers{};
FileSystem *file_provider=nullptr;SocketTransport *socket_provider=nullptr;
void Check(bool value,const char *reason){++checks;if(!value)throw std::runtime_error(reason);}
void *Resolve(const char *name){try{return reinterpret_cast<void*>(file_provider->Marker(name));}catch(const std::invalid_argument&){return reinterpret_cast<void*>(socket_provider->Marker(name));}}
bool Translated(addr_t address){for(const auto &trace:kTraces)if(trace.address==address)return true;return false;}
struct Environment {
  int error=errno;DWORD last=GetLastError();fenv_t floating{};
  Environment(){std::fegetenv(&floating);}
  ~Environment(){std::fesetenv(&floating);errno=error;SetLastError(last);}
};
struct Fixture {
  recomp::Runtime runtime;FileSystem files;SocketTransport sockets{files};
  Pthreads threads{runtime,Translated};SignalHost signals;elf_image image{};
  alignas(16)std::array<unsigned char,65536> stack{};addr_t entry=0;
  unsigned form=0;std::string policy;
  addr_t configured_handler=0;uint64_t configured_mask=0;
  Fixture(const char *mode,unsigned indirect):form(indirect),policy(mode){
    file_provider=&files;socket_provider=&sockets;
    runtime.AddTraces(kTraces,std::size(kTraces));
    Check(!elf_load_bionic(SOCKET_LIBRARY,0x7b000000,Resolve,&image),"actual held NDK caller ELF loads");
    entry=reinterpret_cast<addr_t>(elf_symbol(&image,"guest_socket_operation"));Check(Translated(entry),"actual NDK dispatcher entry is selected");
    threads.AttachCurrentStack(stack.data(),stack.size());const auto token=threads.Self();
    Check(token!=0&&signals.RegisterThread(token)==0&&signals.BindCurrent(token)==0,"real native Pthreads token and SignalHost registration");
    AndroidSignalAction action{};action.handler=policy=="ignore"?1:policy=="custom"?addr_t{0x5e130000}:0;configured_handler=action.handler;
    Check(signals.Action(13,&action,nullptr)==0,"actual guest SIGPIPE disposition configured");
    configured_mask=policy=="blocked"||policy=="ignore"?SignalHost::Bit(13):0;
    Check(signals.Mask(token,2,&configured_mask,nullptr)==0,"explicit actual SIGPIPE mask configured");
    uint64_t observed_mask=0;Check(signals.Mask(token,0,nullptr,&observed_mask)==0&&(observed_mask&SignalHost::Bit(13))==configured_mask,"actual SIGPIPE mask bit matches explicit test setup");
    configured_mask=observed_mask;  // Retain Android's provider-owned reserved bits.
    std::fprintf(stderr,"POLICY-MASK mode=%s actual=%#llx blocked13=%u\n",policy.c_str(),static_cast<unsigned long long>(observed_mask),unsigned((observed_mask&SignalHost::Bit(13))!=0));std::fflush(stderr);
    sockets.SetBrokenPipeNotification([this](State *state){
      ++hooks;Check(state&&state==recomp::CurrentExecutionState(),"policy sees actual active Runtime import State");
      Check(threads.Self()!=0,"policy uses actual Pthreads Self token");
      std::fprintf(stderr,"POLICY-NOTIFY mode=%s form=%u count=%u\n",policy.c_str(),form,hooks);std::fflush(stderr);
      errno=ERANGE;SetLastError(0x13131313);std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_OVERFLOW|FE_INVALID);
      const int floating=std::fetestexcept(FE_ALL_EXCEPT);
      try{GameSocketSigpipe::Notify(signals,threads.Self(),state);}
      catch(...){
        AndroidSignalAction observed{};uint64_t mask=0,pending=0;const auto token=threads.Self();
        Check(signals.Action(13,nullptr,&observed)==0&&observed.handler==configured_handler,"rejected policy leaves actual disposition unchanged");
        Check(signals.Mask(token,0,nullptr,&mask)==0&&mask==configured_mask,"rejected policy leaves actual mask unchanged");
        Check(signals.Pending(token,&pending)==0&&pending==0&&!SignalHost::NeedsPoll(signals.Lookup(token)),"rejected policy queues no undeliverable signal");
        std::fprintf(stderr,"POLICY-REJECT mode=%s actionUnchanged=1 maskUnchanged=1 pending=0\n",policy.c_str());std::fflush(stderr);throw;
      }
      Check(errno==ERANGE&&GetLastError()==0x13131313,"production ignored-policy native errno/LastError identity");
      Check(std::fegetround()==FE_UPWARD&&std::fetestexcept(FE_ALL_EXCEPT)==floating,"production ignored-policy nonzero floating state identity");
      std::fputs("POLICY-RETURN ignored=1 nativeEnvironment=1\n",stderr);std::fflush(stderr);
    });
    guarded_markers={sockets.Marker("socket"),sockets.Marker("send"),files.Marker("close")};
    files.Install(runtime);sockets.Install(runtime);
  }
  ~Fixture(){signals.DropThread(threads.Self());if(threads.Shutdown())std::abort();}
  int64_t Invoke(int operation,const std::array<uint64_t,6> &arguments,int &error){
    State state{};state.gpr.x0.dword=static_cast<uint32_t>(operation);state.gpr.x1.qword=reinterpret_cast<addr_t>(arguments.data());state.gpr.x2.dword=form;state.gpr.x3.qword=reinterpret_cast<addr_t>(&error);
    const auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.sp.qword=top;state.gpr.x30.qword=0xfeedffff;state.gpr.x19.qword=0xf123456789abcdefULL;state.gpr.x29.qword=0xe123456789abcdefULL;
    std::array<unsigned char,16> vector{};vector.fill(0xd3);std::memcpy(&state.simd.v[31],vector.data(),16);reinterpret_cast<unsigned char*>(&state)[1199]=0x73;
    auto *memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);++ndk_calls;
    std::fprintf(stderr,"NDK-CALL api=%s form=%u ordinal=%u\n",net_names[operation],form,ndk_calls);std::fflush(stderr);
    Check(runtime.Run(state,entry,memory)==memory,"actual NDK Memory64 identity");
    Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==top&&state.gpr.x19.qword==0xf123456789abcdefULL&&state.gpr.x29.qword==0xe123456789abcdefULL,"actual NDK PCSP/high64 callee-saved state");
    Check(!std::memcmp(vector.data(),&state.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&state)[1199]==0x73,"actual NDK SIMD128 and State1200 high cell");
    return static_cast<int64_t>(state.gpr.x0.qword);
  }
  void Run(){
    int error=0;const auto descriptor=Invoke(NET_SOCKET,{2,1,0,0,0,0},error);Check(descriptor>=0,"real unconnected TCP socket created");
    const char payload='p';const uint64_t flags=policy=="nosignal"?0x4000:0;
    std::fprintf(stderr,"BEFORE-GUEST-SEND mode=%s form=%u defaultAction=%u\n",policy.c_str(),form,policy=="ignore"?1:0);std::fflush(stderr);
    const auto result=Invoke(NET_SEND,{static_cast<uint64_t>(descriptor),reinterpret_cast<addr_t>(&payload),1,flags,0,0},error);
    std::fprintf(stderr,"AFTER-GUEST-SEND mode=%s result=%lld errno=%d hooks=%u\n",policy.c_str(),static_cast<long long>(result),error,hooks);std::fflush(stderr);
    Check(policy=="ignore"||policy=="nosignal","default/custom policy must not return to post-call code");
    Check(result==-1&&error==32,"actual unconnected NDK send returns EPIPE");
    Check(hooks==(policy=="ignore"?1u:0u),"MSG_NOSIGNAL suppresses notification; ignored signal notifies once");
    AndroidSignalAction action{};Check(signals.Action(13,nullptr,&action)==0&&action.handler==(policy=="ignore"?1u:0u),"actual SignalHost disposition remains intact");
    uint64_t mask=0;Check(signals.Mask(threads.Self(),0,nullptr,&mask)==0&&mask==configured_mask,"returned policy preserves actual bound thread mask");
    Check(Invoke(NET_CLOSE,{static_cast<uint64_t>(descriptor),0,0,0,0,0},error)==0,"owned native socket closes through shared descriptor provider");
    Check(guarded_calls==3&&ndk_calls==3,"three actual NDK entries/installed guarded callbacks");
    std::fprintf(stderr,"SIGPIPE-PASS mode=%s form=%u checks=%u hooks=%u NDK_calls=%u nativeEnvironment=1 State1200=1 Memory64=1\n",policy.c_str(),form,checks,hooks,ndk_calls);std::fflush(stderr);
  }
};
}  // namespace
extern "C" void RealAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__real__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime*,addr_t,std::function<void(State&)>) __asm__("__wrap__ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE");
extern "C" void WrapAddImport(recomp::Runtime *runtime,addr_t marker,std::function<void(State&)> callback){
  bool guarded=false;for(const auto watched:guarded_markers)if(marker==watched)guarded=true;
  if(guarded){auto original=std::move(callback);callback=[original=std::move(original)](State &state){
    Environment previous;errno=EDOM;SetLastError(0x7013abcd);std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);
    const int floating=std::fetestexcept(FE_ALL_EXCEPT);Check(recomp::CurrentExecutionState()==&state,"real installed callback is inside actual Runtime frame");
    original(state);Check(errno==EDOM&&GetLastError()==0x7013abcd,"complete installed callback native errno/LastError identity");
    Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==floating,"complete installed callback native floating identity");++guarded_calls;
  };}
  RealAddImport(runtime,marker,std::move(callback));
}
int main(int argc,char **argv){try{if(argc!=3)return 2;const std::string mode=argv[1];if(mode!="ignore"&&mode!="default"&&mode!="nosignal"&&mode!="custom"&&mode!="blocked")return 2;const unsigned form=static_cast<unsigned>(std::strtoul(argv[2],nullptr,10));if(form>1)return 2;static_assert(sizeof(State)==1200&&alignof(State)==16);Fixture fixture(argv[1],form);fixture.Run();return 0;}catch(const std::exception &error){std::fprintf(stderr,"SIGPIPE-FIXTURE-FAIL %s\n",error.what());return 1;}}
