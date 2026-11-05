#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "frame_rounding_cases.h"
#include "component_helpers.h"
#include <array>
#include <cfenv>
#include <stdexcept>
extern "C" Memory*sub_70167bbc(State&,addr_t,Memory*);
#include "unexecuted-sentinels.inc"
static void require(bool v,const char*why){if(!v)throw std::runtime_error(why);}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(FrameOutput)==104);
 require(argc==2&&!map_original(argv[1]),"real original ELF maps and TEST data allocates");recomp::Runtime runtime;recomp::Trace target{0x70167bbc,sub_70167bbc};runtime.AddTraces(&target,1);runtime.AddTraces(bunker::frame_rounding_fixture::kRealHelperTraces,3);unsigned executions=0;
 for(unsigned sample=0;sample<34;sample++)if(normal_geometry(sample))for(unsigned chain=0;chain<2;chain++)for(unsigned mode=0;mode<4;mode++)for(unsigned initial=0;initial<2;initial++){
  seed(sample,chain);uint64_t before=object_hash();State s{};memset(&s.simd,0x5a,sizeof(s.simd));reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x0.qword=owned;s.gpr.sp.qword=owned+0x1f000;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x1919;s.gpr.x20.qword=0x2020;s.gpr.x21.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;
  s.fpcr.flat=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);s.fpsr.flat=initial?0x0800009f:0;s.sr.ioc=initial;s.sr.dzc=initial;s.sr.ofc=initial;s.sr.ufc=initial;s.sr.ixc=initial;s.sr.idc=initial;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto copied=opaque;
  require(runtime.Run(s,target.address,token)==token&&opaque==copied,"fullbody preserves actual opaqueMemory64");
  require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==owned+0x1f000&&s.gpr.x19.qword==0x1919&&s.gpr.x20.qword==0x2020&&s.gpr.x21.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"fullbody and realhelpers restore PC/SP/callee high64 GPRs");
  std::array<unsigned char,16>v;v.fill(0x5a);require(!memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200 unmodified SIMD/highcell");
  require(object_hash()==before&&!(get64(0x712b8b58)>>32),"realhelpers preserve full TEST owned data and restore real globalcounter");FrameOutput out{};out.result=s.gpr.x0.qword;out.fpsr=fpsr(s);out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;memcpy(out.vectors,&s.simd.v[0],64);out.abi_ok=1;require(sample<32?out.vectors[0][15]==0:(out.result==120&&out.vectors[0][15]==0x5a),"actual component hit executes FP body; actual lookup misses take120 fallback");record(sample,chain,mode,initial,&out);++executions;
 }
 printf("WINDOWS-FRAME-ROUNDING-PASS executions=%u State=1200 Memory64=1 real_helpers=3 helper_result_stubs=0\n",executions);return 0;
 }catch(const std::exception&e){fprintf(stderr,"frame rounding: %s\n",e.what());return 1;}}
