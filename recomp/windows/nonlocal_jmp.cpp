#include "nonlocal_jmp.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#else
#include <sys/random.h>
#include <cerrno>
#endif

namespace bunker::windows {
namespace {
constexpr const char *names[]={"setjmp","_setjmp","sigsetjmp","longjmp","_longjmp","siglongjmp"};
void Need(bool condition,const char *why){if(!condition)throw std::runtime_error(why);}
bool Within(addr_t low,addr_t high,addr_t address,size_t size){
  return low&&high>low&&address>=low&&address<=high&&size<=high-address;
}
uint64_t X(const State &s,unsigned n){
  static_assert(offsetof(GPR,x0)==8&&offsetof(GPR,x30)==488);
  uint64_t value;std::memcpy(&value,reinterpret_cast<const uint8_t*>(&s.gpr)+n*16+8,8);return value;
}
void X(State &s,unsigned n,uint64_t value){
  std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+n*16+8,&value,8);
}
uint64_t D(const State &s,unsigned n){uint64_t value;std::memcpy(&value,&s.simd.v[n],8);return value;}
uint64_t Checksum(const std::array<uint64_t,25>&w){uint64_t v=0;for(size_t i=0;i<24;++i)v^=w[i];return v;}
}
uint64_t NonlocalJumps::RandomCookie(){
  uint64_t value=0;
#ifdef _WIN32
  Need(BCryptGenRandom(nullptr,reinterpret_cast<PUCHAR>(&value),sizeof(value),BCRYPT_USE_SYSTEM_PREFERRED_RNG)==0,
       "cannot obtain setjmp process cookie");
#else
  size_t n=0;while(n<sizeof(value)){
    auto result=getrandom(reinterpret_cast<uint8_t*>(&value)+n,sizeof(value)-n,0);
    if(result<0&&errno==EINTR)continue;
    Need(result>0,"cannot obtain setjmp process cookie");n+=size_t(result);
  }
#endif
  return value&~uint64_t(1);
}
NonlocalJumps::NonlocalJumps(Current current,Environment environment,Mask mask,Executable executable,
                            uint64_t cookie,addr_t marker)
    :current_(std::move(current)),environment_(std::move(environment)),mask_(std::move(mask)),
     executable_(std::move(executable)),cookie_(cookie),marker_base_(marker){
  Need(current_&&environment_&&executable_,"nonlocal adapter requires thread, lifetime and code validators");
  Need(!(cookie_&1),"setjmp cookie low bit is reserved");
}
std::pair<NonlocalJumps::Thread,NonlocalJumps::Region> NonlocalJumps::Check(addr_t env,size_t size)const{
  auto t=current_();Need(t.token&&t.generation,"unregistered nonlocal-jump thread");
  Need(t.stack_low&&t.stack_high>t.stack_low,"unregistered guest stack");
  Need(env&&!(env&7),"null or misaligned jmp_buf");
  auto r=environment_(env,size);Need(r&&r->generation&&Within(r->low,r->high,env,size),"jmp_buf lifetime/range is not registered");
  return {t,*r};
}
void NonlocalJumps::Save(State &s,addr_t env,int flag,size_t size){
  Need(flag==0||flag==1,"Android 13 sigsetjmp accepts only signal flag zero or one");
  Need(size==kJmpBytes||size==kSigJmpBytes,"invalid Android jmp_buf declaration size");
  auto [t,r]=Check(env,size);
  Need(!(s.gpr.sp.qword&15)&&Within(t.stack_low,t.stack_high,s.gpr.sp.qword,0)&&
       s.gpr.sp.qword-t.stack_low>=32,"setjmp SP is outside the registered guest stack");
  Need(X(s,30)&&!(X(s,30)&3)&&executable_(X(s,30)),"setjmp return PC is not executable guest code");
  Need(!flag||bool(mask_),"setjmp requires a truthful target-thread signal mask source");
  // Do not touch the unsaved mask word or the ABI's reserved tail.
  std::array<uint64_t,25>w{};
  if(!flag)recomp::ReadGuestMemory(&w[1],env+8,8);
  else w[1]=mask_();
  w[0]=cookie_|uint64_t(flag);w[2]=X(s,30)^cookie_;w[3]=s.gpr.sp.qword^cookie_;
  for(unsigned n=20;n<=28;n+=2){unsigned at=4+(28-n);w[at]=X(s,n)^cookie_;w[at+1]=X(s,n+1)^cookie_;}
  w[14]=(X(s,18)&8191)^cookie_;w[15]=X(s,19)^cookie_;
  for(unsigned n=8;n<=14;n+=2){unsigned at=16+(14-n);w[at]=D(s,n);w[at+1]=D(s,n+1);}
  w[24]=Checksum(w);
  // All validation and callback work precedes publication; no host lock is
  // held across any owner callback or tracked guest-memory operation.
  {std::lock_guard<std::mutex> lock(mutex_);saved_[env]={t,r,size};}
  recomp::WriteGuestMemory(env,&w[0],8);
  if(flag)recomp::WriteGuestMemory(env+8,&w[1],8);
  recomp::WriteGuestMemory(env+16,&w[2],kWrittenBytes-16);
  s.gpr.x0.qword=0;
}
NonlocalJumps::Plan NonlocalJumps::Inspect(const State &s,addr_t env,int value){
  Saved record;{std::lock_guard<std::mutex> lock(mutex_);auto i=saved_.find(env);
    Need(i!=saved_.end(),"jmp_buf has no live save registration");record=i->second;}
  auto [t,r]=Check(env,record.size);
  Need(t.token==record.thread.token&&t.generation==record.thread.generation,"cross-thread or recycled-thread longjmp");
  Need(r.low==record.region.low&&r.high==record.region.high&&r.generation==record.region.generation,"jmp_buf allocation lifetime changed");
  Need(t.stack_low==record.thread.stack_low&&t.stack_high==record.thread.stack_high,"saved guest stack lifetime changed");
  std::array<uint64_t,25>w{};recomp::ReadGuestMemory(w.data(),env,sizeof(w));
  Need(w[24]==Checksum(w),"setjmp checksum mismatch");
  Need((w[0]&~uint64_t(1))==cookie_,"setjmp cookie mismatch");
  Plan p;p.thread=t.token;p.thread_generation=t.generation;p.environment_generation=r.generation;p.environment=env;
  p.pc=w[2]^cookie_;p.sp=w[3]^cookie_;p.scs_low=w[14]^cookie_;
  Need(p.scs_low<8192,"invalid saved shadow-stack low bits");
  Need(!(p.sp&15)&&Within(t.stack_low,t.stack_high,p.sp,0)&&p.sp-t.stack_low>=32,"invalid saved guest SP");
  Need(!(s.gpr.sp.qword&15)&&Within(t.stack_low,t.stack_high,s.gpr.sp.qword,0)&&s.gpr.sp.qword<=p.sp,
       "longjmp saved frame is below current SP or current stack is invalid");
  Need(p.pc&&!(p.pc&3)&&executable_(p.pc),"invalid saved guest continuation");
  p.x19_x30[0]=w[15]^cookie_;
  for(unsigned n=20;n<=28;n+=2){unsigned at=4+(28-n);p.x19_x30[n-19]=w[at]^cookie_;p.x19_x30[n-18]=w[at+1]^cookie_;}
  p.x19_x30[11]=p.pc;
  for(unsigned n=8;n<=14;n+=2){unsigned at=16+(14-n);p.d8_d15[n-8]=w[at];p.d8_d15[n-7]=w[at+1];}
  if(w[0]&1)p.mask=w[1];
  p.value=value?uint32_t(value):1;return p;
}
State NonlocalJumps::Materialize(const State &current,const Plan&p){
  State s=current;for(unsigned n=19;n<=30;++n)X(s,n,p.x19_x30[n-19]);
  X(s,18,(X(s,18)&~uint64_t(8191))|p.scs_low);
  for(unsigned n=8;n<=15;++n){std::memset(&s.simd.v[n],0,16);std::memcpy(&s.simd.v[n],&p.d8_d15[n-8],8);}
  s.gpr.sp.qword=p.sp;s.gpr.pc.qword=p.pc;s.gpr.x0.qword=p.value;return s;
}
void NonlocalJumps::Forget(addr_t env){std::lock_guard<std::mutex> lock(mutex_);saved_.erase(env);}
void NonlocalJumps::DropThread(uint64_t token,uint64_t generation){
  std::lock_guard<std::mutex> lock(mutex_);for(auto i=saved_.begin();i!=saved_.end();)
    if(i->second.thread.token==token&&i->second.thread.generation==generation)i=saved_.erase(i);else ++i;
}
addr_t NonlocalJumps::Marker(const std::string&name)const{
  for(size_t i=0;i<6;++i)if(name==names[i])return marker_base_+i*16;
  throw std::invalid_argument("unknown nonlocal-jump import "+name);
}
[[noreturn]] void NonlocalJumps::Fatal(const char *name,const State&s,const std::exception&e)noexcept{
  std::fprintf(stderr,"Bunker guest nonlocal jump fatal: %s: %s (env=0x%llx LR=0x%llx)\n",
               name,e.what(),(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x30.qword);
  std::fflush(stderr);std::_Exit(3);
}
void NonlocalJumps::Install(recomp::Runtime&runtime){
  Need(!installed_,"nonlocal-jump imports already installed");installed_=true;
  for(size_t i=0;i<6;++i)runtime.AddImport(Marker(names[i]),[this,i](State&s){
    try{
      if(i<3){
        if(i==2)Need(s.gpr.x1.qword<=1,"Android 13 sigsetjmp cookie rejects unexpected signal flag bits");
        Save(s,s.gpr.x0.qword,i==0?1:i==1?0:int(s.gpr.x1.qword),i==2?kSigJmpBytes:kJmpBytes);return;
      }
      auto plan=Inspect(s,s.gpr.x0.qword,int32_t(s.gpr.x1.dword));
      char why[200];std::snprintf(why,sizeof(why),
        "controlled nonlocal transfer is unimplemented (destination PC=0x%llx SP=0x%llx value=0x%x)",
        (unsigned long long)plan.pc,(unsigned long long)plan.sp,plan.value);
      throw std::runtime_error(why);
    }catch(const std::exception&e){Fatal(names[i],s,e);}
  });
}
}  // namespace bunker::windows
