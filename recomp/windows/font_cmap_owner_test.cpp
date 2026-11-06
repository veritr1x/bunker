#define NOMINMAX
#include <windows.h>
#include <pthread.h>
#include "pthread_host.h"
#include "nonlocal_jmp.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include <array>
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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
#include "font_cmap_cases.h"
extern "C" Memory *sub_708d905c(State&,addr_t,Memory*);
extern "C" Memory *sub_708d9240(State&,addr_t,Memory*);
extern "C" Memory *sub_708e6e98(State&,addr_t,Memory*);
extern "C" Memory *__real_sub_825b0544(State&,addr_t,Memory*);
namespace {
unsigned checks=0,saves=0,validations=0,creations=0,good=0,same=0,original_calls=0,negatives=0;addr_t last=0;uint64_t generation=0;
void Require(bool yes,const char*why){++checks;if(!yes)throw std::runtime_error(why);}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
bool Translated(addr_t p){return p!=0;}
#include "game_bootstrap_detail.h"
using Thread=bunker::windows::NonlocalJumps::Thread;Thread thread{};recomp::Runtime *runtime=nullptr;GameFontCmapEnvironments *owner=nullptr;bunker::windows::NonlocalJumps*jumps=nullptr;
Memory *Original(State&s,addr_t pc,Memory*m){++original_calls;return sub_708d905c(s,pc,m);}
void Setjmp(State&s){owner->BeforeSetjmp(s,thread.token);const auto env=s.gpr.x0.qword;auto region=owner->Find(env,256,thread.token);Require(region&&region->low==env&&region->high==env+256,"actual original Save has exact live subobject owner");if(generation)Require(generation==region->generation,"loop re-save retains invocation generation");else generation=region->generation;++saves;}
void Validator(State&s){++validations;auto env=s.gpr.x1.qword;good+=Read<uint64_t>(env+0x100)==s.gpr.x0.qword&&Read<uint64_t>(env+0x108)>s.gpr.x0.qword&&Read<uint32_t>(env+0x110)==0&&Read<uint32_t>(env+0x114)==0&&Read<uint32_t>(env+0x118)==44;if(!last||last==env)++same;last=env;
 auto plan=jumps->Inspect(s,env,1);Require(plan.environment==env&&plan.pc==0x708d9240&&plan.sp==env-0x10,"actual Bionic wire context decodes original continuation and stack");}
template<class F>void Reject(F f,const char*why){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Require(rejected,why);++negatives;}
unsigned fake_mode=0,depth=0;addr_t fake_env=0,nested_env=0;uint64_t fake_generation=0,previous_generation=0;
Memory*Fake(State&s,addr_t pc,Memory*m){
 const auto entry=s.gpr.sp.qword,ret=s.gpr.x30.qword;s.gpr.sp.qword=entry-0x1a0;s.gpr.x0.qword=s.gpr.sp.qword+0x10;s.gpr.x30.qword=0x708d9240;s.gpr.pc.qword=pc;fake_env=s.gpr.x0.qword;
 if(fake_mode==1)s.gpr.sp.qword-=16;
 if(fake_mode==2)s.gpr.x0.qword+=8;
 if(fake_mode==3)++thread.token;
 if(fake_mode==4)++thread.generation;
 owner->BeforeSetjmp(s,thread.token);auto region=owner->Find(s.gpr.x0.qword,256,thread.token);Require(bool(region),"synthetic invocation has registered exact subobject");fake_generation=region->generation;
 if(fake_mode==5){GameFontCmapEnvironments other;other.current=[]{return thread;};Require(!other.Find(fake_env,256,thread.token),"another owner instance cannot borrow frame");Reject([&]{other.BeforeSetjmp(s,thread.token);},"another owner cannot certify active save");}
 jumps->Save(s,fake_env,1);
 if(fake_mode==6&&!depth){const auto outer=fake_env;depth=1;State child=s;child.gpr.sp.qword=entry-0x200;child.gpr.x30.qword=0x6f00fff0;owner->Run(child,0x708d905c,m);nested_env=fake_env;depth=0;Require(!owner->Find(nested_env,256,thread.token)&&owner->Find(outer,256,thread.token),"nested return revokes only inner invocation");fake_env=outer;}
 if(fake_mode==7)throw std::runtime_error("explicit TEST native unwind");
 s.gpr.sp.qword=entry;s.gpr.pc.qword=ret;if(fake_mode==8)s.gpr.sp.qword-=16;if(fake_mode==9)s.gpr.pc.qword+=4;return m;
}
void NegativeProfiles(GameFontCmapEnvironments&actual,bunker::windows::NonlocalJumps&nonlocal,addr_t high){
 auto saved=actual.original;actual.original=Fake;auto base_thread=thread;auto state=[&]{State s{};s.gpr.sp.qword=high;s.gpr.x30.qword=0x6f00fff0;return s;};
 State missing=state();missing.gpr.sp.qword-=0x1a0;missing.gpr.x0.qword=missing.gpr.sp.qword+0x10;missing.gpr.x30.qword=0x708d9240;
 Reject([&]{actual.BeforeSetjmp(missing,thread.token);},"valid stack bounds alone never register a save");Reject([&]{nonlocal.Save(missing,missing.gpr.x0.qword,1);},"actual NonlocalJumps rejects unregistered stack buffer");
 auto wrong_site=missing;wrong_site.gpr.x30.qword=0x708d9244;actual.BeforeSetjmp(wrong_site,thread.token);Require(!actual.Find(wrong_site.gpr.x0.qword,256,thread.token),"unknown return site does not admit a frame");
 for(unsigned mode:{1u,2u,3u,4u,7u,8u,9u}){fake_mode=mode;State s=state();Reject([&]{actual.Run(s,0x708d905c,nullptr);},"bad geometry/thread/generation/unwind/return rejects");thread=base_thread;Require(actual.Frames().empty()&&!actual.Find(fake_env,256,thread.token),"failed invocation revokes saved environment");}
 for(unsigned mode:{0u,5u,6u,0u}){fake_mode=mode;State s=state();Require(actual.Run(s,0x708d905c,nullptr)==nullptr,"synthetic valid/nested invocation retains Memory token");Require(actual.Frames().empty()&&!actual.Find(fake_env,256,thread.token),"normal return expires buffer even though bytes remain");Reject([&]{nonlocal.Inspect(missing,fake_env,1);},"nonlocal save cannot outlive original invocation");if(previous_generation)Require(fake_generation>previous_generation,"same address in later invocation receives fresh generation");previous_generation=fake_generation;}
 State bad=state();Reject([&]{actual.Run(bad,0x708d9240,nullptr);},"interior head cannot create owner invocation");bad.gpr.sp.qword-=8;Reject([&]{actual.Run(bad,0x708d905c,nullptr);},"unaligned owner stack rejected");actual.original=saved;
}
}
extern "C" Memory*sub_700b92b0(State&s,addr_t,Memory*m){Setjmp(s);return runtime->Dispatch(s,jumps->Marker("setjmp"),m);}
extern "C" Memory*sub_708e8f70(State&s,addr_t pc,Memory*m){return runtime->Dispatch(s,pc,m);}
extern "C" Memory*__real_sub_825b0544(State&s,addr_t,Memory*m){
 const auto entry=s.gpr.sp.qword,ret=s.gpr.x30.qword;s.gpr.sp.qword=entry-0x140;s.gpr.x0.qword=s.gpr.sp.qword+8;s.gpr.x30.qword=0x825b0580;
 game_environments->BeforeSetjmp(s,thread.token);last=s.gpr.x0.qword;jumps->Save(s,last,0);Require(jumps->Inspect(s,last,1).pc==0x825b0580,"unchanged IL2CPP owner retains actual save/inspect semantics");s.gpr.sp.qword=entry;s.gpr.pc.qword=ret;return m;
}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{
 static_assert(sizeof(State)==1200&&sizeof(Memory*)==8);alignas(16)std::array<uint8_t,65536>stack{};const auto high=reinterpret_cast<addr_t>(stack.data()+stack.size());thread={17,23,reinterpret_cast<addr_t>(stack.data()),high};
 GameFontCmapEnvironments actual;owner=&actual;game_font_environments=&actual;actual.current=[]{return thread;};actual.original=Original;
 bunker::windows::NonlocalJumps nonlocal([]{return thread;},[&](addr_t p,size_t n){auto result=actual.Find(p,n,thread.token);return result||!game_environments?result:game_environments->Find(p,n,thread.token);},[]{return uint64_t(0x80000000);},[](addr_t p){return p==0x708d9240||p==0x825b0580;},0x123456789abcdef0ULL);actual.jumps=&nonlocal;jumps=&nonlocal;
 recomp::Runtime host;runtime=&host;nonlocal.Install(host);recomp::Trace traces[]={{0x708d905c,GameOriginalFontCmapHelper},{0x708d9240,sub_708d9240},{0x708e6e98,sub_708e6e98}};host.AddTraces(traces,std::size(traces));host.AddImport(0x6f001000,Validator);host.AddImport(0x708e8f70,[](State&s){++creations;s.gpr.x0.qword=1;});
 auto*list=static_cast<uint8_t*>(VirtualAlloc(reinterpret_cast<void*>(0x71210000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Require(list==reinterpret_cast<void*>(0x71210000),"owned fixture class array at actual guest address");std::array<std::array<uint8_t,0x60>,2>classes{};uint32_t f4=4,f6=6;uintptr_t fn=0x6f001000,pointers[]={reinterpret_cast<uintptr_t>(classes[0].data()),reinterpret_cast<uintptr_t>(classes[1].data()),0};std::memcpy(classes[0].data()+0x50,&f4,4);std::memcpy(classes[1].data()+0x50,&f6,4);std::memcpy(classes[0].data()+0x58,&fn,8);std::memcpy(classes[1].data()+0x58,&fn,8);std::memcpy(list+0xd858,pointers,sizeof(pointers));DWORD old;Require(VirtualProtect(list,65536,PAGE_READONLY,&old),"fixture class array native readonly");
 for(unsigned c=0;c<FONT_CMAP_CASES;c++){alignas(16)std::array<uint8_t,0x400>face{};std::array<uint8_t,FONT_CMAP_TABLE_BYTES>table{};font_cmap_case(c,face.data(),table.data());saves=validations=creations=good=same=0;last=generation=0;State s{};s.gpr.sp.qword=high;s.gpr.x30.qword=0x6f00fff0;s.gpr.x0.qword=reinterpret_cast<addr_t>(face.data());s.gpr.x19.qword=0x123456789abcdef0ULL;std::array<uint64_t,8>token{};auto unchanged=token;auto*m=reinterpret_cast<Memory*>(token.data());Require(host.Run(s,0x708d905c,m)==m&&token==unchanged,"selected original body retains actual opaque Memory64 token");const unsigned wanted=c==5?2:c==4?1:0;Require(s.gpr.x0.qword==(c==0?8:0)&&s.gpr.sp.qword==high&&s.gpr.pc.qword==0x6f00fff0&&s.gpr.x19.qword==0x123456789abcdef0ULL,"selected original result/SP/continuation/callee-save exact");Require(saves==wanted&&validations==wanted&&creations==wanted&&good==wanted&&same==wanted,"selected original callbacks and native root fields match");Require(actual.Frames().empty()&&(!last||!actual.Find(last,256,thread.token)),"real original invocation retired its optional environment");std::printf("FONT-REF case=%u result=%llu saves=%u validations=%u creations=%u fields=%u same=%u\n",c,(unsigned long long)s.gpr.x0.qword,saves,validations,creations,good,same);}
 NegativeProfiles(actual,nonlocal,high);
 GameAutomaticEnvironments legacy;game_environments=&legacy;legacy.current=[]{return thread;};legacy.jumps=&nonlocal;legacy.original=__real_sub_825b0544;
 for(unsigned i=0;i<2;i++){State s{};s.gpr.sp.qword=high;s.gpr.x30.qword=0x6f00fff0;Require(GameOriginalSaveHelper(s,0x825b0544,nullptr)==nullptr&&legacy.Frames().empty()&&!legacy.Find(last,256,thread.token),"unchanged IL2CPP owner retires actual registered buffer");Reject([&]{nonlocal.Inspect(s,last,1);},"old IL2CPP save also expires at its real return");}
 game_environments=nullptr;Require(VirtualFree(list,0,MEM_RELEASE),"fixture class array cleanup");std::printf("FONT-CMAP-PASS checks=%u original_calls=%u saves=%u negatives=%u State=1200 Memory64=8\n",checks,original_calls,saves,negatives);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"font owner fixture: %s\n",e.what());return 91;}}
