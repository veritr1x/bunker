#include "cooperative_poll.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

namespace {
struct Snapshot {
  State state{}; addr_t state_address=0; uint64_t site=0,epoch=0,fast_calls=0;
  std::thread::id worker; int rounding=0,exceptions=0,error=0;
};
struct Control {
  recomp::PollRequest request;
  std::mutex mutex; std::condition_variable condition;
  uint64_t parked=0,resumed=0; Snapshot snapshot;
  uint64_t Request(){return request.Request();}
  bool Wait(uint64_t epoch,Snapshot &out,std::chrono::milliseconds timeout){
    std::unique_lock lock(mutex);
    if(!condition.wait_for(lock,timeout,[&]{return parked>=epoch;}))return false;
    out=snapshot;return true;
  }
  void Resume(uint64_t epoch){std::lock_guard lock(mutex);resumed=epoch;condition.notify_all();}
};
class Binding {
  recomp::PollBinding binding;
 public:
  Binding(Control &control,State &expected):binding(control.request,[&](State &state,recomp::PollSite site,const std::vector<State*> &frames){
    if(&state!=&expected||frames.size()!=1||frames[0]!=&state)std::abort();
    std::unique_lock lock(control.mutex);
    auto &s=control.snapshot;s.state=state;s.state_address=reinterpret_cast<addr_t>(&state);
    s.site=(site.trace<<8)|site.ordinal;s.epoch=site.epoch;++s.fast_calls;
    s.worker=std::this_thread::get_id();s.rounding=std::fegetround();s.exceptions=std::fetestexcept(FE_ALL_EXCEPT);s.error=errno;
    errno=123;std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);
    control.parked=site.epoch;control.condition.notify_all();
    control.condition.wait(lock,[&]{return control.resumed>=site.epoch;});
  }){}
};
unsigned checks;
thread_local uint64_t host_cookie;
void check(bool value, const char *message) {
  ++checks;
  if (!value) { std::fprintf(stderr,"safepoint proof failed: %s\n",message); std::abort(); }
}
Memory *ProtocolEntry(State &s,addr_t,Memory *m){
  const addr_t address=s.gpr.x0.qword;
  __remill_aarch64_load_exclusive(s,address,8,0);
  if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(&s,0x1000,0,0x1000);
  s.gpr.x1.qword=__remill_aarch64_store_exclusive(s,address,99,8,0);
  if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(&s,0x1000,1,0);
  return m;
}
recomp::Runtime *nested_runtime;
State *outer_state;
Memory *InnerEntry(State &s,addr_t,Memory *m){
  if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(&s,0x1004,0,0x1004);
  s.gpr.x2.qword=std::fegetround()==FE_UPWARD;
  return m;
}
Memory *OuterEntry(State &s,addr_t,Memory *m){
  State inner{};inner.gpr.x19.qword=0x9876;outer_state=&s;
  nested_runtime->Run(inner,0x1004,m);return m;
}
void ProtocolTests(){
  check(!__bunker_guest_poll_requested(),"unbound poll predicate is false");
  recomp::Runtime runtime;
  recomp::Trace traces[]={{0x1000,ProtocolEntry},{0x1004,InnerEntry},{0x1008,OuterEntry}};
  runtime.AddTraces(traces,3);nested_runtime=&runtime;
  alignas(16) uint64_t value=7;State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(&value);
  runtime.Run(state,0x1000);check(!state.gpr.x1.qword&&value==99,"unbound fast polls preserve exclusives");
  recomp::PollRequest request;
  unsigned calls=0;
  {
    recomp::PollBinding binding(request,[&](State &s,recomp::PollSite site,const std::vector<State*> &frames){
      ++calls;check(frames.size()==1&&frames[0]==&s,"current State frame published");
      check(!__bunker_guest_poll_requested(),"same binding suppresses recursive handler polls");
      check(site.epoch==calls,"delivery carries captured epoch");
      if(calls==1)request.Request();
      uint64_t read;recomp::ReadGuestMemory(&read,reinterpret_cast<addr_t>(&value),8);
      check(read==7,"no memory lock held during callback");
    });
    bool rejected=false;try{recomp::PollBinding duplicate(request,[](auto&,auto,const auto&){});}catch(const std::invalid_argument&){rejected=true;}
    check(rejected,"duplicate worker binding rejected");
    value=7;request.Request();runtime.Run(state,0x1000);
    check(calls==2&&state.gpr.x1.qword==1&&value==7,"delivery clears reservation and retains request arriving during callback");
    check(!__bunker_guest_poll_requested(),"all delivered epochs acknowledged");
  }
  {
    recomp::PollBinding binding(request,[&](auto&,auto,const auto&){++calls;});
    check(!__bunker_guest_poll_requested(),"acknowledgment persists across rebinding");
  }
  request.Request();request.Request();
  {
    recomp::PollBinding binding(request,[&](State &s,recomp::PollSite site,const std::vector<State*> &frames){
      check(site.epoch==4&&frames.size()==2&&frames[0]==&s&&frames[1]==outer_state,"nested parent State roots visible");
      check(outer_state->gpr.x20.qword==0xcafef00d&&s.gpr.x19.qword==0x9876,"parent-only and child roots distinct");
      State handler{};runtime.Run(handler,0x1004);++calls;
    });
    state.gpr.x20.qword=0xcafef00d;runtime.Run(state,0x1008);
    check(calls==3,"preexisting requests coalesce; nested handler guest calls do not redeliver");
  }
  request.Request();
  errno=71;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
  {
    recomp::PollBinding binding(request,[&](auto&,auto,const auto&){errno=123;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);throw std::runtime_error("delivery failed");});
    bool thrown=false;try{runtime.Run(state,0x1004);}catch(const std::runtime_error&){thrown=true;}
    check(thrown&&__bunker_guest_poll_requested(),"throwing delivery remains pending");
    check(errno==71&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"exception unwinds poll binding and Runtime fenv/errno scopes");
  }
  {
    recomp::PollBinding binding(request,[&](State &s,auto,const auto&){s.fpcr.rmode=kFPURoundUpInf;++calls;});
    bool rejected=false;try{__bunker_guest_poll_slow(&state,0x1004,0,0x1004);}catch(const std::invalid_argument&){rejected=true;}
    check(rejected&&__bunker_guest_poll_requested(),"wrong execution boundary rejected without acknowledging pending request");
    check(errno==71&&std::fegetround()==FE_DOWNWARD,"invalid boundary preserves caller errno and rounding");
    runtime.Run(state,0x1004);check(calls==4&&!__bunker_guest_poll_requested(),"failed delivery can retry under a later binding");
    check(state.gpr.x2.qword==1&&state.fpcr.rmode==1&&std::fegetround()==FE_DOWNWARD,"resumed guest observes changed FPCR while caller rounding is restored");
  }
  request.Request();
  {
    recomp::PollBinding binding(request,[](State &s,auto,const auto&){s.gpr.pc.qword=0xdeadbeef;});
    bool rejected=false;try{runtime.Run(state,0x1004);}catch(const std::invalid_argument &error){rejected=std::strstr(error.what(),"cannot redirect");}
    check(rejected&&__bunker_guest_poll_requested(),"unsupported PC redirection fails explicitly and does not acknowledge request");
  }
  std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);
}
uint64_t gp(const State &state, unsigned index) {
  uint64_t value; std::memcpy(&value, reinterpret_cast<const char *>(&state.gpr) + index * 16 + 8, 8); return value;
}
void gp(State &state, unsigned index, uint64_t value) {
  std::memcpy(reinterpret_cast<char *>(&state.gpr) + index * 16 + 8, &value, 8);
}
uint64_t lane(const State &state, unsigned vector, unsigned index) {
  uint64_t value; std::memcpy(&value, reinterpret_cast<const char *>(&state.simd.v[vector]) + index * 8, 8); return value;
}
}
int main() {
  ProtocolTests();
  std::thread([] { std::this_thread::sleep_for(std::chrono::seconds(40)); std::fputs("safepoint proof watchdog\n",stderr); std::_Exit(95); }).detach();
  elf_image image{};
  check(!elf_load(SAFEPOINT_LIBRARY,0x56000000,nullptr,&image),"fixture image load");
  const auto entry = reinterpret_cast<addr_t>(elf_symbol(&image,"safepoint_loop"));
  const auto head = reinterpret_cast<addr_t>(elf_symbol(&image,"safepoint_loop_head"));
  recomp::Runtime runtime; runtime.AddTraces(kTraces,std::size(kTraces));
  constexpr uint64_t iterations = 20000000;
  const int modes[] = {FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO};
  for (unsigned mode = 0; mode < 4; ++mode) {
    Control control;
    alignas(16) std::array<uint64_t,4> roots{{1,2,3,4}};
    alignas(16) std::array<uint64_t,6> output{};
    alignas(16) std::array<unsigned char,65536> stack{};
    alignas(16) std::array<uint64_t,8> tls{{0x5678}};
    const addr_t root = reinterpret_cast<addr_t>(roots.data());
    const addr_t sp = reinterpret_cast<addr_t>(stack.data() + stack.size());
    State state{};
    for (unsigned index=0;index<31;++index) gp(state,index,0xbad0000000ULL + index*0x101);
    for (unsigned index=0;index<32;++index) {
      uint64_t lanes[]={0x7ff8000000000000ULL+index,0xfff0000000000001ULL+index};
      std::memcpy(&state.simd.v[index],lanes,16);
    }
    const uint32_t one=0x3f800000,half_ulp=0x33800000;
    std::memcpy(&state.simd.v[3],&one,4);std::memcpy(&state.simd.v[4],&half_ulp,4);
    state.gpr.x0.qword=root;state.gpr.x1.qword=reinterpret_cast<addr_t>(output.data());
    state.gpr.x9.qword=iterations;state.gpr.sp.qword=sp;state.gpr.pc.qword=entry;state.gpr.x30.qword=0xfeedffff;
    state.sr.tpidr_el0.qword=reinterpret_cast<addr_t>(tls.data());state.sr.tpidrro_el0.qword=0x12345678;
    state.fpcr.flat=uint64_t(mode)<<22;state.sr.ioc=1;state.sr.ixc=1;state.sr.idc=1;
    state.sr.n=1;state.sr.z=1;state.sr.c=0;state.sr.v=1;
    State initial=state;
    uint64_t epoch=control.Request();
    std::thread worker([&] {
      host_cookie=0x778899aabbccddULL;errno=71;
      std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
      Binding binding(control,state);state.gpr.pc.qword=0xdeadbeef;runtime.Run(state,entry);
      check(host_cookie==0x778899aabbccddULL&&errno==71,"host TLS/errno restored after all slow polls");
      check(std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"Runtime host fenv restored after all slow polls");
    });
    uint64_t previous_calls=0, previous_iteration=0;
    unsigned backedge_parks=0;
    for (unsigned pause=0;pause<65;++pause) {
      Snapshot snapshot;
      check(control.Wait(epoch,snapshot,std::chrono::seconds(3)),"bounded materialization acknowledgment");
      check(snapshot.worker==worker.get_id()&&snapshot.worker!=std::this_thread::get_id(),"slow poll executes on original guest worker");
      check(snapshot.state_address==reinterpret_cast<addr_t>(&state)&&snapshot.epoch==epoch,"explicit State pointer and request epoch");
      check(snapshot.fast_calls>previous_calls,"new explicit delivery at executing loop boundary");previous_calls=snapshot.fast_calls;
      check(snapshot.rounding==modes[mode]&&!snapshot.exceptions&&snapshot.error==71,"slow poll preserves guest rounding, host flags and errno");
      const auto &s=snapshot.state;
      check(s.sr.tpidr_el0.qword==initial.sr.tpidr_el0.qword&&s.sr.tpidrro_el0.qword==initial.sr.tpidrro_el0.qword,"guest TLS registers materialized");
      check(s.fpcr.flat==initial.fpcr.flat&&s.fpsr.flat==initial.fpsr.flat&&s.sr.ioc&&s.sr.ixc&&s.sr.idc&&
            !s.sr.ofc&&!s.sr.ufc&&!s.sr.dzc&&s.nzcv.flat==initial.nzcv.flat,"FPCR/FPSR/cumulative flags materialized");
      const bool entry_poll=(snapshot.site&255)==0;
      uint64_t count=entry_poll?0:s.gpr.x21.qword;
      if (entry_poll) {
        check(!pause,"trace entry check occurs before loop");
        check(std::memcmp(&s,&initial,sizeof(State))==0,"trace-entry complete State snapshot");
      } else {
        ++backedge_parks;
        check(count>=previous_iteration&&count>0&&count<iterations,"counter materialized during active loop");previous_iteration=count;
        check(s.gpr.x9.qword+count==iterations&&s.gpr.x20.qword==(root^((count&1)?8:0)),"live GPR pointer root and counter coherent");
        check(s.gpr.x22.qword==initial.sr.tpidr_el0.qword&&s.gpr.sp.qword==sp-32,"guest SP and TLS-derived register coherent");
        check(s.gpr.pc.qword==head,"materialized PC is exact next guest instruction at backedge boundary");
        check(!s.sr.n&&!s.sr.z&&s.sr.c&&!s.sr.v,"arithmetic NZCV materialized");
        uint64_t saved_tls=0;recomp::ReadGuestMemory(&saved_tls,s.gpr.sp.qword,8);
        check(saved_tls==initial.sr.tpidr_el0.qword,"stack visible and guest-memory lock is not held by parked worker");
      }
      for(unsigned index=0;index<31;++index)
        if(entry_poll||(index!=9&&index!=20&&index!=21&&index!=22))check(gp(s,index)==gp(initial,index),"all unaffected GPRs preserved");
      for(unsigned index=0;index<32;++index)for(unsigned element=0;element<2;++element) {
        uint64_t expected=lane(initial,index,element);
        if(!entry_poll&&index==29)expected=root+count;
        if(!entry_poll&&index==30)expected=count;
        if(!entry_poll&&index==31)expected=root;
        check(lane(s,index,element)==expected,"all SIMD lanes and live SIMD roots materialized");
      }
      uint64_t probe=0,changed=epoch;
      recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&probe),&changed,sizeof(changed));
      check(probe==epoch,"tracked host write progresses while guest is parked");
      control.Resume(epoch);
      if(pause<64)epoch=control.Request();
    }
    worker.join();
    check(backedge_parks==64,"repeated import-free backedge pause/resume");
    check(state.gpr.x21.qword==iterations&&!state.gpr.x9.qword&&state.gpr.sp.qword==sp&&state.gpr.pc.qword==0xfeedffff,"final counters/PC/SP after resume");
    check(output[0]==root&&output[2]==root&&output[3]==root&&output[4]==root+iterations&&output[5]==root+iterations,"resumed GPR/SIMD roots used correctly after loop");
    check(output[1]==uint64_t(0x3f800000u+(mode==1)),"actual guest FADD after all resumes observes correct host rounding");
  }
  std::printf("Integrated cooperative polling: %u checks, 260 same-thread pauses, four FPCR modes, GPR/SIMD/stack/TLS/fenv preserved.\n",checks);
}
