#include "worker_signal_lifecycle.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>

namespace bunker::windows {
struct WorkerSignalLifecycle::Shared {
  SignalHost *signals;
  mutable std::mutex mutex;
  std::map<uint64_t,ContextRef> children;
  bool taken=false,closed=false;
  explicit Shared(SignalHost &host):signals(&host){}
  static void Same(const Context &c,const Pthreads::WorkerInfo &i){
    const auto &p=c.prepared_;
    if(p.token!=i.token||p.parent_token!=i.parent_token||p.stack_low!=i.stack_low||p.stack_high!=i.stack_high||p.tls_address!=i.tls_address)
      throw std::logic_error("worker signal lifecycle identity changed");
  }
  ContextRef Find(const Pthreads::WorkerInfo &i,const Pthreads::WorkerLease &lease){
    auto found=children.find(i.token);
    if(found==children.end())throw std::logic_error("worker signal lifecycle token is not owned");
    auto c=found->second;Same(*c,i);
    if(lease&&lease.get()!=c.get())throw std::logic_error("worker signal lifecycle lease differs");
    return c;
  }
  Pthreads::WorkerLease Prepare(const Pthreads::WorkerInfo &i){
    if(!i.token||!i.parent_token||!i.stack_low||i.stack_high<=i.stack_low||((i.stack_low|i.stack_high)&15)||!i.tls_address||i.native_tid)
      throw std::invalid_argument("worker signal lifecycle preparation requires actual creator metadata");
    auto c=std::make_shared<Context>();c->prepared_=i;c->creator_=std::this_thread::get_id();
    {std::lock_guard lock(mutex);if(closed)throw std::logic_error("worker signal lifecycle is closed");if(!children.emplace(i.token,c).second)throw std::logic_error("worker signal lifecycle duplicate token");}
    // The ledger precedes registration, so retire(cancelled, empty lease) can
    // revoke a partial preparation even if construction throws after this call.
    const int error=signals->RegisterThread(i.token,i.parent_token);
    if(error)throw std::runtime_error("worker signal registration failed: "+std::to_string(error));
    c->registered_=true;
    c->thread_=signals->Lookup(i.token);c->wake_=signals->Wake(i.token);
    if(!c->thread_||!c->wake_)throw std::logic_error("worker signal registration has no retained context");
    c->phase_.store(Phase::prepared);return c;
  }
  void Enter(const Pthreads::WorkerInfo &i,const Pthreads::WorkerLease &lease){
    ContextRef c;
    {std::lock_guard lock(mutex);c=Find(i,lease);if(!lease||c->phase_!=Phase::prepared||!i.native_tid||i.native_tid!=GetCurrentThreadId())throw std::logic_error("worker signal enter requires actual child");}
    if(signals->BindCurrent(i.token))throw std::logic_error("worker signal child binding failed");
    {std::lock_guard lock(mutex);c->owner_=std::this_thread::get_id();c->native_tid_=i.native_tid;c->phase_=Phase::entered;}
  }
  void BeforeTls(const Pthreads::WorkerInfo &i,const Pthreads::WorkerLease &lease){
    std::lock_guard lock(mutex);auto c=Find(i,lease);
    if(!lease||c->phase_!=Phase::entered||c->owner_!=std::this_thread::get_id()||i.native_tid!=c->native_tid_)
      throw std::logic_error("worker signal TLS phase requires entered owner");
    c->phase_=Phase::finishing;
  }
  void Retire(const Pthreads::WorkerInfo &i,const Pthreads::WorkerLease &lease,Pthreads::WorkerRetirement reason){
    ContextRef c;const bool cancelled=reason==Pthreads::WorkerRetirement::cancelled;
    {std::lock_guard lock(mutex);
      // Preparation can fail before allocating/inserting its ledger entry.
      // No owned registration exists in that case; never drop an unknown token.
      if(cancelled&&!lease&&!children.count(i.token))return;
      c=Find(i,lease);const auto phase=c->phase_.load();
      if(c->users_.load())throw std::logic_error("worker signal retirement has active context use");
      if(cancelled){
        if(phase==Phase::retiring||phase==Phase::retired||phase==Phase::cancelled||phase==Phase::finishing)
          throw std::logic_error("worker signal cancellation phase is invalid");
        const bool child=i.native_tid&&i.native_tid==GetCurrentThreadId();
        if(!child&&(i.native_tid||c->creator_!=std::this_thread::get_id()))throw std::logic_error("worker signal cancellation on wrong native thread");
        if(phase==Phase::entered&&(c->owner_!=std::this_thread::get_id()||i.native_tid!=c->native_tid_))
          throw std::logic_error("worker signal entered cancellation differs from bound owner");
      }else if(!lease||phase!=Phase::finishing||c->owner_!=std::this_thread::get_id()||i.native_tid!=c->native_tid_)
        throw std::logic_error("worker signal retirement precedes actual TLS completion");
      c->phase_=Phase::retiring;
    }
    if(c->registered_&&signals->DropThread(i.token))throw std::logic_error("worker signal retirement could not drop owned token");
    {std::lock_guard lock(mutex);c->phase_=cancelled?Phase::cancelled:Phase::retired;children.erase(i.token);}
    // c and captured leases have passive destructors; no provider callbacks.
  }
};
WorkerSignalLifecycle::WorkerSignalLifecycle(SignalHost &host):shared_(std::make_shared<Shared>(host)){}
WorkerSignalLifecycle::~WorkerSignalLifecycle(){
  std::lock_guard lock(shared_->mutex);
  if(!shared_->closed||!shared_->children.empty()){std::fputs("worker signal lifecycle destroyed before quiescent close\n",stderr);std::abort();}
}
Pthreads::WorkerLifecycleHooks WorkerSignalLifecycle::TakeHooks(){
  auto s=shared_;{std::lock_guard lock(s->mutex);if(s->taken||s->closed)throw std::logic_error("worker signal hooks already taken or closed");s->taken=true;}
  return {[s](const auto&i){return s->Prepare(i);},[s](const auto&i,const auto&l){s->Enter(i,l);},[s](const auto&i,const auto&l){s->BeforeTls(i,l);},[s](const auto&i,const auto&l,auto r){s->Retire(i,l,r);}};
}
WorkerSignalLifecycle::ContextRef WorkerSignalLifecycle::Lookup(uint64_t token)const{
  std::lock_guard lock(shared_->mutex);auto i=shared_->children.find(token);
  return i==shared_->children.end()||i->second->phase_==Phase::preparing?nullptr:i->second;
}
WorkerSignalLifecycle::Use WorkerSignalLifecycle::AcquireUse(uint64_t token){
  std::lock_guard lock(shared_->mutex);auto i=shared_->children.find(token);
  if(i==shared_->children.end())throw std::logic_error("worker signal use requires live owned token");
  auto c=i->second;const auto phase=c->phase_.load();
  if((phase!=Phase::entered&&phase!=Phase::finishing)||c->owner_!=std::this_thread::get_id())throw std::logic_error("worker signal use requires current entered worker");
  if(c->users_==std::numeric_limits<uint64_t>::max())throw std::overflow_error("worker signal active use count overflow");
  ++c->users_;return Use(c);
}
void WorkerSignalLifecycle::Use::Release()noexcept{
  if(context_){
    if(context_->owner_!=std::this_thread::get_id()){
      std::fputs("worker signal use released on wrong native worker\n",stderr);std::abort();
    }
    if(!context_->users_.fetch_sub(1)){
      std::fputs("worker signal use count underflow\n",stderr);std::abort();
    }
    context_.reset();
  }
}
WorkerSignalLifecycle::Use::~Use(){Release();}
WorkerSignalLifecycle::Use::Use(Use&&other)noexcept:context_(std::move(other.context_)){}
WorkerSignalLifecycle::Use &WorkerSignalLifecycle::Use::operator=(Use&&other)noexcept{if(this!=&other){Release();context_=std::move(other.context_);}return *this;}
void WorkerSignalLifecycle::CloseAfterShutdown(){
  std::lock_guard lock(shared_->mutex);if(!shared_->children.empty())throw std::logic_error("worker signal close has live child contexts");shared_->closed=true;
}
}  // namespace bunker::windows
