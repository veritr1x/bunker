#include "pthread_wait_channel.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#include <map>
#include <memory>
#include <cstring>
#include <cerrno>
#include <cfenv>
static std::atomic<unsigned> checks{0};
static void Check(bool value,const char *reason){if(!value){std::fprintf(stderr,"FAIL: %s\n",reason);std::abort();}++checks;}
template<class F>static void Until(F predicate,const char *reason){auto limit=std::chrono::steady_clock::now()+std::chrono::seconds(8);while(!predicate()){Check(std::chrono::steady_clock::now()<limit,reason);std::this_thread::sleep_for(std::chrono::milliseconds(1));}}
static void Channels(){
  for(unsigned i=0;i<128;++i){wait_test::Channel channel;auto generation=channel.Generation();channel.Notify();auto start=std::chrono::steady_clock::now();channel.Wait(generation,1000000000);Check(std::chrono::steady_clock::now()-start<std::chrono::milliseconds(100),"notification before enrollment is retained");
    generation=channel.Generation();std::thread notifier([&]{channel.Notify();});channel.Wait(generation,1000000000);notifier.join();Check(channel.Generation()!=generation,"concurrent notification generation retained");}
  fenv_t saved;Check(!std::fegetenv(&saved),"native environment snapshot");Check(!std::fesetround(FE_DOWNWARD)&&!std::feclearexcept(FE_ALL_EXCEPT)&&!std::feraiseexcept(FE_INEXACT),"native environment canary");errno=173;
  wait_test::Channel channel;auto generation=channel.Generation();channel.Notify();channel.Wait(generation,1000000);
  Check(errno==173&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_INEXACT,"pure transport wake preserves host errno/fenv");Check(!std::fesetenv(&saved),"restore native test environment");
}
#ifdef _WIN32
#include "pthread_host.h"
#include "signal_host.h"
#include "pthread_wait_fixture.h"
#include "../fastaes/elfload.h"
#include "pthread_wait_traces.h"
#include <windows.h>
using bunker::windows::Pthreads;
using bunker::windows::SignalHost;
static Pthreads *current_host;
static constexpr addr_t kProbe=0x7ffb42000000ULL,kMemset=kProbe+8;
static void *Resolve(const char *name){if(!std::strcmp(name,"wait_probe"))return reinterpret_cast<void*>(kProbe);if(!std::strcmp(name,"memset"))return reinterpret_cast<void*>(kMemset);try{return reinterpret_cast<void*>(current_host->Marker(name));}catch(...){return nullptr;}}
static bool Translated(addr_t pc){for(auto &trace:kTraces)if(trace.address==pc)return true;return false;}
static std::shared_ptr<const Pthreads::WaitWake> Wake(const std::shared_ptr<wait_test::Channel>&channel){return std::make_shared<const Pthreads::WaitWake>(Pthreads::WaitWake{[channel]{return channel->Generation();},[channel]{channel->Notify();},[channel](uint64_t generation,uint64_t relative){channel->Wait(generation,relative);}});}
static void Direct(){
  // A failed attempt freezes configuration, including the no-hook route.
  {recomp::Runtime rt;Pthreads h(rt,Translated);Check(h.CondWait(nullptr,nullptr)==22,"invalid wait stays EINVAL");bool frozen=false;try{h.SetWaitHooks({[](uint64_t){return std::shared_ptr<const Pthreads::WaitWake>{};},[](const auto&){}});}catch(const std::logic_error&){frozen=true;}Check(frozen,"first failed CondWait freezes setter");}
  {recomp::Runtime rt;Pthreads h(rt,Translated);uint64_t id=0;Check(h.Create(&id,nullptr,1,0)==22,"invalid create");bool frozen=false;try{h.SetWaitHooks({[](uint64_t){return std::shared_ptr<const Pthreads::WaitWake>{};},[](const auto&){}});}catch(const std::logic_error&){frozen=true;}Check(frozen,"first failed Create freezes setter");}
  {recomp::Runtime rt;Pthreads h(rt,Translated);alignas(8)uint64_t m[8]{},c[8]{};h.SetWaitHooks({[](uint64_t){return std::shared_ptr<const Pthreads::WaitWake>{};},[](const auto&){}});Check(!h.MutexLock(m),"unknown channel mutex lock");bool rejected=false;try{h.CondWait(c,m);}catch(const std::logic_error&){rejected=true;}Check(rejected&&!h.MutexUnlock(m)&&!h.MutexDestroy(m)&&!h.CondDestroy(c),"missing channel rejected before unlock");}
  // Multiple real condition waiters share a mutex, but signals select one
  // unnotified ticket. Waking every channel does not broadcast the condition.
  {recomp::Runtime rt;Pthreads h(rt,Translated);alignas(8)uint64_t m[8]{},c[8]{};std::mutex lock;std::map<uint64_t,std::shared_ptr<wait_test::Channel>> channels;std::atomic<unsigned> enrolled{0},returned{0};
    h.SetWaitHooks({[&](uint64_t token){auto channel=std::make_shared<wait_test::Channel>();{std::lock_guard guard(lock);channels.emplace(token,channel);}return Wake(channel);},[&](const auto&context){Check(context.token==h.Self()&&!context.active_state,"direct checkpoint actual worker without invented State");if(context.phase==Pthreads::WaitPhase::ConditionReleased)++enrolled;}});
    std::vector<std::thread> threads;for(unsigned i=0;i<2;++i)threads.emplace_back([&]{Check(!h.MutexLock(m),"direct waiter lock");Check(!h.CondWait(c,m),"direct condition return");++returned;Check(!h.MutexUnlock(m)&&!h.ReleaseCurrent(),"direct waiter cleanup");});
    Until([&]{std::lock_guard guard(lock);return channels.size()==2&&enrolled>=2;},"two enrolled waiters");
    Check(!h.MutexLock(m)&&h.MutexDestroy(m)==16&&h.CondDestroy(c)==16,"enrollment retains pinned controls");Check(!h.CondWake(c,false)&&!h.MutexUnlock(m),"one genuine signal");Until([&]{return returned==1;},"one signal returns one waiter");
    {std::lock_guard guard(lock);for(auto &entry:channels)entry.second->Notify();}
    std::this_thread::sleep_for(std::chrono::milliseconds(40));Check(returned==1,"transport notifications do not consume another condition ticket");
    Check(!h.CondWake(c,true),"genuine broadcast");for(auto &thread:threads)thread.join();Check(returned==2&&!h.MutexDestroy(m)&&!h.CondDestroy(c),"both controls retire after real broadcast");
  }
  // Every callback failure after release must withdraw its ticket and own the
  // original mutex again before the direct caller observes the exception.
  for(unsigned mode=0;mode<4;++mode){recomp::Runtime rt;Pthreads h(rt,Translated);alignas(8)uint64_t m[8]{},c[8]{};auto channel=std::make_shared<wait_test::Channel>();std::atomic<unsigned> generations{0},ready{0},caught{0};
    auto wake=std::make_shared<const Pthreads::WaitWake>(Pthreads::WaitWake{
      [&]{if(mode==0&&++generations==2)throw std::runtime_error("TEST generation");return channel->Generation();},
      [&]{if(mode==3)throw std::runtime_error("TEST notifier");channel->Notify();},
      [&](uint64_t gen,uint64_t relative){if(mode==1)throw std::runtime_error("TEST wait");channel->Wait(gen,relative);}});
    h.SetWaitHooks({[&](uint64_t){return wake;},[&](const auto&){++ready;if(mode==2)throw std::runtime_error("TEST checkpoint");}});
    std::thread thread([&]{Check(!h.MutexLock(m),"failure test lock");try{auto rc=h.CondWait(c,m);Check(mode==3&&rc==0,"only committed notifier failure may return normally in waiter");}catch(const std::runtime_error&){++caught;}Check(!h.MutexUnlock(m)&&!h.ReleaseCurrent(),"exception returns with mutex owned");});
    if(mode==3){Until([&]{return ready.load()!=0;},"notifier test entered");bool threw=false;try{h.CondWake(c,false);}catch(const std::runtime_error&){threw=true;}Check(threw,"notifier failure propagates after genuine ticket commit");}
    thread.join();Check(caught==(mode==3?0u:1u)&&!h.MutexDestroy(m)&&!h.CondDestroy(c),"callback exception has no stranded enrollment");
  }
  // A failing callback during contended reacquisition still waits for the same
  // mutex, then throws while owning it. Another thread can use all metadata.
  {recomp::Runtime rt;Pthreads h(rt,Translated);alignas(8)uint64_t m[8]{},c[8]{};auto channel=std::make_shared<wait_test::Channel>();std::atomic<bool> entered{false},reacquire{false},caught{false};
    h.SetWaitHooks({[&](uint64_t){return Wake(channel);},[&](const auto &context){if(context.phase==Pthreads::WaitPhase::ConditionReleased)entered=true;else{reacquire=true;throw std::runtime_error("TEST contended reacquire");}}});
    std::thread worker([&]{Check(!h.MutexLock(m),"contended exception worker lock");try{h.CondWait(c,m);Check(false,"reacquire should throw");}catch(const std::runtime_error&){caught=true;}Check(!h.MutexUnlock(m)&&!h.ReleaseCurrent(),"reacquire exception retains ownership");});
    Until([&]{return entered.load();},"worker released");Check(!h.MutexLock(m)&&!h.CondWake(c,false),"controller holds mutex across wake");Until([&]{return reacquire.load();},"reacquire callback invoked despite contention");Check(!caught&&h.CondDestroy(c)==0&&h.MutexDestroy(m)==16,"throw cannot finish without mutex and metadata is unlocked");Check(!h.MutexUnlock(m),"release contended original mutex");worker.join();Check(caught&&!h.MutexDestroy(m),"reacquire failure completes after real unlock");
  }
}
static void Guest(){
  recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));Pthreads host(runtime,Translated);current_host=&host;host.Install();
  std::mutex lock;std::map<uint64_t,std::shared_ptr<wait_test::Channel>> channels;
  SignalHost signals([&](uint64_t token){std::shared_ptr<wait_test::Channel> channel;{std::lock_guard guard(lock);auto it=channels.find(token);if(it!=channels.end())channel=it->second;}if(channel)channel->Notify();});
  Pthreads::WorkerLifecycleHooks lifecycle;
  lifecycle.prepare=[&](const auto&info)->Pthreads::WorkerLease{auto channel=std::make_shared<wait_test::Channel>();{std::lock_guard guard(lock);channels.emplace(info.token,channel);}Check(!signals.RegisterThread(info.token),"real child signal model register");return channel;};
  lifecycle.enter=[&](const auto&info,const auto&){Check(!signals.BindCurrent(info.token),"real child signal model bind");};lifecycle.before_tls=[](const auto&,const auto&){};
  lifecycle.retire=[&](const auto&info,const auto&,auto){Check(!signals.DropThread(info.token),"real child signal model retire");std::shared_ptr<wait_test::Channel> channel;{std::lock_guard guard(lock);channel=std::move(channels.at(info.token));channels.erase(info.token);}};
  host.SetWorkerLifecycleHooks(lifecycle);
  std::atomic<unsigned> condition{0},reacquire{0},handled{0},defers{0},exited{0};std::atomic<bool> admit{false},prove{true},slow{false};
  for(int number:{10,12}){bunker::windows::AndroidSignalAction action{};action.handler=0x80001234;Check(!signals.Action(number,&action,nullptr),"component signal action, no original GC handler claim");}
  host.SetWaitHooks({[&](uint64_t token){std::lock_guard guard(lock);return Wake(channels.at(token));},[&](const auto&context){
    Check(context.token==host.Self()&&context.active_state&&context.active_state==recomp::CurrentExecutionState(),"NDK same-worker active State identity");
    Check(recomp::CurrentExecutionFrames(*context.active_state).size()==1,"component waiter has one actual Runtime frame");
    Check(context.active_state->gpr.x0.qword==reinterpret_cast<addr_t>(context.condition)&&context.active_state->gpr.x1.qword==reinterpret_cast<addr_t>(context.mutex),"original NDK condition arguments remain real");
    if(context.original_deadline)Check(context.active_state->gpr.x2.qword==reinterpret_cast<addr_t>(context.original_deadline),"original automatic deadline identity retained");
    State before=*context.active_state;const auto saved_errno=errno,round=std::fegetround(),exceptions=std::fetestexcept(FE_ALL_EXCEPT);
    if(context.phase==Pthreads::WaitPhase::ConditionReleased){++condition;
      if(prove.exchange(false)){std::atomic<int> acquired{-1};std::thread other([&]{acquired=host.MutexLock(context.mutex,true);if(acquired==0)Check(!host.MutexUnlock(context.mutex),"other native thread releases test mutex");Check(!host.ReleaseCurrent(),"other native thread cleanup");});other.join();Check(acquired==0,"checkpoint holds neither guest mutex nor provider metadata locks");}
    }else{++reacquire;Check(host.MutexUnlock(context.mutex)==1,"contended checkpoint never owns guest mutex");}
    Check(host.MutexDestroy(context.mutex)==16,"same-worker checkpoint may inspect pinned mutex without lock inversion");
    if(context.phase==Pthreads::WaitPhase::ConditionReleased)Check(host.CondDestroy(context.condition)==16,"enrolled condition is busy without lock inversion");
    if(slow.exchange(false))std::this_thread::sleep_for(std::chrono::milliseconds(300));
    if(admit){auto result=signals.DispatchOne(context.token,[&](const auto&delivery)->std::optional<uint64_t>{Check(delivery.token==host.Self()&&delivery.signal==(handled==0?10:12),"exact queued signal model boundary on real worker");++handled;return {};});Check(!result.error,"component signal model dispatch");}else ++defers;
    Check(!std::memcmp(&before,context.active_state,sizeof(State)),"transport/model preserves complete suspended State");
    Check(errno==saved_errno&&std::fegetround()==round&&std::fetestexcept(FE_ALL_EXCEPT)==exceptions,"read-only admission/model preserves host errno/fenv");
  }});
  runtime.AddImport(kProbe,[&](State&s){Check(s.gpr.x1.dword==1||s.gpr.x1.dword==2,"actual NDK probe phase");if(s.gpr.x1.dword==2)++exited;});
  runtime.AddImport(kMemset,[](State&s){auto n=s.gpr.x2.qword;std::vector<unsigned char>bytes(n,static_cast<unsigned char>(s.gpr.x1.dword));recomp::WriteGuestMemory(s.gpr.x0.qword,bytes.data(),bytes.size());});
  elf_image image{};Check(!elf_load(PTHREAD_WAIT_IMAGE,0x70000000,Resolve,&image),"NDK wait ELF image");
  auto call=[&](const char*name,PthreadWaitReport&r){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry&&Translated(entry),"actual NDK exported entry");return host.Run(entry,{reinterpret_cast<addr_t>(&r)});};
  PthreadWaitReport report{};Check(!call("wait_setup",report)&&!call("wait_launch",report),"NDK initializes and creates actual waiter");
  Until([&]{return condition.load()!=0&&!prove.load();},"actual NDK released wait");
  auto token=report.thread;Check(!signals.Queue(token,10),"real pending signal wakes channel");auto old=defers.load();Until([&]{return defers>old;},"rejected admission observed after notification");uint64_t pending=~uint64_t(0);Check(!signals.Pending(token,&pending)&&pending==0&&SignalHost::NeedsPoll(signals.Lookup(token))&&handled==0&&exited==0,"unblocked deliverable signal remains pending across deferral, without condition completion");
  admit=true;{std::lock_guard guard(lock);channels.at(token)->Notify();}Until([&]{return handled==1;},"later allowed checkpoint handles same pending signal");Check(exited==0,"handled signal internally resumes condition wait");
  Check(!host.MutexLock(report.mutex),"controller obtains genuinely released mutex");uint64_t permit=1;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&report.permits),&permit,8);Check(!host.CondWake(report.condition,false),"genuine condition signal under controller mutex");
  Until([&]{return reacquire.load()!=0;},"NDK waiter checkpoint during contended reacquisition");Check(!signals.Queue(token,12),"second signal while mutex contended");Until([&]{return handled==2;},"same worker handles notification without mutex ownership");Check(!host.MutexUnlock(report.mutex),"real mutex release");
  Check(call("wait_join",report)==0x600d&&!report.errors&&report.result==0&&report.returns==1&&!call("wait_cleanup",report),"NDK returns only for genuine condition with owned mutex");
  PthreadWaitReport timed{};timed.timed=1;bunker::windows::AndroidTimespec now{};Check(!Pthreads::ClockGetTime(1,&now),"real monotonic deadline");timed.seconds=now.seconds;timed.nanoseconds=now.nanoseconds+180000000;if(timed.nanoseconds>=1000000000){++timed.seconds;timed.nanoseconds-=1000000000;}
  slow=true;auto start=std::chrono::steady_clock::now();Check(!call("wait_setup",timed)&&!call("wait_launch",timed),"NDK timed waiter");Check(call("wait_join",timed)==0x600d&&!timed.errors&&timed.result==110&&timed.returns==1,"handler time counts against original absolute deadline; no EINTR");Check(std::chrono::steady_clock::now()-start<std::chrono::seconds(2)&&!call("wait_cleanup",timed),"timeout was not restarted and mutex reacquired");
  Check(!host.Shutdown()&&!host.ReleaseCurrent()&&channels.empty(),"all actual workers/channels retired before provider teardown");
  std::printf("Windows NDK transport passed: deferred pending, normal resume, contended reacquire, absolute timeout\n");
}
#endif
int main(){Channels();
#ifdef _WIN32
 Direct();Guest();
 std::printf("Windows optional pthread wait passed: %u checks\n",checks.load());
#else
 std::printf("Linux portable wake channel passed: %u checks (no Windows Pthreads provider claim)\n",checks.load());
#endif
 return 0;}
