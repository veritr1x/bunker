#define NOMINMAX
#include <windows.h>
#include "pthread_host.h"
#include "signal_host.h"
#include "signal_delivery.h"
#include "signal_futex.h"
#include "semaphore_host.h"
#include "worker_signal_lifecycle.h"
#include "../whole/cooperative_poll.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#include "thread_exit_domain_fixture.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
namespace {
using namespace bunker::windows;
std::atomic<unsigned> checks{0},negatives{0};bool pending_case=false,baseline=false;
void Check(bool yes,const char*why){++checks;if(!yes)throw std::runtime_error(why);}
template<class F>void Reject(F f,const char*why){bool yes=false;try{f();}catch(const std::exception&){yes=true;}Check(yes,why);++negatives;}
template<class T>T Read(addr_t p){T v{};recomp::ReadGuestMemory(&v,p,sizeof(v));return v;}
constexpr addr_t kWorker=0x70383624,kProbe=0x6f001000;
bool Translated(addr_t pc){return pc==kWorker||pc==0x825aada0||pc==0x825beb3c||pc==0x825b2af4||pc==0x825b2c70||std::any_of(std::begin(kTraces),std::end(kTraces),[&](const auto&t){return t.address==pc;});}
bool Executable(addr_t pc){return Translated(pc);}
#include "game_unity_worker_collector.h"
struct Harness;Harness*actual=nullptr;
Memory *WorkerAlias(State&,addr_t,Memory*);
struct Harness {
 recomp::Runtime runtime;Pthreads threads{runtime,Translated};
 std::unique_ptr<GameUnityWorkerCollector> profile;
 SignalHost signals{[this](uint64_t token){if(profile&&profile->Owns(token))profile->Notify(token);}};
 Semaphores sem{signals};WorkerSignalLifecycle lifecycle{signals};elf_image image{};addr_t entry=0;uint64_t parent=0;bool veto=false;
 struct Record {Pthreads::WorkerInfo info;WorkerSignalLifecycle::ContextRef context;recomp::PollRequest request;std::unique_ptr<recomp::PollBinding> predecessor;unsigned before=0,retired=0;bool active_before=false,active_retire=false;};
 std::mutex mutex;std::map<uint64_t,std::shared_ptr<Record>> records;unsigned probes=0;
 std::shared_ptr<Record> Find(uint64_t token){std::lock_guard lock(mutex);return records.at(token);}
 addr_t Symbol(const char*name){const auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(pc&&runtime.HasGuestTrace(pc),"current actual NDK export exists and is translated");return pc;}
 static void* Resolve(const char*name){if(!std::strcmp(name,"terminal_probe"))return reinterpret_cast<void*>(kProbe);return reinterpret_cast<void*>(actual->threads.Marker(name));}
 Harness(){actual=this;runtime.AddTraces(kTraces,std::size(kTraces));const recomp::Trace alias{kWorker,WorkerAlias};runtime.AddTraces(&alias,1);threads.Install();parent=threads.Self();Check(!signals.RegisterThread(parent)&&!signals.BindCurrent(parent),"actual creator signal lifetime");profile=std::make_unique<GameUnityWorkerCollector>(threads,signals,sem,runtime);
  auto hooks=lifecycle.TakeHooks();auto installed=hooks;
  installed.prepare=[this,hooks](const auto&i){auto lease=hooks.prepare(i);profile->Prepare(i,lifecycle);auto record=std::make_shared<Record>();record->info=i;record->context=lifecycle.Lookup(i.token);{std::lock_guard lock(mutex);records.emplace(i.token,record);}if(veto)throw std::runtime_error("explicit TEST prepare veto");return lease;};
  installed.enter=[this,hooks](const auto&i,const auto&lease){hooks.enter(i,lease);auto record=Find(i.token);record->info=i;record->predecessor=std::make_unique<recomp::PollBinding>(record->request,[](State&,recomp::PollSite,const auto&){throw std::runtime_error("TEST predecessor must never deliver or acknowledge");});profile->Enter(i);};
  installed.before_tls=[this,hooks](const auto&i,const auto&lease){auto record=Find(i.token);auto*state=recomp::CurrentExecutionState();record->active_before=state!=nullptr;std::fprintf(stderr,"TERMINAL-BEFORE-TLS token=%#llx State=%p PC=%#llx marker=%#llx pending=%d\n",(unsigned long long)i.token,static_cast<void*>(state),(unsigned long long)(state?state->gpr.pc.qword:0),(unsigned long long)threads.Marker("pthread_exit"),int(SignalHost::NeedsPoll(record->context->SignalThread())));if(!baseline)Check(!state,"actual Runtime scopes retired before TLS starts");profile->BeforeTls(i);++record->before;record->request.Request();hooks.before_tls(i,lease);};
  installed.retire=[this,hooks](const auto&i,const auto&lease,auto reason){auto record=Find(i.token);auto*state=recomp::CurrentExecutionState();record->active_retire=state!=nullptr;std::fprintf(stderr,"TERMINAL-RETIRE token=%#llx State=%p native_same=%d pending=%d\n",(unsigned long long)i.token,static_cast<void*>(state),i.native_tid==GetCurrentThreadId(),int(SignalHost::NeedsPoll(record->context->SignalThread())));profile->Retire(i,reason);if(reason==Pthreads::WorkerRetirement::normal){Check(!state&&record->before==1,"normal retirement has actual quiescence and exactly one before-TLS");Check(__bunker_guest_poll_requested()!=0,"strict worker binding removal restores predecessor hint");record->predecessor.reset();Check(!__bunker_guest_poll_requested(),"all worker bindings revoked without forced delivery/ack");}else Check(!record->predecessor,"unentered cancellation has no binding");hooks.retire(i,lease,reason);++record->retired;};
  threads.SetWorkerLifecycleHooks(installed);
  if(pending_case){AndroidSignalAction action{};action.handler=0x825beb3c;action.flags=0x10000004;Check(!signals.Action(30,&action,nullptr),"TEST known pending-signal disposition only; handler never runs");}
  runtime.AddImport(kProbe,recomp::MakeBridge<void(addr_t,uint32_t)>([this](addr_t pointer,uint32_t phase){auto*r=reinterpret_cast<ThreadExitReport*>(pointer);auto token=threads.Self();auto record=Find(token);auto*state=recomp::CurrentExecutionState();AndroidThreadAttr attr{};Check(state&&profile->Owns(token)&&iNative(record,token)&&!threads.GetAttr(token,&attr),"real callback State/current worker/owned stack");Check(state->gpr.sp.qword>=attr.stack_base&&state->gpr.sp.qword<=attr.stack_base+attr.stack_size&&state->sr.tpidr_el0.qword==record->info.tls_address,"actual callback SP/TLS in owned worker allocation");if(phase==2){Check(record->before==1&&record->context->CurrentPhase()==WorkerSignalLifecycle::Phase::finishing,"actual guest TLS callback follows before-TLS boundary");r->tls_sp=state->gpr.sp.qword;r->tls_state=1;if(r->mode==3||r->mode==4)Check(!r->outer_at_tls&&!r->inner_at_tls,"exited once initializers reset before actual TLS callback");}else{Check(phase==1&&record->context->CurrentPhase()==WorkerSignalLifecycle::Phase::entered,"real original worker entry precedes finishing");if(pending_case)Check(!signals.Queue(token,30),"TEST actual pending signal stimulus");}++probes;}));
  Check(!elf_load(THREAD_EXIT_LIBRARY,0x5d000000,Resolve,&image),"actual NDK data image and import markers");entry=Symbol("terminal_entry");Check(!threads.Run(Symbol("terminal_setup")),"actual NDK TLS key configured");
 }
 bool iNative(const std::shared_ptr<Record>&r,uint64_t token){return r->info.token==token&&r->info.native_tid==GetCurrentThreadId()&&r->context->NativeThreadId()==GetCurrentThreadId();}
 uint64_t Create(ThreadExitReport&r,bool detached=false){uint64_t token=0xfeed;AndroidThreadAttr attr{};Check(!threads.AttrInit(&attr)&&!threads.AttrSetStackSize(&attr,65536)&&(!detached||!threads.AttrSetDetach(&attr,1)),"actual worker stack/detach attributes");State witness{};witness.gpr.x2.qword=kWorker;witness.gpr.x3.qword=reinterpret_cast<addr_t>(&r);witness.gpr.x30.qword=0x704389a8;profile->WithCreate(witness,[&](State&){Check(!threads.Create(&token,&attr,kWorker,reinterpret_cast<addr_t>(&r)),"actual prepared native worker created");});return token;}
 void Run(){std::array<ThreadExitReport,6> reports{};for(unsigned i=0;i<reports.size();i++)reports[i].mode=i;
  if(baseline||pending_case){reports[1].mode=1;auto token=Create(reports[1]);uint64_t result=0;(void)threads.Join(token,&result);throw std::runtime_error("expected fatal child returned");}
  for(unsigned i=0;i<5;i++){auto token=Create(reports[i]);uint64_t result=0;Check(!threads.Join(token,&result)&&result==0x6000+i,"normal/direct/volatile/Once/nestedOnce exact native exit result");Check(reports[i].thread==token&&reports[i].entered==1&&reports[i].destructors==1&&reports[i].tls_state&&!reports[i].after_exit&&!reports[i].after_once&&!reports[i].errors,"real NDK no post-exit guest body; exactly one actual TLS destructor");Check(reports[i].once_runs==(i==3?1:i==4?2:0),"known once initializer chain executes only original prefixes");auto record=Find(token);Check(record->retired==1&&!record->active_before&&!record->active_retire&&!profile->Owns(token)&&signals.Queue(token,0)==3,"exactly one quiescent retirement revokes actual worker signal lifetime");}
  Check(threads.Run(Symbol("terminal_retry"))==2&&threads.Run(Symbol("terminal_retry"))==2,"abandoned outer/inner once reset permits exactly one successful retry each");auto detached=Create(reports[5],true);Check(!threads.Shutdown(),"actual detached OS worker terminates before provider shutdown");Check(reports[5].destructors==1&&!reports[5].after_exit&&Find(detached)->retired==1&&!profile->Owns(detached),"detached guarded exit has real TLS and retirement");
  veto=true;ThreadExitReport cancelled{};Reject([&]{Create(cancelled);},"actual preparation rollback remains cancellation");veto=false;
  Check(!threads.Run(Symbol("terminal_cleanup")),"actual NDK TLS key retired after all workers");profile->Close();lifecycle.CloseAfterShutdown();Check(!threads.ReleaseCurrent()&&!signals.DropThread(parent),"creator release after worker lifetimes");
  std::printf("THREAD-EXIT-DOMAIN-PASS checks=%u negatives=%u workers=6 guarded_exit_workers=5 once_exit_levels=2 TLS=6 no_after_exit=1 actual_quiescence=1 strict_collector_unchanged=1\n",checks.load(),negatives.load());
 }
};
Memory *WorkerAlias(State&s,addr_t,Memory*m){return actual->runtime.Dispatch(s,actual->entry,m);}
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);baseline=argc==2&&!std::strcmp(argv[1],"--baseline");pending_case=argc==2&&!std::strcmp(argv[1],"--pending");try{Harness h;h.Run();return 0;}catch(const std::exception&e){std::fprintf(stderr,"thread-exit component: %s\n",e.what());std::_Exit(91);}}
