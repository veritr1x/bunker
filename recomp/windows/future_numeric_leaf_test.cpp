#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "future_numeric_leaf_cases.h"
#include <array>
#include <stdexcept>
#define ENTRY(h) extern "C" Memory*sub_##h(State&,addr_t,Memory*);
#include "entries.inc"
#undef ENTRY
#include "unexecuted-sentinels.inc"
static recomp::Trace targets[]={
#define ENTRY(h) {0x##h,sub_##h},
#include "entries.inc"
#undef ENTRY
};
static void require(bool v,const char*why){if(!v)throw std::runtime_error(why);}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(BatchOutput)==120);require(argc==2&&!map_original(argv[1]),"real original ELF maps and owned blocks allocate");recomp::Runtime runtime;runtime.AddTraces(targets,4);unsigned executions=0;
 for(unsigned fn=0;fn<4;fn++)for(unsigned sample=0;sample<samples(fn);sample++)for(unsigned alias=0;alias<aliases(fn);alias++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
  if(fn==1){for(unsigned i=0;i<6;i++)require(normal_or_zero(vector_inputs[sample][i]),"predefinednormalvectorinputs");}else require(normal_or_zero(scalar_inputs[sample]),"predefinednormalscalarinputs");seed(fn,sample);unsigned char before[0x1000];memcpy(before,(void*)owned,sizeof(before));State s{};memset(&s.simd,0x5a,sizeof(s.simd));if(fn!=1)memcpy(&s.simd.v[0],&scalar_inputs[sample],4);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x0.qword=destination(fn,alias);s.gpr.x1.qword=owned+0x100;s.gpr.x2.qword=owned+0x800;s.gpr.x3.qword=owned+0x200;s.gpr.x8.qword=0xd123456789abcdefULL;s.gpr.x9.qword=0xb123456789abcdefULL;s.gpr.sp.qword=owned+0x1f000;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x1919;s.gpr.x20.qword=0x2020;s.gpr.x21.qword=0xc123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;
  s.fpcr.flat=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);s.fpsr.flat=initial?0x0800009f:0;s.sr.ioc=initial;s.sr.dzc=initial;s.sr.ofc=initial;s.sr.ufc=initial;s.sr.ixc=initial;s.sr.idc=initial;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;State expected=s;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto copied=opaque;require(runtime.Run(s,targets[fn].address,token)==token&&opaque==copied,"actualopaqueMemory64");require(s.gpr.pc.qword==0xfeedffff&&unchanged_canaries(fn,alias,before),"leafreturnandallnonoutputmemorybytes");
  expected.gpr.pc=s.gpr.pc;if(fn==0||fn==2)expected.gpr.x8=s.gpr.x8;if(fn==0)expected.gpr.x9=s.gpr.x9;for(unsigned v=0;v<(fn==1?5:2);v++)memcpy(&expected.simd.v[v],&s.simd.v[v],16);expected.sr.ioc=s.sr.ioc;expected.sr.dzc=s.sr.dzc;expected.sr.ofc=s.sr.ofc;expected.sr.ufc=s.sr.ufc;expected.sr.ixc=s.sr.ixc;expected.sr.idc=s.sr.idc;if(fn==1){expected.sr.n=s.sr.n;expected.sr.z=s.sr.z;expected.sr.c=s.sr.c;expected.sr.v=s.sr.v;}require(!memcmp(&s,&expected,sizeof(s)),"wholeState1200nonoutputbytes");
  BatchOutput out{};out.result=s.gpr.x0.qword;out.fpsr=fpsr(s);out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;memcpy(out.vectors,&s.simd.v[0],80);out.abi_ok=1;record(fn,sample,alias,mode,initial,&out);++executions;
 }printf("WINDOWS-FUTURE-LEAF-PASS executions=%u State=1200 Memory64=1 helpers=0\n",executions);return 0;}catch(const std::exception&e){fprintf(stderr,"futureleaf: %s\n",e.what());return 1;}}
