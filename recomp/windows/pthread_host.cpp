#include "pthread_host.h"
#include "../whole/bridge.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>
#include <windows.h>
#include <process.h>

namespace bunker::windows {
namespace {
// NDK public layouts/initializers are independently checked by prepare_pthreads.
// Private attr flag encodings match Bionic android-13.0.0_r1 pthread_internal.h
// (DETACHED=1), pthread_mutex.cpp (type low nibble), pthread_cond.cpp (clock bit1).
constexpr int kPerm=1, kNoThread=3, kAgain=11, kNoMemory=12, kBusy=16, kInvalid=22,
              kRange=34, kDeadlock=35, kNoSys=38, kNotSupported=95, kTimedOut=110;
constexpr uint64_t kStackSize=1<<20, kStackMin=16384;
constexpr uint32_t kDead=0xffffffff;
std::atomic<uint64_t> next_instance{1}, next_thread{1};
const char *const names[]={
  "pthread_attr_init","pthread_attr_destroy","pthread_attr_setdetachstate","pthread_attr_setstacksize",
  "pthread_attr_getstack","pthread_getattr_np","pthread_create","pthread_join","pthread_detach",
  "pthread_self","pthread_equal","pthread_exit","pthread_setname_np",
  "pthread_mutexattr_init","pthread_mutexattr_destroy","pthread_mutexattr_settype",
  "pthread_mutex_init","pthread_mutex_destroy","pthread_mutex_lock","pthread_mutex_trylock","pthread_mutex_unlock",
  "pthread_condattr_init","pthread_condattr_destroy","pthread_condattr_setclock",
  "pthread_cond_init","pthread_cond_destroy","pthread_cond_wait","pthread_cond_timedwait","pthread_cond_signal","pthread_cond_broadcast",
  "pthread_once","pthread_key_create","pthread_key_delete","pthread_getspecific","pthread_setspecific",
  "pthread_rwlock_init","pthread_rwlock_destroy","pthread_rwlock_rdlock","pthread_rwlock_wrlock","pthread_rwlock_unlock",
  "pthread_kill","pthread_sigmask","pthread_atfork","clock_gettime","gettid","prctl"};
template<class T>T ReadWire(const T *p){T v;recomp::ReadGuestMemory(&v,reinterpret_cast<addr_t>(p),sizeof(v));return v;}
template<class T>void WriteWire(T *p,const T &v){recomp::WriteGuestMemory(reinterpret_cast<addr_t>(p),&v,sizeof(v));}
uint32_t Word(const void *p){return ReadWire(static_cast<const uint32_t*>(p));}
void SetWord(void *p,uint32_t v){WriteWire(static_cast<uint32_t*>(p),v);}
void InitializeOpaque(void *p,size_t size,uint32_t first=0){std::array<uint8_t,56> bytes{};std::memcpy(bytes.data(),&first,4);recomp::WriteGuestMemory(reinterpret_cast<addr_t>(p),bytes.data(),size);}
int64_t NowNs(int clock) {
  if(clock==0) return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
  return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
uint64_t BootTicks100ns(){
  // Biased interrupt time includes sleep/hibernation. Keep CLOCK_MONOTONIC's
  // existing epoch untouched: condition absolute deadlines depend on it.
  // https://learn.microsoft.com/windows/win32/sysinfo/interrupt-time
  // https://learn.microsoft.com/windows-hardware/drivers/ddi/wdm/nf-wdm-kequeryinterrupttimeprecise
  using Query=VOID(WINAPI*)(PULONGLONG);
  static auto precise=reinterpret_cast<Query>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"QueryInterruptTimePrecise"));
  if(precise){ULONGLONG ticks;precise(&ticks);return ticks;}
  // The documented Win32 tick counter also includes suspend; this fallback has
  // the real system timer's coarser resolution, not fabricated precision.
  return GetTickCount64()*10000ULL;
}
}
struct Pthreads::Impl {
  struct Mutex { std::mutex lock; std::condition_variable cv; uint64_t owner=0; uint32_t depth=0; unsigned waiters=0; int type=0; bool dead=false; };
  struct Cond { std::mutex lock; std::condition_variable cv; unsigned waiters=0; uint64_t sequence=0; int clock=0; bool dead=false; };
  struct OnceState { std::mutex lock; std::condition_variable cv; uint64_t owner=0; bool done=false; };
  struct Rw { std::mutex lock; std::condition_variable cv; uint64_t writer=0; std::map<uint64_t,unsigned> readers; unsigned waiters=0; bool dead=false; };
  struct Key { bool live=false; uint64_t generation=0; addr_t destructor=0; };
  struct Value { uint64_t generation=0, value=0; };
  struct Thread {
    Impl *host=nullptr; uint64_t id=0; HANDLE handle=nullptr; unsigned native_id=0;
    bool worker=false, detached=false, joining=false, joined=false, complete=false;
    addr_t entry=0,arg=0,result=0; State *active=nullptr;
    uint64_t parent=0;bool prepared=false,entered=false,finishing=false,retired=false;
    std::shared_ptr<const WorkerLifecycleHooks> hooks;
    WorkerLease lease;
    void *stack_allocation=nullptr; alignas(16) uint8_t tls[256]{};
    addr_t stack_base=0; uint64_t stack_size=0,guard_size=0;
    std::map<int32_t,Value> values;
    std::vector<std::pair<int32_t*,OnceState*>> active_once;
    ~Thread(){if(stack_allocation){recomp::InvalidateGuestMemory(stack_base,stack_size);VirtualFree(stack_allocation,0,MEM_RELEASE);}recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(tls),sizeof(tls));if(handle)CloseHandle(handle);}
  };
  recomp::Runtime &runtime;
  std::function<bool(addr_t)> translated;
  std::function<bool(addr_t)> tls_callable;
  std::shared_ptr<const WorkerLifecycleHooks> hooks;
  std::function<void(int)> error_sink;
  const uint64_t instance=next_instance++;
  addr_t markers; bool installed=false,stopping=false,worker_attempted=false;
  std::mutex registry;
  std::map<uint64_t,std::unique_ptr<Thread>> threads;
  std::map<void*,std::shared_ptr<Mutex>> mutexes;
  std::map<void*,std::shared_ptr<Cond>> conditions;
  std::map<void*,std::shared_ptr<OnceState>> once;
  std::map<void*,std::shared_ptr<Rw>> rwlocks;
  std::array<Key,128> keys{};
  Impl(recomp::Runtime &r,std::function<bool(addr_t)> t,addr_t m,std::function<bool(addr_t)> d)
      :runtime(r),translated(std::move(t)),tls_callable(d?std::move(d):translated),markers(m){}
  static WorkerInfo Info(const Thread &t){return {t.id,t.parent,t.stack_base,t.stack_base+t.stack_size,reinterpret_cast<addr_t>(t.tls),t.native_id};}
  void Retire(Thread &t,WorkerRetirement reason){
    if(!t.prepared)return;
    if(t.retired)throw std::logic_error("pthread worker lifecycle retired twice");
    t.retired=true;
    // Release the last lease outside registry/once locks, even if retire throws.
    auto lease=std::move(t.lease);
    t.hooks->retire(Info(t),lease,reason);
  }
  void Enter(Thread &t){
    if(!t.hooks)return;
    if(!t.prepared||t.entered||t.retired||t.native_id!=GetCurrentThreadId())throw std::logic_error("pthread actual worker lifecycle identity differs");
    try{t.hooks->enter(Info(t),t.lease);t.entered=true;}
    catch(...){Retire(t,WorkerRetirement::cancelled);throw;}
  }
  static std::map<uint64_t,Thread*> &Bindings() { static thread_local std::map<uint64_t,Thread*> bound; return bound; }
  Thread &Current() {
    auto &bound=Bindings(); auto it=bound.find(instance); if(it!=bound.end()) return *it->second;
    auto t=std::make_unique<Thread>(); t->host=this;t->id=0x7ffa00000000ULL+next_thread++;t->native_id=GetCurrentThreadId();
    if(!DuplicateHandle(GetCurrentProcess(),GetCurrentThread(),GetCurrentProcess(),&t->handle,0,FALSE,DUPLICATE_SAME_ACCESS))throw std::runtime_error("cannot retain external thread lifetime handle");
    auto *raw=t.get(); { std::lock_guard guard(registry);threads.emplace(t->id,std::move(t)); }
    bound[instance]=raw; return *raw;
  }
  void AllocateStack(Thread &t,uint64_t size,uint64_t guard=4096) {
    size=(size+4095)&~4095ULL;guard=(guard+4095)&~4095ULL;
    auto *allocation=VirtualAlloc(nullptr,size+guard,MEM_RESERVE,PAGE_NOACCESS);
    if(!allocation)throw std::bad_alloc();
    auto address=reinterpret_cast<addr_t>(allocation)+guard;
    if(!VirtualAlloc(reinterpret_cast<void*>(address),size,MEM_COMMIT,PAGE_READWRITE)){VirtualFree(allocation,0,MEM_RELEASE);throw std::bad_alloc();}
    recomp::InvalidateGuestMemory(address,size);t.stack_allocation=allocation;t.stack_base=address;t.stack_size=size;t.guard_size=guard;
  }
  void ReleaseStack(Thread &t){if(t.stack_allocation){recomp::InvalidateGuestMemory(t.stack_base,t.stack_size);VirtualFree(t.stack_allocation,0,MEM_RELEASE);t.stack_allocation=nullptr;}t.stack_base=0;t.stack_size=0;t.guard_size=0;}
  // Call with registry locked. Keep small token tombstones but release native
  // handles and owned guest stacks only after actual OS thread termination.
  void ReapDetached(){for(auto &item:threads){auto &t=*item.second;if(t.worker&&t.detached&&t.complete&&t.handle&&WaitForSingleObject(t.handle,0)==WAIT_OBJECT_0){ReleaseStack(t);CloseHandle(t.handle);t.handle=nullptr;}}}
  bool IsAlive(const Thread &t)const{return !t.complete&&t.handle&&WaitForSingleObject(t.handle,0)==WAIT_TIMEOUT;}
  uint64_t Run(Thread &t,addr_t entry,const addr_t *args,size_t count,bool destructor=false) {
    if(!entry||!(destructor?tls_callable(entry):translated(entry))) throw std::invalid_argument("pthread callback is not a registered callable for its role");
    State s{};
    if(t.active) s=*t.active;
    else {{std::lock_guard lock(registry);if(!t.stack_base) AllocateStack(t,kStackSize);}s.gpr.sp.qword=t.stack_base+t.stack_size;s.sr.tpidr_el0.qword=reinterpret_cast<addr_t>(t.tls);}
    auto saved_sp=s.gpr.sp.qword;
    Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};
    if(count>8) throw std::invalid_argument("too many pthread callback arguments");
    for(size_t i=0;i<count;++i)(s.gpr.*regs[i]).qword=args[i];
    s.gpr.pc.qword=entry;s.gpr.x30.qword=0xfeedffff;
    auto *previous=t.active;t.active=&s;
    try {runtime.Run(s,entry);} catch(...) {t.active=previous;throw;}
    t.active=previous;
    if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=saved_sp) throw std::runtime_error("pthread guest callback corrupted PC/SP");
    return s.gpr.x0.qword;
  }
  void Finish(Thread &t,uint64_t result) {
    if(t.finishing||t.complete)throw std::logic_error("pthread recursive or repeated finish is unsupported");
    t.finishing=true;
    if(t.hooks){if(!t.entered||t.retired)throw std::logic_error("pthread worker TLS has no live lifecycle");t.hooks->before_tls(Info(t),t.lease);}
    // pthread_exit from a once callback must release blocked initializers before
    // destructors can themselves call once. No C++ unwind crosses lifted IR.
    for(auto pair:t.active_once) {auto &o=*pair.second;std::lock_guard lock(o.lock);o.owner=0;SetWord(pair.first,0);o.cv.notify_all();}
    t.active_once.clear();
    // POSIX clears the value before a destructor; it may install another value.
    for(unsigned round=0;round<4;++round) {
      bool ran=false;
      for(int32_t i=0;i<128;++i) {
        addr_t callback=0,value=0;
        { std::lock_guard guard(registry);auto v=t.values.find(i);
          if(v!=t.values.end()&&keys[i].live&&v->second.generation==keys[i].generation&&v->second.value&&keys[i].destructor) {
            callback=keys[i].destructor;value=v->second.value;v->second.value=0;
          }
        }
        if(callback) {ran=true;Run(t,callback,&value,1,true);}
      }
      if(!ran) break;
    }
    t.values.clear();
    if(t.hooks)Retire(t,WorkerRetirement::normal);
    {std::lock_guard guard(registry);t.result=result;t.complete=true;t.active=nullptr;}
  }
  static unsigned __stdcall Worker(void *arg) {
    auto *t=static_cast<Thread*>(arg);auto *h=t->host;Bindings()[h->instance]=t;
    try {h->Enter(*t);auto value=h->Run(*t,t->entry,&t->arg,1);h->Finish(*t,value);}
    catch(const std::exception &e){std::fprintf(stderr,"pthread translated worker: %s\n",e.what());std::abort();}
    return 0;
  }
  std::shared_ptr<Mutex> GetMutex(void *p) {
    if(!p)return {};
    std::lock_guard guard(registry);auto found=mutexes.find(p);if(found!=mutexes.end())return found->second;
    auto w=Word(p);if(w&~0xc000U||((w>>14)&3)==3)return {};
    auto m=std::make_shared<Mutex>();m->type=(w>>14)&3;mutexes.emplace(p,m);return m;
  }
  std::shared_ptr<Cond> GetCond(void *p) {
    if(!p)return {};
    std::lock_guard guard(registry);auto found=conditions.find(p);if(found!=conditions.end())return found->second;
    auto w=Word(p);if(w&~2U)return {};auto c=std::make_shared<Cond>();c->clock=(w>>1)&1;conditions.emplace(p,c);return c;
  }
  std::shared_ptr<Rw> GetRw(void *p) {
    if(!p)return {};
    std::lock_guard guard(registry);auto found=rwlocks.find(p);if(found!=rwlocks.end())return found->second;
    if(Word(p))return {};
    auto r=std::make_shared<Rw>();rwlocks.emplace(p,r);return r;
  }
};
Pthreads::Pthreads(recomp::Runtime &r,std::function<bool(addr_t)> v,addr_t base,std::function<bool(addr_t)> d):impl_(std::make_unique<Impl>(r,std::move(v),base,std::move(d))){}
Pthreads::~Pthreads() {
  // The host owns native handles until actual OS termination, including detached
  // workers. Stable token tombstones prevent OS thread-id reuse aliasing.
  if(Shutdown()){std::fprintf(stderr,"pthread host destroyed on its own worker\n");std::abort();}
  Impl::Bindings().erase(impl_->instance);
}
addr_t Pthreads::Marker(const std::string &s)const {for(size_t i=0;i<std::size(names);++i)if(s==names[i])return impl_->markers+i*8;throw std::invalid_argument("unsupported pthread import "+s);}
uint64_t Pthreads::Self(){return impl_->Current().id;}
int32_t Pthreads::GetTid(){
  const auto &thread=impl_->Current();
  const auto native=GetCurrentThreadId();
  if(!native||native>static_cast<DWORD>(INT32_MAX)||thread.native_id!=native)
    throw std::runtime_error("current native thread ID does not match a representable Android pid_t");
  return static_cast<int32_t>(native);
}
int Pthreads::Prctl(int32_t option,const char *name){
  auto fail=[&](int error){
    if(!impl_->error_sink)throw std::logic_error("prctl requires a guest errno sink for errors");
    impl_->error_sink(error);return -1;
  };
  if(option!=15){
    std::fprintf(stderr,"unsupported prctl option %d (only PR_SET_NAME=15 is implemented)\n",option);
    return fail(kNoSys);
  }
  if(!name)return fail(14); // EFAULT, not pthread_setname_np's EINVAL.
  // kernel/sys.c PR_SET_NAME uses strncpy_from_user(..., TASK_COMM_LEN-1).
  // Never inspect byte 15: a 15-byte nonterminated source is sufficient.
  // Other variadic registers are unused by this operation, including on Bionic.
  char copy[16]{};
  for(unsigned i=0;i<15;++i){
    recomp::ReadGuestMemory(copy+i,reinterpret_cast<addr_t>(name)+i,1);
    if(!copy[i])break;
  }
  // SetName applies the real Windows thread description and strict UTF-8
  // conversion. Arbitrary Linux byte strings (including a split UTF-8 suffix)
  // cannot be represented faithfully and explicitly fail with EINVAL here.
  auto error=SetName(Self(),copy);
  if(error){
    std::fprintf(stderr,"PR_SET_NAME native/UTF-8 backend failed: Android errno %d\n",error);
    return fail(error);
  }
  return 0;
}
uint64_t Pthreads::Run(addr_t e,std::initializer_list<addr_t> a){return impl_->Run(impl_->Current(),e,a.begin(),a.size());}
uint64_t Pthreads::Run(addr_t e,const std::vector<addr_t> &a){return impl_->Run(impl_->Current(),e,a.data(),a.size());}
void Pthreads::AttachCurrentStack(void *base,uint64_t size){if(!base||size<kStackMin||(reinterpret_cast<addr_t>(base)&15)||(size&15))throw std::invalid_argument("unaligned/invalid guest stack");auto &t=impl_->Current();if(t.active)throw std::logic_error("cannot replace active guest stack");std::lock_guard lock(impl_->registry);impl_->ReleaseStack(t);t.stack_base=reinterpret_cast<addr_t>(base);t.stack_size=size;}
int Pthreads::ReleaseCurrent(){auto &t=impl_->Current();if(t.worker||t.active)return kBusy;impl_->Finish(t,0);{std::lock_guard lock(impl_->registry);impl_->ReleaseStack(t);CloseHandle(t.handle);t.handle=nullptr;impl_->ReapDetached();}Impl::Bindings().erase(impl_->instance);return 0;}
int Pthreads::Shutdown(){
  auto &bindings=Impl::Bindings();auto current=bindings.find(impl_->instance);
  if(current!=bindings.end()&&current->second->worker)return kDeadlock;
  {std::lock_guard guard(impl_->registry);impl_->stopping=true;}
  // External host threads retain their original ownership and are not joined.
  // Callers must stop issuing external imports before destroying the host.
  for(auto &item:impl_->threads){auto &t=*item.second;if(t.worker&&t.handle&&WaitForSingleObject(t.handle,INFINITE)!=WAIT_OBJECT_0)return kInvalid;}
  return 0;
}
int Pthreads::AttrInit(AndroidThreadAttr *a){if(!a)return kInvalid;AndroidThreadAttr v{};v.stack_size=kStackSize;v.guard_size=4096;WriteWire(a,v);return 0;}
int Pthreads::AttrDestroy(AndroidThreadAttr *a){if(!a||ReadWire(a).flags==kDead)return kInvalid;AndroidThreadAttr v{};v.flags=kDead;WriteWire(a,v);return 0;}
int Pthreads::AttrSetDetach(AndroidThreadAttr *a,int d){if(!a||d<0||d>1)return kInvalid;auto v=ReadWire(a);if(v.flags==kDead)return kInvalid;v.flags=(v.flags&~1U)|d;WriteWire(a,v);return 0;}
int Pthreads::AttrSetStackSize(AndroidThreadAttr *a,uint64_t size){if(!a||size<kStackMin)return kInvalid;auto v=ReadWire(a);if(v.flags==kDead)return kInvalid;v.stack_size=size;WriteWire(a,v);return 0;}
int Pthreads::AttrGetStack(const AndroidThreadAttr *a,uint64_t *base,uint64_t *size){if(!a||!base||!size)return kInvalid;auto v=ReadWire(a);if(v.flags==kDead)return kInvalid;WriteWire(base,v.stack_base);WriteWire(size,v.stack_size);return 0;}
int Pthreads::GetAttr(uint64_t id,AndroidThreadAttr *a){if(!a)return kInvalid;std::lock_guard lock(impl_->registry);auto it=impl_->threads.find(id);if(it==impl_->threads.end()||!impl_->IsAlive(*it->second))return kNoThread;auto &t=*it->second;if(!t.stack_base)return kNotSupported;AndroidThreadAttr v{};v.flags=t.detached?1:0;v.stack_base=t.stack_base;v.stack_size=t.stack_size;v.guard_size=t.guard_size;WriteWire(a,v);return 0;}
int Pthreads::Create(uint64_t *out,const AndroidThreadAttr *attr,addr_t entry,addr_t arg) {
  std::shared_ptr<const WorkerLifecycleHooks> hooks;
  {std::lock_guard lock(impl_->registry);impl_->worker_attempted=true;hooks=impl_->hooks;}
  if(!out||!entry||!impl_->translated(entry))return kInvalid;
  AndroidThreadAttr a;AttrInit(&a);if(attr)a=ReadWire(attr);
  if(a.flags&~1U||a.stack_size<kStackMin)return kInvalid;
  if(a.stack_base||a.sched_policy||a.sched_priority||std::any_of(std::begin(a.reserved),std::end(a.reserved),[](auto x){return x!=0;}))return kNotSupported;
  if(a.stack_size>1ULL<<30||a.guard_size>1ULL<<30)return kAgain;
  std::unique_ptr<Impl::Thread> t;
  try{t=std::make_unique<Impl::Thread>();}catch(const std::bad_alloc&){return kAgain;}
  t->host=impl_.get();t->id=0x7ffa00000000ULL+next_thread++;t->entry=entry;t->arg=arg;t->worker=true;t->detached=a.flags&1;
  try{impl_->AllocateStack(*t,a.stack_size,a.guard_size);}catch(const std::bad_alloc&){return kAgain;}
  t->hooks=hooks;
  if(hooks){t->parent=Self();t->prepared=true;try{t->lease=hooks->prepare(Impl::Info(*t));}catch(...){impl_->Retire(*t,WorkerRetirement::cancelled);throw;}}
  auto *raw=t.get();auto id=t->id;
  int failure=0;
  {
    std::lock_guard lock(impl_->registry);
    if(impl_->stopping)failure=kAgain;
    else{
      impl_->ReapDetached();
      try{auto inserted=impl_->threads.try_emplace(id,std::move(t));if(!inserted.second)failure=kAgain;}
      catch(const std::bad_alloc&){failure=kAgain;}
      if(!failure){
        auto handle=_beginthreadex(nullptr,0,Impl::Worker,raw,CREATE_SUSPENDED,&raw->native_id);
        if(!handle){t=std::move(impl_->threads.at(id));impl_->threads.erase(id);failure=kAgain;}
        else{raw->handle=reinterpret_cast<HANDLE>(handle);WriteWire(out,id);
          if(ResumeThread(raw->handle)==DWORD(-1)){std::fprintf(stderr,"pthread ResumeThread failed\n");std::abort();}}
      }
    }
  }
  if(failure)impl_->Retire(*raw,WorkerRetirement::cancelled);
  return failure;
}
int Pthreads::Join(uint64_t id,uint64_t *result) {
  if(id==Self())return kDeadlock;
  Impl::Thread *t;
  {std::lock_guard lock(impl_->registry);auto it=impl_->threads.find(id);if(it==impl_->threads.end())return kNoThread;t=it->second.get();if(!t->worker||t->detached||t->joining||t->joined)return kInvalid;t->joining=true;}
  if(WaitForSingleObject(t->handle,INFINITE)!=WAIT_OBJECT_0){std::lock_guard lock(impl_->registry);t->joining=false;return kInvalid;}
  std::lock_guard lock(impl_->registry);if(result)WriteWire(result,t->result);t->joined=true;t->joining=false;impl_->ReleaseStack(*t);CloseHandle(t->handle);t->handle=nullptr;impl_->ReapDetached();return 0;
}
int Pthreads::Detach(uint64_t id){std::lock_guard lock(impl_->registry);auto it=impl_->threads.find(id);if(it==impl_->threads.end())return kNoThread;auto &t=*it->second;if(!t.worker||t.detached||t.joining||t.joined)return kInvalid;t.detached=true;return 0;}
[[noreturn]] void Pthreads::Exit(uint64_t result){auto &t=impl_->Current();if(!t.worker){std::fprintf(stderr,"pthread_exit on an external host thread is unsupported\n");std::abort();}impl_->Finish(t,result);_endthreadex(0);std::abort();}
int Pthreads::MutexAttrInit(int64_t *a){if(!a)return kInvalid;WriteWire(a,int64_t(0));return 0;}
int Pthreads::MutexAttrDestroy(int64_t *a){if(!a)return kInvalid;auto v=ReadWire(a);if(v<0||v>2)return kInvalid;WriteWire(a,int64_t(-1));return 0;}
int Pthreads::MutexAttrSetType(int64_t *a,int type){if(!a||type<0||type>2)return kInvalid;auto v=ReadWire(a);if(v<0||v>2)return kInvalid;WriteWire(a,int64_t(type));return 0;}
int Pthreads::MutexInit(void *p,const int64_t *a){if(!p)return kInvalid;int64_t type=a?ReadWire(a):0;if(type<0||type>2)return kNotSupported;std::lock_guard lock(impl_->registry);if(impl_->mutexes.count(p))return kBusy;auto m=std::make_shared<Impl::Mutex>();m->type=static_cast<int>(type);InitializeOpaque(p,40,static_cast<uint32_t>(type)<<14);impl_->mutexes.emplace(p,m);return 0;}
int Pthreads::MutexDestroy(void *p){auto m=impl_->GetMutex(p);if(!m)return kInvalid;std::lock_guard lock(m->lock);if(m->dead)return kInvalid;if(m->owner||m->waiters)return kBusy;m->dead=true;{std::lock_guard guard(impl_->registry);impl_->mutexes.erase(p);SetWord(p,kDead);}return 0;}
int Pthreads::MutexLock(void *p,bool attempt){auto m=impl_->GetMutex(p);if(!m)return kInvalid;auto id=Self();std::unique_lock lock(m->lock);if(m->dead)return kInvalid;if(m->owner==id&&m->type==1){if(m->depth==UINT32_MAX)return kAgain;++m->depth;return 0;}if(m->owner&&attempt)return kBusy;if(m->owner==id&&m->type==2)return kDeadlock;++m->waiters;m->cv.wait(lock,[&]{return !m->owner||m->dead;});--m->waiters;if(m->dead)return kInvalid;m->owner=id;m->depth=1;return 0;}
int Pthreads::MutexUnlock(void *p){auto m=impl_->GetMutex(p);if(!m)return kInvalid;std::lock_guard lock(m->lock);if(m->dead)return kInvalid;if(m->owner!=Self())return kPerm;if(--m->depth==0){m->owner=0;m->cv.notify_one();}return 0;}
int Pthreads::CondAttrInit(int64_t *a){if(!a)return kInvalid;WriteWire(a,int64_t(0));return 0;}
int Pthreads::CondAttrDestroy(int64_t *a){if(!a)return kInvalid;auto v=ReadWire(a);if(v!=0&&v!=2)return kInvalid;WriteWire(a,int64_t(0xdeada11d));return 0;}
int Pthreads::CondAttrSetClock(int64_t *a,int clock){if(!a||clock<0||clock>1)return kInvalid;auto v=ReadWire(a);if(v!=0&&v!=2)return kInvalid;WriteWire(a,int64_t(clock<<1));return 0;}
int Pthreads::CondInit(void *p,const int64_t *a){if(!p)return kInvalid;auto flags=a?ReadWire(a):0;if(flags!=0&&flags!=2)return kNotSupported;std::lock_guard lock(impl_->registry);if(impl_->conditions.count(p))return kBusy;auto c=std::make_shared<Impl::Cond>();c->clock=static_cast<int>(flags>>1);InitializeOpaque(p,48,static_cast<uint32_t>(flags));impl_->conditions.emplace(p,c);return 0;}
int Pthreads::CondDestroy(void *p){auto c=impl_->GetCond(p);if(!c)return kInvalid;std::lock_guard lock(c->lock);if(c->dead)return kInvalid;if(c->waiters)return kBusy;c->dead=true;{std::lock_guard guard(impl_->registry);impl_->conditions.erase(p);SetWord(p,kDead);}return 0;}
int Pthreads::CondWake(void *p,bool all){auto c=impl_->GetCond(p);if(!c)return kInvalid;std::lock_guard lock(c->lock);if(c->dead)return kInvalid;++c->sequence;if(all)c->cv.notify_all();else c->cv.notify_one();return 0;}
int Pthreads::CondWait(void *p,void *mp,const AndroidTimespec *deadline){
  AndroidTimespec copied;if(deadline){copied=ReadWire(deadline);deadline=&copied;}
  if(deadline&&(deadline->nanoseconds<0||deadline->nanoseconds>=1000000000))return kInvalid;
  auto c=impl_->GetCond(p);auto m=impl_->GetMutex(mp);if(!c||!m)return kInvalid;
  std::unique_lock lock(c->lock);if(c->dead)return kInvalid;
  {std::lock_guard guard(m->lock);if(m->owner!=Self())return kPerm;if(m->depth!=1)return kNotSupported;}
  uint64_t seq=c->sequence;++c->waiters;int result=MutexUnlock(mp);if(result){--c->waiters;return result;}
  if(!deadline)c->cv.wait(lock,[&]{return c->sequence!=seq;});
  else {
    // Bound waits to one second so realtime clock changes are observed and
    // distant time_t deadlines cannot overflow Windows chrono durations.
    while(c->sequence==seq){auto now=NowNs(c->clock);int64_t sec=now/1000000000,ns=now%1000000000;
      if(deadline->seconds<sec||(deadline->seconds==sec&&deadline->nanoseconds<=ns)){result=kTimedOut;break;}
      int64_t delta=1000000000;if(deadline->seconds==sec)delta=deadline->nanoseconds-ns;else if(sec!=INT64_MAX&&deadline->seconds==sec+1)delta=1000000000-ns+deadline->nanoseconds;
      c->cv.wait_for(lock,std::chrono::nanoseconds(std::min<int64_t>(delta,1000000000)));
    }
  }
  --c->waiters;lock.unlock();auto relock=MutexLock(mp);return relock?relock:result;
}
int Pthreads::Once(int32_t *p,addr_t callback){
  if(!p||!callback||!impl_->translated(callback))return kInvalid;
  Impl::OnceState *o;
  {std::lock_guard guard(impl_->registry);auto it=impl_->once.find(p);if(it==impl_->once.end()){auto w=Word(p);if(w!=0&&w!=2)return kInvalid;auto item=std::make_shared<Impl::OnceState>();item->done=w==2;o=item.get();impl_->once.emplace(p,std::move(item));}else o=it->second.get();}
  auto &t=impl_->Current();std::unique_lock lock(o->lock);if(o->owner==t.id)return kDeadlock;o->cv.wait(lock,[&]{return !o->owner;});
  // A newly constructed once object can reuse the address of a destroyed
  // allocation. Its NDK zero initializer starts a new lifetime.
  if(o->done&&Word(p)==0)o->done=false;
  if(o->done)return 0;
  o->owner=t.id;SetWord(p,1);t.active_once.emplace_back(p,o);lock.unlock();
  try {impl_->Run(t,callback,nullptr,0);}catch(...){lock.lock();o->owner=0;SetWord(p,0);t.active_once.pop_back();o->cv.notify_all();throw;}
  lock.lock();t.active_once.pop_back();o->owner=0;o->done=true;SetWord(p,2);o->cv.notify_all();return 0;
}
int Pthreads::KeyCreate(int32_t *out,addr_t callback){if(!out||(callback&&!impl_->tls_callable(callback)))return kInvalid;std::lock_guard lock(impl_->registry);for(int32_t i=0;i<128;++i)if(!impl_->keys[i].live){auto &k=impl_->keys[i];k.live=true;++k.generation;k.destructor=callback;WriteWire(out,i);return 0;}return kAgain;}
int Pthreads::KeyDelete(int32_t key){if(key<0||key>=128)return kInvalid;std::lock_guard lock(impl_->registry);auto &k=impl_->keys[key];if(!k.live)return kInvalid;k.live=false;k.destructor=0;return 0;}
int Pthreads::SetSpecific(int32_t key,uint64_t value){if(key<0||key>=128)return kInvalid;auto &t=impl_->Current();std::lock_guard lock(impl_->registry);auto &k=impl_->keys[key];if(!k.live)return kInvalid;try{t.values[key]={k.generation,value};}catch(const std::bad_alloc&){return kNoMemory;}return 0;}
uint64_t Pthreads::GetSpecific(int32_t key){if(key<0||key>=128)return 0;auto &t=impl_->Current();std::lock_guard lock(impl_->registry);auto &k=impl_->keys[key];auto it=t.values.find(key);return k.live&&it!=t.values.end()&&it->second.generation==k.generation?it->second.value:0;}
int Pthreads::RwInit(void *p,const int64_t *a){if(!p)return kInvalid;if(a&&ReadWire(a))return kNotSupported;std::lock_guard lock(impl_->registry);if(impl_->rwlocks.count(p))return kBusy;InitializeOpaque(p,56);impl_->rwlocks.emplace(p,std::make_shared<Impl::Rw>());return 0;}
int Pthreads::RwDestroy(void *p){auto r=impl_->GetRw(p);if(!r)return kInvalid;std::lock_guard lock(r->lock);if(r->dead)return kInvalid;if(r->writer||!r->readers.empty()||r->waiters)return kBusy;r->dead=true;{std::lock_guard guard(impl_->registry);impl_->rwlocks.erase(p);SetWord(p,kDead);}return 0;}
int Pthreads::RwLock(void *p,bool write){auto r=impl_->GetRw(p);if(!r)return kInvalid;auto id=Self();std::unique_lock lock(r->lock);if(r->dead)return kInvalid;if(r->writer==id||(write&&r->readers.count(id)))return kDeadlock;++r->waiters;r->cv.wait(lock,[&]{return !r->writer&&(!write||r->readers.empty());});--r->waiters;if(write)r->writer=id;else ++r->readers[id];return 0;}
int Pthreads::RwUnlock(void *p){auto r=impl_->GetRw(p);if(!r)return kInvalid;auto id=Self();std::lock_guard lock(r->lock);if(r->dead)return kInvalid;if(r->writer==id)r->writer=0;else{auto it=r->readers.find(id);if(it==r->readers.end())return kPerm;if(!--it->second)r->readers.erase(it);}r->cv.notify_all();return 0;}
int Pthreads::SetName(uint64_t id,const char *name){if(!name)return kInvalid;std::string copy;for(unsigned i=0;i<16;++i){char c;recomp::ReadGuestMemory(&c,reinterpret_cast<addr_t>(name)+i,1);if(!c)break;copy+=c;}if(copy.size()==16)return kRange;std::lock_guard lock(impl_->registry);auto it=impl_->threads.find(id);if(it==impl_->threads.end()||!impl_->IsAlive(*it->second))return kNoThread;auto handle=it->second->handle;using SetDescription=HRESULT(WINAPI*)(HANDLE,PCWSTR);auto fn=reinterpret_cast<SetDescription>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"SetThreadDescription"));if(!fn)return kNoSys;wchar_t text[32];int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,copy.c_str(),-1,text,32);if(!n)return kInvalid;return SUCCEEDED(fn(handle,text))?0:kPerm;}
int Pthreads::Kill(uint64_t id,int signal){if(signal<0||signal>64)return kInvalid;std::lock_guard lock(impl_->registry);auto it=impl_->threads.find(id);if(it==impl_->threads.end()||!impl_->IsAlive(*it->second))return kNoThread;return signal==0?0:kNoSys;}
int Pthreads::ClockGetTime(int clock,AndroidTimespec *out){if(!out||(clock!=0&&clock!=1&&clock!=7))return -1;AndroidTimespec value;if(clock==7){auto ticks=BootTicks100ns();value={static_cast<int64_t>(ticks/10000000),static_cast<int64_t>(ticks%10000000*100)};}else{auto ns=NowNs(clock);value={ns/1000000000,ns%1000000000};}WriteWire(out,value);return 0;}
void Pthreads::SetErrorSink(std::function<void(int)> sink){impl_->error_sink=std::move(sink);}
void Pthreads::SetWorkerLifecycleHooks(WorkerLifecycleHooks hooks){
  if(!hooks.prepare||!hooks.enter||!hooks.before_tls||!hooks.retire)throw std::invalid_argument("pthread lifecycle requires all four callbacks");
  auto pending=std::make_shared<const WorkerLifecycleHooks>(std::move(hooks));
  std::lock_guard lock(impl_->registry);
  if(impl_->worker_attempted||impl_->hooks)throw std::logic_error("pthread worker lifecycle is immutable before the first Create attempt");
  impl_->hooks=std::move(pending);
}

void Pthreads::Install(){
  if(impl_->installed)throw std::logic_error("pthread imports already installed");
  auto add=[&](const char *name,std::function<void(State&)> f){impl_->runtime.AddImport(Marker(name),[this,f=std::move(f)](State &s){auto &t=impl_->Current();auto *previous=t.active;t.active=&s;try{f(s);}catch(const std::exception &e){std::fprintf(stderr,"pthread import: %s\n",e.what());std::abort();}t.active=previous;});};
  add("pthread_attr_init",recomp::MakeBridge<int32_t(AndroidThreadAttr*)>([this](auto a){return AttrInit(a);}));
  add("pthread_attr_destroy",recomp::MakeBridge<int32_t(AndroidThreadAttr*)>([this](auto a){return AttrDestroy(a);}));
  add("pthread_attr_setdetachstate",recomp::MakeBridge<int32_t(AndroidThreadAttr*,int32_t)>([this](auto a,auto d){return AttrSetDetach(a,d);}));
  add("pthread_attr_setstacksize",recomp::MakeBridge<int32_t(AndroidThreadAttr*,uint64_t)>([this](auto a,auto n){return AttrSetStackSize(a,n);}));
  add("pthread_attr_getstack",recomp::MakeBridge<int32_t(const AndroidThreadAttr*,uint64_t*,uint64_t*)>([this](auto a,auto b,auto n){return AttrGetStack(a,b,n);}));
  add("pthread_getattr_np",recomp::MakeBridge<int32_t(uint64_t,AndroidThreadAttr*)>([this](auto t,auto a){return GetAttr(t,a);}));
  add("pthread_create",recomp::MakeBridge<int32_t(uint64_t*,const AndroidThreadAttr*,addr_t,addr_t)>([this](auto t,auto a,auto f,auto v){return Create(t,a,f,v);}));
  add("pthread_join",recomp::MakeBridge<int32_t(uint64_t,uint64_t*)>([this](auto t,auto r){return Join(t,r);}));
  add("pthread_detach",recomp::MakeBridge<int32_t(uint64_t)>([this](auto t){return Detach(t);}));
  add("pthread_self",recomp::MakeBridge<uint64_t()>([this]{return Self();}));
  add("gettid",recomp::MakeBridge<int32_t()>([this]{return GetTid();}));
  add("prctl",recomp::MakeBridge<int32_t(int32_t,const char*)>([this](auto option,auto name){return Prctl(option,name);}));
  add("pthread_equal",recomp::MakeBridge<int32_t(uint64_t,uint64_t)>([](auto a,auto b){return a==b;}));
  add("pthread_exit",recomp::MakeBridge<void(uint64_t)>([this](auto r){Exit(r);}));
  add("pthread_setname_np",recomp::MakeBridge<int32_t(uint64_t,const char*)>([this](auto t,auto s){return SetName(t,s);}));
  add("pthread_mutexattr_init",recomp::MakeBridge<int32_t(int64_t*)>([this](auto a){return MutexAttrInit(a);}));
  add("pthread_mutexattr_destroy",recomp::MakeBridge<int32_t(int64_t*)>([this](auto a){return MutexAttrDestroy(a);}));
  add("pthread_mutexattr_settype",recomp::MakeBridge<int32_t(int64_t*,int32_t)>([this](auto a,auto t){return MutexAttrSetType(a,t);}));
  add("pthread_mutex_init",recomp::MakeBridge<int32_t(void*,const int64_t*)>([this](auto p,auto a){return MutexInit(p,a);}));
  add("pthread_mutex_destroy",recomp::MakeBridge<int32_t(void*)>([this](auto p){return MutexDestroy(p);}));
  add("pthread_mutex_lock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return MutexLock(p);}));
  add("pthread_mutex_trylock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return MutexLock(p,true);}));
  add("pthread_mutex_unlock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return MutexUnlock(p);}));
  add("pthread_condattr_init",recomp::MakeBridge<int32_t(int64_t*)>([this](auto a){return CondAttrInit(a);}));
  add("pthread_condattr_destroy",recomp::MakeBridge<int32_t(int64_t*)>([this](auto a){return CondAttrDestroy(a);}));
  add("pthread_condattr_setclock",recomp::MakeBridge<int32_t(int64_t*,int32_t)>([this](auto a,auto c){return CondAttrSetClock(a,c);}));
  add("pthread_cond_init",recomp::MakeBridge<int32_t(void*,const int64_t*)>([this](auto p,auto a){return CondInit(p,a);}));
  add("pthread_cond_destroy",recomp::MakeBridge<int32_t(void*)>([this](auto p){return CondDestroy(p);}));
  add("pthread_cond_wait",recomp::MakeBridge<int32_t(void*,void*)>([this](auto p,auto m){return CondWait(p,m);}));
  add("pthread_cond_timedwait",recomp::MakeBridge<int32_t(void*,void*,const AndroidTimespec*)>([this](auto p,auto m,auto d){return CondWait(p,m,d);}));
  add("pthread_cond_signal",recomp::MakeBridge<int32_t(void*)>([this](auto p){return CondWake(p,false);}));
  add("pthread_cond_broadcast",recomp::MakeBridge<int32_t(void*)>([this](auto p){return CondWake(p,true);}));
  add("pthread_once",recomp::MakeBridge<int32_t(int32_t*,addr_t)>([this](auto p,auto f){return Once(p,f);}));
  add("pthread_key_create",recomp::MakeBridge<int32_t(int32_t*,addr_t)>([this](auto p,auto f){return KeyCreate(p,f);}));
  add("pthread_key_delete",recomp::MakeBridge<int32_t(int32_t)>([this](auto k){return KeyDelete(k);}));
  add("pthread_getspecific",recomp::MakeBridge<uint64_t(int32_t)>([this](auto k){return GetSpecific(k);}));
  add("pthread_setspecific",recomp::MakeBridge<int32_t(int32_t,uint64_t)>([this](auto k,auto v){return SetSpecific(k,v);}));
  add("pthread_rwlock_init",recomp::MakeBridge<int32_t(void*,const int64_t*)>([this](auto p,auto a){return RwInit(p,a);}));
  add("pthread_rwlock_destroy",recomp::MakeBridge<int32_t(void*)>([this](auto p){return RwDestroy(p);}));
  add("pthread_rwlock_rdlock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return RwLock(p,false);}));
  add("pthread_rwlock_wrlock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return RwLock(p,true);}));
  add("pthread_rwlock_unlock",recomp::MakeBridge<int32_t(void*)>([this](auto p){return RwUnlock(p);}));
  add("pthread_kill",recomp::MakeBridge<int32_t(uint64_t,int32_t)>([this](auto t,auto s){return Kill(t,s);}));
  add("pthread_sigmask",recomp::MakeBridge<int32_t(int32_t,void*,void*)>([](auto,auto,auto){return kNoSys;}));
  add("pthread_atfork",recomp::MakeBridge<int32_t(addr_t,addr_t,addr_t)>([](auto,auto,auto){return kNoSys;}));
  add("clock_gettime",recomp::MakeBridge<int32_t(int32_t,AndroidTimespec*)>([this](auto c,auto p){if(!p||(c!=0&&c!=1&&c!=7)){if(!impl_->error_sink){std::fprintf(stderr,"pthread clock_gettime requires guest errno sink for errors\n");std::abort();}impl_->error_sink(p?kInvalid:14);return -1;}return ClockGetTime(c,p);}));
  impl_->installed=true;
}
} // namespace bunker::windows
