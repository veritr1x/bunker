#define NOMINMAX
#include <windows.h>
#include <pthread.h>
#include "pthread_host.h"
#include "nonlocal_jmp.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cerrno>
#include <cfenv>
#include <cstring>
#include <functional>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
extern "C" Memory *sub_70a8aa08(State&,addr_t,Memory*);
extern "C" Memory *__real_sub_825b0544(State&,addr_t,Memory*);
namespace {
unsigned checks=0,negatives=0,saves=0,calls=0,cleanup=0,mode=0,profile=0,depth=0,repeats=1;addr_t environment=0;uint64_t observed_generation=0,previous_generation=0;bool nested=false;
void Require(bool yes,const char *why){++checks;if(!yes)throw std::runtime_error(why);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
bool Translated(addr_t p){return p!=0;}
#include "game_bootstrap_detail.h"
using Thread=bunker::windows::NonlocalJumps::Thread;Thread thread{};GameUnityDecodeEnvironments *owner=nullptr;bunker::windows::NonlocalJumps*jumps=nullptr;recomp::Runtime *runtime=nullptr;
template<class F>void Reject(F f,const char *why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Require(rejected,why);++negatives;}
Memory *OriginalInner(State&s,addr_t pc,Memory*m){auto*r=sub_70a8aa08(s,pc,m);
 if(profile==13)s.gpr.sp.qword-=16;
 if(profile==14)s.gpr.pc.qword+=4;
 return r;}
Memory *OuterHarness(State&s,addr_t,Memory*m){
 const auto entry=s.gpr.sp.qword,ret=s.gpr.x30.qword;const auto post=entry-0x42a0,env=post+0x10;std::array<uint8_t,0x400> object{};std::memset(object.data(),0xa5,object.size());uint32_t skip=mode/3;std::memcpy(object.data()+0x120,&skip,4);recomp::WriteGuestMemory(env,object.data(),object.size());
 for(unsigned r=0;r<repeats;r++){
  s.gpr.sp.qword=post;s.gpr.x0.qword=env;s.gpr.x30.qword=0x70a8a8b0;
  if(profile==2)s.gpr.sp.qword-=16;
 if(profile==3)s.gpr.x30.qword+=4;
 if(profile==4)s.gpr.x0.qword+=8;
  const auto result=owner->RunInner(s,profile==1?0x70a8aa0c:0x70a8aa08,m);Require(result==m,"actual inner preserves opaque Memory token");
  Require(!owner->Live().outer.empty(),"exact outer remains live");const auto outer_generation=owner->Live().outer.back().generation;Require(std::none_of(owner->Live().inner.begin(),owner->Live().inner.end(),[&](const auto &i){return i.outer_generation==outer_generation;}),"this outer has no saved inner after its return");Require(!owner->Find(env,256,thread.token),"outer object alone never authorizes a saved inner context");Reject([&]{jumps->Inspect(s,env,1);},"dead inner save is forgotten before outer return");
  Require(observed_generation>previous_generation,"repeated inner invocation receives a fresh continuation generation");previous_generation=observed_generation;
 }
 s.gpr.sp.qword=entry;s.gpr.pc.qword=ret;
 if(profile==15)s.gpr.sp.qword-=16;
 if(profile==16)s.gpr.pc.qword+=4;
 return m;
}
void BeforeSave(State&s){
 if(profile==5)++thread.token;
 if(profile==6)++thread.generation;
 if(profile==7)s.gpr.sp.qword-=16;
 if(profile==8)s.gpr.x0.qword+=8;
 if(profile==9)s.gpr.x19.qword+=8;
 if(profile==10)thread.stack_low+=16;
 owner->BeforeSetjmp(s,thread.token);
 if(profile==11)owner->BeforeSetjmp(s,thread.token);
 const auto region=owner->Find(s.gpr.x0.qword,256,thread.token);Require(region&&region->low==s.gpr.x0.qword&&region->high==s.gpr.x0.qword+256,"exact live original outer subobject and inner save window");observed_generation=region->generation;environment=s.gpr.x0.qword;++saves;
}
Memory *SyntheticInner(State&s,addr_t,Memory*m){
 const auto entry=s.gpr.sp.qword,ret=s.gpr.x30.qword;s.gpr.sp.qword=entry-0x20;s.gpr.x19.qword=s.gpr.x0.qword;s.gpr.x30.qword=0x70a8aa1c;
 BeforeSave(s);jumps->Save(s,s.gpr.x0.qword,1);
 if(profile==12)throw std::runtime_error("explicit TEST native unwind outside guest-call noexcept boundary");
 s.gpr.sp.qword=entry;s.gpr.pc.qword=ret;
 if(profile==13)s.gpr.sp.qword-=16;
 if(profile==14)s.gpr.pc.qword+=4;
 return m;
}
void Callback(State&s){
 ++calls;const auto env=s.gpr.x2.qword;Require(env==environment&&s.gpr.x0.qword==env+0x158&&s.gpr.x1.qword==0x712265e0,"actual original decoder callback arguments");
 const auto plan=jumps->Inspect(s,env,1);Require(plan.environment==env&&plan.pc==0x70a8aa1c&&plan.sp==env-0x30,"actual wire context preserves original inner continuation and SP");Require(owner->Find(env,256,thread.token).has_value(),"inner callback sees live owner");
 if(profile==12)throw std::runtime_error("explicit test native unwind");
 if(profile==17){State again=s;again.gpr.sp.qword=env-0x10;again.gpr.x0.qword=env;again.gpr.x30.qword=0x70a8a8b0;Reject([&]{owner->RunInner(again,0x70a8aa08,nullptr);},"same outer cannot reenter a second live inner with forged identical geometry");}
 if(profile==18){GameUnityDecodeEnvironments foreign;foreign.current=[]{return thread;};Require(!foreign.Find(env,256,thread.token),"another owner instance cannot borrow save");State forged=s;forged.gpr.x30.qword=0x70a8aa1c;Reject([&]{foreign.BeforeSetjmp(forged,thread.token);},"another owner cannot certify current invocation");}
 if(profile==19){bool absent=false;std::thread other([&]{absent=!owner->Find(env,256,thread.token);});other.join();Require(absent,"another native thread cannot borrow active invocation metadata");}
 if(nested&&!depth){const auto saved_generation=observed_generation;const auto old_environment=environment;const auto saved_previous=previous_generation;depth=1;State child=s;child.gpr.sp.qword=s.gpr.sp.qword-0x100;child.gpr.x30.qword=0x6f00fff0;runtime->Run(child,0x70a8a5c4,nullptr);depth=0;environment=old_environment;observed_generation=saved_generation;previous_generation=saved_previous;Require(owner->Find(env,256,thread.token)->generation==saved_generation,"nested outer retires only its own inner save");}
 s.gpr.x0.qword=(mode%3)*17;
}
}
extern "C" Memory *sub_700b92b0(State&s,addr_t,Memory*m){BeforeSave(s);return runtime->Dispatch(s,jumps->Marker("setjmp"),m);}
extern "C" Memory *sub_70a82428(State&s,addr_t,Memory*m){Callback(s);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
extern "C" Memory *__wrap_sub_70a8aa64(State&s,addr_t,Memory*m){++cleanup;Require(s.gpr.x0.qword==environment,"actual cleanup callback environment");s.gpr.pc.qword=s.gpr.x30.qword;return m;}
extern "C" Memory *__real_sub_825b0544(State&,addr_t,Memory*m){throw std::runtime_error("unexpected legacy save helper in decode fixture");return m;}
extern "C" Memory *__real___bunker_guest_call(State&,addr_t,Memory*,addr_t,addr_t,recomp::Entry) noexcept;
extern "C" Memory *__wrap___bunker_guest_call(State&s,addr_t target,Memory*m,addr_t expected,addr_t sp,recomp::Entry direct) noexcept {
 if(target==0x70a8aa64)direct=__wrap_sub_70a8aa64;
 return __real___bunker_guest_call(s,target,m,expected,sp,direct);
}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{
 (void)&GameOriginalSaveHelper;(void)&GameOriginalFontCmapHelper;
 static_assert(sizeof(State)==1200&&sizeof(Memory*)==8);alignas(16)std::array<uint8_t,262144> stack{};const auto high=reinterpret_cast<addr_t>(stack.data()+stack.size());thread={17,23,reinterpret_cast<addr_t>(stack.data()),high};const auto base_thread=thread;
 GameUnityDecodeEnvironments actual;owner=&actual;game_unity_decode_environments=&actual;actual.current=[]{return thread;};actual.original_outer=OuterHarness;actual.original_inner=OriginalInner;
 bunker::windows::NonlocalJumps nonlocal([]{return thread;},[&](addr_t p,size_t n){return actual.Find(p,n,thread.token);},[]{return uint64_t(0x80000000);},[](addr_t p){return p==0x70a8aa1c;},0x123456789abcdef0ULL);jumps=&nonlocal;actual.jumps=&nonlocal;recomp::Runtime host;runtime=&host;nonlocal.Install(host);recomp::Trace trace[]={ {0x70a8a5c4,GameOriginalUnityDecodeOuter} };host.AddTraces(trace,1);
 auto state=[&]{State s{};s.gpr.sp.qword=high;s.gpr.x30.qword=0x6f00fff0;s.gpr.x19.qword=0x123456789abcdef0ULL;return s;};
 for(mode=0;mode<6;mode++){saves=calls=cleanup=0;State s=state();std::array<uint64_t,8> token{};const auto old=token;auto*m=reinterpret_cast<Memory*>(token.data());Require(host.Run(s,0x70a8a5c4,m)==m&&token==old,"outer harness and actual inner retain Memory64");Require(s.gpr.x0.qword==(mode%3)*17&&s.gpr.sp.qword==high&&s.gpr.pc.qword==0x6f00fff0&&s.gpr.x19.qword==0x123456789abcdef0ULL,"actual inner result/normal SP/continuation/callee X19");Require(saves==1&&calls==1&&cleanup==!(mode/3),"actual original inner callback path");Require(actual.Live().outer.empty()&&actual.Live().inner.empty(),"normal outer retirement removes metadata");std::printf("DECODE-REF case=%u result=%llu saves=%u calls=%u cleanup=%u\n",mode,(unsigned long long)s.gpr.x0.qword,saves,calls,cleanup);}
 mode=0;repeats=2;State repeated=state();host.Run(repeated,0x70a8a5c4,nullptr);repeats=1;nested=true;State recursion=state();host.Run(recursion,0x70a8a5c4,nullptr);nested=false;
 for(profile=1;profile<=19;profile++){actual.original_inner=profile<=16?SyntheticInner:OriginalInner;State s=state();
 if(profile<=16){Reject([&]{actual.RunOuter(s,0x70a8a5c4,nullptr);},"wrong entry/site/SP/env/thread/re-save/unwind/return fails closed");}
 else{host.Run(s,0x70a8a5c4,nullptr);}
 thread=base_thread;Require(actual.Live().outer.empty()&&actual.Live().inner.empty()&&!actual.Find(environment,256,thread.token),"failed/positive bounded invocation retires all metadata");}
 profile=0;State bare=state();Reject([&]{actual.RunInner(bare,0x70a8aa08,nullptr);},"inner cannot invent an outer object lifetime");bare.gpr.x30.qword=0x70a8aa1c;Reject([&]{actual.BeforeSetjmp(bare,thread.token);},"setjmp cannot invent invocations from stack bounds");bare=state();Reject([&]{actual.RunOuter(bare,0x70a8a5c8,nullptr);},"interior entry does not create outer owner");bare=state();bare.gpr.sp.qword-=8;Reject([&]{actual.RunOuter(bare,0x70a8a5c4,nullptr);},"misaligned outer SP rejected");bare=state();bare.gpr.sp.qword=thread.stack_low+0x42b0;Reject([&]{actual.RunOuter(bare,0x70a8a5c4,nullptr);},"complete outer plus inner frame must fit owned stack");
 std::printf("UNITY-DECODE-OWNER-PASS checks=%u negatives=%u actual_inner=92 outer_test_harness=1 State=1200 Memory64=8\n",checks,negatives);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"decode owner fixture: %s\n",e.what());return 91;}}
