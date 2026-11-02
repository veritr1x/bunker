#pragma once
// Included inside the harness's anonymous namespace after Require/Read helpers.
using bunker::windows::NonlocalJumps;
using bunker::windows::Pthreads;
using bunker::windows::SignalHost;
using bunker::windows::AndroidThreadAttr;
constexpr addr_t kObserveSave=0x7ffc50000000ULL;
uint64_t SaveX(const State &s,unsigned n){static_assert(offsetof(GPR,x0)==8&&offsetof(GPR,x30)==488);uint64_t v;std::memcpy(&v,reinterpret_cast<const uint8_t*>(&s.gpr)+n*16+8,8);return v;}
uint64_t SaveD(const State &s,unsigned n){uint64_t v;std::memcpy(&v,&s.simd.v[n],8);return v;}
struct SaveAudit {
 Pthreads *threads=nullptr;SignalHost *signals=nullptr;NonlocalJumps *jumps=nullptr;recomp::Entry original=nullptr;
 uint64_t token=0,generation=0,mask=0;addr_t callback=0,opaque=0,environment=0;
 bool active=false,owner_live=false;size_t entered=0,saved=0,observed=0,revoked=0;
 State entry{},save{};uint64_t adjacent=0,zero_slot=0;
 NonlocalJumps::Thread Current(){
  auto current=threads->Self();AndroidThreadAttr attr{};
  Require(current==token&&!threads->GetAttr(current,&attr)&&attr.stack_base&&attr.stack_size&&attr.stack_size<=UINT64_MAX-attr.stack_base,"save audit has no real owned thread stack");
  return {current,current,attr.stack_base,attr.stack_base+attr.stack_size};
 }
 std::optional<NonlocalJumps::Region> Environment(addr_t address,size_t size){
  if(active&&owner_live&&environment&&address==environment&&size==256)return NonlocalJumps::Region{environment,environment+256,generation};
  return {};
 }
 uint64_t Mask(){uint64_t value=0;Require(!signals->Mask(token,0,nullptr,&value),"cannot query actual target signal mask");return value;}
 void Saved(State &s,recomp::Runtime &bridges,addr_t marker){
  Require(active&&!owner_live&&saved++==0,"setjmp outside unique original helper invocation");
  const auto sp=s.gpr.sp.qword,env=s.gpr.x0.qword;auto t=Current();
  Require(entry.gpr.sp.qword>=0x140&&sp==entry.gpr.sp.qword-0x140&&env==sp+8&&sp>=t.stack_low&&entry.gpr.sp.qword<=t.stack_high,"original automatic frame/environment differs");
  Require(SaveX(s,19)==callback&&SaveX(s,20)==env&&SaveX(s,29)==sp+0x130&&SaveX(s,30)==0x825b0580,"original helper save point register flow differs");
  std::array<uint8_t,256> before{};recomp::ReadGuestMemory(before.data(),env,before.size());for(auto v:before)Require(v==0,"original memset did not clear full environment");
  adjacent=Read<uint64_t>(sp);zero_slot=Read<uint64_t>(sp+0x108);Require(!zero_slot,"original callback second-argument slot is not zero");
  environment=env;owner_live=true;save=s;bridges.Dispatch(s,marker,nullptr);
  Require(!s.gpr.x0.qword,"actual setjmp did not return zero normally");
  Require(s.fpcr.flat==save.fpcr.flat&&s.fpsr.flat==save.fpsr.flat&&s.nzcv.flat==save.nzcv.flat&&!std::memcmp(&s.sr,&save.sr,sizeof(SR)),"setjmp bridge changed current FP/system state");
  Require(Read<uint64_t>(sp)==adjacent&&Read<uint64_t>(sp+0x108)==zero_slot,"save bridge touched adjacent original frame bytes");
  for(size_t i=200;i<256;++i)Require(Read<uint8_t>(env+i)==0,"save bridge touched original reserved tail");
 }
 void Observe(State &s){
  Require(active&&owner_live&&saved==1&&observed++==0&&s.gpr.x0.qword==opaque&&!s.gpr.x1.qword,"actual translated callback arguments/order differ");
  auto t=Current();Require(s.gpr.sp.qword>=t.stack_low&&s.gpr.sp.qword<=save.gpr.sp.qword,"callback is not below the live save frame on its owned stack");
  const auto sp=save.gpr.sp.qword;
  Require(Read<uint64_t>(sp+0x110)==SaveX(entry,28)&&Read<uint64_t>(sp+0x120)==SaveX(entry,20)&&Read<uint64_t>(sp+0x128)==SaveX(entry,19)&&Read<uint64_t>(sp+0x130)==SaveX(entry,29)&&Read<uint64_t>(sp+0x138)==SaveX(entry,30),"original high-frame callee-save spills differ from entry State");
  Require(Read<uint64_t>(sp+0x118)==opaque&&Read<uint64_t>(sp+0x108)==0,"original callback reload slots differ");
  auto plan=jumps->Inspect(s,environment,1);
  Require(plan.thread==token&&plan.environment_generation==generation&&plan.environment==environment&&plan.pc==0x825b0580&&plan.sp==sp&&plan.mask&&*plan.mask==mask&&Mask()==mask,"actual saved wire context/thread/mask differs");
  for(unsigned n=19;n<=30;++n)Require(plan.x19_x30[n-19]==SaveX(save,n),"actual wire GPR differs from captured save State");
  for(unsigned n=8;n<=15;++n)Require(plan.d8_d15[n-8]==SaveD(save,n),"actual wire lower D register differs");
  Require(plan.scs_low==(SaveX(save,18)&8191),"actual reserved platform register low bits differ");
  Require(Read<uint64_t>(environment)&1,"actual setjmp wire did not record mask-save mode");
  std::fprintf(stderr,"IL2CPP save callback observed: actual env=%#llx frameSP=%#llx callbackSP=%#llx generation=%llu mask=%#llx; original spills/wire/lowerD8..15 checked live\n",(unsigned long long)environment,(unsigned long long)sp,(unsigned long long)s.gpr.sp.qword,(unsigned long long)generation,(unsigned long long)mask);
 }
};
SaveAudit *save_audit=nullptr;
Memory *OriginalSaveHelper(State &s,addr_t pc,Memory *m){try{
 auto &a=*save_audit;Require(!a.active&&!a.owner_live&&a.entered++==0&&s.gpr.x0.qword==a.callback&&s.gpr.x1.qword==a.opaque,"original save helper entry ownership differs");
 a.active=true;++a.generation;a.entry=s;auto result=a.original(s,pc,m);
 Require(a.saved==1&&a.observed==1&&a.owner_live&&Read<addr_t>(0x87cb1e60)==a.environment,"original save/callback/trailing global sequence differs");
 Require(s.gpr.sp.qword==a.entry.gpr.sp.qword&&s.gpr.pc.qword==SaveX(a.entry,30),"original helper did not return to real NDK caller with exact SP");
 for(unsigned n=19;n<=30;++n)Require(SaveX(s,n)==SaveX(a.entry,n),"original helper callee-saved GPR restoration differs");
 for(unsigned n=8;n<=15;++n)Require(SaveD(s,n)==SaveD(a.entry,n),"normal callback/helper did not preserve lower D ABI");
 // This ordering is essential: revoke the automatic object BEFORE returning
 // from this forwarding Entry to the suspended outer NDK caller.
 a.owner_live=false;a.jumps->Forget(a.environment);a.active=false;++a.revoked;
 bool gone=false;try{a.jumps->Inspect(s,a.environment,1);}catch(const std::runtime_error &e){gone=std::string(e.what())=="jmp_buf has no live save registration";}
 Require(gone,"expired automatic environment remains registered");
 std::fprintf(stderr,"IL2CPP save helper returned: env=%#llx registration revoked before outer caller resumes; original raw global retained, never dereferenced as root\n",(unsigned long long)a.environment);return result;
 }catch(const std::exception &e){std::fprintf(stderr,"IL2CPP original save-helper audit failure:%s\n",e.what());std::abort();}}
