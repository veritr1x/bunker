#pragma once
#include "game_collector_mask.h"
#include "game_socket_wait_context.h"
// Included in the harness namespace after Read/Translated/Executable helpers.
// Actual prepared Unity-wrapper workers at one exact timed-private-futex phase.
// Ordinary GC records remain original-owned. No callback role, record, epoch,
// semaphore post, or signal acknowledgment is synthesized by this adapter.
class GameUnityWorkerCollector {
  using Pthreads=bunker::windows::Pthreads;
  using SignalHost=bunker::windows::SignalHost;
  using SignalDelivery=bunker::windows::SignalDelivery;
  using Lifecycle=bunker::windows::WorkerSignalLifecycle;
  struct Deferred {};
  struct Witness {addr_t data=0;};
  struct Owner {
    uint64_t token=0,parent=0;DWORD native_tid=0;
    Lifecycle::ContextRef context;Lifecycle* lifecycle=nullptr;addr_t create_data=0;
    SignalHost::ThreadRef signal_thread;std::shared_ptr<bunker::windows::SignalWake> wake;
    recomp::PollRequest requests;std::unique_ptr<recomp::PollBinding> binding;
    std::unique_ptr<SignalDelivery> delivery;
    std::mutex sender_mutex;std::atomic<bool> live{false};
    std::atomic<addr_t> low{0},high{0},tls{0},record{0};
    std::atomic<uint64_t> certified_epoch{0},begun_epoch{0},stop_epoch{0};
    std::atomic<bool> certified_new_epoch{false},stop_live{false};
    State *sleep_state=nullptr;bool phase=false,copied=false,returned=false,eligible=false;uint64_t deadline=0;
    std::atomic<GameSocketWaitContext*> socket_wait{nullptr};
    bunker::windows::SignalFutexes::WaitObservation observation{};
    const SignalHost::Boundary *provider_boundary=nullptr;
    SignalHost::Dispatch selected{};State interrupted{};addr_t frame_base=0;
    unsigned depth=0,posts=0;
  };
  Pthreads &threads_;SignalHost &signals_;bunker::windows::Semaphores &semaphores_;recomp::Runtime &runtime_;
  std::mutex mutex_;std::map<uint64_t,std::shared_ptr<Owner>> owners_;bool closed_=false;
  static Owner *&Current(){static thread_local Owner *owner=nullptr;return owner;}
  static const Witness*&Creating(){static thread_local const Witness* value=nullptr;return value;}
  static unsigned &OpaqueDepth(){static thread_local unsigned depth=0;return depth;}
  static constexpr uint64_t kOrdinal=UINT64_MAX-2;
  static constexpr addr_t kReturn=0x825aada0,kAck=0x87cb1e68,kEpoch=0x879a6b08,kStopped=0x879a6b10;
  static constexpr addr_t kSyscall=0x7ff600400000ULL;
  static void Check(bool okay,const char*why){if(!okay)throw std::runtime_error(std::string("ordinary Unity worker collector: ")+why);}
  std::shared_ptr<Owner> Lookup(uint64_t token){std::lock_guard lock(mutex_);auto found=owners_.find(token);return found==owners_.end()?nullptr:found->second;}
  bool Pending(const Owner&owner){uint64_t blocked=0;Check(!signals_.Pending(owner.token,&blocked),"signal lifetime is absent");return blocked||SignalHost::NeedsPoll(owner.signal_thread);}
  void ActualBounds(Owner&owner){
    bunker::windows::AndroidThreadAttr attr{};
    Check(!threads_.GetAttr(owner.token,&attr)&&attr.stack_base&&attr.stack_size&&attr.stack_size<=UINT64_MAX-attr.stack_base,"actual worker Pthreads stack is unavailable");
    const auto high=attr.stack_base+attr.stack_size;Check(!((attr.stack_base|high)&15),"actual stack alignment differs");
    auto low=owner.low.load();if(!low){owner.high=high;owner.low=attr.stack_base;}else Check(low==attr.stack_base&&owner.high==high,"actual worker stack lifetime changed");
  }
  addr_t Record(uint64_t token){
    Check(Read<uint32_t>(0x879a62a0)==1,"original registry is not initialized");
    uint32_t hash=uint32_t(token>>8)^uint32_t(token);hash^=hash>>16;
    addr_t cursor=Read<addr_t>(0x879a6b28+(hash&255)*8);std::array<addr_t,256>seen{};size_t count=0;
    while(cursor){Check(!(cursor&7)&&cursor<=UINT64_MAX-0x60&&count<seen.size(),"original registry chain shape differs");for(size_t i=0;i<count;++i)Check(seen[i]!=cursor,"original registry chain cycles");seen[count++]=cursor;if(Read<uint64_t>(cursor+8)==token)return cursor;cursor=Read<addr_t>(cursor);}
    return 0;
  }
  void OrdinaryRecord(Owner&owner,addr_t record){
    Check(record&&record!=0x879a7330&&Read<uint64_t>(record+8)==owner.token,"original ordinary record/token differs");
    Check(Read<uint32_t>(record+0x20)==2,"original ordinary flags are not exact2");
    Check(Read<addr_t>(record+0x28)==owner.high&&Read<addr_t>(record+0x30)==0&&Read<addr_t>(record+0x38)==0&&Read<addr_t>(record+0x50)==0,"ordinary scan high/segment/sections differs from captured owned stack");
    const auto fp=Read<addr_t>(record+0x18);Check(fp>=owner.low&&fp<=owner.high&&!(fp&7),"ordinary published stack pointer is outside captured stack");
  }
  void Dispositions(){
    Check(Read<int32_t>(0x87984e14)==30&&Read<int32_t>(0x87984e18)==24&&Read<int32_t>(0x87984e10)==1,"original configured signals/retry differ");
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){bunker::windows::AndroidSignalAction action{};Check(!signals_.Action(signal,nullptr,&action)&&action.handler==0x825beb3c&&action.flags==uint32_t(signal==30?0x10000004:0x10000000)&&action.mask==mask,"original disposition/thunk/mask differs");}
    Check(Read<addr_t>(0x879a7788)==0x825b2af4&&Read<addr_t>(0x879a7758)==0x825b2c70,"original handler table differs");
    int32_t count=0;Check(!semaphores_.GetValue(kAck,&count),"original acknowledgment semaphore is unavailable");
  }
  void Phase(Owner&owner,const SignalHost::Delivery *selected=nullptr){
    if(auto*socket=owner.socket_wait.load()){
      Check(owner.live&&owner.context&&owner.context->CurrentPhase()==Lifecycle::Phase::entered&&Current()==&owner&&owner.native_tid==GetCurrentThreadId()&&threads_.Self()==owner.token&&owner.phase&&owner.sleep_state==&socket->StateRef()&&!OpaqueDepth(),"socket phase has no actual entered nonopaque owner");
      socket->Validate(threads_,signals_,selected);return;
    }
    auto *state=recomp::CurrentExecutionState();Check(owner.live&&owner.context&&owner.context->CurrentPhase()==Lifecycle::Phase::entered&&Current()==&owner&&owner.native_tid==GetCurrentThreadId()&&threads_.Self()==owner.token,"phase is not on actual entered prepared worker");
    Check(owner.phase&&owner.sleep_state&&state==owner.sleep_state&&!OpaqueDepth(),"phase has no exact live syscall State");
    const auto frames=recomp::CurrentExecutionFrames(*state);Check(frames.size()==1&&frames[0]==state,"phase has enclosing Runtime roots");
    Check(Shape(*state),"phase is not original timed private-futex helper");
    const auto sp=state->gpr.sp.qword;Check(!(sp&15)&&sp>=owner.low&&sp<=owner.high&&sp-owner.low>=9504&&owner.high-sp>=32,"actual normal stack lacks helper/two-frame bounds");
    Check(owner.tls&&state->sr.tpidr_el0.qword==owner.tls,"materialized worker TLS identity changed");
    const auto alternate=signals_.AlternateStack(owner.token);const auto &stack=alternate.configured;
    Check(stack.flags==2&&!stack.pointer&&!stack.size&&!alternate.region,"worker alternate stack is not fresh disabled");
    uint64_t mask=0;Check(!signals_.Mask(owner.token,0,nullptr,&mask),"actual signal mask query failed");
    Check(selected?GameCollectorWaitMask::SelectedStop(owner.token,mask,*selected):GameCollectorWaitMask::Ordinary(mask),"ordinary/selected original stop masks differ");
  }
  bool Admit(const recomp::PollAdmissionContext&context)const noexcept{
    if(const auto*owner=Current())if(const auto*socket=owner->socket_wait.load())return owner->live&&owner->phase&&!OpaqueDepth()&&socket->Admit(context);
    const auto *owner=Current();return owner&&owner->live&&owner->phase&&owner->eligible&&owner->copied&&!owner->returned&&owner->provider_boundary&&!OpaqueDepth()&&context.site.ordinal==kOrdinal&&context.frames.size()==1&&context.frames[0]==&context.state&&owner->sleep_state==&context.state&&context.program_counter==context.state.gpr.pc.qword&&context.site.trace==context.state.gpr.pc.qword;
  }
  void Pump(Owner&owner){
    Phase(owner);Check(owner.provider_boundary,"controlled site has no real timed-futex wrapped boundary");
    const auto epoch=Read<uint64_t>(kEpoch);
    if(owner.certified_epoch!=epoch||!owner.certified_new_epoch||owner.begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)throw Deferred{};
    const auto record=Record(owner.token);Check(record&&record==owner.record,"certified original ordinary record changed");OrdinaryRecord(owner,record);Dispositions();
    owner.selected=signals_.DispatchOneAdmittedSubset(owner.token,SignalHost::Bit(30)|SignalHost::Bit(24),SignalHost::Bit(30),*owner.provider_boundary);
    Check(!owner.selected.error,"unknown eligible signal or invalid controlled subset selection");
  }
  void NestedSuspend(Owner&owner,State&state){
    const auto frames=recomp::CurrentExecutionFrames(state);const auto record=owner.record.load();
    Check(Current()==&owner&&owner.depth==1&&owner.stop_live&&owner.posts==1&&frames.size()==2&&frames[0]==&state&&frames[1]==owner.sleep_state&&state.gpr.x30.qword==0x825b2c24&&state.gpr.x0.qword==0x879a6b18&&state.gpr.sp.qword==owner.frame_base-0x60&&state.gpr.x29.qword==owner.frame_base-0x30,"nested sigsuspend is outside exact original worker stop");
    Check(record&&Read<addr_t>(record+0x18)==state.gpr.x29.qword&&Read<uint64_t>(record+0x10)==owner.stop_epoch&&owner.stop_epoch==Read<uint64_t>(kEpoch),"original published ordinary FP/epoch differs");
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24));Check(Read<uint64_t>(0x879a6b18)==mask,"original temporary mask differs");Dispositions();
  }
 public:
  struct Opaque{bool active;explicit Opaque(bool enabled):active(enabled){if(active)++OpaqueDepth();}~Opaque(){if(active)--OpaqueDepth();}};
  GameUnityWorkerCollector(Pthreads&threads,SignalHost&signals,bunker::windows::Semaphores&sem,recomp::Runtime&runtime):threads_(threads),signals_(signals),semaphores_(sem),runtime_(runtime){Check(Translated(kReturn)&&Executable(kReturn)&&Translated(0x825beb3c)&&Translated(0x825b2af4)&&Translated(0x825b2c70),"genuine original signal heads are unavailable");}
  ~GameUnityWorkerCollector(){if(!closed_||!owners_.empty())std::terminate();}
  bool Owns(uint64_t token){auto owner=Lookup(token);return owner&&owner->live;}
  template<class F>void WithCreate(State&state,F&&invoke){
    Witness witness;const Witness* previous=Creating();
    if(state.gpr.x2.qword==0x70383624&&state.gpr.x30.qword==0x704389a8){Check(state.gpr.x3.qword!=0,"Unity create has null original threadData");witness.data=state.gpr.x3.qword;}
    Creating()=&witness;struct Scope{const Witness* previous;~Scope(){Creating()=previous;}}scope{previous};invoke(state);
  }
  void Prepare(const Pthreads::WorkerInfo&info,Lifecycle&lifecycle){
    if(!Creating()||!Creating()->data)return;
    auto owner=std::make_shared<Owner>();owner->token=info.token;owner->parent=info.parent_token;owner->low=info.stack_low;owner->high=info.stack_high;owner->tls=info.tls_address;owner->create_data=Creating()->data;owner->lifecycle=&lifecycle;owner->context=lifecycle.Lookup(info.token);
    Check(owner->context&&owner->context->CurrentPhase()==Lifecycle::Phase::prepared&&info.token&&info.parent_token&&info.token!=info.parent_token&&info.stack_low&&info.stack_high>info.stack_low&&info.tls_address&&!info.native_tid,"invalid prepared real Unity worker");
    owner->signal_thread=owner->context->SignalThread();owner->wake=owner->context->Wake();Check(owner->signal_thread&&owner->wake,"prepared actual signal lifetime absent");
    std::lock_guard lock(mutex_);Check(!closed_&&owners_.emplace(info.token,owner).second,"duplicate/closed Unity worker preparation");
  }
  void Enter(const Pthreads::WorkerInfo&info){
    auto owner=Lookup(info.token);if(!owner)return;
    Check(!Current()&&owner->context->CurrentPhase()==Lifecycle::Phase::entered&&owner->context->NativeThreadId()==GetCurrentThreadId()&&info.native_tid==GetCurrentThreadId()&&threads_.Self()==info.token,"prepared worker entered on wrong native owner");
    owner->native_tid=info.native_tid;owner->live=true;ActualBounds(*owner);
    owner->delivery=std::make_unique<SignalDelivery>(runtime_,Translated,kReturn,recomp::signal_frame::Bounds{owner->low,owner->high},signals_,owner->token);
    owner->binding=std::make_unique<recomp::PollBinding>(owner->requests,[this,owner](State&,recomp::PollSite,const auto&){Pump(*owner);},[this](const auto&context){return Admit(context);});Current()=owner.get();
  }
  void BeforeTls(const Pthreads::WorkerInfo&info){auto owner=Lookup(info.token);if(!owner)return;Check(Current()==owner.get()&&owner->native_tid==GetCurrentThreadId()&&!owner->phase&&!owner->depth&&!owner->stop_live&&!Pending(*owner),"worker reaches TLS with active/pending collector state");}
  void Retire(const Pthreads::WorkerInfo&info,Pthreads::WorkerRetirement reason){
    auto owner=Lookup(info.token);if(!owner)return;
    std::lock_guard lock(owner->sender_mutex);Check(!owner->phase&&!owner->depth&&!owner->stop_live,"worker retires in active collector phase");
    if(owner->binding){Check(Current()==owner.get()&&owner->native_tid==GetCurrentThreadId()&&!recomp::CurrentExecutionState()&&!Pending(*owner),"same-worker binding retirement is not quiescent");owner->binding.reset();owner->delivery.reset();Current()=nullptr;}
    else Check(reason==Pthreads::WorkerRetirement::cancelled,"unentered worker retirement is not cancellation");
    owner->live=false;std::lock_guard guard(mutex_);owners_.erase(info.token);
  }
  void Checkpoint(const Pthreads::WaitContext&context){auto owner=Lookup(context.token);if(owner){const auto retained=signals_.DispatchOneAdmittedSubset(context.token,SignalHost::Bit(30)|SignalHost::Bit(24),0,{});Check(!retained.error,"unknown eligible signal at unqualified Pthreads wait phase");}}
  void Notify(uint64_t token){auto owner=Lookup(token);Check(owner&&owner->live,"notify has no attached worker lifetime");if(SignalHost::NeedsPoll(owner->signal_thread))owner->requests.Request();}
  uint64_t FutexAdmission(uint64_t token)const noexcept{auto *owner=Current();return owner&&owner->token==token&&owner->live&&owner->phase&&owner->eligible&&owner->copied&&!owner->returned&&!owner->depth&&!OpaqueDepth()&&SignalHost::NeedsPoll(owner->signal_thread)?SignalHost::Bit(30):0;}
  template<class F>void WithSocketWait(const std::string&name,State&state,F&&invoke,const GameSocketWaitContext::SitePolicy&policy={}){
    auto owner=Lookup(threads_.Self());Check(owner&&Current()==owner.get()&&owner->native_tid==GetCurrentThreadId()&&!owner->phase&&!owner->depth&&!owner->socket_wait.load(),"socket import has no idle actual worker owner");
    auto use=owner->lifecycle->AcquireUse(owner->token);ActualBounds(*owner);
    GameSocketWaitContext socket(state,name,owner->token,owner->low,owner->high,owner->tls,false,policy);
    {std::lock_guard lock(owner->sender_mutex);owner->phase=true;owner->sleep_state=&state;owner->socket_wait=&socket;}
    struct Scope{Owner&owner;~Scope(){std::lock_guard lock(owner.sender_mutex);owner.socket_wait=nullptr;owner.phase=false;owner.sleep_state=nullptr;owner.provider_boundary=nullptr;}}scope{*owner};
    invoke();socket.Complete();
  }
  GameSocketWaitContext::Decision ObserveSocketWait(const GameSocketWaitContext::Observation&observation){
    auto*owner=Current();if(!owner||!owner->socket_wait.load())return{};auto*socket=owner->socket_wait.load();
    return socket->Observe(observation,[&]{
      Phase(*owner);const auto epoch=Read<uint64_t>(kEpoch);
      if(!SignalHost::NeedsPoll(owner->signal_thread)||owner->certified_epoch!=epoch||!owner->certified_new_epoch||owner->begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)return GameSocketWaitContext::Decision{};
      const auto record=Record(owner->token);Check(record&&record==owner->record,"socket sender-certified ordinary record changed");GameSocketWaitContext::PollCertificate certificate(*socket,record,epoch);
      owner->selected={};const SignalHost::Boundary boundary=[this](const auto&delivery){return Deliver(delivery);};owner->provider_boundary=&boundary;
      struct Scope{Owner&owner;~Scope(){owner.provider_boundary=nullptr;}}scope{*owner};
      if(SignalHost::NeedsPoll(owner->signal_thread))owner->requests.Request();
      try{if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(&socket->StateRef(),socket->StateRef().gpr.pc.qword,GameSocketWaitContext::kOrdinal,socket->StateRef().gpr.pc.qword);}
      catch(const Deferred&){return GameSocketWaitContext::Decision{};}
      return GameSocketWaitContext::Decision{owner->selected.handled,owner->selected.restart};
    });
  }
  static bool Shape(const State&state){return state.gpr.pc.qword==kSyscall&&state.gpr.x30.qword==0x708f2f14&&uint32_t(state.gpr.x0.qword)==98&&state.gpr.x2.dword==0x80&&state.gpr.x4.qword==state.gpr.sp.qword&&state.gpr.x4.qword!=0;}
  template<class F>void WithSyscall(State&state,F&&invoke){
    auto owner=Lookup(threads_.Self());Check(owner&&Current()==owner.get()&&owner->native_tid==GetCurrentThreadId()&&!owner->phase&&!owner->depth,"syscall owner/phase is invalid");
    if(!Shape(state)){invoke();return;}
    auto use=owner->lifecycle->AcquireUse(owner->token);owner->phase=true;owner->sleep_state=&state;owner->copied=false;owner->returned=false;owner->eligible=false;owner->deadline=0;
    struct Scope{Owner&owner;~Scope(){owner.phase=false;owner.sleep_state=nullptr;owner.provider_boundary=nullptr;owner.copied=false;owner.returned=false;owner.eligible=false;owner.deadline=0;}}scope{*owner};
    invoke();Check(owner->returned,"timed futex omitted actual Return observation");
  }
  void ObserveFutex(const bunker::windows::SignalFutexes::WaitObservation&observation){
    auto *owner=Current();if(!owner||!owner->phase)return;
    Check(observation.timeout_pointer==owner->sleep_state->gpr.sp.qword,"futex observer changed original request identity");
    if(observation.phase==bunker::windows::SignalFutexes::WaitPhase::Copied){
      Check(!owner->copied&&!owner->returned,"duplicate futex copy observer");owner->copied=true;owner->observation=observation;owner->deadline=observation.deadline_nanoseconds;
      owner->eligible=observation.copied&&observation.deadline_valid&&observation.seconds==4294967&&observation.nanoseconds==295000000&&observation.deadline_nanoseconds;
    }else{
      Check(!owner->returned,"duplicate futex Return observer");
      if(owner->copied){const auto&saved=owner->observation;Check(observation.copied==saved.copied&&observation.seconds==saved.seconds&&observation.nanoseconds==saved.nanoseconds&&observation.deadline_valid==saved.deadline_valid&&observation.deadline_nanoseconds==saved.deadline_nanoseconds,"futex Return did not preserve actual immutable snapshot/fixed deadline");}
      else Check(!observation.copied,"futex Return invented unobserved copied bytes");
      owner->returned=true;
    }
  }
  SignalHost::Dispatch DispatchFutex(uint64_t token,uint64_t allowed,const SignalHost::Boundary&boundary){
    auto owner=Lookup(token);Check(owner&&Current()==owner.get(),"dispatcher requires entered actual current owner");
    Check(allowed==0||allowed==SignalHost::Bit(30),"dispatcher admission is outside bounded worker profile");
    const auto known=SignalHost::Bit(30)|SignalHost::Bit(24);
    if(!allowed||!owner->phase||!owner->eligible)return signals_.DispatchOneAdmittedSubset(token,known,0,{});
    ActualBounds(*owner);Phase(*owner);Check(owner->copied&&!owner->returned&&owner->deadline,"dispatcher has no immutable timeout/fixed deadline witness");owner->selected={};owner->provider_boundary=&boundary;
    struct Scope{Owner&owner;~Scope(){owner.provider_boundary=nullptr;}}scope{*owner};
    if(SignalHost::NeedsPoll(owner->signal_thread))owner->requests.Request();
    try{if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(owner->sleep_state,owner->sleep_state->gpr.pc.qword,kOrdinal,owner->sleep_state->gpr.pc.qword);}
    catch(const Deferred&){return signals_.DispatchOneAdmittedSubset(token,known,0,{});}
    return owner->selected;
  }
  void Send(State&state,const std::function<void()>&invoke){
    auto owner=Lookup(state.gpr.x0.qword);Check(owner&&owner->live,"send target has no attached worker lifetime");std::lock_guard lock(owner->sender_mutex);Check(owner->live,"send raced worker retirement");
    const auto signal=state.gpr.x1.dword;Check(signal==30||signal==24,"only original stop/restart sends are supported");
    Check(state.gpr.x30.qword==(signal==30?0x825b2d1cULL:0x825b2f74ULL),"nonzero send is outside original caller");
    auto *active=recomp::CurrentExecutionState();Check(active==&state&&!OpaqueDepth(),"sender State/opaque scope differs");const auto frames=recomp::CurrentExecutionFrames(state);Check(frames.size()==1&&frames[0]==&state,"sender has enclosing Runtime roots");
    const auto epoch=Read<uint64_t>(kEpoch);Check(epoch&&!(epoch&1)&&Read<uint8_t>(0x879a62a8)==1&&threads_.Self()!=owner->token,"original sender epoch/registry lock/self differs");
    Check(signal==30?Read<uint64_t>(kStopped)==1:owner->stop_live&&owner->stop_epoch==epoch&&!Read<uint64_t>(kStopped),"original stop/restart phase differs");
    ActualBounds(*owner);Dispositions();const auto record=Record(owner->token);Check(record&&(signal==30?state.gpr.x26.qword:state.gpr.x27.qword)==record,"actual original sender traversal record differs");OrdinaryRecord(*owner,record);owner->record=record;
    if(signal==30){owner->certified_new_epoch=(Read<uint64_t>(record+0x10)&~uint64_t(1))!=epoch;owner->certified_epoch=epoch;}
    std::fprintf(stderr,"Game GC Unity worker: original send signal=%u target=%#llx record=%#llx epoch=%llu ordinary_stack_high=%#llx LR=%#llx; before real pthread_kill\n",signal,(unsigned long long)owner->token,(unsigned long long)record,(unsigned long long)epoch,(unsigned long long)owner->high.load(),(unsigned long long)state.gpr.x30.qword);
    invoke();
  }
  std::optional<uint64_t> Deliver(const SignalHost::Delivery&delivery){
    auto *owner=Current();Check(owner&&owner->live&&delivery.token==owner->token&&owner->native_tid==GetCurrentThreadId(),"delivery is on wrong worker owner");Dispositions();const auto record=owner->record.load();Check(record!=0,"delivery has no sender-certified ordinary record");OrdinaryRecord(*owner,record);
    if(!owner->depth){
      Check(delivery.signal==30&&owner->provider_boundary,"outer delivery is not controlled stop30");Phase(*owner,&delivery);const auto epoch=Read<uint64_t>(kEpoch);const bool duplicate=(Read<uint64_t>(record+0x10)&~uint64_t(1))==epoch;
      Check(epoch&&!(epoch&1)&&(duplicate||Read<uint64_t>(kStopped)==1),"original worker stopped epoch differs");
      owner->interrupted=*recomp::CurrentExecutionState();owner->frame_base=owner->interrupted.gpr.sp.qword-4704;owner->posts=0;owner->stop_epoch=epoch;owner->begun_epoch=epoch;owner->stop_live=!duplicate;owner->depth=1;
      auto result=owner->delivery->Deliver(delivery);Check(owner->posts==(duplicate?0u:2u),"original stop did not perform its own expected posts");if(!duplicate)Check(Read<uint64_t>(record+0x10)==(epoch|1),"original resumed record epoch was not observed");owner->depth=0;owner->stop_live=false;
      std::fprintf(stderr,"Game GC Unity worker: genuine stop returned token=%#llx epoch=%llu duplicate=%u actual_posts=%u; no collection/frame claim\n",(unsigned long long)owner->token,(unsigned long long)epoch,unsigned(duplicate),owner->posts);return result;
    }
    auto *state=recomp::CurrentExecutionState();Check(delivery.signal==24,"nested signal is not restart24");NestedSuspend(*owner,*state);owner->depth=2;auto result=owner->delivery->Deliver(delivery);owner->depth=1;return result;
  }
  void WithWait(const std::string&name,State&state,const std::function<void()>&invoke){auto *owner=Current();Check(owner&&owner->live,"wait has no worker lifetime");if(name=="sigsuspend"){NestedSuspend(*owner,state);invoke();return;}Check(!owner->depth,"unqualified provider inside active worker collector frame");invoke();}
  void BeforeNonlocal(){auto *owner=Current();Check(!owner||!owner->depth,"nonlocal transfer inside active worker collector frame");}
  void BeforePost(const State&state){
    auto *owner=Current();if(!owner||!owner->depth)return;
    Check(owner->depth==1&&owner->stop_live&&state.gpr.x0.qword==kAck&&state.gpr.x30.qword==(owner->posts?0x825b2c50ULL:0x825b2c04ULL)&&owner->posts<2,"original acknowledgment caller differs");
    if(auto*socket=owner->socket_wait.load()){socket->PhysicalRoots(owner->interrupted,owner->frame_base,owner->record.load());return;}
    const auto record=owner->record.load();OrdinaryRecord(*owner,record);const auto fp=Read<addr_t>(record+0x18);Check(fp==owner->frame_base-0x30,"actual original published ordinary FP differs");
    const addr_t saved=owner->frame_base+recomp::signal_frame::kMachineOffset+8;
    Check(fp<=saved&&saved+31*8<=owner->high,"physical GPR range is outside original ordinary scan bounds");
    for(unsigned i=0;i<31;++i){uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&owner->interrupted.gpr)+i*16+8,8);Check(Read<uint64_t>(saved+i*8)==value,"physical interrupted GPR differs");}
    const auto vectors_at=owner->frame_base+recomp::signal_frame::kFpsimdOffset+16;std::array<uint8_t,512>vectors{};Check(fp<=vectors_at&&vectors_at+vectors.size()<=owner->high,"physical Q range is outside original ordinary scan bounds");recomp::ReadGuestMemory(vectors.data(),vectors_at,vectors.size());Check(!std::memcmp(vectors.data(),&owner->interrupted.simd,vectors.size()),"physical interrupted Q registers differ");
    std::fprintf(stderr,"Game GC Unity worker: physical ordinary roots token=%#llx FP=%#llx ordinary_scan_high=%#llx actual_stack_high=%#llx GPR=31 Q=32; before original sem_post\n",(unsigned long long)owner->token,(unsigned long long)fp,(unsigned long long)Read<addr_t>(record+0x28),(unsigned long long)owner->high.load());
  }
  void AfterPost(const State&state){auto *owner=Current();if(!owner||!owner->depth)return;Check(!state.gpr.x0.dword,"original acknowledgment post failed");++owner->posts;}
  void Close(){std::lock_guard lock(mutex_);Check(owners_.empty(),"worker collector closed before real retirement");closed_=true;}
};
