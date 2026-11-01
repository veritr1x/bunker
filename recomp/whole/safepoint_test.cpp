#include "safepoint_control.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

using namespace recomp::safepoint_proof;
namespace {
unsigned checks;
thread_local uint64_t host_cookie;
void check(bool value, const char *message) {
  ++checks;
  if (!value) { std::fprintf(stderr,"safepoint proof failed: %s\n",message); std::abort(); }
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
      Binding binding(control,state);runtime.Run(state,entry);
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
      check(snapshot.fast_calls>previous_calls,"fast predicate remains inside executing loop");previous_calls=snapshot.fast_calls;
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
  std::printf("Safepoint materialization proof: %u checks, 260 same-thread pauses, four FPCR modes, GPR/SIMD/stack/TLS/fenv preserved.\n",checks);
}
