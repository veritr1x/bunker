#pragma once
#include "game_collector_mask.h"
#include "game_socket_wait_context.h"
// Included inside the harness namespace, after its checked Read/Require helpers.
// Creator-certified original finalizer and managed-worker condition profiles.
// Their role-specific wait certificates share the original stop/restart path.
class GameCollectorDelivery {
  using Pthreads=bunker::windows::Pthreads;
  using SignalHost=bunker::windows::SignalHost;
  using SignalDelivery=bunker::windows::SignalDelivery;
  using Lifecycle=bunker::windows::WorkerSignalLifecycle;
 public:
  // Optional composition at the already installed lifecycle/wait hooks. The
  // extension owns its admission policy; the finalizer profile stays separate.
  struct WorkerExtension {
    std::function<void(const Pthreads::WorkerInfo&,Lifecycle&)> prepare;
    std::function<void(const Pthreads::WorkerInfo&)> enter,before_tls;
    std::function<void(const Pthreads::WorkerInfo&,Pthreads::WorkerRetirement)> retire;
    std::function<bool(uint64_t)> owns;
    std::function<void(const Pthreads::WaitContext&)> checkpoint;
  };
 private:
  struct Channel {
    std::mutex mutex;std::condition_variable condition;uint64_t generation=0;
    uint64_t Generation(){std::lock_guard lock(mutex);return generation;}
    void Notify(){std::lock_guard lock(mutex);Require(generation!=UINT64_MAX,"collector wake generation exhausted");++generation;condition.notify_all();}
    void Wait(uint64_t expected,uint64_t relative){std::unique_lock lock(mutex);if(relative)condition.wait_for(lock,std::chrono::nanoseconds(relative),[&]{return generation!=expected;});else condition.wait(lock,[&]{return generation!=expected;});}
  };
  enum class Role {unknown,finalizer,managed_worker};
  enum class ManagedWait {unknown,event_timed,event_untimed,condition_timed,condition_untimed};
  // Select by the proven caller, then validate all phase/argument/root fields.
  // A malformed known caller must not escape validation as an ordinary wait.
  static ManagedWait ManagedSite(const State&state){
    switch(state.gpr.x30.qword){
      case 0x82550574:return ManagedWait::event_timed;
      case 0x825505d8:return ManagedWait::event_untimed;
      case 0x82550164:return ManagedWait::condition_timed;
      case 0x82550174:return ManagedWait::condition_untimed;
      default:return ManagedWait::unknown;
    }
  }
  static bool ManagedContext(State&state){
    if(OpaqueDepth()||recomp::CurrentExecutionState()!=&state)return false;
    const auto frames=recomp::CurrentExecutionFrames(state);
    return frames.size()==1&&frames[0]==&state;
  }
  struct Owner {
    Lifecycle::ContextRef context;Role role=Role::unknown;
    std::shared_ptr<Channel> channel=std::make_shared<Channel>();
    std::unique_ptr<recomp::PollBinding> binding;
    std::unique_ptr<SignalDelivery> delivery;
    std::atomic<bool> wait_live{false},stop_live{false};
    std::atomic<addr_t> record{0};std::atomic<uint64_t> stop_epoch{0};
    std::atomic<uint64_t> certified_epoch{0},begun_epoch{0};
    std::atomic<bool> certified_new_epoch{false};uint64_t pump_calls=0;
    const Pthreads::WaitContext *checkpoint=nullptr;State *wait_state=nullptr;
    std::atomic<GameSocketWaitContext*> socket_wait{nullptr};std::mutex socket_sender_mutex;
    const SignalHost::Boundary *socket_boundary=nullptr;SignalHost::Dispatch socket_selected{};
    State interrupted{};addr_t frame_base=0;unsigned depth=0,posts=0;
    ~Owner(){if(binding||delivery){std::fputs("Game GC: owner destroyed without same-worker retirement\n",stderr);std::abort();}}
  };
  static bool ConditionRole(const Owner&owner){return owner.role==Role::finalizer||owner.role==Role::managed_worker;}
  struct Witness {Role role=Role::unknown;};
  struct ProviderDeferred {}; // Caught only by the direct C++ provider site.
  Pthreads &threads_;SignalHost &signals_;bunker::windows::Semaphores &semaphores_;recomp::Runtime &runtime_;
  Lifecycle lifecycle_;WorkerExtension extension_;std::mutex mutex_;std::map<uint64_t,std::shared_ptr<Owner>> owners_;bool closed_=false;
  static Owner *&Current(){static thread_local Owner *owner=nullptr;return owner;}
  static const Witness *&Creating(){static thread_local const Witness *witness=nullptr;return witness;}
  static unsigned &OpaqueDepth(){static thread_local unsigned depth=0;return depth;}
  static constexpr uint64_t kProviderOrdinal=UINT64_MAX,kManagedProviderOrdinal=UINT64_MAX-4;
  static uint64_t ProviderOrdinal(const Owner&owner){return owner.role==Role::managed_worker?kManagedProviderOrdinal:kProviderOrdinal;}
  static constexpr addr_t kReturn=0x825aada0,kAck=0x87cb1e68,kEpoch=0x879a6b08,kStopped=0x879a6b10;
  [[noreturn]] static void Fail(const char *message){std::fprintf(stderr,"Game GC: unsupported bounded profile: %s; execution stopped without host-generated collector acknowledgment\n",message);std::fflush(stderr);std::abort();}
  static void Check(bool value,const char *message){if(!value)Fail(message);}
  std::shared_ptr<Owner> Lookup(uint64_t token){std::lock_guard lock(mutex_);auto i=owners_.find(token);return i==owners_.end()?nullptr:i->second;}
  bool Pending(const Owner &owner){uint64_t blocked=0;Check(!signals_.Pending(owner.context->PreparedWorker().token,&blocked),"signal owner is not live");return blocked||SignalHost::NeedsPoll(owner.context->SignalThread());}
  addr_t Record(uint64_t token){
    Check(Read<uint32_t>(0x879a62a0)==1,"original GC registry is not initialized");
    uint32_t hash=uint32_t(token>>8)^uint32_t(token);hash^=hash>>16;
    addr_t cursor=Read<addr_t>(0x879a6b28+(hash&255)*8);std::array<addr_t,256> seen{};size_t count=0;
    while(cursor){Check(!(cursor&7)&&cursor<=UINT64_MAX-0x60&&count<seen.size(),"original GC record chain shape/capacity");for(size_t i=0;i<count;++i)Check(seen[i]!=cursor,"original GC record cycle");seen[count++]=cursor;if(Read<uint64_t>(cursor+8)==token)return cursor;cursor=Read<addr_t>(cursor);}
    return 0;
  }
  void Dispositions(){
    Check(Read<int32_t>(0x87984e14)==30&&Read<int32_t>(0x87984e18)==24&&Read<int32_t>(0x87984e10)==1,"original configured signals/retry differ");
    const uint64_t expected=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){bunker::windows::AndroidSignalAction action{};Check(!signals_.Action(signal,nullptr,&action),"original disposition query failed");Check(action.handler==0x825beb3c&&action.flags==uint32_t(signal==30?0x10000004:0x10000000)&&action.mask==expected,"original disposition/thunk/mask differs");}
    Check(Read<addr_t>(0x879a7788)==0x825b2af4&&Read<addr_t>(0x879a7758)==0x825b2c70,"original handler table differs");
    int32_t count=0;Check(!semaphores_.GetValue(kAck,&count),"original acknowledgment semaphore is not initialized");
  }
  void ValidateWait(Owner &owner,const Pthreads::WaitContext &context,const SignalHost::Delivery *selected=nullptr){
    const auto &info=owner.context->PreparedWorker();auto *state=recomp::CurrentExecutionState();
    Check(ConditionRole(owner)&&owner.context->CurrentPhase()==Lifecycle::Phase::entered&&Current()==&owner,"wait has no entered creator-certified condition owner");
    Check(context.token==info.token&&context.active_state&&context.active_state==state&&threads_.Self()==info.token&&owner.context->NativeThreadId()==GetCurrentThreadId(),"wait active State/native identity differs");
    const auto frames=recomp::CurrentExecutionFrames(*state);Check(frames.size()==1&&frames[0]==state&&!OpaqueDepth(),"parent/native opaque root phase is not qualified");
    Check(context.phase==Pthreads::WaitPhase::ConditionReleased||context.phase==Pthreads::WaitPhase::MutexReacquire,"unknown native wait phase");
    const addr_t condition=reinterpret_cast<addr_t>(context.condition),mutex=reinterpret_cast<addr_t>(context.mutex);
    if(owner.role==Role::finalizer){
      Check(!context.original_deadline&&!state->gpr.x2.qword&&state->gpr.x30.qword==0x825505d8&&state->gpr.x0.qword==reinterpret_cast<addr_t>(context.condition)&&state->gpr.x1.qword==reinterpret_cast<addr_t>(context.mutex),"original untimed condition arguments/return differ");
      Check(condition>=0x2c&&mutex==condition-0x28&&Read<addr_t>(0x879a7a40)==condition-0x2c&&state->gpr.pc.qword==0x7ffc60000020ULL,"actual finalizer event/import identity or condition/mutex geometry differs");
    }else{
      Check(owner.role==Role::managed_worker,"condition owner has no certified role");
      const auto site=ManagedSite(*state);Check(site!=ManagedWait::unknown,"managed-worker condition caller is unqualified");
      const bool timed=site==ManagedWait::event_timed||site==ManagedWait::condition_timed;
      if(timed)Check(context.original_deadline&&reinterpret_cast<addr_t>(context.original_deadline)==state->gpr.sp.qword&&state->gpr.x2.qword==state->gpr.sp.qword&&state->gpr.pc.qword==0x7ffc60000028ULL,"original managed-worker timed condition phase/deadline differs");
      else Check(!context.original_deadline&&state->gpr.pc.qword==0x7ffc60000020ULL,"original managed-worker untimed condition phase differs"); // X2 is not an untimed ABI argument.
      Check(condition&&mutex&&state->gpr.x0.qword==condition&&state->gpr.x1.qword==mutex,"original managed-worker condition/mutex arguments differ");
      const bool event=site==ManagedWait::event_timed||site==ManagedWait::event_untimed;
      if(event)Check(condition>=0x2c&&mutex==condition-0x28,"original managed-worker event geometry differs");
      const uint64_t frame_size=event?0x70:0x50,frame_pointer=event?0x60:0x40;
      Check(state->gpr.sp.qword<=info.stack_high&&info.stack_high-state->gpr.sp.qword>=frame_size&&state->gpr.x29.qword==state->gpr.sp.qword+frame_pointer,"original managed-worker helper frame differs");
    }
    Check(!(state->gpr.sp.qword&15)&&state->gpr.sp.qword>=info.stack_low&&state->gpr.sp.qword<=info.stack_high&&state->gpr.sp.qword-info.stack_low>=9504&&state->sr.tpidr_el0.qword==info.tls_address,"normal stack/TLS or two-frame capacity differs");
    const auto stack=signals_.AlternateStack(info.token).configured;Check(stack.flags==2&&!stack.pointer&&!stack.size,"target alternate stack is not fresh disabled");
    uint64_t mask=0;Check(!signals_.Mask(info.token,0,nullptr,&mask),"wait signal mask query failed");
    Check(selected?GameCollectorWaitMask::SelectedStop(info.token,mask,*selected):GameCollectorWaitMask::Ordinary(mask),selected?"selected stop action/saved/current mask differs":"ordinary wait blocks original stop/restart signals");
    if(selected)std::fprintf(stderr,"Game GC: selected outer mask verified target=%#llx saved=%#llx current=%#llx action=%#llx signal=%d; no host mask mutation\n",(unsigned long long)info.token,(unsigned long long)selected->saved_mask,(unsigned long long)mask,(unsigned long long)selected->action.mask,selected->signal);
  }
  bool Admit(const recomp::PollAdmissionContext &context) noexcept {
    if(auto*owner=Current())if(const auto*socket=owner->socket_wait.load())return !OpaqueDepth()&&socket->Admit(context);
    auto *owner=Current();if(!owner||!owner->checkpoint||context.site.ordinal!=ProviderOrdinal(*owner))return false;
    return owner->wait_live.load()&&!OpaqueDepth()&&context.frames.size()==1&&context.frames[0]==&context.state&&owner->checkpoint->active_state==&context.state&&context.site.trace==context.state.gpr.pc.qword&&context.program_counter==context.state.gpr.pc.qword;
  }
  void Pump(Owner &owner,State &state){
    if(auto*socket=owner.socket_wait.load()){
      Check(Current()==&owner&&owner.context->CurrentPhase()==Lifecycle::Phase::entered&&owner.context->NativeThreadId()==GetCurrentThreadId()&&owner.wait_state==&state&&!OpaqueDepth()&&owner.socket_boundary,"socket phase has no actual entered bounded owner");
      socket->Validate(threads_,signals_);++owner.pump_calls;if(!Pending(owner))return;
      const auto epoch=Read<uint64_t>(kEpoch);
      if(owner.certified_epoch!=epoch||!owner.certified_new_epoch||owner.begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)throw ProviderDeferred{};
      const auto record=Record(owner.context->PreparedWorker().token);Check(record&&record==owner.record,"socket certified record changed");socket->ValidateRecord(record);Dispositions();
      owner.socket_selected=signals_.DispatchOneAdmittedSubset(socket->Token(),SignalHost::Bit(30)|SignalHost::Bit(24),SignalHost::Bit(30),*owner.socket_boundary);Check(!owner.socket_selected.error,"socket eligible signal outside controlled subset");return;
    }
    // This handler is reached only through the separately qualified controlled
    // provider site. It is not a compiler-inserted trace/backedge site.
    Check(owner.checkpoint&&owner.wait_live,"provider poll has no live certificate");ValidateWait(owner,*owner.checkpoint);
    ++owner.pump_calls;
    if(!Pending(owner))return; // Only a transport hint, never a collector ack.
    Check(SignalHost::NeedsPoll(owner.context->SignalThread()),"masked pending signal outside an owned stop frame");
    const auto epoch=Read<uint64_t>(kEpoch);
    if(owner.certified_epoch!=epoch||!owner.certified_new_epoch||owner.begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)throw ProviderDeferred{};
    const auto record=Record(owner.context->PreparedWorker().token);Check(record&&record==owner.record&&Read<addr_t>(record+0x28)==owner.context->PreparedWorker().stack_high,"pending request has no matching original record");Dispositions();
    // Selection and eligibility intersection are atomic inside SignalHost.
    // A late24 is not cleared by this outer30-only provider boundary.
    auto result=signals_.DispatchOneAllowed(owner.context->PreparedWorker().token,SignalHost::Bit(30),[&](const auto&delivery){return Deliver(delivery);});Check(!result.error,"admitted original signal dispatch failed");(void)state;
  }
  void Retire(const Pthreads::WorkerInfo &info,const Pthreads::WorkerLease &lease,Pthreads::WorkerRetirement reason,const Pthreads::WorkerLifecycleHooks &hooks){
    if(extension_.retire)extension_.retire(info,reason);
    auto owner=Lookup(info.token);
    if(owner){Check(!owner->depth&&!owner->wait_live&&!owner->stop_live,"worker retires through active provider/signal frame");if(owner->binding||owner->delivery){Check(owner->context->NativeThreadId()==GetCurrentThreadId()&&(!owner->binding||Current()==owner.get()),"poll binding retirement on wrong worker");Check(!Pending(*owner),"worker retires with an original pending signal");owner->binding.reset();owner->delivery.reset();Current()=nullptr;}}
    hooks.retire(info,lease,reason);
    {std::lock_guard lock(mutex_);owners_.erase(info.token);}
    GameWorkerObservation::Retire(info,reason);
  }
  void NestedSuspend(Owner &owner,State &state){
    const auto frames=recomp::CurrentExecutionFrames(state);const auto record=owner.record.load();
    Check(Current()==&owner&&owner.depth==1&&owner.stop_live&&owner.posts==1&&frames.size()==2&&frames[0]==&state&&frames[1]==owner.wait_state&&state.gpr.x30.qword==0x825b2c24&&state.gpr.x0.qword==0x879a6b18&&state.gpr.sp.qword==owner.frame_base-0x60&&state.gpr.x29.qword==owner.frame_base-0x30,"sigsuspend is outside the exact original stop frame");
    Check(record&&Read<addr_t>(record+0x18)==state.gpr.x29.qword&&Read<uint64_t>(record+0x10)==owner.stop_epoch&&owner.stop_epoch==Read<uint64_t>(kEpoch),"original stop FP/epoch is not published before sigsuspend");
    const auto expected=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24));
    Check(Read<uint64_t>(0x879a6b18)==expected,"original temporary mask can select an unqualified handler");Dispositions();
    // An early/old24 may run while worldStopped is still1. The original body
    // itself tests that flag after EINTR and waits again; no host early resume.
  }
 public:
  struct Opaque {bool active;explicit Opaque(bool enabled):active(enabled){if(active)++OpaqueDepth();}~Opaque(){if(active)--OpaqueDepth();}};
  static constexpr uint32_t kVirtualRealUid=10000; // Explicit sandbox, not Windows/device identity.
  GameCollectorDelivery(Pthreads &threads,SignalHost &signals,bunker::windows::Semaphores &sem,recomp::Runtime &runtime,WorkerExtension extension={}):threads_(threads),signals_(signals),semaphores_(sem),runtime_(runtime),lifecycle_(signals),extension_(std::move(extension)){
    const bool any_extension=extension_.prepare||extension_.enter||extension_.before_tls||extension_.retire||extension_.owns||extension_.checkpoint;
    Check(!any_extension||(extension_.prepare&&extension_.enter&&extension_.before_tls&&extension_.retire&&extension_.owns&&extension_.checkpoint),"worker extension hooks are incomplete");
    Check(Translated(kReturn)&&Executable(kReturn)&&Translated(0x825beb3c)&&Translated(0x825b2af4)&&Translated(0x825b2c70),"original normal-return/handler heads missing from final cohort");
    auto hooks=lifecycle_.TakeHooks();auto installed=hooks;
    installed.prepare=[this,hooks](const auto &info){auto lease=hooks.prepare(info);auto owner=std::make_shared<Owner>();owner->context=lifecycle_.Lookup(info.token);owner->role=Creating()?Creating()->role:Role::unknown;{std::lock_guard lock(mutex_);Check(!closed_&&owners_.emplace(info.token,owner).second,"duplicate/closed worker owner");}if(extension_.prepare)extension_.prepare(info,lifecycle_);GameWorkerObservation::Lifecycle("prepare",info);return lease;};
    installed.enter=[this,hooks](const auto &info,const auto &lease){hooks.enter(info,lease);auto owner=Lookup(info.token);Check(owner&&Current()==nullptr,"worker owner entry is not cold");owner->delivery=std::make_unique<SignalDelivery>(runtime_,Translated,kReturn,recomp::signal_frame::Bounds{info.stack_low,info.stack_high},signals_,info.token);owner->binding=std::make_unique<recomp::PollBinding>(owner->context->PollRequests(),[this,owner](State &s,recomp::PollSite,const auto&){try{Pump(*owner,s);}catch(const ProviderDeferred&){throw;}catch(const std::exception&e){Fail(e.what());}catch(...){Fail("unknown original delivery exception");}},[this](const auto &context){return Admit(context);});Current()=owner.get();if(extension_.enter)extension_.enter(info);GameWorkerObservation::Enter(info);};
    installed.before_tls=[this,hooks](const auto &info,const auto &lease){if(extension_.before_tls)extension_.before_tls(info);auto owner=Lookup(info.token);Check(owner&&!owner->depth&&!owner->wait_live&&!Pending(*owner),"worker reaches TLS with active/pending stop");hooks.before_tls(info,lease);GameWorkerObservation::Lifecycle("before_tls",info);};
    installed.retire=[this,hooks](const auto &i,const auto&l,auto r){Retire(i,l,r,hooks);};threads_.SetWorkerLifecycleHooks(std::move(installed));
    threads_.SetWaitHooks({[this](uint64_t token){auto owner=Lookup(token);auto channel=owner?owner->channel:std::make_shared<Channel>();return std::make_shared<const Pthreads::WaitWake>(Pthreads::WaitWake{[channel]{return channel->Generation();},[channel]{channel->Notify();},[channel](auto generation,auto relative){channel->Wait(generation,relative);}});},[this](const auto &context){Checkpoint(context);}});
    std::fprintf(stderr,"Game GC: creator-certified finalizer untimed and managed-worker timed/untimed condition profiles configured; virtual Android real UID=%u; no Windows/device UID claim\n",kVirtualRealUid);
  }
  ~GameCollectorDelivery(){Check(closed_,"collector adapter destroyed before worker drain");}
  void CloseAfterShutdown(){std::lock_guard lock(mutex_);Check(owners_.empty(),"collector close has live workers");lifecycle_.CloseAfterShutdown();closed_=true;}
  void Notify(uint64_t token){
    // SignalHost normally calls its request_poll callback only while eligible
    // pending bits exist. A concurrent retirement/mask change may already have
    // cleared that condition; an obsolete wake is not another GC request.
    if(!SignalHost::NeedsPoll(signals_.Lookup(token)))return;
    if(auto owner=Lookup(token))if(owner->socket_wait.load()){owner->context->PollRequests().Request();return;}
    auto owner=Lookup(token);Check(owner&&ConditionRole(*owner)&&(owner->wait_live.load()||owner->stop_live.load()),"queued target has left its qualified wait/stop lifetime");owner->context->PollRequests().Request();owner->channel->Notify();
  }
  void WithCreate(State &state,const std::function<void(State&)> &invoke){
    GameWorkerObservation::BeforeCreate(state);Witness witness;
    if(state.gpr.x30.qword==0x82556a64&&state.gpr.x2.qword==0x82556a94&&state.gpr.x3.qword){const auto record=state.gpr.x3.qword;Check(record<=UINT64_MAX-0x20,"original creator prefix overflow");if(Read<addr_t>(record+0x10)==0x82557c80){const auto payload=Read<addr_t>(record+0x18);Check(payload&&payload<=UINT64_MAX-24,"original creator payload overflow");const auto owner=Read<addr_t>(payload),function=Read<addr_t>(payload+8),argument=Read<addr_t>(payload+16);if(owner&&function==0x825c3ed0&&!argument)witness.role=Role::finalizer;else if(owner&&function==0x8258aa94&&argument)witness.role=Role::managed_worker;}}
    struct Scope {const Witness *previous;explicit Scope(const Witness &w):previous(Creating()){Creating()=&w;}~Scope(){Creating()=previous;}} scope(witness);invoke(state);
  }
  void WithWait(const std::string &name,State &state,const std::function<void()> &invoke){
    auto *owner=Current();
    if(owner&&owner->socket_wait.load()&&name=="sigsuspend"){NestedSuspend(*owner,state);invoke();return;}
    if(owner&&owner->role==Role::managed_worker&&!owner->socket_wait.load()&&!owner->depth&&
       ((name!="pthread_cond_wait"&&name!="pthread_cond_timedwait")||ManagedSite(state)==ManagedWait::unknown||!ManagedContext(state))){
      // An outer certificate is not live while nested/opaque ordinary roots run.
      // Only a later fully qualified checkpoint may publish it again.
      owner->wait_live=false;
      Check(!Pending(*owner),"unqualified managed wait has pending collector delivery");
      invoke();Check(!Pending(*owner),"pending collector delivery raced an unqualified managed wait");return;
    }
    if(name=="sigsuspend"){Check(owner&&ConditionRole(*owner),"sigsuspend has no owned original stop");NestedSuspend(*owner,state);invoke();return;}
    if(owner&&ConditionRole(*owner)&&(name=="sem_wait"||name=="sem_timedwait"))Fail("unqualified semaphore wait cannot consume a collector signal");
    if(owner&&ConditionRole(*owner)&&(name=="pthread_cond_wait"||name=="pthread_cond_timedwait")){
      Check(!owner->wait_state&&!owner->depth,"nested condition provider is unqualified");owner->wait_state=&state;invoke();owner->wait_live=false;Check(!Pending(*owner),"original pending signal raced provider exit");owner->wait_state=nullptr;
    }else invoke();
  }
  void Checkpoint(const Pthreads::WaitContext &context){
    GameWorkerObservation::NativeEnvironment native;
    if(extension_.owns&&extension_.owns(context.token)){extension_.checkpoint(context);return;}
    auto owner=Lookup(context.token);if(!owner||!ConditionRole(*owner)){if(owner)Check(!Pending(*owner),"unknown-role worker has pending delivery");return;}
    if(owner->role==Role::managed_worker&&(!context.active_state||ManagedSite(*context.active_state)==ManagedWait::unknown||!ManagedContext(*context.active_state))){
      owner->wait_live=false;
      Check(!Pending(*owner),"unqualified managed checkpoint has pending collector delivery");return;
    }
    // Basic wait publication does not walk the original registry. It can run
    // while unrelated original registrations/unlinks mutate their buckets.
    ValidateWait(*owner,context);Check(owner->wait_state==context.active_state,"checkpoint is outside actual observed import invocation");
    auto use=lifecycle_.AcquireUse(context.token);owner->wait_live=true;owner->checkpoint=&context;
    struct Scope {Owner &owner;~Scope(){owner.checkpoint=nullptr;}} scope{*owner};
    for(unsigned count=0;__bunker_guest_poll_requested();++count){
      Check(count<16,"provider transport hint drain budget exhausted");
      if(Pending(*owner)){
        const auto epoch=Read<uint64_t>(kEpoch);
        // A late standard30 may outlive resume. Keep both the model bit and
        // transport epoch pending until a new genuine stop send certifies a
        // stable registry cycle. Do not interpret an unrelated lockword1 as it.
        // Once this target has begun the epoch, the coordinator can complete
        // and release its lock. Do not walk buckets again for late retries.
        if(owner->certified_epoch!=epoch||!owner->certified_new_epoch||owner->begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)return;
        const auto record=Record(context.token);Check(record&&record==owner->record,"certified target record changed");
        if((Read<uint64_t>(record+0x10)&~uint64_t(1))==epoch)return;
      }
      const auto previous=owner->pump_calls;
      try{__bunker_guest_poll_slow(context.active_state,context.active_state->gpr.pc.qword,ProviderOrdinal(*owner),context.active_state->gpr.pc.qword);}
      catch(const ProviderDeferred&){return;}
      if(owner->pump_calls==previous)return; // Admission deferred: keep epoch.
    }
  }
  void BeforeKill(const State &state){
    if(auto owner=Lookup(state.gpr.x0.qword))if(auto*socket=owner->socket_wait.load()){
      const auto signal=state.gpr.x1.dword;Check((signal==30||signal==24)&&state.gpr.x30.qword==(signal==30?0x825b2d1cULL:0x825b2f74ULL),"socket signal sender is outside original coordinator");
      Check(recomp::CurrentExecutionState()==&state&&!OpaqueDepth(),"socket sender is opaque or foreign State");const auto frames=recomp::CurrentExecutionFrames(*recomp::CurrentExecutionState());Check(frames.size()==1&&frames[0]==&state,"socket sender has parent Runtime roots");
      const auto epoch=Read<uint64_t>(kEpoch);Check(epoch&&!(epoch&1)&&Read<uint8_t>(0x879a62a8)==1&&threads_.Self()!=socket->Token(),"socket original sender epoch/lock/self differs");
      Check(signal==30?Read<uint64_t>(kStopped)==1:owner->stop_live&&owner->stop_epoch==epoch&&!Read<uint64_t>(kStopped),"socket stop/restart phase differs");Dispositions();
      const auto record=Record(socket->Token());Check(record&&(signal==30?state.gpr.x26.qword:state.gpr.x27.qword)==record,"socket original sender traversal differs");socket->ValidateRecord(record);owner->record=record;
      if(signal==30){owner->certified_new_epoch=(Read<uint64_t>(record+0x10)&~uint64_t(1))!=epoch;owner->certified_epoch=epoch;}return;
    }
    const auto token=state.gpr.x0.qword;const auto signal=state.gpr.x1.dword;Check(signal==30||signal==24,"only original stop/restart nonzero sends are supported");auto owner=Lookup(token);Check(owner&&ConditionRole(*owner)&&owner->context->CurrentPhase()==Lifecycle::Phase::entered,"send target is not a captured live creator-certified condition owner");
    Check(state.gpr.x30.qword==(signal==30?0x825b2d1cULL:0x825b2f74ULL),"nonzero send is outside audited original caller");
    auto *active=recomp::CurrentExecutionState();Check(active==&state&&!OpaqueDepth(),"collector sender is inside an opaque native continuation");const auto sender_frames=recomp::CurrentExecutionFrames(*active);Check(sender_frames.size()==1&&sender_frames[0]==active,"collector sender has unqualified parent Runtime roots");
    const auto epoch=Read<uint64_t>(kEpoch);Check(epoch&&!(epoch&1)&&Read<uint8_t>(0x879a62a8)==1&&token!=threads_.Self(),"original epoch/registry-lock consistency differs");
    if(signal==30)Check(state.gpr.x30.qword==0x825b2d1c&&owner->wait_live&&Read<uint64_t>(kStopped)==1,"original stop caller/live wait cycle differs");
    else Check(state.gpr.x30.qword==0x825b2f74&&owner->stop_live&&owner->stop_epoch==epoch&&!Read<uint64_t>(kStopped),"original restart caller/owned stop differs");
    // Only the audited sender paths, paused under their original collector
    // registry lock, may authorize this host bucket walk.
    Dispositions();
    const auto record=Record(token);const auto actual=signal==30?state.gpr.x26.qword:state.gpr.x27.qword;
    Check(record&&actual==record&&Read<uint64_t>(record+8)==token&&Read<addr_t>(record+0x28)==owner->context->PreparedWorker().stack_high,"actual original traversal record/owned stack differs");
    if(signal==30){Check(state.gpr.x30.qword==0x825b2d1c&&owner->wait_live&&Read<uint64_t>(kStopped)==1&&!(Read<uint8_t>(record+0x20)&1)&&!Read<uint8_t>(record+0x21),"original stop sender/eligible wait differs");}
    else Check(state.gpr.x30.qword==0x825b2f74&&owner->stop_live&&owner->stop_epoch==epoch&&!Read<uint64_t>(kStopped),"original restart sender/owned stop differs");
    owner->record=record;
    if(signal==30){owner->certified_new_epoch=(Read<uint64_t>(record+0x10)&~uint64_t(1))!=epoch;owner->certified_epoch=epoch;}
    std::fprintf(stderr,"Game GC: original request signal=%u target=%#llx record=%#llx epoch=%llu LR=%#llx; source validated before actual pthread_kill\n",signal,(unsigned long long)token,(unsigned long long)record,(unsigned long long)epoch,(unsigned long long)state.gpr.x30.qword);
  }
  void Send(State &state,const std::function<void()> &invoke){
    auto owner=Lookup(state.gpr.x0.qword);Check(bool(owner),"nonzero send has no real worker owner");
    std::unique_lock socket_guard(owner->socket_sender_mutex);if(!owner->socket_wait.load())socket_guard.unlock();
    BeforeKill(state);invoke();
  }
  void BeforeNonlocal(){auto *owner=Current();if(owner&&owner->depth)Fail("nonlocal capture/transfer attempted inside an active collector frame");}
  std::optional<uint64_t> Deliver(const SignalHost::Delivery &delivery){
    if(auto*owner=Current())if(auto*socket=owner->socket_wait.load()){
      Check(delivery.token==socket->Token()&&owner->context->NativeThreadId()==GetCurrentThreadId(),"socket delivery has foreign owner");Dispositions();const auto token=socket->Token();auto use=lifecycle_.AcquireUse(token);const auto record=owner->record.load();Check(record!=0,"socket delivery lacks sender certificate");socket->ValidateRecord(record);
      if(!owner->depth){
        Check(delivery.signal==30&&owner->socket_boundary,"socket outer delivery is not controlled stop30");socket->Validate(threads_,signals_,&delivery);const auto epoch=Read<uint64_t>(kEpoch);const bool duplicate=(Read<uint64_t>(record+0x10)&~uint64_t(1))==epoch;Check(epoch&&!(epoch&1)&&(duplicate||Read<uint64_t>(kStopped)==1),"socket stopped epoch differs");
        owner->interrupted=*recomp::CurrentExecutionState();owner->frame_base=owner->interrupted.gpr.sp.qword-4704;owner->posts=0;owner->stop_epoch=epoch;owner->begun_epoch=epoch;owner->stop_live=!duplicate;owner->depth=1;
        auto result=owner->delivery->Deliver(delivery);Check(owner->posts==(duplicate?0u:2u),"socket original handler omitted genuine posts");if(!duplicate)Check(Read<uint64_t>(record+0x10)==(epoch|1),"socket original resume epoch store absent");owner->depth=0;owner->stop_live=false;
        std::fprintf(stderr,"Game GC socket wait: genuine stop returned token=%#llx epoch=%llu actual_posts=%u; no collection/frame claim\n",(unsigned long long)token,(unsigned long long)epoch,owner->posts);return result;
      }
      Check(delivery.signal==24,"socket nested delivery is not restart24");NestedSuspend(*owner,*recomp::CurrentExecutionState());owner->depth=2;auto result=owner->delivery->Deliver(delivery);owner->depth=1;return result;
    }
    auto *owner=Current();Check(owner&&ConditionRole(*owner)&&delivery.token==owner->context->PreparedWorker().token,"delivery has wrong original worker");Dispositions();
    const auto token=delivery.token;auto use=lifecycle_.AcquireUse(token);const auto record=owner->record.load();Check(record&&Read<uint64_t>(record+8)==token,"delivery record was not the validated original record");
    if(!owner->depth){
      Check(delivery.signal==30&&owner->checkpoint,"outer delivery is not qualified stop30");ValidateWait(*owner,*owner->checkpoint,&delivery);const auto epoch=Read<uint64_t>(kEpoch);const bool duplicate=(Read<uint64_t>(record+0x10)&~uint64_t(1))==epoch;
      Check(epoch&&!(epoch&1)&&(duplicate||Read<uint64_t>(kStopped)==1),"new stop has no live original stopped epoch");
      owner->interrupted=*recomp::CurrentExecutionState();owner->frame_base=owner->interrupted.gpr.sp.qword-4704;owner->posts=0;owner->stop_epoch=epoch;owner->begun_epoch=epoch;owner->stop_live=!duplicate;owner->depth=1;
      auto result=owner->delivery->Deliver(delivery);
      Check(owner->posts==(duplicate?0u:2u),"original stop path returned without its own expected post calls");if(!duplicate)Check(Read<uint64_t>(record+0x10)==(epoch|1),"original resume epoch store was not observed");
      owner->depth=0;owner->stop_live=false;
      std::fprintf(stderr,"Game GC: original stop handler returned target=%#llx epoch=%llu duplicate=%u actual_posts=%u observed_record_epoch=%llu; no collection/init/frame claim\n",(unsigned long long)token,(unsigned long long)epoch,unsigned(duplicate),owner->posts,(unsigned long long)Read<uint64_t>(record+0x10));return result;
    }
    auto *state=recomp::CurrentExecutionState();Check(delivery.signal==24,"nested signal is not original restart24");NestedSuspend(*owner,*state);owner->depth=2;auto result=owner->delivery->Deliver(delivery);owner->depth=1;
    std::fprintf(stderr,"Game GC: original nested restart handler returned target=%#llx epoch=%llu\n",(unsigned long long)token,(unsigned long long)owner->stop_epoch.load());return result;
  }
  void BeforePost(const State &state){
    auto *owner=Current();if(!owner||!owner->depth)return;
    if(auto*socket=owner->socket_wait.load()){Check(owner->depth==1&&owner->stop_live&&state.gpr.x0.qword==kAck&&state.gpr.x30.qword==(owner->posts?0x825b2c50ULL:0x825b2c04ULL)&&owner->posts<2,"socket acknowledgment caller differs");socket->PhysicalRoots(owner->interrupted,owner->frame_base,owner->record.load());return;}
    Check(owner->depth==1&&owner->stop_live&&state.gpr.x0.qword==kAck&&state.gpr.x30.qword==(owner->posts?0x825b2c50ULL:0x825b2c04ULL)&&owner->posts<2,"unqualified acknowledgment path");
    const auto record=owner->record.load();Check(Read<addr_t>(record+0x18)==owner->frame_base-0x30,"original published FP differs from real handler frame");
    const addr_t saved=owner->frame_base+recomp::signal_frame::kMachineOffset+8;
    for(unsigned i=0;i<31;++i){uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&owner->interrupted.gpr)+i*16+8,8);Check(Read<uint64_t>(saved+i*8)==value,"interrupted GPR is not physically in original scan range");}
    std::array<uint8_t,512> vectors{};recomp::ReadGuestMemory(vectors.data(),owner->frame_base+recomp::signal_frame::kFpsimdOffset+16,vectors.size());Check(!std::memcmp(vectors.data(),&owner->interrupted.simd,vectors.size()),"interrupted SIMD is not physically in original scan range");
    std::fprintf(stderr,"Game GC: physical interrupted roots verified target=%#llx frame=%#llx published_fp=%#llx original_sp=%#llx stack_high=%#llx GPR=31 Q=32; before original sem_post\n",(unsigned long long)owner->context->PreparedWorker().token,(unsigned long long)owner->frame_base,(unsigned long long)Read<addr_t>(record+0x18),(unsigned long long)owner->interrupted.gpr.sp.qword,(unsigned long long)owner->context->PreparedWorker().stack_high);
  }
  void AfterPost(const State &state){auto *owner=Current();if(!owner||!owner->depth)return;Check(!state.gpr.x0.dword,"original acknowledgment sem_post failed");++owner->posts;std::fprintf(stderr,"Game GC: original sem_post returned target=%#llx ordinal=%u LR=%#llx; epoch store follows in original code\n",(unsigned long long)owner->context->PreparedWorker().token,owner->posts,(unsigned long long)state.gpr.x30.qword);}
  bool Owns(uint64_t token){auto owner=Lookup(token);return owner&&owner->context->CurrentPhase()==Lifecycle::Phase::entered;}
  template<class F>void WithSocketWait(const std::string&name,State&state,F&&invoke,const GameSocketWaitContext::SitePolicy&policy={}){
    auto owner=Lookup(threads_.Self());Check(owner&&Current()==owner.get()&&owner->context->CurrentPhase()==Lifecycle::Phase::entered&&owner->context->NativeThreadId()==GetCurrentThreadId()&&!owner->wait_state&&!owner->depth&&!owner->socket_wait.load(),"socket import has no idle actual entered worker");
    const auto&info=owner->context->PreparedWorker();auto use=lifecycle_.AcquireUse(info.token);GameSocketWaitContext socket(state,name,info.token,info.stack_low,info.stack_high,info.tls_address,false,policy);
    {std::lock_guard lock(owner->socket_sender_mutex);owner->wait_state=&state;owner->socket_wait=&socket;}
    struct Scope{Owner&owner;~Scope(){std::lock_guard lock(owner.socket_sender_mutex);owner.socket_wait=nullptr;owner.wait_state=nullptr;owner.socket_boundary=nullptr;}}scope{*owner};invoke();socket.Complete();
  }
  GameSocketWaitContext::Decision ObserveSocketWait(const GameSocketWaitContext::Observation&observation){
    auto*owner=Current();if(!owner||!owner->socket_wait.load())return{};auto*socket=owner->socket_wait.load();
    return socket->Observe(observation,[&]{
      Check(!OpaqueDepth(),"socket checkpoint is opaque");socket->Validate(threads_,signals_);const auto epoch=Read<uint64_t>(kEpoch);
      if(!SignalHost::NeedsPoll(owner->context->SignalThread())||owner->certified_epoch!=epoch||!owner->certified_new_epoch||owner->begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)return GameSocketWaitContext::Decision{};
      const auto record=Record(socket->Token());Check(record&&record==owner->record,"socket sender-certified worker record changed");GameSocketWaitContext::PollCertificate certificate(*socket,record,epoch);
      owner->socket_selected={};const SignalHost::Boundary boundary=[this](const auto&delivery){return Deliver(delivery);};owner->socket_boundary=&boundary;
      struct Scope{Owner&owner;~Scope(){owner.socket_boundary=nullptr;}}scope{*owner};
      if(SignalHost::NeedsPoll(owner->context->SignalThread()))owner->context->PollRequests().Request();
      try{if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(&socket->StateRef(),socket->StateRef().gpr.pc.qword,GameSocketWaitContext::kOrdinal,socket->StateRef().gpr.pc.qword);}
      catch(const ProviderDeferred&){return GameSocketWaitContext::Decision{};}
      return GameSocketWaitContext::Decision{owner->socket_selected.handled,owner->socket_selected.restart};
    });
  }
};
