#pragma once
#include "game_collector_mask.h"
// Included in the harness namespace after Read/Translated/Executable helpers.
// One explicitly attached external UnityMain lifetime. This does not create a
// Pthreads worker, finalizer role, guest GC record or collector acknowledgment.
class GameUnityMainCollector {
  using Pthreads=bunker::windows::Pthreads;
  using SignalHost=bunker::windows::SignalHost;
  using SignalDelivery=bunker::windows::SignalDelivery;
  struct Deferred {};
  struct Owner {
    uint64_t token=0,parent=0;DWORD native_tid=0;
    SignalHost::ThreadRef signal_thread;std::shared_ptr<bunker::windows::SignalWake> wake;
    recomp::PollRequest requests;std::unique_ptr<recomp::PollBinding> binding;
    std::unique_ptr<SignalDelivery> delivery;
    std::mutex sender_mutex;std::atomic<bool> live{true};
    std::atomic<addr_t> low{0},high{0},tls{0},record{0};
    std::atomic<uint64_t> certified_epoch{0},begun_epoch{0},stop_epoch{0};
    std::atomic<bool> certified_new_epoch{false},stop_live{false};
    State *sleep_state=nullptr;bool phase=false;
    const SignalHost::Boundary *provider_boundary=nullptr;
    SignalHost::Dispatch selected{};State interrupted{};addr_t frame_base=0;
    unsigned depth=0,posts=0;
  };
  Pthreads &threads_;SignalHost &signals_;bunker::windows::Semaphores &semaphores_;recomp::Runtime &runtime_;
  std::mutex mutex_;std::shared_ptr<Owner> owner_;bool closed_=false;
  static Owner *&Current(){static thread_local Owner *owner=nullptr;return owner;}
  static unsigned &OpaqueDepth(){static thread_local unsigned depth=0;return depth;}
  static constexpr uint64_t kOrdinal=UINT64_MAX-1;
  static constexpr addr_t kReturn=0x825aada0,kAck=0x87cb1e68,kEpoch=0x879a6b08,kStopped=0x879a6b10;
  static constexpr addr_t kMainRecord=0x879a7330,kMainStackHigh=0x879a6ac0,kNanoSleep=0x7ff600300008ULL;
  static void Check(bool okay,const char*why){if(!okay)throw std::runtime_error(std::string("external UnityMain collector: ")+why);}
  std::shared_ptr<Owner> Lookup(uint64_t token){std::lock_guard lock(mutex_);return owner_&&owner_->token==token?owner_:nullptr;}
  bool Pending(const Owner&owner){uint64_t blocked=0;Check(!signals_.Pending(owner.token,&blocked),"signal lifetime is absent");return blocked||SignalHost::NeedsPoll(owner.signal_thread);}
  void ActualBounds(Owner&owner){
    bunker::windows::AndroidThreadAttr attr{};
    Check(!threads_.GetAttr(owner.token,&attr)&&attr.stack_base&&attr.stack_size&&attr.stack_size<=UINT64_MAX-attr.stack_base,"actual external Pthreads stack is unavailable");
    const auto high=attr.stack_base+attr.stack_size;Check(!((attr.stack_base|high)&15),"actual stack alignment differs");
    auto low=owner.low.load();if(!low){owner.high=high;owner.low=attr.stack_base;}else Check(low==attr.stack_base&&owner.high==high,"actual external stack lifetime changed");
  }
  addr_t Record(uint64_t token){
    Check(Read<uint32_t>(0x879a62a0)==1,"original registry is not initialized");
    uint32_t hash=uint32_t(token>>8)^uint32_t(token);hash^=hash>>16;
    addr_t cursor=Read<addr_t>(0x879a6b28+(hash&255)*8);std::array<addr_t,256>seen{};size_t count=0;
    while(cursor){Check(!(cursor&7)&&cursor<=UINT64_MAX-0x60&&count<seen.size(),"original registry chain shape differs");for(size_t i=0;i<count;++i)Check(seen[i]!=cursor,"original registry chain cycles");seen[count++]=cursor;if(Read<uint64_t>(cursor+8)==token)return cursor;cursor=Read<addr_t>(cursor);}
    return 0;
  }
  void MainRecord(Owner&owner,addr_t record){
    Check(record==kMainRecord&&Read<uint64_t>(record+8)==owner.token,"original static main record/token differs");
    Check(Read<uint32_t>(record+0x20)==6,"original main flags differ from flag4 scanner profile");
    // The original flag4 scanner selects this global, not record+28. Reject
    // unqualified special segments rather than inventing/patching their bounds.
    Check(Read<addr_t>(kMainStackHigh)==owner.high&&Read<addr_t>(record+0x30)==0&&Read<addr_t>(record+0x38)==0&&Read<addr_t>(record+0x50)==0,"original main scan bound/segment/sections differs from actual external stack");
  }
  void Dispositions(){
    Check(Read<int32_t>(0x87984e14)==30&&Read<int32_t>(0x87984e18)==24&&Read<int32_t>(0x87984e10)==1,"original configured signals/retry differ");
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(9)|SignalHost::Bit(19));
    for(int signal:{30,24}){bunker::windows::AndroidSignalAction action{};Check(!signals_.Action(signal,nullptr,&action)&&action.handler==0x825beb3c&&action.flags==uint32_t(signal==30?0x10000004:0x10000000)&&action.mask==mask,"original disposition/thunk/mask differs");}
    Check(Read<addr_t>(0x879a7788)==0x825b2af4&&Read<addr_t>(0x879a7758)==0x825b2c70,"original handler table differs");
    int32_t count=0;Check(!semaphores_.GetValue(kAck,&count),"original acknowledgment semaphore is unavailable");
  }
  void Phase(Owner&owner,const SignalHost::Delivery *selected=nullptr){
    auto *state=recomp::CurrentExecutionState();Check(owner.live&&Current()==&owner&&owner.native_tid==GetCurrentThreadId()&&threads_.Self()==owner.token,"phase is not on attached actual external thread");
    Check(owner.phase&&owner.sleep_state&&state==owner.sleep_state&&!OpaqueDepth(),"phase has no exact live NanoSleep State");
    const auto frames=recomp::CurrentExecutionFrames(*state);Check(frames.size()==1&&frames[0]==state,"phase has enclosing Runtime roots");
    Check(state->gpr.pc.qword==kNanoSleep&&state->gpr.x30.qword==0x70383878&&state->gpr.x0.qword==state->gpr.sp.qword&&!state->gpr.x1.qword,"phase is not original null-rem helper NanoSleep");
    const auto sp=state->gpr.sp.qword;Check(!(sp&15)&&sp>=owner.low&&sp<=owner.high&&sp-owner.low>=9504&&owner.high-sp>=32,"actual normal stack lacks helper/two-frame bounds");
    Check(owner.tls&&state->sr.tpidr_el0.qword==owner.tls,"materialized external TLS identity changed");
    const auto stack=signals_.AlternateStack(owner.token).configured;Check(stack.flags==2&&!stack.pointer&&!stack.size,"alternate stack is not fresh disabled");
    uint64_t mask=0;Check(!signals_.Mask(owner.token,0,nullptr,&mask),"actual signal mask query failed");
    Check(selected?GameCollectorWaitMask::SelectedStop(owner.token,mask,*selected):GameCollectorWaitMask::Ordinary(mask),"ordinary/selected original stop masks differ");
  }
  bool Admit(const recomp::PollAdmissionContext&context)const noexcept{
    const auto *owner=Current();return owner&&owner->live&&owner->phase&&owner->provider_boundary&&!OpaqueDepth()&&context.site.ordinal==kOrdinal&&context.frames.size()==1&&context.frames[0]==&context.state&&owner->sleep_state==&context.state&&context.program_counter==context.state.gpr.pc.qword&&context.site.trace==context.state.gpr.pc.qword;
  }
  void Pump(Owner&owner){
    Phase(owner);Check(owner.provider_boundary,"controlled site has no real NanoSleep boundary");
    const auto epoch=Read<uint64_t>(kEpoch);
    if(owner.certified_epoch!=epoch||!owner.certified_new_epoch||owner.begun_epoch==epoch||Read<uint64_t>(kStopped)!=1||Read<uint8_t>(0x879a62a8)!=1)throw Deferred{};
    const auto record=Record(owner.token);Check(record&&record==owner.record,"certified original main record changed");MainRecord(owner,record);Dispositions();
    owner.selected=signals_.DispatchOneAdmittedSubset(owner.token,SignalHost::Bit(30)|SignalHost::Bit(24),SignalHost::Bit(30),*owner.provider_boundary);
    Check(!owner.selected.error,"unknown eligible signal or invalid controlled subset selection");
  }
  void NestedSuspend(Owner&owner,State&state){
    const auto frames=recomp::CurrentExecutionFrames(state);const auto record=owner.record.load();
    Check(Current()==&owner&&owner.depth==1&&owner.stop_live&&owner.posts==1&&frames.size()==2&&frames[0]==&state&&frames[1]==owner.sleep_state&&state.gpr.x30.qword==0x825b2c24&&state.gpr.x0.qword==0x879a6b18&&state.gpr.sp.qword==owner.frame_base-0x60&&state.gpr.x29.qword==owner.frame_base-0x30,"nested sigsuspend is outside exact original main stop");
    Check(record&&Read<addr_t>(record+0x18)==state.gpr.x29.qword&&Read<uint64_t>(record+0x10)==owner.stop_epoch&&owner.stop_epoch==Read<uint64_t>(kEpoch),"original published main FP/epoch differs");
    const auto mask=~(SignalHost::Bit(2)|SignalHost::Bit(3)|SignalHost::Bit(6)|SignalHost::Bit(15)|SignalHost::Bit(24));Check(Read<uint64_t>(0x879a6b18)==mask,"original temporary mask differs");Dispositions();
  }
 public:
  struct Opaque{bool active;explicit Opaque(bool enabled):active(enabled){if(active)++OpaqueDepth();}~Opaque(){if(active)--OpaqueDepth();}};
  GameUnityMainCollector(Pthreads&threads,SignalHost&signals,bunker::windows::Semaphores&sem,recomp::Runtime&runtime):threads_(threads),signals_(signals),semaphores_(sem),runtime_(runtime){Check(Translated(kReturn)&&Executable(kReturn)&&Translated(0x825beb3c)&&Translated(0x825b2af4)&&Translated(0x825b2c70),"genuine original signal heads are unavailable");}
  ~GameUnityMainCollector(){if(!closed_||owner_)std::terminate();}
  bool Owns(uint64_t token){auto owner=Lookup(token);return owner&&owner->live;}
  void AttachCurrent(uint64_t token,uint64_t parent){
    Check(token&&parent&&token!=parent&&threads_.Self()==token&&Current()==nullptr,"external attachment requires actual distinct current token");
    Check(!signals_.DispatchOneAllowed(token,0,{}).error&&signals_.Lookup(parent),"external SignalHost registration/binding is absent");
    auto owner=std::make_shared<Owner>();owner->token=token;owner->parent=parent;owner->native_tid=GetCurrentThreadId();owner->signal_thread=signals_.Lookup(token);owner->wake=signals_.Wake(token);Check(owner->signal_thread&&owner->wake,"actual external signal lifetime is absent");
    {std::lock_guard lock(mutex_);Check(!closed_&&!owner_,"external attachment is duplicate or closed");owner_=owner;}
    try{owner->binding=std::make_unique<recomp::PollBinding>(owner->requests,[this,owner](State&,recomp::PollSite,const auto&){Pump(*owner);},[this](const auto&context){return Admit(context);});Current()=owner.get();}
    catch(...){std::lock_guard lock(mutex_);owner_.reset();throw;}
  }
  void Notify(uint64_t token){auto owner=Lookup(token);Check(owner&&owner->live,"notify has no attached external lifetime");if(SignalHost::NeedsPoll(owner->signal_thread))owner->requests.Request();}
  uint64_t NanoSleepAdmission(uint64_t token)const noexcept{auto *owner=Current();return owner&&owner->token==token&&owner->live&&owner->phase&&!owner->depth&&!OpaqueDepth()?SignalHost::Bit(30):0;}
  template<class F>void WithNanoSleep(State&state,F&&invoke){
    auto owner=Lookup(threads_.Self());Check(owner&&Current()==owner.get()&&owner->native_tid==GetCurrentThreadId()&&!owner->phase&&!owner->depth,"NanoSleep owner/phase is invalid");
    ActualBounds(*owner);const auto tls=state.sr.tpidr_el0.qword;Check(tls!=0,"materialized external Pthreads TLS is absent");if(!owner->tls)owner->tls=tls;
    owner->phase=true;owner->sleep_state=&state;
    struct Scope{Owner&owner;~Scope(){owner.phase=false;owner.sleep_state=nullptr;owner.provider_boundary=nullptr;}}scope{*owner};
    Phase(*owner);
    if(!owner->delivery)owner->delivery=std::make_unique<SignalDelivery>(runtime_,Translated,kReturn,recomp::signal_frame::Bounds{owner->low,owner->high},signals_,owner->token);
    invoke(); // A late pending signal is intentionally retained at phase exit.
  }
  SignalHost::Dispatch DispatchNanoSleep(uint64_t token,uint64_t allowed,const SignalHost::Boundary&boundary){
    auto owner=Lookup(token);Check(owner&&Current()==owner.get(),"dispatcher requires attached actual current owner");
    Check(allowed==0||allowed==SignalHost::Bit(30),"dispatcher admission is outside bounded main profile");
    const auto known=SignalHost::Bit(30)|SignalHost::Bit(24);
    if(!allowed||!owner->phase)return signals_.DispatchOneAdmittedSubset(token,known,0,{});
    Phase(*owner);owner->selected={};owner->provider_boundary=&boundary;
    struct Scope{Owner&owner;~Scope(){owner.provider_boundary=nullptr;}}scope{*owner};
    if(SignalHost::NeedsPoll(owner->signal_thread))owner->requests.Request();
    try{if(__bunker_guest_poll_requested())__bunker_guest_poll_slow(owner->sleep_state,owner->sleep_state->gpr.pc.qword,kOrdinal,owner->sleep_state->gpr.pc.qword);}
    catch(const Deferred&){return signals_.DispatchOneAdmittedSubset(token,known,0,{});}
    return owner->selected;
  }
  void Send(State&state,const std::function<void()>&invoke){
    auto owner=Lookup(state.gpr.x0.qword);Check(owner&&owner->live,"send target has no attached external lifetime");std::lock_guard lock(owner->sender_mutex);Check(owner->live,"send raced external retirement");
    const auto signal=state.gpr.x1.dword;Check(signal==30||signal==24,"only original stop/restart sends are supported");
    Check(state.gpr.x30.qword==(signal==30?0x825b2d1cULL:0x825b2f74ULL),"nonzero send is outside original caller");
    auto *active=recomp::CurrentExecutionState();Check(active==&state&&!OpaqueDepth(),"sender State/opaque scope differs");const auto frames=recomp::CurrentExecutionFrames(state);Check(frames.size()==1&&frames[0]==&state,"sender has enclosing Runtime roots");
    const auto epoch=Read<uint64_t>(kEpoch);Check(epoch&&!(epoch&1)&&Read<uint8_t>(0x879a62a8)==1&&threads_.Self()!=owner->token,"original sender epoch/registry lock/self differs");
    Check(signal==30?Read<uint64_t>(kStopped)==1:owner->stop_live&&owner->stop_epoch==epoch&&!Read<uint64_t>(kStopped),"original stop/restart phase differs");
    ActualBounds(*owner);Dispositions();const auto record=Record(owner->token);Check(record&&(signal==30?state.gpr.x26.qword:state.gpr.x27.qword)==record,"actual original sender traversal record differs");MainRecord(*owner,record);owner->record=record;
    if(signal==30){owner->certified_new_epoch=(Read<uint64_t>(record+0x10)&~uint64_t(1))!=epoch;owner->certified_epoch=epoch;}
    std::fprintf(stderr,"Game GC external main: original send signal=%u target=%#llx record=%#llx epoch=%llu main_stack_high=%#llx LR=%#llx; before real pthread_kill\n",signal,(unsigned long long)owner->token,(unsigned long long)record,(unsigned long long)epoch,(unsigned long long)owner->high.load(),(unsigned long long)state.gpr.x30.qword);
    invoke();
  }
  std::optional<uint64_t> Deliver(const SignalHost::Delivery&delivery){
    auto *owner=Current();Check(owner&&owner->live&&delivery.token==owner->token&&owner->native_tid==GetCurrentThreadId(),"delivery is on wrong external owner");Dispositions();const auto record=owner->record.load();Check(record!=0,"delivery has no sender-certified main record");MainRecord(*owner,record);
    if(!owner->depth){
      Check(delivery.signal==30&&owner->provider_boundary,"outer delivery is not controlled stop30");Phase(*owner,&delivery);const auto epoch=Read<uint64_t>(kEpoch);const bool duplicate=(Read<uint64_t>(record+0x10)&~uint64_t(1))==epoch;
      Check(epoch&&!(epoch&1)&&(duplicate||Read<uint64_t>(kStopped)==1),"original main stopped epoch differs");
      owner->interrupted=*recomp::CurrentExecutionState();owner->frame_base=owner->interrupted.gpr.sp.qword-4704;owner->posts=0;owner->stop_epoch=epoch;owner->begun_epoch=epoch;owner->stop_live=!duplicate;owner->depth=1;
      auto result=owner->delivery->Deliver(delivery);Check(owner->posts==(duplicate?0u:2u),"original stop did not perform its own expected posts");if(!duplicate)Check(Read<uint64_t>(record+0x10)==(epoch|1),"original resumed record epoch was not observed");owner->depth=0;owner->stop_live=false;
      std::fprintf(stderr,"Game GC external main: genuine stop returned token=%#llx epoch=%llu duplicate=%u actual_posts=%u; no collection/frame claim\n",(unsigned long long)owner->token,(unsigned long long)epoch,unsigned(duplicate),owner->posts);return result;
    }
    auto *state=recomp::CurrentExecutionState();Check(delivery.signal==24,"nested signal is not restart24");NestedSuspend(*owner,*state);owner->depth=2;auto result=owner->delivery->Deliver(delivery);owner->depth=1;return result;
  }
  void WithWait(const std::string&name,State&state,const std::function<void()>&invoke){auto *owner=Current();Check(owner&&owner->live,"wait has no external lifetime");if(name=="sigsuspend"){NestedSuspend(*owner,state);invoke();return;}Check(!owner->depth,"unqualified provider inside active external collector frame");invoke();}
  void BeforeNonlocal(){auto *owner=Current();Check(!owner||!owner->depth,"nonlocal transfer inside active external collector frame");}
  void BeforePost(const State&state){
    auto *owner=Current();if(!owner||!owner->depth)return;
    Check(owner->depth==1&&owner->stop_live&&state.gpr.x0.qword==kAck&&state.gpr.x30.qword==(owner->posts?0x825b2c50ULL:0x825b2c04ULL)&&owner->posts<2,"original acknowledgment caller differs");
    const auto record=owner->record.load();MainRecord(*owner,record);const auto fp=Read<addr_t>(record+0x18);Check(fp==owner->frame_base-0x30,"actual original published main FP differs");
    const addr_t saved=owner->frame_base+recomp::signal_frame::kMachineOffset+8;
    Check(fp<=saved&&saved+31*8<=owner->high,"physical GPR range is outside original main scan bounds");
    for(unsigned i=0;i<31;++i){uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&owner->interrupted.gpr)+i*16+8,8);Check(Read<uint64_t>(saved+i*8)==value,"physical interrupted GPR differs");}
    const auto vectors_at=owner->frame_base+recomp::signal_frame::kFpsimdOffset+16;std::array<uint8_t,512>vectors{};Check(fp<=vectors_at&&vectors_at+vectors.size()<=owner->high,"physical Q range is outside original main scan bounds");recomp::ReadGuestMemory(vectors.data(),vectors_at,vectors.size());Check(!std::memcmp(vectors.data(),&owner->interrupted.simd,vectors.size()),"physical interrupted Q registers differ");
    std::fprintf(stderr,"Game GC external main: physical main roots token=%#llx FP=%#llx global_scan_high=%#llx actual_stack_high=%#llx GPR=31 Q=32; before original sem_post\n",(unsigned long long)owner->token,(unsigned long long)fp,(unsigned long long)Read<addr_t>(kMainStackHigh),(unsigned long long)owner->high.load());
  }
  void AfterPost(const State&state){auto *owner=Current();if(!owner||!owner->depth)return;Check(!state.gpr.x0.dword,"original acknowledgment post failed");++owner->posts;}
  void DetachCurrent(){
    auto *current=Current();Check(current&&current->native_tid==GetCurrentThreadId()&&threads_.Self()==current->token&&!recomp::CurrentExecutionState(),"external detach is not quiescent same-worker");auto owner=Lookup(current->token);std::lock_guard lock(owner->sender_mutex);Check(!owner->phase&&!owner->depth&&!owner->stop_live&&!Pending(*owner),"external detach has active/pending collector state");owner->live=false;owner->binding.reset();owner->delivery.reset();Current()=nullptr;std::lock_guard guard(mutex_);owner_.reset();
  }
  void Close(){std::lock_guard lock(mutex_);Check(!owner_,"external collector closed before real detach");closed_=true;}
};
