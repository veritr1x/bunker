#include "game_guest_call_routing.h"
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

extern "C" Memory *RoutingTestOriginal(State &,addr_t,Memory *);
extern "C" Memory *RoutingTestOther(State &,addr_t,Memory *);
extern "C" Memory *sub_825b0544(State &,addr_t,Memory *);
extern "C" Memory *RoutingOtherEntry(State &,addr_t,Memory *);
[[maybe_unused]] static Memory *Call(State &s,Memory *memory,addr_t target,addr_t continuation,
                    recomp::Entry direct) {
  const auto root=s.gpr.x30.qword,sp=s.gpr.sp.qword;
  s.gpr.x30.qword=continuation;s.gpr.pc.qword=target;
  auto *result=__bunker_guest_call(s,target,memory,continuation,sp,direct);
  if(__bunker_guest_transfer_pending(s)||s.gpr.pc.qword!=continuation||s.gpr.sp.qword!=sp)return result;
  s.gpr.x30.qword=root;s.gpr.pc.qword=root;return result;
}

#if defined(ROUTING_SAME_OBJECT)
extern "C" __attribute__((noinline)) Memory *sub_825b0544(State &s,addr_t pc,Memory *m){return RoutingTestOriginal(s,pc,m);}
extern "C" __attribute__((noinline)) Memory *RoutingOtherEntry(State &s,addr_t pc,Memory *m){return RoutingTestOther(s,pc,m);}
extern "C" recomp::Entry RoutingRawSaveEntry(){return sub_825b0544;}
extern "C" recomp::Entry RoutingRawOtherEntry(){return RoutingOtherEntry;}
extern "C" Memory *RoutingSameCaller(State &s,addr_t,Memory *m){return Call(s,m,0x825b0544,0x11110004,sub_825b0544);}
extern "C" Memory *RoutingOrdinaryCaller(State &s,addr_t,Memory *m){return Call(s,m,0x71120000,0x11110008,RoutingOtherEntry);}
#elif defined(ROUTING_CROSS_OBJECT)
extern "C" Memory *RoutingCrossCaller(State &s,addr_t,Memory *m){return Call(s,m,0x825b0544,0x22220004,sub_825b0544);}
extern "C" Memory *RoutingDynamicCaller(State &s,addr_t,Memory *m){return Call(s,m,0x825b0544,0x22220008,nullptr);}
extern "C" Memory *RoutingOtherDynamicCaller(State &s,addr_t,Memory *m){return Call(s,m,0x71120000,0x2222000c,nullptr);}
#else
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <pthread.h>
#include "pthread_host.h"
#include "nonlocal_jmp.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include <algorithm>
#include <atomic>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
extern "C" recomp::Entry RoutingRawSaveEntry();
extern "C" recomp::Entry RoutingRawOtherEntry();
extern "C" Memory *RoutingSameCaller(State &,addr_t,Memory *);
extern "C" Memory *RoutingCrossCaller(State &,addr_t,Memory *);
extern "C" Memory *RoutingDynamicCaller(State &,addr_t,Memory *);
extern "C" Memory *RoutingOrdinaryCaller(State &,addr_t,Memory *);
extern "C" Memory *RoutingOtherDynamicCaller(State &,addr_t,Memory *);
extern "C" Memory *__real_sub_825b0544(State &,addr_t,Memory *);
#if !defined(ROUTING_LEGACY)
extern "C" Memory *__real___bunker_guest_call(State &,addr_t,Memory *,addr_t,addr_t,recomp::Entry) noexcept;
#endif
namespace {
unsigned checks=0,original_calls=0,owned_calls=0,other_calls=0,legacy_wrap_calls=0,forward_calls=0;
bool permit_unowned=false;
void Require(bool yes,const char *why){if(!yes){std::fprintf(stderr,"routing: %s\n",why);std::abort();}++checks;}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
bool Translated(addr_t pc){return pc!=0;}
#include "game_bootstrap_detail.h"
using Thread=bunker::windows::NonlocalJumps::Thread;
Thread test_thread{};
addr_t last_environment=0;
struct ForwardRecord {State *state=nullptr;addr_t target=0;Memory *memory=nullptr;addr_t expected=0,sp=0;recomp::Entry direct=nullptr;};
ForwardRecord recorded{};
[[maybe_unused]] Memory *RecordOriginal(State &s,addr_t target,Memory *m,addr_t expected,addr_t sp,recomp::Entry direct) noexcept {
  recorded={&s,target,m,expected,sp,direct};++forward_calls;
#if !defined(ROUTING_LEGACY)
  return __real___bunker_guest_call(s,target,m,expected,sp,direct);
#else
  std::abort();
#endif
}
std::array<unsigned char,1200> unit_expected{};
Memory *unit_result=nullptr;
Memory *UnitOriginal(State &s,addr_t target,Memory *m,addr_t expected,addr_t sp,recomp::Entry direct) noexcept {
  recorded={&s,target,m,expected,sp,direct};
  Require(errno==EAGAIN&&GetLastError()==0x1234&&std::fegetround()==FE_UPWARD,"input native environment forwarded");
  std::memcpy(&s,unit_expected.data(),sizeof(s));std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);errno=E2BIG;SetLastError(0x5678);
  return unit_result;
}
void UnitForwarding(){
  static_assert(sizeof(State)==1200&&alignof(State)==16);
  alignas(16)std::array<unsigned char,64> input{},output{};unit_result=reinterpret_cast<Memory*>(output.data());
  for(unsigned i=0;i<unit_expected.size();++i)unit_expected[i]=static_cast<unsigned char>(i*37+11);
  for(unsigned scenario=0;scenario<4;++scenario){
    State s{};const auto target=scenario<2?0x825b0544ULL:0x71120000ULL;
    const auto direct=scenario%2?nullptr:RoutingRawSaveEntry();
    std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);errno=EAGAIN;SetLastError(0x1234);
    auto *result=bunker::windows::GuestCallRouting::Forward(UnitOriginal,GameOriginalSaveHelper,s,target,reinterpret_cast<Memory*>(input.data()),0x1234567887654320ULL,0x9876543212345600ULL,direct);
    Require(recorded.state==&s&&recorded.target==target&&recorded.memory==reinterpret_cast<Memory*>(input.data())&&recorded.expected==0x1234567887654320ULL&&recorded.sp==0x9876543212345600ULL,"all six ABI inputs preserved");
    Require(recorded.direct==((scenario==0)?GameOriginalSaveHelper:direct),"only nonnull matching direct entry substituted");
    Require(result==unit_result&&!std::memcmp(&s,unit_expected.data(),1200),"actual result and all State bytes forwarded unchanged after original");
    Require(errno==E2BIG&&GetLastError()==0x5678&&std::fegetround()==FE_DOWNWARD&&(std::fetestexcept(FE_INVALID)&FE_INVALID),"original native environment changes survive adapter");
    Require(std::all_of(input.begin(),input.end(),[](auto v){return v==0;})&&std::all_of(output.begin(),output.end(),[](auto v){return v==0;}),"opaque input/result tokens untouched");
  }
  std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);
}
}
extern "C" Memory *RoutingTestOriginal(State &s,addr_t pc,Memory *m){
  ++original_calls;Require(pc==0x825b0544,"actual original helper receives target PC");
  const auto entry=s.gpr.sp.qword,ret=s.gpr.x30.qword;
  if(!GameAutomaticEnvironments::Frames().empty()){
    ++owned_calls;s.gpr.sp.qword=entry-0x140;s.gpr.x0.qword=s.gpr.sp.qword+8;s.gpr.x30.qword=0x825b0580;
    game_environments->BeforeSetjmp(s,test_thread.token);last_environment=s.gpr.x0.qword;
    auto region=game_environments->Find(last_environment,256,test_thread.token);Require(region&&region->generation,"unchanged production owner publishes real invocation generation");
    game_environments->jumps->Save(s,last_environment,0);Require(game_environments->jumps->Inspect(s,last_environment,1).environment==last_environment,"actual NonlocalJumps registration is live inside unchanged owner");
  }else Require(permit_unowned,"matching static call bypassed required production owner");
  s.gpr.sp.qword=entry;s.gpr.x30.qword=ret;s.gpr.pc.qword=ret;return m;
}
extern "C" Memory *RoutingTestOther(State &s,addr_t,Memory *m){++other_calls;s.gpr.x9.qword=0xa55aa55a;s.gpr.pc.qword=s.gpr.x30.qword;return m;}
extern "C" Memory *__wrap_sub_825b0544(State &s,addr_t pc,Memory *m){++legacy_wrap_calls;return GameOriginalSaveHelper(s,pc,m);}
#if !defined(ROUTING_LEGACY)
extern "C" Memory *__wrap___bunker_guest_call(State &s,addr_t target,Memory *m,addr_t expected,addr_t sp,recomp::Entry direct) noexcept {
  return bunker::windows::GuestCallRouting::Forward(RecordOriginal,GameOriginalSaveHelper,s,target,m,expected,sp,direct);
}
#endif
int main(){
  UnitForwarding();
  recomp::Runtime runtime;GameAutomaticEnvironments owner;game_environments=&owner;owner.original=__real_sub_825b0544;
  alignas(16)std::array<unsigned char,65536> stack{};const auto low=reinterpret_cast<addr_t>(stack.data()),high=low+stack.size();test_thread={17,23,low,high};owner.current=[]{return test_thread;};
  bunker::windows::NonlocalJumps jumps([]{return test_thread;},[&](addr_t env,size_t size){return owner.Find(env,size,test_thread.token);},[]{return uint64_t(0);},[](addr_t pc){return pc==0x825b0580;},0x1020304050607080ULL);owner.jumps=&jumps;
  recomp::Trace traces[]={{0x11110000,RoutingSameCaller},{0x22220000,RoutingCrossCaller},{0x33330000,RoutingDynamicCaller},{0x44440000,RoutingOrdinaryCaller},{0x55550000,RoutingOtherDynamicCaller},{0x71120000,RoutingRawOtherEntry()},{0x825b0544,GameOriginalSaveHelper}};runtime.AddTraces(traces,std::size(traces));
  for(unsigned scenario=0;scenario<5;++scenario){
    State s{};s.gpr.sp.qword=high;s.gpr.x30.qword=0x77770000;const auto before_original=original_calls,before_owned=owned_calls,before_other=other_calls,before_legacy=legacy_wrap_calls,before_forward=forward_calls;
#if defined(ROUTING_LEGACY)
    permit_unowned=scenario==0;
#else
    permit_unowned=false;
#endif
    runtime.Run(s,traces[scenario].address);
    Require(s.gpr.pc.qword==0x77770000&&s.gpr.sp.qword==high,"actual Runtime logical call protocol returns to root normally");
    if(scenario<3){Require(original_calls==before_original+1,"original helper called exactly once");
#if defined(ROUTING_LEGACY)
      Require(owned_calls==before_owned+(scenario?1:0),"legacy same-object bypass and cross/dynamic ownership witnessed");
      Require(legacy_wrap_calls==before_legacy+(scenario==1?1:0),"legacy linker wrap sees only cross-object static reference");
#else
      Require(owned_calls==before_owned+1&&legacy_wrap_calls==before_legacy,"new route enters existing owner once for same/cross/dynamic calls");
      Require(forward_calls==before_forward+1,"actual runtime call facade invoked once");
      if(scenario==2)Require(recorded.direct==nullptr,"dynamic direct-entry remains null for selected-table Dispatch");
      else Require(recorded.direct==GameOriginalSaveHelper,"same/cross direct-entry selects unchanged production owner");
#endif
    }else Require(other_calls==before_other+1&&owned_calls==before_owned&&s.gpr.x9.qword==0xa55aa55a,"ordinary direct and dynamic calls unchanged");
    Require(GameAutomaticEnvironments::Frames().empty(),"production owner frame retired after actual return");
    if(last_environment){Require(!owner.Find(last_environment,256,test_thread.token),"owner lifetime lookup revoked");bool rejected=false;try{jumps.Inspect(s,last_environment,1);}catch(const std::exception&){rejected=true;}Require(rejected,"actual saved nonlocal environment forgotten after return");}
    (void)before_forward;
  }
  std::printf("GUEST-CALL-ROUTING-PASS checks=%u original_calls=%u owned_calls=%u legacy_wrap_calls=%u forward_calls=%u mode=%s\n",checks,original_calls,owned_calls,legacy_wrap_calls,forward_calls,
#if defined(ROUTING_LEGACY)
  "legacy"
#else
  "adapter"
#endif
  );
}
#endif
