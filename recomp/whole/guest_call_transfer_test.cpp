#include <array>
#include <atomic>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#ifdef _WIN32
extern "C" __declspec(dllimport) unsigned long __stdcall SetErrorMode(unsigned long);
#endif
#include "runtime.h"

namespace {
constexpr addr_t ROOT=0x1000,LEAF=0x2000,TAIL=0x2100,OWNER=0x2200,THROW=0x2300;
constexpr addr_t LAND1=0x3000,LAND2=0x3100,RETHROW=0x3200,RECURSE=0x4000;
constexpr addr_t INNER=0x6000,CALLBACK=0x6100,IMPORT=0x6200;
constexpr addr_t ROOT_RETURN=0x9000,OWNER_RETURN=0x1010,INNER_RETURN=0x2210;
enum Mode {Direct,Indirect,Tail,Landing,Ancestor,Recursive,NestedRethrow,NestedDifferent,
           NestedSame,Import,Unknown,NoOwner,CrossState,EscapeSame,StaleToken,WrongThread};
struct Fixture {
  recomp::Runtime *runtime=nullptr,*child_runtime=nullptr;
  Mode mode=Direct;
  unsigned checks=0,leaf=0,tail=0,owner_after=0,root_after=0,landing1=0,landing2=0;
  unsigned landing_after=0,rethrows=0,callbacks=0,inner=0,recursive_after=0;
  unsigned recursive_mask=0;
  State expected{};
  bool captured=false;
  addr_t root_sp=0x10000,root_return=ROOT_RETURN;
  alignas(16)std::array<unsigned char,64> a{},b{},c{};
  Memory *A(){return reinterpret_cast<Memory*>(a.data());}
  Memory *B(){return reinterpret_cast<Memory*>(b.data());}
  Memory *C(){return reinterpret_cast<Memory*>(c.data());}
};
thread_local Fixture *fixture;
void Check(bool value,const char *why){
  ++fixture->checks;
  if(!value){std::fprintf(stderr,"TRANSFER-TEST-FAIL %s\n",why);std::abort();}
}
void Finish(State &s){
  s.gpr.pc.qword=fixture->root_return;s.gpr.x30.qword=fixture->root_return;
  s.gpr.sp.qword=fixture->root_sp;fixture->expected=s;fixture->captured=true;
}
Memory *Leaf(State &s,addr_t pc,Memory *m){
  Check(pc==LEAF,"leaf argument PC");Check(m==fixture->A()||m==fixture->B(),"leaf input token");
  ++fixture->leaf;s.gpr.x7.qword^=0x12345678;
  if(fixture->mode==EscapeSame){s.gpr.pc.qword=OWNER_RETURN;s.gpr.sp.qword=fixture->root_sp-0x100;}
  else s.gpr.pc.qword=s.gpr.x30.qword;
  return fixture->B();
}
Memory *TailLeaf(State &s,addr_t pc,Memory *m){
  Check(pc==TAIL,"tail argument PC");++fixture->tail;s.gpr.pc.qword=LEAF;
  return __remill_jump(s,LEAF,m); // Same-result tail dispatch, no logical call frame.
}
Memory *Throw(State &s,addr_t pc,Memory *m){
  Check(pc==THROW,"throw argument PC");Check(m==fixture->A(),"throw token");
  s.gpr.pc.qword=fixture->mode==Ancestor?OWNER_RETURN:fixture->mode==Unknown?0xdeadbeec:LAND1;
  s.gpr.sp.qword=fixture->mode==NoOwner?fixture->root_sp+0x100:fixture->root_sp-0x100;
  s.gpr.x21.qword=0x8799a000;s.gpr.x30.qword=s.gpr.pc.qword;
  std::fesetround(FE_UPWARD);std::feraiseexcept(FE_DIVBYZERO);
  return fixture->B();
}
Memory *Owner(State &s,addr_t pc,Memory *m){
  Check(pc==OWNER,"owner argument PC");const auto sp=s.gpr.sp.qword,lr=s.gpr.x30.qword;
  s.gpr.sp.qword-=0x100;s.gpr.x30.qword=INNER_RETURN;s.gpr.pc.qword=THROW;
  auto *result=__bunker_guest_call(s,THROW,m,INNER_RETURN,s.gpr.sp.qword,Throw);
  if(__bunker_guest_transfer_pending(s))return fixture->mode==StaleToken?m:result;
  ++fixture->owner_after;s.gpr.sp.qword=sp;s.gpr.x30.qword=lr;s.gpr.pc.qword=lr;
  return result;
}
Memory *Rethrow(State &s,addr_t pc,Memory *m){
  Check(pc==RETHROW,"rethrow PC");Check(m==fixture->B(),"rethrow token");++fixture->rethrows;
  s.gpr.pc.qword=LAND2;s.gpr.x30.qword=LAND2;s.gpr.sp.qword=fixture->root_sp-0x100;
  s.gpr.x8.qword=0x2222;return fixture->C();
}
Memory *LandingOne(State &s,addr_t pc,Memory *m){
  Check(pc==LAND1,"landing PC");Check(m==fixture->B(),"landing actual token");
  Check(s.gpr.sp.qword==fixture->root_sp-0x100,"landing actual restored SP");
  Check(s.gpr.x21.qword==0x8799a000,"landing actual restored register");
  Check(fixture->owner_after==0,"abandoned inner frame unwound before catch");
  Check(!__bunker_guest_transfer_pending(s),"landing has no pending old event");
  Check(std::fegetround()==FE_UPWARD,"landing does not reset rounding");
  Check((std::fetestexcept(FE_ALL_EXCEPT)&FE_DIVBYZERO)!=0,"landing does not reset exceptions");
  ++fixture->landing1;
  if(fixture->mode==NestedRethrow){
    s.gpr.sp.qword-=0x80;s.gpr.x30.qword=0x3020;s.gpr.pc.qword=RETHROW;
    auto *result=__bunker_guest_call(s,RETHROW,m,0x3020,s.gpr.sp.qword,Rethrow);
    if(__bunker_guest_transfer_pending(s))return result;
    ++fixture->landing_after;return result;
  }
  s.gpr.x0.qword=42;Finish(s);return m;
}
Memory *LandingTwo(State &s,addr_t pc,Memory *m){
  Check(pc==LAND2,"second landing PC");Check(m==fixture->C(),"second landing token");
  Check(fixture->landing1==1&&fixture->landing_after==0,"nested rethrow skipped old landing continuation");
  ++fixture->landing2;s.gpr.x0.qword=84;Finish(s);return m;
}
Memory *Recursion(State &s,addr_t pc,Memory *m){
  Check(pc==RECURSE,"recursive PC");const unsigned depth=unsigned(s.gpr.x0.qword);
  const auto entry_sp=s.gpr.sp.qword,entry_lr=s.gpr.x30.qword;
  if(depth==4){
    s.gpr.pc.qword=0x4010;s.gpr.x30.qword=0x4010;s.gpr.sp.qword=fixture->root_sp-0x400;
    return fixture->B();
  }
  s.gpr.sp.qword-=0x100;s.gpr.x0.qword=depth+1;s.gpr.x30.qword=0x4010;s.gpr.pc.qword=RECURSE;
  auto *result=__bunker_guest_call(s,RECURSE,m,0x4010,s.gpr.sp.qword,Recursion);
  if(__bunker_guest_transfer_pending(s))return result;
  ++fixture->recursive_after;fixture->recursive_mask|=1u<<depth;
  s.gpr.sp.qword=entry_sp;s.gpr.x30.qword=entry_lr;s.gpr.pc.qword=entry_lr;return result;
}
Memory *Inner(State &s,addr_t pc,Memory *m){
  Check(pc==INNER,"inner Run argument PC");++fixture->inner;
  const auto lr=s.gpr.x30.qword;s.gpr.x30.qword=0x6010;s.gpr.pc.qword=LEAF;
  auto *result=__bunker_guest_call(s,LEAF,m,0x6010,s.gpr.sp.qword,nullptr);
  if(__bunker_guest_transfer_pending(s))return result;
  s.gpr.x30.qword=lr;s.gpr.pc.qword=lr;return result;
}
Memory *Callback(State &s,addr_t pc,Memory *m){
  Check(pc==CALLBACK,"callback PC");++fixture->callbacks;
  const auto sp=s.gpr.sp.qword,lr=s.gpr.x30.qword;
  if(fixture->mode==CrossState){State wrong=s;return __bunker_guest_call(wrong,LEAF,m,0x6010,wrong.gpr.sp.qword,Leaf);}
  std::fesetround(FE_UPWARD);std::feraiseexcept(FE_DIVBYZERO);
  if(fixture->mode==NestedDifferent){
    const State before=s;State child=s;child.gpr.sp.qword=0x5000;child.gpr.x30.qword=0x7000;child.fpcr.rmode=kFPURoundDownNegInf;
    Check(fixture->child_runtime->Run(child,INNER,m)==fixture->B(),"different-State inner result");
    Check(!std::memcmp(&s,&before,sizeof(s)),"different-State inner Run cannot mutate outer State");
  }else{
    s.gpr.sp.qword-=0x100;s.gpr.x30.qword=0x7000;s.fpcr.rmode=kFPURoundDownNegInf;
    Check(fixture->child_runtime->Run(s,INNER,m)==fixture->B(),"same-State inner result");
    s.gpr.sp.qword=sp;s.gpr.x30.qword=lr;
  }
  Check(!__bunker_guest_transfer_pending(s),"inner Run cannot leak pending event");
  Check(std::fegetround()==FE_UPWARD,"nested Run restores parent native rounding");
  Check((std::fetestexcept(FE_ALL_EXCEPT)&FE_DIVBYZERO)!=0,"nested Run restores parent exception flags");
  s.gpr.pc.qword=lr;return fixture->B();
}
Memory *Root(State &s,addr_t pc,Memory *m){
  Check(pc==ROOT,"root PC");Check(recomp::CurrentExecutionState()==&s,"root State identity");
  if(fixture->mode==WrongThread){
    std::thread other([&]{__bunker_guest_call(s,LEAF,m,OWNER_RETURN,s.gpr.sp.qword,Leaf);});
    other.join();return m;
  }
  if(fixture->mode==Direct||fixture->mode==Indirect||fixture->mode==Tail||fixture->mode==Import){
    const auto target=fixture->mode==Tail?TAIL:fixture->mode==Import?IMPORT:LEAF;
    s.gpr.x30.qword=OWNER_RETURN;s.gpr.pc.qword=target;
    auto *result=__bunker_guest_call(s,target,m,OWNER_RETURN,s.gpr.sp.qword,
      fixture->mode==Direct?Leaf:fixture->mode==Tail?TailLeaf:nullptr);
    if(__bunker_guest_transfer_pending(s))return result;
    ++fixture->root_after;Finish(s);return result;
  }
  s.gpr.sp.qword-=0x100;s.gpr.x30.qword=OWNER_RETURN;
  const auto target=fixture->mode==Recursive?RECURSE:
    fixture->mode==NestedDifferent||fixture->mode==NestedSame||fixture->mode==CrossState||fixture->mode==EscapeSame?CALLBACK:OWNER;
  s.gpr.x0.qword=0;s.gpr.pc.qword=target;
  auto *result=__bunker_guest_call(s,target,m,OWNER_RETURN,s.gpr.sp.qword,
    target==RECURSE?Recursion:target==CALLBACK?Callback:Owner);
  if(__bunker_guest_transfer_pending(s))return result;
  ++fixture->root_after;Finish(s);return result;
}
void Configure(recomp::Runtime &runtime){
  const recomp::Trace traces[]={{ROOT,Root},{LEAF,Leaf},{TAIL,TailLeaf},{OWNER,Owner},{THROW,Throw},
    {LAND1,LandingOne},{LAND2,LandingTwo},{RETHROW,Rethrow},{RECURSE,Recursion},{INNER,Inner},{CALLBACK,Callback}};
  runtime.AddTraces(traces,sizeof(traces)/sizeof(*traces));
  runtime.AddImport(IMPORT,[](State &s){++fixture->leaf;s.gpr.x0.qword=77;});
}
unsigned RunCase(Mode mode,recomp::Runtime *shared=nullptr){
  Fixture f;fixture=&f;f.mode=mode;recomp::Runtime runtime,child;Configure(runtime);Configure(child);
  f.runtime=shared?shared:&runtime;f.child_runtime=&child;
  f.a.fill(0xa1);f.b.fill(0xb2);f.c.fill(0xc3);const auto a=f.a,b=f.b,c=f.c;
  State state;std::memset(&state,0x5a,sizeof(state));state.fpcr.rmode=kFPURoundToNearestEven;
  state.gpr.sp.qword=f.root_sp;state.gpr.x30.qword=f.root_return;
  std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);
  Memory *result=f.runtime->Run(state,ROOT,f.A());
  Check(result==(mode==NestedRethrow?f.C():mode==Import?f.A():f.B()),"actual final opaque token");
  Check(f.captured&&!std::memcmp(&state,&f.expected,sizeof(state)),"all1200 bytes equal original final State");
  Check(f.a==a&&f.b==b&&f.c==c,"all opaque64 byte buffers unchanged");
  Check(recomp::CurrentExecutionState()==nullptr,"Run frame retired");
  Check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INVALID,"outer native FENV restored");
  if(mode==Landing||mode==NestedRethrow){Check(f.root_after==0&&f.owner_after==0,"abandoned continuations skipped");Check(f.landing1==1,"landing dispatched once");}
  if(mode==NestedRethrow)Check(f.landing2==1&&f.rethrows==1&&state.gpr.x0.qword==84,"nested resume dispatched once");
  if(mode==Ancestor)Check(f.landing1==0&&f.owner_after==0&&f.root_after==1,"ancestor return consumed without landing dispatch");
  if(mode==Recursive)Check(f.recursive_mask==7&&f.recursive_after==3,"samePC recursion matches exact SP");
  if(mode==NestedDifferent||mode==NestedSame)Check(f.callbacks==1&&f.inner==1,"nested Run case executed");
  return f.checks;
}
unsigned LegacyRun(){
  Fixture f;fixture=&f;State state{};state.gpr.pc.qword=0x777777;
  state.gpr.x30.qword=0x888888;state.gpr.sp.qword=0x10000;
  recomp::Runtime runtime;
  const recomp::Trace trace{0x7000,[](State &s,addr_t pc,Memory *m)->Memory*{
    Check(pc==0x7000,"legacy entry PC");s.gpr.x4.qword=123;fixture->expected=s;return m;
  }};
  runtime.AddTraces(&trace,1);
  Check(runtime.Run(state,0x7000,f.A())==f.A(),"legacy Run token");
  Check(!std::memcmp(&state,&f.expected,sizeof(state)),"legacy entry without protocol remains unchanged");
  Check(recomp::CurrentExecutionState()==nullptr,"legacy context retired");
  return f.checks;
}
}
int main(int argc,char **argv){
#ifdef _WIN32
  SetErrorMode(0x1|0x2);
  _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
  if(argc>1){
    Mode mode=Unknown;
    if(!std::strcmp(argv[1],"no-owner"))mode=NoOwner;
    if(!std::strcmp(argv[1],"cross-state"))mode=CrossState;
    if(!std::strcmp(argv[1],"same-state-escape"))mode=EscapeSame;
    if(!std::strcmp(argv[1],"stale-token"))mode=StaleToken;
    if(!std::strcmp(argv[1],"wrong-thread"))mode=WrongThread;
    if(!std::strcmp(argv[1],"outside-run")){
      State s{};__bunker_guest_call(s,LEAF,nullptr,0,0,Leaf);return 9;
    }
    RunCase(mode);return 9;
  }
  unsigned checks=0;
  for(Mode mode:{Direct,Indirect,Tail,Landing,Ancestor,Recursive,NestedRethrow,NestedDifferent,NestedSame,Import})checks+=RunCase(mode);
  std::array<unsigned,4> thread_checks{};std::array<std::thread,4> threads;
  recomp::Runtime shared;Configure(shared);
  for(unsigned n=0;n<threads.size();++n)threads[n]=std::thread([&,n]{thread_checks[n]=RunCase(n&1?NestedRethrow:Recursive,&shared);});
  for(auto &thread:threads){thread.join();}
  for(auto count:thread_checks){checks+=count;}
  checks+=LegacyRun();
  std::printf("GUEST-CALL-TRANSFER-PASS cases=15 checks=%u State_bytes=%zu token_bytes=64\n",checks,sizeof(State));
}
