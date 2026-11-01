#include "nonlocal_jmp.h"
#include "nonlocal_jmp_checks.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>
using bunker::windows::NonlocalJumps;
namespace {
unsigned checks=0;NonlocalJumps *adapter;
void Check(bool yes,const char *why){++checks;if(!yes){std::fprintf(stderr,"nonlocal check: %s\n",why);std::abort();}}
template<class F>void Reject(F f,const char *why){bool caught=false;try{f();}catch(const std::exception&){caught=true;}Check(caught,why);}
void *Resolve(const char*name){return reinterpret_cast<void*>(adapter->Marker(name));}
uint64_t X(const State&s,unsigned n){uint64_t v;std::memcpy(&v,reinterpret_cast<const uint8_t*>(&s.gpr)+n*16+8,8);return v;}
void X(State&s,unsigned n,uint64_t v){std::memcpy(reinterpret_cast<uint8_t*>(&s.gpr)+n*16+8,&v,8);}
}
int main(int argc,char**argv){
  alignas(16)uint64_t env[33],before[33],out[66];
  std::vector<uint8_t> stack(65536);addr_t low=(addr_t)stack.data(),high=(low+stack.size())&~addr_t(15);
  uint64_t token=17,thread_epoch=4,region_epoch=7;bool region_live=true;
  NonlocalJumps jumps([&]{return NonlocalJumps::Thread{token,thread_epoch,low,high};},
    [&](addr_t at,size_t size)->std::optional<NonlocalJumps::Region>{
      auto start=(addr_t)env;if(!region_live||at<start||at>start+sizeof(env)||size>start+sizeof(env)-at)return {};
      return NonlocalJumps::Region{start,start+sizeof(env),region_epoch};
    },[]{return NJ_MASK;},[](addr_t pc){return !(pc&3)&&pc>=0x1000;},NJ_COOKIE);
  adapter=&jumps;recomp::Runtime runtime;jumps.Install(runtime);
  State saved{};saved.gpr.sp.qword=high-64;saved.gpr.x30.qword=0x12345000;
  for(unsigned n=18;n<=29;++n)X(saved,n,0xabc0000000000000ULL+n*0x1234567);
  for(unsigned n=8;n<=15;++n){uint64_t q[]={0x7ff0000000000001ULL+n,0xfedcba9876543210ULL+n};std::memcpy(&saved.simd.v[n],q,16);}
  saved.fpcr.flat=0x1400000;saved.fpsr.flat=0x91;saved.sr.idc=true;saved.sr.ixc=true;
  saved.sr.tpidr_el0.qword=0x123456789abcdef0ULL;
  nj_inputs(env,out,17);std::memcpy(before,env,sizeof(env));jumps.Save(saved,(addr_t)env,1);
  State current=saved;current.gpr.sp.qword-=128;current.gpr.x18.qword=0x9876543212340000ULL;
  if(argc>1){
    if(!std::strcmp(argv[1],"--fatal-corrupt"))env[24]^=1;
    current.gpr.x0.qword=(addr_t)env;current.gpr.x1.qword=0;
    if(!std::strcmp(argv[1],"--fatal-flag")){
      current.gpr.x1.qword=0x100000001ULL;runtime.Run(current,jumps.Marker("sigsetjmp"));
    }else runtime.Run(current,jumps.Marker("longjmp"));return 99;
  }
  auto plan=jumps.Inspect(current,(addr_t)env,-7);auto result=NonlocalJumps::Materialize(current,plan);
  Check(plan.value==uint32_t(-7)&&plan.mask==NJ_MASK,"return sign bits and saved signal mask");
  for(unsigned n=19;n<=30;++n)Check(X(result,n)==X(saved,n),"callee GPR restored");
  Check(result.gpr.x18.qword==((current.gpr.x18.qword&~uint64_t(8191))|(saved.gpr.x18.qword&8191)),"only shadow stack low bits restored");
  for(unsigned n=8;n<=15;++n){uint64_t a[2],b[2];std::memcpy(a,&saved.simd.v[n],16);std::memcpy(b,&result.simd.v[n],16);Check(a[0]==b[0]&&b[1]==0,"LDP D clears high SIMD half");}
  Check(result.fpcr.flat==current.fpcr.flat&&result.fpsr.flat==current.fpsr.flat&&result.sr.idc==current.sr.idc&&result.sr.ixc==current.sr.ixc,"FPCR/FPSR remain current");
  Check(result.sr.tpidr_el0.qword==current.sr.tpidr_el0.qword,"TLS is not restored from jmp_buf");
  Check(result.gpr.sp.qword==saved.gpr.sp.qword&&result.gpr.pc.qword==saved.gpr.x30.qword,"saved SP and continuation");
  Check(jumps.Inspect(current,(addr_t)env,0).value==1,"zero longjmp value maps to one");
  auto original=env[24];env[24]^=1;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"checksum corruption rejected");env[24]=original;
  env[0]^=2;env[24]^=2;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"cookie corruption with corrected checksum rejected");env[0]^=2;env[24]^=2;
  ++token;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"cross-thread longjmp rejected");--token;
  ++thread_epoch;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"thread ABA rejected");--thread_epoch;
  ++region_epoch;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"environment region ABA rejected");--region_epoch;
  region_live=false;Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"revoked environment rejected");region_live=true;
  auto invalid=current;invalid.gpr.sp.qword=saved.gpr.sp.qword+16;Reject([&]{jumps.Inspect(invalid,(addr_t)env,1);},"returned frame rejected when saved SP below current");
  Reject([&]{jumps.Save(current,(addr_t)env,2);},"Bionic invalid signal flag rejected");
  Reject([&]{jumps.Save(current,(addr_t)env,-1);},"negative signal flag rejected");
  Reject([&]{jumps.Save(current,(addr_t)env,1,200);},"partial declaration size rejected");
  auto invalid_sp=current;invalid_sp.gpr.sp.qword=low;
  Reject([&]{jumps.Save(invalid_sp,(addr_t)env,1);},"insufficient registered guest stack rejected");
  auto invalid_pc=current;invalid_pc.gpr.x30.qword=0x12345001;
  Reject([&]{jumps.Save(invalid_pc,(addr_t)env,1);},"misaligned saved continuation rejected");
  Reject([&]{jumps.Marker("not_setjmp");},"unknown imports rejected");
  Check(!std::memcmp(env+25,before+25,8*8),"reserved jmp_buf and extra sigjmp_buf word untouched");
  Reject([&]{jumps.Save(current,(addr_t)env+1,1);},"misaligned environment rejected");
  Reject([&]{jumps.Save(current,(addr_t)env+16,1);},"truncated registered environment rejected");
  jumps.Forget((addr_t)env);Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"explicit environment lifetime end");
  jumps.Save(current,(addr_t)env,0);Check(!jumps.Inspect(current,(addr_t)env,1).mask,"_setjmp does not restore a mask");
  jumps.DropThread(token,thread_epoch);Reject([&]{jumps.Inspect(current,(addr_t)env,1);},"thread teardown removes saved contexts");
  {
    NonlocalJumps no_mask([&]{return NonlocalJumps::Thread{token,thread_epoch,low,high};},
      [&](addr_t,size_t)->std::optional<NonlocalJumps::Region>{return NonlocalJumps::Region{(addr_t)env,(addr_t)env+sizeof(env),region_epoch};},
      {},[](addr_t){return true;},NJ_COOKIE);
    std::memcpy(before,env,sizeof(env));
    Reject([&]{no_mask.Save(current,(addr_t)env,1);},"no invented signal mask");
    Check(!std::memcmp(before,env,sizeof(env)),"rejected save publishes no guest bytes");
    no_mask.Save(current,(addr_t)env,0);Check(!no_mask.Inspect(current,(addr_t)env,1).mask,"_setjmp works without mask service");
  }
  auto random=NonlocalJumps::RandomCookie();Check(!(random&1),"secure process cookie reserves low bit");
  elf_image image{};Check(!elf_load(NONLOCAL_LIBRARY,0x5b000000,Resolve,&image),"actual NDK ELF load");
  auto probe=(addr_t)elf_symbol(&image,"nonlocal_probe");Check(probe!=0,"actual NDK assembly caller");
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(kTraces[0]));
  for(unsigned testcase=0;testcase<128;++testcase)for(unsigned kind=0;kind<4;++kind){
    nj_inputs(env,out,testcase);std::memcpy(before,env,sizeof(env));
    State s{};s.gpr.sp.qword=high-64;s.gpr.x0.qword=(addr_t)env;s.gpr.x1.qword=(addr_t)out;s.gpr.x2.qword=kind;s.gpr.x30.qword=0xfeedfff0;
    s.fpcr.flat=(testcase%4)<<22;
    runtime.Run(s,probe);
    auto bad=nj_check(env,out,before,kind);
    if(bad)std::fprintf(stderr,"actual caller case%u kind%u mismatchbits0x%llx\n",testcase,kind,(unsigned long long)bad);
    Check(!bad,"actual NDK caller matches original Bionic assembly wire and preserved state");
  }
  std::printf("Nonlocal context: %u checks, 512 actual NDK caller records; longjmp transfer remains unsupported.\n",checks);
  return 0;
}
