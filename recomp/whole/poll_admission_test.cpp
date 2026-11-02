#include "cooperative_poll.h"
#include "../windows/module_registry.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <mutex>
#include <stdexcept>
#include <thread>
using Clock=std::chrono::steady_clock;
static std::atomic<unsigned> checks{0};
static void Check(bool v,const char*why){++checks;if(!v){std::fprintf(stderr,"poll admission: %s\n",why);std::abort();}}
template<class F>static void Until(F predicate,const char*why){const auto end=Clock::now()+std::chrono::seconds(5);while(!predicate()){Check(Clock::now()<end,why);std::this_thread::yield();}}
static void Put(uint64_t&target,uint64_t value){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&target),&value,8);}
static uint64_t Get(const uint64_t&target){uint64_t value;recomp::ReadGuestMemory(&value,reinterpret_cast<addr_t>(&target),8);return value;}
static void Disturb(){errno=137;std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);}
struct Unit {recomp::PollRequest request;unsigned mode=0,attempts=0,handlers=0;uint64_t captured=0;State*expected=nullptr;std::thread::id worker;};
static thread_local Unit*unit;
static Memory*Protocol(State&s,addr_t,Memory*m){
 auto&u=*unit;u.expected=&s;alignas(128)uint64_t value=7;__remill_aarch64_load_exclusive(s,reinterpret_cast<addr_t>(&value),8,0);
 const State before=s;errno=71;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);bool thrown=false;
 try{__bunker_guest_poll_slow(&s,0x51000000,0,0x51000000);}catch(const std::runtime_error&){Check(u.mode==1,"only expected standard admission exception");thrown=true;}catch(int v){Check(u.mode==2&&v==67,"only expected nonstandard admission exception");thrown=true;}
 Check(thrown==(u.mode==1||u.mode==2),"admission exception outcome");
 if(u.mode<3){Check(!std::memcmp(&s,&before,sizeof(s)),"defer/throw leaves entire State and stale PC unchanged");Check(errno==71&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"defer/throw restores exact native environment, not guest rounding");}
 else{Check(s.gpr.pc.qword==0x51000000,"accepted entry normalizes authoritative PC");Check(errno==71&&std::fegetround()==FE_UPWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"accepted path restores errno/exceptions and reapplies guest rounding");}
 auto status=__remill_aarch64_store_exclusive(s,reinterpret_cast<addr_t>(&value),8,8,0);Check(status==(u.mode<3?0U:1U)&&value==(u.mode<3?8U:7U),"false/throw retain real reservation; accepted delivery clears it");return m;
}
static void UnitTests(){
 recomp::Runtime runtime;recomp::Trace trace{0x51000000,Protocol};runtime.AddTraces(&trace,1);Unit u;unit=&u;u.worker=std::this_thread::get_id();State s{};s.fpcr.rmode=kFPURoundUpInf;s.gpr.sp.qword=0x12345000;s.gpr.x20.qword=0xcafef00d;
 auto handler=[&](State&state,recomp::PollSite site,const std::vector<State*>&frames){Check(&state==u.expected&&frames.size()==1&&frames[0]==&state,"accepted handler gets actual State/frame");Check(std::this_thread::get_id()==u.worker&&!__bunker_guest_poll_requested(),"handler stays on owner with recursive polls suppressed");++u.handlers;u.captured=site.epoch;Disturb();if(u.handlers==1)u.request.Request();};
 {
  recomp::PollBinding binding(u.request,handler,[&](const recomp::PollAdmissionContext&context){
   ++u.attempts;Check(&context.state==u.expected&&context.frames.size()==1&&context.frames[0]==u.expected,"read-only admission State chain");Check(context.program_counter==0x51000000&&context.state.gpr.pc.qword==0xdeadbeef,"effective entry PC reported without normalizing State");Check(!__bunker_guest_poll_requested(),"decision guard suppresses recursive predicates");Disturb();if(u.mode<3)u.request.Request();if(u.mode==1)throw std::runtime_error("TEST admission");if(u.mode==2)throw 67;return u.mode==3;
  });
  u.request.Request();for(unsigned mode=0;mode<4;++mode){u.mode=mode;s.gpr.pc.qword=0xdeadbeef;runtime.Run(s,trace.address);if(mode<3)Check(!u.handlers&&__bunker_guest_poll_requested(),"deferred/throwing requests never complete or invoke handler");}
  Check(u.handlers==1&&u.captured==4&&u.request.Sequence()==5&&__bunker_guest_poll_requested(),"requests during deferral/handler are retained with captured epoch");s.gpr.pc.qword=0xdeadbeef;runtime.Run(s,trace.address);Check(u.handlers==2&&u.captured==5&&!__bunker_guest_poll_requested(),"later same-worker delivery consumes only captured pending epoch");
 }
 {
  recomp::PollBinding deny(u.request,handler,[](const auto&){Disturb();return false;});u.mode=0;u.request.Request();s.gpr.pc.qword=0xdeadbeef;runtime.Run(s,trace.address);Check(__bunker_guest_poll_requested(),"deferred request remains before rebinding");
 }
 {
  recomp::PollBinding accept(u.request,handler);u.mode=3;s.gpr.pc.qword=0xdeadbeef;runtime.Run(s,trace.address);Check(u.handlers==3&&!__bunker_guest_poll_requested(),"pending deferral survives rebinding and default admission remains compatible");
 }
 std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);unit=nullptr;
}
struct alignas(128) Page {uint64_t words[16]{};};
static void ExclusiveLoop(recomp::Runtime&runtime,addr_t entry,addr_t boundary,bool accept_during_loop){
 Page target,gate,output;target.words[0]=7;output.words[0]=0xa5a5a5a5;recomp::PollRequest request;std::atomic<bool>allow{false};std::atomic<unsigned>backedges{0},handled{0};std::atomic<uint64_t>last{0};State snapshot{};std::atomic<unsigned>published{0};std::thread::id worker_id;
 std::thread worker([&]{worker_id=std::this_thread::get_id();alignas(16)std::array<uint8_t,65536>stack{};State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(&target.words[0]);state.gpr.x1.qword=reinterpret_cast<addr_t>(&gate.words[0]);state.gpr.x2.qword=reinterpret_cast<addr_t>(&output.words[0]);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;state.gpr.pc.qword=0xdeadbeef;state.fpcr.rmode=kFPURoundUpInf;
  recomp::PollBinding binding(request,[&](State&,recomp::PollSite site,const auto&){Check(std::this_thread::get_id()==worker_id,"compiled loop handler executes on actual native worker");last=site.epoch;++handled;Put(gate.words[0],1);},[&](const recomp::PollAdmissionContext&context){Check(context.frames.size()==1&&context.frames[0]==&context.state,"compiled-loop actual materialized State");if(context.site.ordinal){++backedges;unsigned zero=0;if(published.compare_exchange_strong(zero,1)){snapshot=context.state;published.store(2,std::memory_order_release);}}Disturb();return allow.load(std::memory_order_acquire);});
  errno=71;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);runtime.Run(state,entry);Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"compiled exclusive loop normal PC/SP");
  if(!accept_during_loop){Check(handled==0&&__bunker_guest_poll_requested(),"compiled false decisions never invoke handler or acknowledge");allow=true;}
  // Admission may see allow=true after this boundary already captured an older
  // request epoch. That epoch is valid; newer requests must remain pending.
  if(__bunker_guest_poll_requested()){State retry{};retry.gpr.sp.qword=state.gpr.sp.qword;retry.gpr.x30.qword=0xfeedffff;runtime.Run(retry,boundary);}
  Check(handled>=1&&handled<=3&&last==3&&!__bunker_guest_poll_requested()&&(accept_during_loop||handled==1),"captured epochs and newer deferred requests are delivered on same worker");Check(errno==71&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"compiled path restores outer native environment");
 });
 request.Request();Until([&]{return published.load(std::memory_order_acquire)==2&&backedges>3;},"compiled loop reached deferred backedge");Check(snapshot.gpr.x10.qword==7,"actual LDXR executed before backedge admission");request.Request();request.Request();
 if(accept_during_loop)allow=true;else Put(gate.words[0],1);worker.join();Check(uint32_t(Get(output.words[0]))==(accept_during_loop?1U:0U)&&Get(target.words[0])==(accept_during_loop?7U:8U),"actual NDK LDXR/STXR preserves on false and clears on acceptance");
}
static thread_local unsigned opaque_depth;
struct OpaqueControl {Page memory;recomp::PollRequest request;std::atomic<unsigned>phase{0},deferred[3]{},handled{0};std::atomic<uint64_t>epoch[3]{};std::mutex mutex;std::condition_variable condition;unsigned parked=0,resume=0;State*parent=nullptr;std::thread::id worker;};
static void RegistryCase(recomp::Runtime&runtime,addr_t parent,addr_t child,bunker::windows::ModuleRegistry&registry,recomp::Runtime&bridges,OpaqueControl&control){
 auto wrap=[&](const char*name,bool closing){const auto marker=registry.Marker(name);runtime.AddImport(marker,[&,marker,closing](State&s){if(closing)Put(control.memory.words[0],0);struct Scope{OpaqueControl&c;Scope(OpaqueControl&c,unsigned phase):c(c){++opaque_depth;c.phase=phase;c.request.Request();}~Scope(){--opaque_depth;c.phase=0;}}scope(control,closing?2:1);bridges.Dispatch(s,marker,nullptr);});};wrap("dlopen",false);wrap("dlclose",true);
 std::thread worker([&]{control.worker=std::this_thread::get_id();alignas(16)std::array<uint8_t,65536>stack{};State state{};control.parent=&state;state.gpr.x0.qword=reinterpret_cast<addr_t>(control.memory.words);state.gpr.x1.qword=0xcafef00d;state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0xfeedffff;state.fpcr.rmode=kFPURoundUpInf;state.simd.v[31]={};
  recomp::PollBinding binding(control.request,[&](State&s,recomp::PollSite site,const std::vector<State*>&frames){Check(!opaque_depth&&frames.size()==1&&frames[0]==control.parent&& &s==control.parent,"only unlocked parent phase is admitted");unsigned number=++control.handled;control.epoch[number]=site.epoch;std::unique_lock lock(control.mutex);control.parked=number;control.condition.notify_all();control.condition.wait(lock,[&]{return control.resume>=number;});},[&](const recomp::PollAdmissionContext&context){if(opaque_depth){unsigned phase=control.phase.load();Check(phase==1||phase==2,"real registry phase identified");Check(context.frames.size()==2&&context.frames[1]==control.parent&&context.state.gpr.x20.qword==0x12345678&&context.frames[1]->gpr.x20.qword==0xcafef00d,"parent-only/child State values remain distinct in opaque callback");++control.deferred[phase];Disturb();return false;}return true;});
  errno=71;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);runtime.Run(state,parent);Check(state.gpr.pc.qword==0xfeedffff&&state.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"registry parent returns with original stack");Check(errno==71&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"opaque/accepted nested paths preserve outer native environment");Check(!__bunker_guest_poll_requested(),"both pending registry requests complete after unlocking");
 });
 for(unsigned phase=1;phase<=2;++phase){Until([&]{return control.deferred[phase]>3;},"opaque registry guest callback deferred");Check(control.handled==phase-1,"no handler or false acknowledgment while registry is locked");std::atomic<bool>reader_done{false};size_t references=99;std::thread reader([&]{references=registry.ReferenceCount("admission-test.so");reader_done=true;});control.request.Request();if(phase==1)control.request.Request();Put(control.memory.words[0],1);
  {std::unique_lock lock(control.mutex);Check(control.condition.wait_for(lock,std::chrono::seconds(5),[&]{return control.parked>=phase;}),"deferred request accepted after registry callback returns");}
  Until([&]{return reader_done.load();},"registry reader progresses while accepted handler parks");reader.join();Check(references==(phase==1?1U:0U),"real module lifecycle reference state");uint64_t probe=0;Put(probe,phase);Check(Get(probe)==phase,"tracked memory progresses while handler parks");Put(control.memory.words[1],phase);{std::lock_guard lock(control.mutex);control.resume=phase;}control.condition.notify_all();
 }
 worker.join();Check(control.handled==2&&control.epoch[1]==3&&control.epoch[2]==5&&Get(control.memory.words[2])==0xcafef00d,"ctor/fini deferrals retain requests and actual parent value");(void)child;
}
static bunker::windows::ModuleRegistry*resolver;
static void*Resolve(const char*name){return reinterpret_cast<void*>(resolver->Marker(name));}
int main(){UnitTests();recomp::Runtime runtime,bridges;runtime.AddTraces(kTraces,std::size(kTraces));elf_image image{};OpaqueControl control;unsigned lifecycle=0;addr_t child=0;
 bunker::windows::ModuleRegistry registry([&](addr_t entry){Check(entry==child&&opaque_depth==1,"actual registry lifecycle callback owns opaque phase");auto*outer=recomp::CurrentExecutionState();Check(outer==control.parent,"actual parent Runtime context retained");const State before=*outer;State inner=before;inner.gpr.x0.qword=reinterpret_cast<addr_t>(&control.memory.words[0]);inner.gpr.x20.qword=0x12345678;inner.gpr.x22.qword=0;inner.gpr.x30.qword=0xfeedffff;inner.fpcr.rmode=kFPURoundToNearestEven;const State child_initial=inner;int error=errno,rounding=std::fegetround(),exceptions=std::fetestexcept(FE_ALL_EXCEPT);runtime.Run(inner,entry);Check(!std::memcmp(outer,&before,sizeof(before)),"nested registry guest call preserves complete parent State");Check(inner.gpr.pc.qword==0xfeedffff&&inner.gpr.sp.qword==before.gpr.sp.qword&&inner.gpr.x20.qword==0x12345678&&inner.gpr.x22.qword>0,"nested child state and normal stack return");State child_expected=child_initial;child_expected.gpr.pc.qword=0xfeedffff;child_expected.gpr.x9.qword=1;child_expected.gpr.x22.qword=inner.gpr.x22.qword;Check(!std::memcmp(&inner,&child_expected,sizeof(inner)),"complete child State follows only its actual loop effects");Check(errno==error&&std::fegetround()==rounding&&std::fetestexcept(FE_ALL_EXCEPT)==exceptions,"nested rejected polls preserve native callback errno/fenv");++lifecycle;});resolver=&registry;registry.Install(bridges);Check(!elf_load(ADMISSION_LIBRARY,0x59000000,Resolve,&image),"actual NDK admission fixture loads");auto symbol=[&](const char*name){auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(pc!=0,"fixture exported entry exists");return pc;};
 ExclusiveLoop(runtime,symbol("admission_exclusive"),symbol("admission_boundary"),false);ExclusiveLoop(runtime,symbol("admission_exclusive"),symbol("admission_boundary"),true);child=symbol("admission_child");bunker::windows::Module module;module.name="admission-test.so";module.initializers={child};module.finalizers={child};registry.Add(std::move(module));RegistryCase(runtime,symbol("admission_parent"),child,registry,bridges,control);Check(lifecycle==2&&!registry.ReferenceCount("admission-test.so"),"real ctor/fini ownership completed");std::printf("POLL-ADMISSION-SUCCESS checks=%u exclusive_profiles=2 registry_phases=2 no-GC-or-root-safety-claim\n",checks.load());}
