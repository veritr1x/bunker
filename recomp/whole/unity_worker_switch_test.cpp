#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "unity_worker_switch_cases.h"
#include <array>
#include <stdexcept>
extern "C" Memory*sub_70ddd584(State&,addr_t,Memory*);
static uint64_t selected_pc;static unsigned observations,checks;
static void require(bool v,const char*m){++checks;if(!v)throw std::runtime_error(m);}
static Memory*observe(State&s,addr_t pc,Memory*m){bool known=pc==default_pc;for(auto t:targets)if(pc==t)known=true;require(known&&pc==s.gpr.pc.qword,"actual guard reaches registered original destination");selected_pc=pc;observations++;s.gpr.x0.qword=pc;s.gpr.pc.qword=s.gpr.x30.qword;return m;}
#include "default-observer.inc"
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Out)==80);
 require(argc==2&&!map_original(argv[1]),"original mapped signed table and owned input");recomp::Runtime runtime;recomp::Trace entry{dispatch_pc,sub_70ddd584};runtime.AddTraces(&entry,1);
 for(auto pc:targets){recomp::Trace t{pc,observe};runtime.AddTraces(&t,1);}recomp::Trace def{default_pc,observe};runtime.AddTraces(&def,1);unsigned executions=0;
 for(unsigned i=0;i<sizeof(indices)/sizeof(*indices);i++)for(unsigned n=0;n<2;n++){
  seed(indices[i]);const uint64_t before=hash_owned();State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7,&GPR::x8,&GPR::x9,&GPR::x10,&GPR::x11,&GPR::x12,&GPR::x13,&GPR::x14,&GPR::x15,&GPR::x16,&GPR::x17,&GPR::x18,&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29,&GPR::x30};for(unsigned j=0;j<31;j++)(s.gpr.*regs[j]).qword=UINT64_C(0xbead000000000000)+j*UINT64_C(0x1010101);memset(&s.simd,0x5a,sizeof(s.simd));reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x19.qword=owned;s.gpr.sp.qword=owned+0x1f000;s.gpr.x30.qword=0xfeedffff;s.gpr.x8.qword=incoming[n];s.gpr.x9.qword=old_x9;s.gpr.x10.qword=old_x10;s.gpr.x22.qword=old_x22;s.gpr.x27.qword=input_table(indices[i],n);
  s.fpcr.flat=0xc00000;s.fpsr.flat=0x0800009f;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=1;s.nzcv.flat=0xa0000000;s.sr.n=s.sr.c=1;State expected=s;const uint32_t diff=indices[i]-7;expected.sr.n=diff>>31;expected.sr.z=diff==0;expected.sr.c=indices[i]>=7;expected.sr.v=((indices[i]^7)&(indices[i]^diff))>>31;expected.gpr.x0.qword=expected_target(indices[i]);expected.gpr.x8.qword=indices[i]<=7?expected_target(indices[i]):indices[i];expected.gpr.pc.qword=expected.gpr.x30.qword;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto saved=opaque;observations=0;selected_pc=0;
  require(runtime.Run(s,dispatch_pc,token)==token&&opaque==saved,"opaque Memory64 exact");require(observations==1&&selected_pc==expected_target(indices[i]),"unsigned bound and signed table target exact");require(!memcmp(&s,&expected,sizeof(State)),"full State1200 matches independently expected effects");require(hash_owned()==before,"all owned bytes unchanged");
  Out out{};out.target=s.gpr.x0.qword;out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;out.fpsr=fpsr(s);out.x8=s.gpr.x8.qword;out.x9=s.gpr.x9.qword;out.x10=s.gpr.x10.qword;out.x22=s.gpr.x22.qword;out.x27=s.gpr.x27.qword;out.abi=1;record(indices[i],n,&out);executions++;
 }
 printf("WINDOWS-UNITY-WORKER-SWITCH-PASS executions=%u checks=%u State1200=1 Memory64=1 observers=9\n",executions,checks);return 0;
}catch(const std::exception&e){fprintf(stderr,"Unity worker switch fixture: %s\n",e.what());return 1;}}
