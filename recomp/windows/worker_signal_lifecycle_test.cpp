#include "worker_signal_lifecycle.h"
#include "worker_signal_lifecycle_fixture.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <stdexcept>
using namespace bunker::windows;
static std::atomic<unsigned> checks{0};
static void Check(bool b,const char *why){++checks;if(!b)throw std::runtime_error(why);}
template<class F>static void Reject(F f,const char *why){bool failed=false;try{f();}catch(const std::exception&){failed=true;}Check(failed,why);}
struct Harness;
static Harness *current;
struct Harness {
  recomp::Runtime runtime;
  Pthreads threads;
  SignalHost signals;
  WorkerSignalLifecycle adapter;
  uint64_t parent=0,old_mask=0,new_mask=0;
  std::mutex mutex;std::condition_variable condition;
  bool pause=false,entered=false,released=false,prepare_throw=false,enter_throw=false,active_exit=false,foreign_use=false;
  unsigned prepared=0,retired=0,cancelled=0,final_tls=0;
  uint64_t last=0;
  std::vector<WorkerSignalLifecycle::ContextRef> retained;
  Pthreads::WorkerLifecycleHooks raw_hooks;
  std::unique_ptr<WorkerSignalLifecycle::Use> held;
  Harness():threads(runtime,[](addr_t p){for(const auto &t:kTraces)if(t.address==p)return true;return false;}),adapter(signals){
    runtime.AddTraces(kTraces,std::size(kTraces));parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"real parent signal registration");
    const uint64_t initial=SignalHost::Bit(2);Check(!signals.Mask(parent,2,&initial,nullptr)&&!signals.Mask(parent,0,nullptr,&old_mask),"initial parent mask");
    AndroidSignalAction blocked{};blocked.handler=kTraces[0].address;Check(!signals.Action(2,&blocked,nullptr)&&!signals.Queue(parent,2),"real blocked parent pending signal");
    const uint64_t changed=SignalHost::Bit(6);new_mask=changed|SignalHost::Bit(32);
    auto hooks=adapter.TakeHooks();raw_hooks=hooks;Reject([&]{adapter.TakeHooks();},"hooks taken exactly once");
    auto prepare=hooks.prepare;hooks.prepare=[&,prepare,changed](const auto&i){auto lease=prepare(i);++prepared;last=i.token;auto c=adapter.Lookup(i.token);Check(c&&c.get()==lease.get()&&c->PreparedWorker().parent_token==i.parent_token,"actual prepared context");Check(c->PreparedWorker().native_tid==0&&c->NativeThreadId()==0,"creator has not invented native child identity");Check(c->SignalThread()==signals.Lookup(i.token)&&c->Wake()==signals.Wake(i.token)&&!c->PollRequests().Sequence(),"passive real wake/thread/request ownership");uint64_t mask=0,pending=99;Check(!signals.Mask(i.token,0,nullptr,&mask)&&!signals.Pending(i.token,&pending)&&!pending,"new child has no inherited pending signals");if(i.parent_token==parent){Check(mask==old_mask,"snapshot copied at actual creator prepare");Check(!signals.Mask(parent,2,&changed,nullptr),"parent changes after child snapshot");}retained.push_back(c);if(prepare_throw)throw std::runtime_error("TEST direct-host prepare throw");return lease;};
    auto enter=hooks.enter;hooks.enter=[&,enter](const auto&i,const auto&l){enter(i,l);if(enter_throw)throw std::runtime_error("TEST actual child enter throw");};
    auto retire=hooks.retire;hooks.retire=[&,retire](const auto&i,const auto&l,auto reason){auto c=adapter.Lookup(i.token);if(reason==Pthreads::WorkerRetirement::normal)Check(c&&c->CurrentPhase()==WorkerSignalLifecycle::Phase::finishing,"retire follows TLS phase");retire(i,l,reason);Check(!adapter.Lookup(i.token)&&signals.Queue(i.token,0)==3&&signals.BindCurrent(i.token)==3,"actual retired token returns ESRCH");Reject([&]{adapter.AcquireUse(i.token);},"stale adapter token rejected");if(reason==Pthreads::WorkerRetirement::normal)++retired;else{++cancelled;if(enter_throw){std::fputs("ENTER-FAILURE-CANCELLED-ESRCH\n",stderr);std::fflush(stderr);}}};
    threads.SetWorkerLifecycleHooks(std::move(hooks));threads.Install();
    signals.Install(runtime,[&]{return threads.Self();},[](const auto&)->std::optional<uint64_t>{throw std::runtime_error("no signal delivery installed in lifecycle gate");});
    runtime.AddImport(0x7ffc74000000ULL,[&](State &s){try{auto bridge=recomp::MakeBridge<void(addr_t,uint32_t)>([&](auto p,auto stage){Observe(reinterpret_cast<WorkerSignalReport*>(p),stage);});bridge(s);}catch(const std::exception&e){std::fprintf(stderr,"worker signal observation: %s\n",e.what());std::abort();}catch(...){std::fputs("worker signal observation: unknown exception\n",stderr);std::abort();}});
  }
  void Observe(WorkerSignalReport *pointer,unsigned stage){
    WorkerSignalReport r{};recomp::ReadGuestMemory(&r,reinterpret_cast<addr_t>(pointer),sizeof(r));auto token=threads.Self();auto c=adapter.Lookup(token);Check(c&&c->PreparedWorker().token==token&&r.token==token,"real NDK worker token");Check(c->NativeThreadId()==GetCurrentThreadId(),"actual child native ownership");auto *s=recomp::CurrentExecutionState();Check(s&&s->gpr.sp.qword>=c->PreparedWorker().stack_low&&s->gpr.sp.qword<=c->PreparedWorker().stack_high&&s->sr.tpidr_el0.qword==c->PreparedWorker().tls_address,"actual owned guest stack and TLS, including tailcall at stack top");
    {auto use=adapter.AcquireUse(token);auto moved=std::move(use);(void)moved;}
    Check(r.mask==old_mask&&!r.pending&&r.alt_flags==2&&!r.alt_pointer&&!r.alt_size,"actual NDK inherited mask/fresh pending/disabled alternate stack");
    Check(c->CurrentPhase()==(stage?WorkerSignalLifecycle::Phase::finishing:WorkerSignalLifecycle::Phase::entered),"context remains live throughout real TLS rounds");
    if(stage==2){Check(r.rounds==4&&signals.Queue(token,0)==0,"last actual TLS callback precedes DropThread");++final_tls;}
    if(stage==0){if(foreign_use){std::thread wrong([use=adapter.AcquireUse(token)]{});wrong.join();}if(active_exit)held=std::make_unique<WorkerSignalLifecycle::Use>(adapter.AcquireUse(token));if(pause){std::unique_lock lock(mutex);entered=true;condition.notify_all();condition.wait(lock,[&]{return released;});}}
  }
  void Close(){Check(!threads.Shutdown(),"native workers really drained");adapter.CloseAfterShutdown();Check(!threads.ReleaseCurrent()&&!signals.DropThread(parent),"manual parent retires separately");}
};
static void *Resolve(const char *name){
  if(!std::strcmp(name,"test_observe"))return reinterpret_cast<void*>(0x7ffc74000000ULL);
  if(!std::strcmp(name,"pthread_sigmask")||!std::strcmp(name,"pthread_kill"))return reinterpret_cast<void*>(current->signals.Marker(name));
  try{return reinterpret_cast<void*>(current->threads.Marker(name));}catch(const std::exception&){}
  return reinterpret_cast<void*>(current->signals.Marker(name));
}
static addr_t Load(Harness &h,elf_image &image,const char*name){current=&h;Check(!elf_load(WORKER_SIGNAL_LIBRARY,0x5a000000,Resolve,&image),"actual NDK fixture loaded");auto p=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(p!=0,"actual NDK fixture entry");return p;}
static void Unload(elf_image &image){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.base),image.span);Check(VirtualFree(image.base,0,MEM_RELEASE)!=0,"fixture mapping retired after workers");std::free(const_cast<uint8_t*>(image.file));}
static void Normal(bool exiting,bool nested){
  Harness h;elf_image image{};auto entry=Load(h,image,"signal_lifecycle_driver");WorkerSignalReport r[2]{};r[0].flags=(exiting?1:0)|(nested?2:0);h.pause=true;
  std::thread controller([&]{
    {std::unique_lock lock(h.mutex);Check(h.condition.wait_for(lock,std::chrono::seconds(5),[&]{return h.entered;}),"actual child reaches observation");}
    Reject([&]{h.adapter.AcquireUse(h.last);},"foreign native worker cannot acquire context");Reject([&]{h.adapter.CloseAfterShutdown();},"live child prevents close");
    {std::lock_guard lock(h.mutex);h.pause=false;h.released=true;}h.condition.notify_all();
  });
  Check(h.threads.Run(entry,{reinterpret_cast<addr_t>(r)})==0,"NDK driver success");controller.join();
  const unsigned count=nested?2:1;Check(h.prepared==count&&h.retired==count&&!h.cancelled&&h.final_tls==count,"real workers retire after all TLS callbacks");for(unsigned n=0;n<count;++n)Check(!r[n].error&&r[n].rounds==4,"four real guest destructor rounds");Check(r[0].joined==0x1234,"real normal/pthread_exit result");for(auto &c:h.retained)Check(c->CurrentPhase()==WorkerSignalLifecycle::Phase::retired&&!SignalHost::NeedsPoll(c->SignalThread()),"passive retained context cannot resurrect retired thread");h.Close();Unload(image);
}
static void Cancel(bool throwing){
  Harness h;elf_image image{};auto entry=Load(h,image,"signal_lifecycle_try_create");WorkerSignalReport r{};h.prepare_throw=throwing;
  if(throwing){uint64_t output=0x11223344;Reject([&]{h.threads.Create(&output,nullptr,reinterpret_cast<addr_t>(elf_symbol(&image,"signal_lifecycle_try_create")),0);},"direct host prepare throw propagated after cancellation");Check(output==0x11223344,"throwing preparation did not publish child token");}
  else{Check(!h.threads.Shutdown(),"real stopping provider");Check(h.threads.Run(entry,{reinterpret_cast<addr_t>(&r)})==11&&r.joined==0x11223344,"actual NDK Create failure rolls registration back");}
  Check(h.prepared==1&&h.cancelled==1&&!h.retired&&h.retained[0]->CurrentPhase()==WorkerSignalLifecycle::Phase::cancelled,"cancelled context is terminal");h.Close();Unload(image);
}
static void ClosedCapture(){
  Pthreads::WorkerLifecycleHooks captured;Pthreads::WorkerInfo real_retired{};
  {Harness h;elf_image image{};auto entry=Load(h,image,"signal_lifecycle_try_create");WorkerSignalReport r{};Check(!h.threads.Shutdown()&&h.threads.Run(entry,{reinterpret_cast<addr_t>(&r)})==11,"real rollback context for captured-hook lifetime");captured=h.raw_hooks;real_retired=h.retained[0]->PreparedWorker();h.Close();Unload(image);}
  bool closed=false;try{captured.prepare(real_retired);}catch(const std::logic_error&e){closed=std::string(e.what()).find("closed")!=std::string::npos;}Check(closed,"closed captured hooks reject before expired SignalHost access");
}
int main(int argc,char **argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);try{
  if(argc==2){Harness h;elf_image image{};auto entry=Load(h,image,"signal_lifecycle_driver");WorkerSignalReport r{};r.flags=1;h.enter_throw=!std::strcmp(argv[1],"--enter-fail");h.active_exit=!std::strcmp(argv[1],"--active-exit");h.foreign_use=!std::strcmp(argv[1],"--foreign-use");h.threads.Run(entry,{reinterpret_cast<addr_t>(&r)});throw std::runtime_error("negative mode unexpectedly returned");}
  Normal(false,false);Normal(true,false);Normal(false,true);Cancel(false);Cancel(true);ClosedCapture();std::printf("WORKER-SIGNAL-LIFECYCLE-SUCCESS checks=%u no-delivery-no-GC\n",checks.load());return 0;
}catch(const std::exception&e){std::fprintf(stderr,"worker signal fixture: %s\n",e.what());return 1;}}
