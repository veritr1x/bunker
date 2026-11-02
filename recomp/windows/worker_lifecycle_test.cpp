#include "pthread_host.h"
#include "signal_host.h"
#include "nonlocal_jmp.h"
#include "libc.h"
#include "worker_lifecycle_fixture.h"
#include "../whole/guest_memory.h"
#include "../fastaes/elfload.h"
#include "worker_lifecycle_traces.h"
#include "worker_lifecycle_imports.h"
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <windows.h>
using namespace bunker::windows;
namespace {
std::atomic<unsigned> checks{0};
void Check(bool yes,const char *why){++checks;if(!yes){std::fprintf(stderr,"worker lifecycle: %s\n",why);std::abort();}}
bool Translated(addr_t pc){for(auto&t:kTraces)if(t.address==pc)return true;return false;}
bool Executable(addr_t pc){if(pc&3)return false;for(auto&r:kWorkerCodeRanges)if(pc>=r.low&&pc<r.high&&r.high-pc>=4)return true;return false;}
template<class T>T Read(addr_t at){T value{};recomp::ReadGuestMemory(&value,at,sizeof(value));return value;}
Pthreads *owner=nullptr;SignalHost *signals=nullptr;NonlocalJumps *jumps=nullptr;LibC *libc=nullptr;
constexpr addr_t kProbe=0x7ffc70000000ULL;
void *Resolve(const char *name){
 if(!std::strcmp(name,"lifecycle_probe"))return reinterpret_cast<void*>(kProbe);
 try{return reinterpret_cast<void*>(signals->Marker(name));}catch(const std::invalid_argument&){}
 try{return reinterpret_cast<void*>(jumps->Marker(name));}catch(const std::invalid_argument&){}
 try{return reinterpret_cast<void*>(owner->Marker(name));}catch(const std::invalid_argument&){}
 try{return reinterpret_cast<void*>(libc->Marker(name));}catch(const std::invalid_argument&){}
 std::fprintf(stderr,"worker lifecycle missing actual fixture import:%s\n",name);std::abort();
}
struct Context {
 Pthreads::WorkerInfo prepared;uint64_t inherited=0;DWORD creator=0;
 bool registered=false,entered=false,before=false,retired=false,env_live=false,cancelled=false;
 addr_t environment=0;unsigned freed=0;std::vector<std::string>events;
};
std::mutex mutex;std::condition_variable changed;
std::map<uint64_t,std::shared_ptr<Context>> contexts;
std::vector<std::shared_ptr<Context>> retired;
bool veto=false,gate=false,waiting=false,release_gate=false;
std::shared_ptr<Context> Find(uint64_t token){std::lock_guard lock(mutex);auto i=contexts.find(token);return i==contexts.end()?nullptr:i->second;}
bool Committed(addr_t address){MEMORY_BASIC_INFORMATION info{};return VirtualQuery(reinterpret_cast<void*>(address),&info,sizeof(info))&&info.State==MEM_COMMIT;}
void Current(const Pthreads::WorkerInfo &info){
 Check(owner->Self()==info.token&&GetCurrentThreadId()==info.native_tid,"hook executes on its actual Windows worker/token");
 AndroidThreadAttr attr{};Check(!owner->GetAttr(info.token,&attr)&&attr.stack_base==info.stack_low&&attr.stack_base+attr.stack_size==info.stack_high,"hook sees actual owned guest stack");
 Check(Committed(info.stack_low)&&Committed(info.stack_high-1),"owned stack stays committed through callbacks");
}
}
int main(){
 recomp::Runtime runtime,libc_bridges;runtime.AddTraces(kTraces,std::size(kTraces));
 SignalHost signal_model;signals=&signal_model;
 LibC library;libc=&library;library.Install(libc_bridges);
 const auto free_marker=library.Marker("free");
 Pthreads host(runtime,Translated,0x7ff900000000ULL,[&](addr_t pc){return Translated(pc)||pc==free_marker;});owner=&host;host.Install();
 const auto parent=host.Self();Check(!signal_model.RegisterThread(parent)&&!signal_model.BindCurrent(parent),"actual creator signal lifetime");
 auto current=[&]{auto token=host.Self();Check(bool(signal_model.Lookup(token)),"current signal token exists");return token;};
 signal_model.Install(runtime,current,{});
 NonlocalJumps nonlocal([&]{auto token=host.Self();AndroidThreadAttr attr{};Check(!host.GetAttr(token,&attr),"nonlocal current has actual stack");return NonlocalJumps::Thread{token,token,attr.stack_base,attr.stack_base+attr.stack_size};},
  [&](addr_t at,size_t size)->std::optional<NonlocalJumps::Region>{auto context=Find(host.Self());if(!context||!context->env_live||at!=context->environment||size!=256)return {};return NonlocalJumps::Region{at,at+256,context->prepared.token};},
  [&]{uint64_t mask=0;Check(!signal_model.Mask(host.Self(),0,nullptr,&mask),"nonlocal mask uses actual bound worker");return mask;},Executable);jumps=&nonlocal;nonlocal.Install(runtime);
 for(auto &import:kWorkerLifecycleImports){std::string name=import;addr_t marker=0;try{marker=library.Marker(name);}catch(const std::invalid_argument&){}if(!marker)continue;
  runtime.AddImport(marker,[&,marker,name](State&s){if(name=="free"){auto context=Find(host.Self());Check(context&&context->entered&&context->before&&!context->retired,"actual free TLS destructor retains full worker lifetime");++context->freed;}libc_bridges.Dispatch(s,marker,nullptr);});
 }
 runtime.AddImport(kProbe,[&](State&s){auto r=reinterpret_cast<WorkerLifecycleReport*>(s.gpr.x0.qword);auto phase=s.gpr.x1.dword;auto context=Find(host.Self());Check(context&&context->entered&&!context->retired,"NDK callback has entered live ownership");
  Current(Pthreads::WorkerInfo{context->prepared.token,context->prepared.parent_token,context->prepared.stack_low,context->prepared.stack_high,context->prepared.tls_address,GetCurrentThreadId()});
  Check(s.sr.tpidr_el0.qword==context->prepared.tls_address,"actual guest TLS register matches hook identity");
  Check(!signal_model.DispatchOne(host.Self(),{}).error,"only actual bound worker may dispatch its signal state");
  if(phase==1){Check(!context->environment&&s.gpr.x2.qword>=context->prepared.stack_low&&s.gpr.x2.qword+256<=context->prepared.stack_high,"NDK-declared automatic jmp_buf lies in owned stack");context->environment=s.gpr.x2.qword;context->env_live=true;Check(Read<uint64_t>(reinterpret_cast<addr_t>(&r->mask))==context->inherited,"NDK first instruction observes creator-time mask snapshot");}
  else if(phase==2){Check(context->environment==s.gpr.x2.qword,"NDK closes its actual automatic environment scope");context->env_live=false;}
  else{Check(phase==3&&context->before&&!context->env_live,"TLS callbacks execute after scope exit and before retirement");bool rejected=false;try{nonlocal.Inspect(s,context->environment,1);}catch(const std::exception&e){rejected=std::string(e.what()).find("lifetime/range")!=std::string::npos;}Check(rejected,"dead automatic object is rejected while TLS worker still lives");}
  auto probes=Read<uint64_t>(reinterpret_cast<addr_t>(&r->probes))+1;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&r->probes),&probes,sizeof(probes));
 });
 Pthreads::WorkerLifecycleHooks hooks;
 hooks.prepare=[&](const Pthreads::WorkerInfo &info)->Pthreads::WorkerLease{
  Check(!info.native_tid&&info.parent_token==host.Self()&&info.token!=info.parent_token,"creator preparation uses real identities before native launch");
  Check(info.stack_high>info.stack_low&&Committed(info.stack_low)&&info.tls_address,"real guarded stack/TLS exist before prepare");
  auto context=std::make_shared<Context>();context->prepared=info;context->creator=GetCurrentThreadId();context->events.push_back("prepare");
  {std::lock_guard lock(mutex);Check(contexts.emplace(info.token,context).second,"unique hook lifecycle token");}
  Check(!signal_model.Mask(info.parent_token,0,nullptr,&context->inherited)&&!signal_model.RegisterThread(info.token,info.parent_token),"prepare copies live creator mask before resume");context->registered=true;
  if(veto)throw std::runtime_error("test prepare veto");return context;
 };
 hooks.enter=[&](const Pthreads::WorkerInfo &info,const Pthreads::WorkerLease &lease){auto context=std::static_pointer_cast<Context>(lease);Check(context&&Find(info.token)==context,"enter receives actual prepared passive lease");Current(info);Check(!signal_model.BindCurrent(info.token),"bind on actual native child");context->entered=true;context->events.push_back("enter");
  std::unique_lock lock(mutex);if(gate){waiting=true;changed.notify_all();changed.wait(lock,[&]{return release_gate;});}
 };
 hooks.before_tls=[&](const Pthreads::WorkerInfo &info,const Pthreads::WorkerLease &lease){auto context=std::static_pointer_cast<Context>(lease);Current(info);Check(context&&context->entered&&!context->before&&!context->retired,"one pre-TLS owner boundary");context->before=true;context->env_live=false;context->events.push_back("before_tls");};
 hooks.retire=[&](const Pthreads::WorkerInfo &info,const Pthreads::WorkerLease &lease,Pthreads::WorkerRetirement reason){auto context=Find(info.token);Check(context&&!context->retired&&context->registered,"retire finds actual partially/fully prepared context");
  if(reason==Pthreads::WorkerRetirement::normal){Current(info);Check(lease==context&&context->entered&&context->before&&context->freed==1,"all TLS including exact free precede normal retirement");context->events.push_back("retire");}
  else{Check(GetCurrentThreadId()==context->creator&&!context->entered&&!lease,"prepare failure cancels on creator with no guest entry");context->cancelled=true;context->events.push_back("cancel");}
  Check(Committed(info.stack_low),"explicit revocation precedes owned stack destruction");nonlocal.DropThread(info.token,info.token);Check(!signal_model.DropThread(info.token),"signal lifetime revoked exactly once");context->retired=true;
  {std::lock_guard lock(mutex);contexts.erase(info.token);retired.push_back(context);}changed.notify_all();
 };
 host.SetWorkerLifecycleHooks(hooks);
 bool frozen=false;try{host.SetWorkerLifecycleHooks(hooks);}catch(const std::logic_error&){frozen=true;}Check(frozen,"hook replacement is forbidden");
 elf_image image{};Check(!elf_load(WORKER_LIFECYCLE_IMAGE,0x70000000,Resolve,&image),"actual NDK fixture data image");
 auto symbol=[&](const char *name){auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(pc&&Translated(pc),"actual translated NDK export");return pc;};
 auto call=[&](const char *name,WorkerLifecycleReport*r=nullptr){return host.Run(symbol(name),r?std::vector<addr_t>{reinterpret_cast<addr_t>(r)}:std::vector<addr_t>{});};
 Check(!call("lifecycle_setup"),"NDK creates guest destructor and exact real free TLS key");
 uint64_t unused=0;int32_t once=0,key=0;Check(host.Create(&unused,nullptr,free_marker,0)==22&&host.Once(&once,free_marker)==22,"provider free never becomes a worker or once initializer");
 bool rejected=false;try{host.Run(free_marker);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"public callback role remains translated-only");
 {recomp::Runtime other_runtime;Pthreads default_host(other_runtime,Translated);Check(default_host.KeyCreate(&key,free_marker)==22,"default destructor validator remains unchanged");Check(default_host.Create(&unused,nullptr,free_marker,0)==22,"failed Create still freezes configuration");bool locked=false;try{default_host.SetWorkerLifecycleHooks(hooks);}catch(const std::logic_error&){locked=true;}Check(locked,"setter freezes under first Create attempt");}
 for(unsigned race=0;race<16;++race){recomp::Runtime other_runtime;Pthreads other(other_runtime,Translated);std::atomic<unsigned>ready{0},setter{0},created{0};std::atomic<bool>go{false};
  std::thread configure([&]{++ready;while(!go.load())std::this_thread::yield();try{other.SetWorkerLifecycleHooks(hooks);setter=1;}catch(const std::logic_error&){setter=2;}});
  std::thread attempt([&]{++ready;while(!go.load())std::this_thread::yield();uint64_t out=0;created=other.Create(&out,nullptr,free_marker,0);});
  while(ready.load()!=2)std::this_thread::yield();go=true;configure.join();attempt.join();
  Check(created==22&&(setter==1||setter==2),"concurrent setter/Create has one synchronized legal ordering");bool locked=false;try{other.SetWorkerLifecycleHooks(hooks);}catch(const std::logic_error&){locked=true;}Check(locked,"configuration stays frozen after either race outcome");
 }
 WorkerLifecycleReport cancelled{};uint64_t output=0xfeed;
 veto=true;rejected=false;try{host.Create(&output,nullptr,symbol("lifecycle_worker_entry"),reinterpret_cast<addr_t>(&cancelled));}catch(const std::runtime_error&e){rejected=std::string(e.what())=="test prepare veto";}veto=false;
 Check(rejected&&output==0xfeed&&!cancelled.probes&&retired.back()->cancelled&&retired.back()->events==std::vector<std::string>{"prepare","cancel"},"defined hook veto rolls back without publishing output or starting guest");
 Check(signal_model.Queue(retired.back()->prepared.token,0)==3&&!Committed(retired.back()->prepared.stack_low),"cancelled token is stale and stack released after revocation");
 std::array<WorkerLifecycleReport,6> reports{};reports[1].mode=1;reports[2].mode=2;reports[3].mode=3;reports[3].child=&reports[4];reports[5].mode=4;
 auto stale=[&](const WorkerLifecycleReport&r){Check(signal_model.Queue(r.token,0)==3&&host.Kill(r.token,0)==3,"finished real token is never reused/live");State state{};bool missing=false;try{nonlocal.Inspect(state,r.environment,1);}catch(const std::exception&e){missing=std::string(e.what())=="jmp_buf has no live save registration";}Check(missing,"retirement removed old saves immediately before later stack reuse");};
 uint64_t first_mask=SignalHost::Bit(10),later_mask=SignalHost::Bit(12);Check(!signal_model.Mask(parent,2,&first_mask,nullptr),"creator establishes actual mask");gate=true;
 Check(!call("lifecycle_create",&reports[0]),"NDK launches real first worker");{std::unique_lock lock(mutex);changed.wait(lock,[&]{return waiting;});}
 Check(!signal_model.Mask(parent,2,&later_mask,nullptr),"creator changes mask after child creation");{std::lock_guard lock(mutex);release_gate=true;gate=false;}changed.notify_all();
 Check(call("lifecycle_join",&reports[0])==0x7010,"normal return joins exact actual result");
 stale(reports[0]);
 for(unsigned n=1;n<4;++n){Check(!call("lifecycle_create",&reports[n]),"NDK creates exit/once/nested worker");Check(call("lifecycle_join",&reports[n])==0x7010+n,"explicit/once/nested return result");stale(reports[n]);}
 Check(call("lifecycle_retry_once")==1&&call("lifecycle_retry_once")==1,"pthread_exit releases incomplete once for one genuine retry");
 Check(!call("lifecycle_create",&reports[5]),"NDK creates detached actual worker");Check(!host.Shutdown(),"all actual OS workers terminate before provider teardown");
 std::set<uint64_t>tokens;
 for(auto&r:reports){std::fprintf(stderr,"NDK report mode=%llu thread=%#llx token=%#llx tid=%llu stack=%#llx/%llu tls=%#llx mask=%#llx env=%#llx allocation=%#llx destructors=%llu probes=%llu errors=%llu\n",r.mode,r.thread,r.token,r.native_tid,r.stack_low,r.stack_size,r.tls,r.mask,r.environment,r.allocation,r.destructors,r.probes,r.errors);Check(!r.errors&&r.token==r.thread&&r.native_tid&&r.tls&&r.stack_size==(&r==&reports[4]?1048576:65536)&&r.environment&&r.allocation&&r.destructors==4&&r.probes==6,"NDK worker observes exact identities, declared/default stack and four TLS rounds");stale(r);tokens.insert(r.token);}
 Check(tokens.size()==reports.size(),"every actual worker retains a distinct lifetime token");
 Check(reports[0].mask==(first_mask|SignalHost::Bit(32))&&reports[4].mask==(SignalHost::Bit(15)|SignalHost::Bit(32)),"first and nested masks reflect their actual creator snapshots");
 Check(retired.size()==7&&contexts.empty(),"six actual workers and one cancellation retire once");
 for(auto&context:retired)if(!context->cancelled)Check(context->events==std::vector<std::string>{"prepare","enter","before_tls","retire"},"normal and pthread_exit share exactly-once hook ordering");
 Check(!call("lifecycle_cleanup"),"real TLS keys deleted after workers complete");Check(!host.ReleaseCurrent()&&!signal_model.DropThread(parent),"explicit external creator teardown remains separate");
 std::printf("Worker lifecycle: %u checks passed;6 actual NDK workers, normal/exit/once/nested/detached, real free TLS callback, creator mask snapshot and rollback; no polls/GC/Java.\n",checks.load());
}
