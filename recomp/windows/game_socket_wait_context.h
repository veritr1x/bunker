#pragma once
// Included inside the harness namespace. This is a distinct socket provider
// phase; it never constructs a pthread condition/futex/nanosleep observation.
class GameSocketWaitContext {
 public:
  enum class Operation {Read,Write,Connect,Accept,Poll,Select,PipeRead,PipeWrite};
  enum class Phase {Copied,BeforeNativeWait,AfterNativeWait,Returned};
  struct Observation {
    State *state;int32_t descriptor;Operation operation;Phase phase;
    const void *request_identity;std::shared_ptr<const void> retained_request;
    bool finite;int64_t deadline_nanoseconds;
  };
  struct Decision {bool handled=false,restart=false;};
  using SitePolicy=std::function<bool(const std::string&,const State&)>;
  static constexpr uint64_t kOrdinal=UINT64_MAX-3;
  struct NativeEnvironment {
    int error=errno;DWORD last_error=GetLastError();fenv_t environment{};
    NativeEnvironment(){std::fegetenv(&environment);}
    ~NativeEnvironment(){std::fesetenv(&environment);errno=error;SetLastError(last_error);}
  };
 private:
  State &state_;std::string name_;uint64_t token_;DWORD native_tid_;
  addr_t low_,high_,tls_,pc_,lr_;bool main_,eligible_=false,copied_=false,returned_=false,waiting_=false,checkpoint_=false,before_interrupted_=false,certified_=false;
  int32_t descriptor_=0;Operation operation_{};const void *identity_=nullptr;
  std::shared_ptr<const void> retained_;bool finite_=false;int64_t deadline_=0;
  static void Check(bool value,const char *why){if(!value)throw std::runtime_error(std::string("socket collector phase: ")+why);}
  static bool OneOf(addr_t value,std::initializer_list<addr_t> values){return std::find(values.begin(),values.end(),value)!=values.end();}
  bool OperationMatches(Operation operation)const{
    if(name_=="read")return operation==Operation::Read||operation==Operation::PipeRead;
    if(name_=="write")return operation==Operation::Write||operation==Operation::PipeWrite;
    if(name_=="recv"||name_=="recvfrom"||name_=="recvmsg")return operation==Operation::Read;
    if(name_=="send"||name_=="sendto"||name_=="sendmsg")return operation==Operation::Write;
    if(name_=="connect")return operation==Operation::Connect;
    if(name_=="accept")return operation==Operation::Accept;
    if(name_=="poll")return operation==Operation::Poll;
    if(name_=="select")return operation==Operation::Select;
    return false;
  }
 public:
  // Exact direct original Unity client/file callsites from the pinned boundary
  // inventory. Other libraries/indirect callsites remain outside this profile.
  static bool OriginalSite(const std::string&name,const State&state){
    const auto lr=state.gpr.x30.qword;
    if(name=="poll")return OneOf(lr,{0x70b57ae8,0x70b57c4c,0x70b57cbc,0x70b57e48,0x70b57eb8});
    if(name=="select")return OneOf(lr,{0x70b3b188,0x70b9c610});
    if(name=="connect")return OneOf(lr,{0x70b3b108,0x70b49cd8,0x70b9c4f0});
    if(name=="send")return OneOf(lr,{0x70b3b45c,0x70b9c774,0x70b9c7f8,0x70b9c8c0,0x70e19074});
    if(name=="sendto")return lr==0x70e1905c;
    if(name=="recv")return OneOf(lr,{0x70b3b504,0x70b3b5cc,0x70b4a0e8,0x70b9c664,0x70e19158,0x70e195f4});
    if(name=="read")return OneOf(lr,{0x7023675c,0x7036dba0,0x708f24ec,0x70955bcc,0x70a96c78,0x70b46e8c,0x70b46f0c,0x70b47178,0x70e17688});
    if(name=="write")return OneOf(lr,{0x7023690c,0x7040f0b8,0x70e17370});
    // accept callsites are server-side paths, not the reached connected-client
    // profile. A component may supply an explicit separately labelled policy.
    return false;
  }
  GameSocketWaitContext(State&state,std::string name,uint64_t token,addr_t low,addr_t high,addr_t tls,bool main,const SitePolicy&policy)
    :state_(state),name_(std::move(name)),token_(token),native_tid_(GetCurrentThreadId()),low_(low),high_(high),tls_(tls),pc_(state.gpr.pc.qword),lr_(state.gpr.x30.qword),main_(main){
    Check(token_&&low_&&high_>low_&&tls_,"actual owner bounds/TLS absent");
    eligible_=policy?policy(name_,state_):OriginalSite(name_,state_);
  }
  State&StateRef()const{return state_;}
  uint64_t Token()const{return token_;}
  bool CheckpointOpen()const noexcept{return checkpoint_&&copied_&&!returned_&&eligible_&&bool(retained_);}
  bool Admit(const recomp::PollAdmissionContext&c)const noexcept{
    return CheckpointOpen()&&certified_&&c.site.ordinal==kOrdinal&&c.frames.size()==1&&c.frames[0]==&c.state&&&c.state==&state_&&c.site.trace==pc_&&c.program_counter==pc_&&state_.gpr.pc.qword==pc_;
  }
  // The persistent owner creates this only after checking its genuine original
  // sender-certified epoch/world/registry-lock and retained matching record.
  // Record reads happen before the read-only PollBinding admission callback.
  struct PollCertificate {
    GameSocketWaitContext&context;
    PollCertificate(GameSocketWaitContext&c,addr_t record,uint64_t epoch):context(c){Check(!context.certified_&&epoch&&!(epoch&1),"invalid/nested original sender certificate");context.ValidateRecord(record);context.certified_=true;}
    ~PollCertificate(){context.certified_=false;}
  };
  void Validate(bunker::windows::Pthreads&threads,bunker::windows::SignalHost&signals,const bunker::windows::SignalHost::Delivery*selected=nullptr)const{
    Check(CheckpointOpen()&&GetCurrentThreadId()==native_tid_&&threads.Self()==token_&&recomp::CurrentExecutionState()==&state_,"checkpoint is not the actual copied waiting caller");
    const auto frames=recomp::CurrentExecutionFrames(state_);Check(frames.size()==1&&frames[0]==&state_,"unpublished parent Runtime roots");
    Check(state_.gpr.pc.qword==pc_&&state_.gpr.x30.qword==lr_&&state_.sr.tpidr_el0.qword==tls_,"import State/return/TLS identity changed");
    const auto sp=state_.gpr.sp.qword;Check(!(sp&15)&&!(low_&15)&&!(high_&15)&&sp>=low_&&sp<=high_&&sp-low_>=9504&&high_-sp>=32,"normal stack lacks two genuine signal frames");
    const auto alternate=signals.AlternateStack(token_);const auto&stack=alternate.configured;
    if(stack.flags==2)Check(!stack.pointer&&!stack.size&&!alternate.region,"disabled alternate stack is not canonical");
    else Check(stack.flags==0&&stack.pointer&&stack.size>=5120&&stack.size<=UINT64_MAX-stack.pointer&&alternate.region&&alternate.region->generation&&stack.pointer>=alternate.region->low&&stack.pointer<=alternate.region->high&&stack.size<=alternate.region->high-stack.pointer&&!bunker::windows::SignalHost::OnAlternateStack(stack,sp)&&(stack.pointer+stack.size<=low_||stack.pointer>=high_),"enabled alternate stack has no disjoint owned mapping");
    uint64_t mask=0;Check(!signals.Mask(token_,0,nullptr,&mask),"signal mask unavailable");
    Check(selected?GameCollectorWaitMask::SelectedStop(token_,mask,*selected):GameCollectorWaitMask::Ordinary(mask),"original selected/ordinary mask differs");
  }
  void ValidateRecord(addr_t record)const{
    Check(record&&Read<uint64_t>(record+8)==token_,"sender record does not name actual owner");
    Check(Read<uint32_t>(record+0x20)==uint32_t(main_?6:2),"original record flags outside ordinary/main profile");
    Check(main_?record==0x879a7330&&Read<addr_t>(0x879a6ac0)==high_:record!=0x879a7330&&Read<addr_t>(record+0x28)==high_,"original scanner high differs from actual owner stack");
    Check(!Read<addr_t>(record+0x30)&&!Read<addr_t>(record+0x38)&&!Read<addr_t>(record+0x50),"unqualified original special root sections");
    const auto fp=Read<addr_t>(record+0x18);Check(fp>=low_&&fp<=high_&&!(fp&7),"published original FP outside owned stack");
  }
  void PhysicalRoots(const State&interrupted,addr_t frame,addr_t record)const{
    ValidateRecord(record);const auto fp=Read<addr_t>(record+0x18);Check(fp==frame-0x30&&fp>=low_&&fp<high_,"published FP is not genuine handler frame");
    const auto saved=frame+recomp::signal_frame::kMachineOffset+8;Check(saved>=fp&&saved+31*8<=high_,"GPR roots outside original scan range");
    for(unsigned i=0;i<31;++i){uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&interrupted.gpr)+i*16+8,8);Check(Read<uint64_t>(saved+i*8)==value,"physical GPR root differs");}
    const auto vectors_at=frame+recomp::signal_frame::kFpsimdOffset+16;std::array<uint8_t,512>vectors{};Check(vectors_at>=fp&&vectors_at+vectors.size()<=high_,"Q roots outside original scan range");recomp::ReadGuestMemory(vectors.data(),vectors_at,vectors.size());Check(!std::memcmp(vectors.data(),&interrupted.simd,vectors.size()),"physical SIMD roots differ");
    std::fprintf(stderr,"Game GC socket wait: physical roots token=%#llx flags=%u FP=%#llx actual_high=%#llx GPR=31 Q=32; before original sem_post\n",(unsigned long long)token_,unsigned(main_?6:2),(unsigned long long)fp,(unsigned long long)high_);
  }
  template<class Dispatch>Decision Observe(const Observation&o,Dispatch&&dispatch){
    NativeEnvironment preserve;Check(o.state==&state_&&GetCurrentThreadId()==native_tid_&&recomp::CurrentExecutionState()==&state_,"provider observation has foreign State/thread");
    Check(o.request_identity&&o.retained_request&&o.request_identity==o.retained_request.get()&&OperationMatches(o.operation),"provider snapshot/resource identity or operation differs");
    if(o.phase==Phase::Copied){Check(!copied_&&!returned_,"duplicate Copied phase");copied_=true;descriptor_=o.descriptor;operation_=o.operation;identity_=o.request_identity;retained_=o.retained_request;finite_=o.finite;deadline_=o.deadline_nanoseconds;Check(finite_?deadline_>=0:deadline_==0,"fixed deadline convention differs");return{};}
    Check(copied_&&!returned_&&identity_==o.request_identity&&retained_.get()==o.retained_request.get()&&descriptor_==o.descriptor&&operation_==o.operation&&finite_==o.finite&&deadline_==o.deadline_nanoseconds,"provider replaced copied request or fixed deadline");
    // A Before callback can genuinely interrupt before the OS wait, or its
    // elapsed time can exhaust the fixed deadline. Returned closes that attempt
    // without inventing an AfterNativeWait observation for a wait not performed.
    if(o.phase==Phase::Returned){if(waiting_){const auto now=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();Check(before_interrupted_||(finite_&&now>=deadline_),"return omitted actual native wait completion");}waiting_=false;returned_=true;return{};}
    if(o.phase==Phase::BeforeNativeWait){Check(!waiting_,"nested native wait phase");waiting_=true;before_interrupted_=false;}
    else{Check(o.phase==Phase::AfterNativeWait&&waiting_,"native wait completion without start");waiting_=false;}
    if(!eligible_)return{};
    checkpoint_=true;struct Scope{bool&v;~Scope(){v=false;}}scope{checkpoint_};
    const auto result=dispatch();
    if(o.phase==Phase::BeforeNativeWait&&result.handled&&(!result.restart||operation_==Operation::Poll||operation_==Operation::Select))before_interrupted_=true;
    return result;
  }
  void Complete()const{Check(!copied_||returned_,"prepared socket wait omitted actual Returned phase");Check(!waiting_&&!checkpoint_,"socket import exits active wait checkpoint");}
};
