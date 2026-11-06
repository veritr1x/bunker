#include "runtime.h"
#include <array>
#include <cstdio>
#include <stdexcept>
#include <thread>

namespace {
unsigned checks=0, negatives=0, after=0;
bool bad_memory=false;
void Check(bool ok,const char *why) { ++checks; if(!ok) throw std::runtime_error(why); }
template<class F> void Reject(F f,const char *why) {
  bool rejected=false; try { f(); } catch(const std::logic_error &) { rejected=true; }
  Check(rejected,why); ++negatives;
}
constexpr addr_t entry=0x1000, marker=0x2000, resume=0x1004;
Memory *Guarded(State &s,addr_t,Memory *m) {
  const auto lr=s.gpr.x30.qword;
  s.gpr.x30.qword=resume;
  m=__bunker_guest_call(s,marker,m,resume,s.gpr.sp.qword,nullptr);
  if(__bunker_guest_transfer_pending(s)) return bad_memory?nullptr:m;
  ++after;
  s.gpr.x30.qword=lr;s.gpr.pc.qword=lr;return m;
}
State StateFor() { State s{};s.gpr.sp.qword=0x8000;s.gpr.x30.qword=0x9000;return s; }
}

int main(int argc,char **) {
  try {
    bad_memory=argc>1;
    recomp::Runtime owner,foreign;recomp::ThreadExitDomain domain,other;
    const recomp::Trace trace{entry,Guarded};owner.AddTraces(&trace,1);foreign.AddTraces(&trace,1);
    std::array<unsigned char,64> memory{};auto *token=reinterpret_cast<Memory*>(memory.data());
    unsigned mode=0;
    owner.AddImport(marker,[&](State &s) {
      if(mode==0) {
        Check(!owner.RequestThreadExit(s,domain,1),"ordinary Run cannot request");
        return;
      }
      if(mode==4) {
        Check(!owner.RequestThreadExit(s,domain,1),"opaque nested ordinary Run cannot terminate parent domain");
        return;
      }
      State different=StateFor();
      Check(!owner.RequestThreadExit(different,domain,1),"wrong State rejected");
      Check(!owner.RequestThreadExit(s,other,1),"wrong domain rejected");
      Check(!foreign.RequestThreadExit(s,domain,1),"wrong Runtime request rejected");
      Reject([&]{owner.ConsumeThreadExit(domain);},"consume while active rejected");
      Reject([&]{owner.RunWithThreadExit(different,entry,domain,nullptr);},"nested Memory token mismatch rejected");
      if(mode==1) {
        mode=4;
        Check(owner.Run(different,entry,token)==token,"opaque nested Run ordinary return");
        mode=1;
        Check(!domain.Pending(),"opaque nested request leaves owner outcome untouched");
      }
      if(mode==2) {
        mode=3;
        Check(owner.RunWithThreadExit(different,entry,domain,token)==token,"shared nested token");
        Check(domain.Pending(),"nested outcome propagated");
        return;
      }
      Check(owner.RequestThreadExit(s,domain,0xabcdef0123456789ULL),"owned request accepted");
      Reject([&]{owner.RequestThreadExit(s,domain,2);},"duplicate request rejected");
      Reject([&]{owner.Run(different,entry,token);},"ordinary reentry while pending rejected");
      Reject([&]{owner.RunWithThreadExit(different,entry,other,token);},"different domain reentry while pending rejected");
      Check(recomp::CurrentExecutionState()==&s,"actual active State retained");
    });
    auto s=StateFor();Check(owner.Run(s,entry,token)==token,"ordinary Memory preserved");
    Check(after==1&&!domain.Pending()&&!recomp::CurrentExecutionState(),"ordinary Run quiescent");
    mode=1;s=StateFor();Check(owner.RunWithThreadExit(s,entry,domain,token)==token,"terminal Memory preserved");
    Check(after==2&&domain.Pending()&&!recomp::CurrentExecutionState(),"guard suppresses continuation and retires");
    Check(s.gpr.pc.qword==resume&&s.gpr.sp.qword==0x8000,"terminal request fabricates no State");
    Reject([&]{foreign.ConsumeThreadExit(domain);},"foreign Runtime consume rejected");
    bool foreign_thread_rejected=false;
    std::thread t([&]{try { owner.ConsumeThreadExit(domain); }catch(const std::logic_error&){foreign_thread_rejected=true;}});t.join();
    Check(foreign_thread_rejected&&domain.Pending(),"foreign native consume rejected");++negatives;
    Check(owner.ConsumeThreadExit(domain)==0xabcdef0123456789ULL,"exact opaque exit result");
    Check(!domain.Pending()&&!domain.MemoryToken(),"consumed outcome cleared");
    Reject([&]{owner.ConsumeThreadExit(domain);},"double consume rejected");
    s=StateFor();Reject([&]{foreign.RunWithThreadExit(s,entry,domain,token);},"foreign Runtime cannot reuse domain");
    bool foreign_run_rejected=false;
    std::thread t2([&]{auto child=StateFor();try {owner.RunWithThreadExit(child,entry,domain,token);}catch(const std::logic_error&){foreign_run_rejected=true;}});t2.join();
    Check(foreign_run_rejected,"foreign native Run rejected");++negatives;
    mode=2;s=StateFor();Check(owner.RunWithThreadExit(s,entry,domain,token)==token,"owned reused domain nested Run");
    Check(!recomp::CurrentExecutionState()&&after==2,"both nested frames really retired");
    Check(owner.ConsumeThreadExit(domain)==0xabcdef0123456789ULL,"nested exact result");
    mode=0;s=StateFor();Check(owner.Run(s,entry,token)==token,"outcome cannot leak into ordinary Run");
    Check(after==3&&!recomp::CurrentExecutionState(),"ordinary continuation restored only on new Run");
    for(auto b:memory) Check(b==0,"Memory64 bytes unchanged");
    std::printf("THREAD-EXIT-CONTROLS-PASS checks=%u negatives=%u Memory64=1 synthetic_guarded_protocol=1\n",checks,negatives);return 0;
  }catch(const std::exception &e){std::fprintf(stderr,"THREAD-EXIT-CONTROLS-FAIL %s\n",e.what());return 1;}
}
