#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "leaf_rounding_cases.h"
#include <array>
#include <stdexcept>
extern "C" Memory*sub_70167fc4(State&,addr_t,Memory*);
#include "unexecuted-sentinels.inc"
static void require(bool v,const char*why){if(!v)throw std::runtime_error(why);}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(FrameOutput)==104);require(argc==2&&!map_original(argv[1]),"real original ELF maps and owned canaries allocate");recomp::Runtime runtime;recomp::Trace target{0x70167fc4,sub_70167fc4};runtime.AddTraces(&target,1);unsigned executions=0;
 for(unsigned sample=0;sample<24;sample++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
  const auto&input=leaf_inputs[sample];require(normal_or_zero(input.value)&&normal_or_zero(input.scale),"predefinednormal-or-zero input domain");seed(sample);uint64_t before_hash=object_hash();State s{};memset(&s.simd,0x5a,sizeof(s.simd));memcpy(&s.simd.v[0],&input.value,4);memcpy(&s.simd.v[1],&input.scale,4);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x0.qword=0xf123456789abcdefULL;s.gpr.x8.qword=0xd123456789abcdefULL;s.gpr.sp.qword=owned+0x1f000;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x1919;s.gpr.x20.qword=0x2020;s.gpr.x21.qword=0xc123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;
  s.fpcr.flat=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);s.fpsr.flat=initial?0x0800009f:0;s.sr.ioc=initial;s.sr.dzc=initial;s.sr.ofc=initial;s.sr.ufc=initial;s.sr.ixc=initial;s.sr.idc=initial;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;State expected=s;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto copied=opaque;require(runtime.Run(s,target.address,token)==token&&opaque==copied,"leaf preserves actual opaqueMemory64");
  require(s.gpr.x8.qword==0x70e7d000&&s.gpr.x0.qword<=0xffffffffULL&&s.gpr.pc.qword==0xfeedffff&&object_hash()==before_hash,"actual ROconstant page loaded/W0 zeroextended/return PC/wholeownedcanary");
  expected.gpr.x0=s.gpr.x0;expected.gpr.x8=s.gpr.x8;expected.gpr.pc=s.gpr.pc;memcpy(&expected.simd.v[0],&s.simd.v[0],16);memcpy(&expected.simd.v[2],&s.simd.v[2],16);expected.sr.ioc=s.sr.ioc;expected.sr.dzc=s.sr.dzc;expected.sr.ofc=s.sr.ofc;expected.sr.ufc=s.sr.ufc;expected.sr.ixc=s.sr.ixc;expected.sr.idc=s.sr.idc;require(!memcmp(&s,&expected,sizeof(s)),"all1200Statebytes preserve every nonoutput cell includingSP/calleeGPR/unusedSIMD/NZCV/FPCR");
  FrameOutput out{};out.result=s.gpr.x0.qword;out.fpsr=fpsr(s);out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;memcpy(out.vectors,&s.simd.v[0],64);out.abi_ok=1;record(sample,mode,initial,&out);++executions;
 }
 printf("WINDOWS-LEAF-ROUNDING-PASS executions=%u State=1200 Memory64=1 helpers=0\n",executions);return 0;
 }catch(const std::exception&e){fprintf(stderr,"leaf rounding: %s\n",e.what());return 1;}}
