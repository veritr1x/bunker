#include <cfenv>
#include "signal_futex.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cerrno>
#include <future>
#include <memory>
#include <stdexcept>
#include <thread>
using namespace bunker::windows;
namespace {
thread_local uint64_t current;
thread_local int guest_error;
std::atomic<unsigned> checks{0};
void Check(bool value,const char*why){if(!value)throw std::runtime_error(why);++checks;}
template<class F>void Until(F f){const auto end=std::chrono::steady_clock::now()+std::chrono::seconds(3);while(!f()){Check(std::chrono::steady_clock::now()<end,"bounded actual wait enrollment");std::this_thread::sleep_for(std::chrono::milliseconds(1));}}
struct Relative {int64_t seconds,nanoseconds;};
const auto known=SignalHost::Bit(30)|SignalHost::Bit(24);
struct Fixture {
 SignalHost signals;std::atomic<unsigned> enrolled{0},dispatched{0},handled{0};
 alignas(64)uint32_t word=0;SignalFutexes futex;
 bool change_word=false;unsigned handler_delay=0;
 Fixture():futex(signals,[]{return current;},[this](const auto&delivery)->std::optional<uint64_t>{
  Check(delivery.signal==30&&delivery.info[100]==30,"actual selected signal and retained info");
  Check(futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x81,1,0,0,0)==0,"provider withdraws ticket BEFORE actual boundary callback");
  uint64_t mask=0;Check(!signals.Mask(current,0,nullptr,&mask),"wrapped boundary outside model locks");
  ++handled;if(change_word)recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&word),&one,sizeof(one));
  if(handler_delay)std::this_thread::sleep_for(std::chrono::milliseconds(handler_delay));
  errno=999;std::fesetround(FE_UPWARD);std::feraiseexcept(FE_INVALID);
  return {};
 },[this](uint64_t token){Check(token==2,"actual enrolled worker token");++enrolled;return SignalHost::Bit(30);}) {
  current=1;Check(!signals.RegisterThread(1)&&!signals.BindCurrent(1),"real main registration and bind");
  Check(!signals.RegisterThread(2,1),"real child registration");
  futex.SetErrorSink([](int error){guest_error=error;});
  for(int sig:{30,24,12}){AndroidSignalAction a{};a.handler=0x12340000;Check(!signals.Action(sig,&a,nullptr),"TEST caught action only, no original handler-body claim");}
 }
 static constexpr uint32_t one=1;
 void Restart(bool enabled){AndroidSignalAction a{};a.handler=0x12340000;a.flags=enabled?0x10000000:0;Check(!signals.Action(30,&a,nullptr),"actual SA_RESTART disposition");}
 void Queue(int signal){SignalHost::Info info{};info[100]=uint8_t(signal);Check(!signals.Queue(2,signal,&info),"real queued model signal/info");}
 void Inspect(std::initializer_list<int> pending){
  for(int signal:pending){Check(SignalHost::NeedsPoll(signals.Lookup(2)),"retained pending bit before TEST-only inspection");
   auto selected=signals.DispatchOneAdmittedSubset(2,known|SignalHost::Bit(12),SignalHost::Bit(signal),[&](const auto&d)->std::optional<uint64_t>{Check(d.signal==signal&&d.info[100]==signal,"all retained siginfo bytes survive deferred/rejected selection");return {};});
   Check(!selected.error&&selected.handled,"TEST-only retained-bit inspection after provider result");}
  Check(!SignalHost::NeedsPoll(signals.Lookup(2)),"no unexamined signal after TEST-only inspection");
 }
 struct Result {int64_t value=99;int error=0;std::exception_ptr exception;std::chrono::nanoseconds elapsed{};};
 std::thread Start(Result&r,Relative*timeout,std::function<void()>after={}) {
  return std::thread([&,timeout,after]{current=2;Check(!signals.BindCurrent(2),"actual native waiter binding");guest_error=731;
   errno=88;std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);
   const auto begin=std::chrono::steady_clock::now();
   try{r.value=futex.Syscall(98,reinterpret_cast<addr_t>(&word),0x80,0,reinterpret_cast<addr_t>(timeout),0,0);}catch(...){r.exception=std::current_exception();}
   r.elapsed=std::chrono::steady_clock::now()-begin;r.error=guest_error;
   Check(errno==88&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"callback/native exception path preserves errno/fenv");
   if(after){after();}
   Check(!signals.DropThread(2),"same-worker actual retirement after inspection");
  });
 }
 void Subset(){futex.SetDispatcher([this](uint64_t token,uint64_t bits,const SignalHost::Boundary&wrapped){++dispatched;Check(bits==SignalHost::Bit(30),"real provider admission forwarded unchanged");return signals.DispatchOneAdmittedSubset(token,known,SignalHost::Bit(30),wrapped);});}
 ~Fixture(){Check(!signals.DropThread(1),"actual main retirement");}
};
}
int main(){try{
 // These are labelled direct-provider tests, not compiler safepoints or GC
 // handlers. The separate unchanged NDK timed/untimed tests cover the default.
 for(bool restart:{false,true}){
  Fixture h;h.Restart(restart);h.Subset();h.handler_delay=70;h.Queue(30);h.Queue(24);
  Relative timeout{0,30000000};Fixture::Result r;auto worker=h.Start(r,&timeout,[&]{h.Inspect({24});});worker.join();
  Check(!r.exception&&r.value==-1&&r.error==4&&h.handled==1,"timed caught handler returns EINTR even SA_RESTART and handler overruns deadline");
  Check(r.elapsed>=std::chrono::milliseconds(60),"real boundary handler delay observed");
 }
 for(bool restart:{false,true}){
  Fixture h;h.Restart(restart);h.Subset();h.change_word=restart;h.Queue(30);h.Queue(24);
  Fixture::Result r;auto worker=h.Start(r,nullptr,[&]{h.Inspect({24});});worker.join();
  Check(!r.exception&&r.value==-1&&r.error==(restart?11:4)&&h.handled==1,"untimed original expected/restart/recomparison preserved");
 }
 {Fixture h;h.Queue(30);h.Queue(24);Relative timeout{0,40000000};std::atomic<unsigned> copied{0};
  h.futex.SetWaitObserver([&](const auto&o){if(o.phase==SignalFutexes::WaitPhase::Copied){++copied;Check(o.copied&&o.deadline_valid&&o.nanoseconds==40000000,"one immutable copied timeout/deadline");timeout={10,0};}});
  h.futex.SetDispatcher([&](uint64_t token,uint64_t,const SignalHost::Boundary&){++h.dispatched;return h.signals.DispatchOneAdmittedSubset(token,known,0,{});});
  Fixture::Result r;auto worker=h.Start(r,&timeout,[&]{h.Inspect({30,24});});
  Until([&]{return h.enrolled.load()!=0;});for(unsigned i=0;i<5;++i){h.signals.Wake(2)->Notify();std::this_thread::sleep_for(std::chrono::milliseconds(2));}worker.join();
  Check(!r.exception&&r.value==-1&&r.error==110&&h.handled==0&&copied==1,"deferred subset preserves timer and never invokes real wrapped boundary");
  Check(r.elapsed>=std::chrono::milliseconds(30)&&r.elapsed<std::chrono::seconds(2),"deferral/spurious wakes/source mutation never rearm duration");
  Check(!h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0),"expired deferred ticket fully removed");
 }
 {Fixture h;h.Queue(30);h.Queue(24);h.Queue(12);h.Subset();Relative timeout{5,0};Fixture::Result r;
  auto worker=h.Start(r,&timeout,[&]{h.Inspect({30,24,12});});worker.join();
  Check(r.exception&&h.handled==0,"mixed unknown signal rejected before any selection or boundary");
  Check(!h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0),"unknown rejection removes only real waiter ticket");
 }
 {Fixture h;h.Queue(30);h.Queue(24);Relative timeout{5,0};Fixture::Result r;
  h.futex.SetDispatcher([&](uint64_t token,uint64_t,const SignalHost::Boundary&){++h.dispatched;return h.signals.DispatchOneAdmittedSubset(token,known,0,{});});
  auto worker=h.Start(r,&timeout,[&]{h.Inspect({30,24});});Until([&]{return h.dispatched.load()!=0;});
  bool rejected=false;try{h.futex.SetDispatcher({});}catch(const std::logic_error&){rejected=true;}Check(rejected,"dispatcher reconfiguration rejects live provider call");
  Check(h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0)==1,"genuine WAKE selects still-linked deferred ticket");worker.join();
  Check(!r.exception&&r.value==0&&r.error==731&&h.handled==0,"deferred dispatch did not remove ticket or synthesize EINTR/success");
 }
 for(bool select_wake:{false,true}){
  Fixture h;h.Queue(30);h.Queue(24);Relative timeout{0,30000000};Fixture::Result r;
  h.futex.SetDispatcher([&](uint64_t token,uint64_t,const SignalHost::Boundary&wrapped){++h.dispatched;
   if(select_wake)Check(h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0)==1,"genuine WAKE before provider boundary cause latch");
   else std::this_thread::sleep_for(std::chrono::milliseconds(50));
   return h.signals.DispatchOneAdmittedSubset(token,known,SignalHost::Bit(30),wrapped);
  });auto worker=h.Start(r,&timeout,[&]{h.Inspect({24});});worker.join();
  Check(!r.exception&&h.handled==1&&r.value==(select_wake?0:-1)&&r.error==(select_wake?731:110),"provider's real boundary exclusively latches prior WAKE or elapsed timeout");
 }
 {Fixture h;h.Queue(30);h.Queue(24);Relative timeout{5,0};Fixture::Result r;
  h.futex.SetDispatcher([](uint64_t,uint64_t,const SignalHost::Boundary&)->SignalHost::Dispatch{errno=999;std::fesetround(FE_UPWARD);throw std::runtime_error("TEST dispatcher throw");});
  auto worker=h.Start(r,&timeout,[&]{h.Inspect({30,24});});worker.join();Check(r.exception&&h.handled==0,"throwing dispatcher consumes no model signal");
  Check(!h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0),"throwing dispatcher leaves no real waiter behind");
 }
 {Fixture h;struct Payload{std::function<void()> retire;~Payload(){retire();}};bool retired=false;
  auto payload=std::make_shared<Payload>();payload->retire=[&]{Check(!h.futex.Syscall(98,reinterpret_cast<addr_t>(&h.word),0x81,1,0,0,0),"old dispatcher capture retires outside queue lock");retired=true;};
  h.futex.SetDispatcher([payload](uint64_t,uint64_t,const SignalHost::Boundary&){return SignalHost::Dispatch{};});payload.reset();h.futex.SetDispatcher({});Check(retired,"quiescent empty hook releases previous callback outside lock");
  // Empty hook must restore actual default unknown-signal admission behavior.
  h.Queue(24);Relative timeout{5,0};Fixture::Result r;auto worker=h.Start(r,&timeout,[&]{h.Inspect({24});});worker.join();Check(r.exception&&h.handled==0,"empty hook restores exact default DispatchOneAdmitted policy");
 }
 std::printf("FUTEX-DISPATCHER-PASS checks=%u cases=12 direct_provider_TEST_boundaries=1\n",checks.load());return 0;
}catch(const std::exception&e){std::fprintf(stderr,"FUTEX-DISPATCHER-FAIL %s\n",e.what());return 1;}}
