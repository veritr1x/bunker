#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "gpu_cleanup_cases.h"
#include <array>
#include <cfenv>
#include <stdexcept>
extern "C" Memory*sub_70470818(State&,addr_t,Memory*);
#include "unexecuted-sentinels.inc"
static void require(bool v,const char*why){if(!v)throw std::runtime_error(why);}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(CleanupOutput)==152);
 require(argc==2&&!map_original(argv[1]),"real original ELF maps and TEST data allocates");recomp::Runtime runtime;recomp::Trace target{0x70470818,sub_70470818};runtime.AddTraces(&target,1);unsigned executions=0;
 unsigned char before[0x10000];
 for(unsigned sample=0;sample<CLEANUP_SAMPLES;sample++)for(unsigned layout=0;layout<2;layout++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
  seed(sample,layout);memcpy(before,(void*)owned,sizeof(before));State s{};memset(&s.simd,0x5a,sizeof(s.simd));reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;s.gpr.x0.qword=owned;s.gpr.sp.qword=owned+0x3f000;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x1919;s.gpr.x20.qword=0x2020;s.gpr.x21.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;
  s.fpcr.flat=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);s.fpsr.flat=initial?0x0800009f:0;s.sr.ioc=initial;s.sr.dzc=initial;s.sr.ofc=initial;s.sr.ufc=initial;s.sr.ixc=initial;s.sr.idc=initial;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto copied=opaque;
  require(runtime.Run(s,target.address,token)==token&&opaque==copied,"complete function preserves opaqueMemory64");require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==owned+0x3f000&&s.gpr.x19.qword==0x1919&&s.gpr.x20.qword==0x2020&&s.gpr.x21.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"actual128byteframe restores PC/SP/callee high64GPRs");
  std::array<unsigned char,16>v;v.fill(0x5a);require(!memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200 unmodified SIMD/highcell");require(!memcmp(before,(void*)owned,sizeof(before))&&!get64(0x7123d688),"all65536 TESTownedbytes/unusedglobalpointer unchanged without helpers");CleanupOutput out{};out.result=s.gpr.x0.qword;out.fpsr=fpsr(s);out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;memcpy(out.vectors,&s.simd.v[0],64);memcpy(out.vectors+4,&s.simd.v[8],48);out.abi_ok=1;require(out.result==owned,"retained-node function leavesoriginalargument returnregister");record(sample,layout,mode,initial,&out);++executions;
 }

 printf("WINDOWS-GPU-CLEANUP-PASS executions=%u State=1200 Memory64=1 helpers=0 helper_result_stubs=0\n",executions);return 0;
 }catch(const std::exception&e){fprintf(stderr,"gpu cleanup: %s\n",e.what());return 1;}}
