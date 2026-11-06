#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "cases.h"
#include <array>
#include <stdexcept>
extern "C" Memory*sub_83aaabec(State&,addr_t,Memory*);
extern "C" Memory*sub_841ebd60(State&,addr_t,Memory*);
static uint64_t selected_pc;static unsigned observations;
static void require(bool v,const char*m){if(!v)throw std::runtime_error(m);}
static Memory*observe(State&s,addr_t pc,Memory*m){bool known=false;for(const auto&p:prefixes){if(pc==p.default_pc)known=true;for(auto t:p.targets)if(pc==t)known=true;}require(known&&pc==s.gpr.pc.qword,"actual dispatch reaches qualified observer PC");selected_pc=pc;observations++;s.gpr.x0.qword=pc;s.gpr.pc.qword=s.gpr.x30.qword;return m;}

#include "default-observers.inc"
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Out)==80);
 require(argc==2&&!map_original(argv[1]),"map original tables and owned inputs");recomp::Runtime runtime;const recomp::Trace dispatch[]={{0x83aaabec,sub_83aaabec},{0x841ebd60,sub_841ebd60}};runtime.AddTraces(dispatch,2);
 for(const auto&p:prefixes){for(auto pc:p.targets){recomp::Trace t{pc,observe};runtime.AddTraces(&t,1);}recomp::Trace t{p.default_pc,observe};runtime.AddTraces(&t,1);}unsigned executions=0;
 for(unsigned p=0;p<2;p++)for(unsigned i=0;i<sizeof(indices)/sizeof(*indices);i++)for(unsigned n=0;n<2;n++){
  seed(indices[i]);uint64_t before=hash_owned();State s{};memset(&s.simd,0x5a,sizeof(s.simd));reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x0.qword=owned;s.gpr.x19.qword=owned;s.gpr.sp.qword=owned+0x1f000;s.gpr.x29.qword=0xe123456789abcdefULL;s.gpr.x30.qword=0xfeedffff;s.gpr.x22.qword=incoming[n];s.gpr.x26.qword=stack_value;s.gpr.x27.qword=old_x27;s.gpr.x9.qword=old_x9;s.gpr.x10.qword=old_x10;put64(s.gpr.sp.qword+0x140,stack_value);
  s.fpcr.flat=0xc00000;s.fpsr.flat=0x0800009f;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=1;s.nzcv.flat=0xa0000000;s.sr.n=s.sr.c=1;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto saved=opaque;observations=0;selected_pc=0;
  require(runtime.Run(s,prefixes[p].start,token)==token&&opaque==saved,"Memory64 exact");require(observations==1&&selected_pc==expected_target(p,indices[i]),"real guard/table mapping exact");require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==owned+0x1f000&&s.gpr.x19.qword==owned&&s.gpr.x29.qword==0xe123456789abcdefULL&&s.gpr.x26.qword==stack_value,"PC/SP/callee context preserved");
  std::array<unsigned char,16>v;v.fill(0x5a);for(unsigned j=0;j<32;j++)require(!memcmp(v.data(),&s.simd.v[j],16),"all SIMD unchanged by integer dispatch");require(reinterpret_cast<unsigned char*>(&s)[1199]==0x6d&&hash_owned()==before,"highState/owneddata exact");
  Out out{};out.target=s.gpr.x0.qword;out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;out.fpsr=fpsr(s);out.x8=s.gpr.x8.qword;out.x9=s.gpr.x9.qword;out.x10=s.gpr.x10.qword;out.x22=s.gpr.x22.qword;out.x27=s.gpr.x27.qword;out.abi=1;record(p,indices[i],n,&out);executions++;
 }
 printf("WINDOWS-TMP-GUARD-PASS executions=%u State1200=1 Memory64=1 observers=10\n",executions);return 0;
}catch(const std::exception&e){fprintf(stderr,"TMP guard fixture: %s\n",e.what());return 1;}}
