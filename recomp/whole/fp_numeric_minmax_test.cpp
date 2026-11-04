#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "fp_numeric_minmax_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;static elf_image image;
alignas(16)static uint8_t stack[65536];
static void require(bool b,const char*why){if(!b)throw std::runtime_error(why);}
static void run(State&s,const char*name){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"actual fixture export");runtime.Run(s,entry);require(s.gpr.pc.qword==0xfeedffff,"actual core normal PC return");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;const auto flags=get64(in+736);s.nzcv.flat=flags;s.sr.n=flags>>31&1;s.sr.z=flags>>30&1;s.sr.c=flags>>29&1;s.sr.v=flags>>28&1;const auto sp=s.gpr.sp.qword;run(s,cases[n].name);require(s.gpr.sp.qword==sp,"owned SP restored");}

static void raw_state_checks(){
 static_assert(sizeof(State)==1200&&alignof(State)==16,"actual State ABI");
 for(unsigned n=0;n<CASE_COUNT;++n)for(unsigned mode=0;mode<16;++mode){
  const auto&c=cases[n];State s{},expected{};std::memset(&s.simd,0xa5,sizeof(s.simd));
  s.gpr.x5.qword=UINT64_C(0xdeadbeefc0ffee00);s.gpr.x30.qword=0xfeedffff;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
  s.nzcv.flat=UINT64_C(0xa0000000);s.sr.n=1;s.sr.c=1;s.fpcr.flat=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);
  uint64_t a,b;pair_bits(c.width,mode+14,&a,&b);std::memcpy(&s.simd.v[c.rn],&a,c.width/8);std::memcpy(&s.simd.v[c.rm],&b,c.width/8);std::memcpy(&expected,&s,sizeof(s));
  std::memcpy(&a,&s.simd.v[c.rn],c.width/8);std::memcpy(&b,&s.simd.v[c.rm],c.width/8);uint64_t status=0,value=numeric_expected(a,b,c.width,c.maximum,s.fpcr.flat,&status);
  std::memset(&expected.simd.v[c.rd],0,16);std::memcpy(&expected.simd.v[c.rd],&value,c.width/8);expected.sr.ioc=status&1;expected.sr.idc=(status>>7)&1;expected.gpr.pc.qword=0xfeedffff;
  auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,(std::string("raw_")+c.name).c_str()));require(entry!=0,"raw actual export");
  require(runtime.Run(s,entry,token)==token,"numeric instruction preserves opaque memory token");require(std::memcmp(&s,&expected,sizeof(s))==0,"raw full1200 State exact preservation");
 }
}
int main(){try{if(elf_load(FP_NUMERIC_MINMAX_LIB,0x39000000,[](const char*)->void*{return nullptr;},&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));uint32_t source=0x7f812345,destination=0;State control{};control.gpr.x0.qword=reinterpret_cast<addr_t>(&source);control.gpr.x1.qword=reinterpret_cast<addr_t>(&destination);control.gpr.x30.qword=0xfeedffff;control.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));run(control,"fp_numeric_minmax_control_copy");require(source==destination,"neighboring scalar load/store retains real memory effect");raw_state_checks();int result=run_numeric_records(call);if(result)return result;std::puts("FP_NUMERIC_MINMAX-HOST-SUCCESS memory_control=1 raw_State1200=384 memory_tokens=384");return 0;}catch(const std::exception&e){std::fprintf(stderr,"fp_numeric_minmax fixture: %s\n",e.what());return 1;}}
