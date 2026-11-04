#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "faddp_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;static elf_image image;
alignas(16)static uint8_t stack[65536];
static void require(bool b,const char*why){if(!b)throw std::runtime_error(why);}
static void run(State&s,const char*name){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"actual fixture export");runtime.Run(s,entry);require(s.gpr.pc.qword==0xfeedffff,"actual core normal PC return");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;const auto flags=get64(in+736);s.nzcv.flat=flags;s.sr.n=flags>>31&1;s.sr.z=flags>>30&1;s.sr.c=flags>>29&1;s.sr.v=flags>>28&1;const auto sp=s.gpr.sp.qword;run(s,cases[n].name);require(s.gpr.sp.qword==sp,"owned SP restored");}

static void raw_state_checks(){
 static_assert(sizeof(State)==1200&&alignof(State)==16,"State ABI");
 for(unsigned n=0;n<CASE_COUNT;++n){const auto&c=cases[n];State s{},expected{};memset(&s.simd,0xa5,sizeof(s.simd));s.gpr.x30.qword=0xfeedffff;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;
  uint64_t a=c.width==32?UINT64_C(0x3fc00000):UINT64_C(0x3ff8000000000000),b=c.width==32?UINT64_C(0x40100000):UINT64_C(0x4002000000000000),result=c.width==32?UINT64_C(0x40700000):UINT64_C(0x400e000000000000);memcpy(&s.simd.v[c.rn],&a,c.width/8);memcpy(reinterpret_cast<uint8_t*>(&s.simd.v[c.rn])+c.width/8,&b,c.width/8);memcpy(&expected,&s,sizeof(s));memset(&expected.simd.v[c.rd],0,16);memcpy(&expected.simd.v[c.rd],&result,c.width/8);expected.gpr.pc.qword=0xfeedffff;
  auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,(std::string("raw_")+c.name).c_str()));require(entry!=0,"raw fixture export");require(runtime.Run(s,entry,token)==token,"raw token identity");require(memcmp(&s,&expected,sizeof(s))==0,"raw independently modeled full1200 State exact");
 }
}
int main(){try{if(elf_load(FADDP_LIB,0x38000000,[](const char*)->void*{return nullptr;},&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));uint32_t source=0x7f812345,destination=0;State control{};control.gpr.x0.qword=reinterpret_cast<addr_t>(&source);control.gpr.x1.qword=reinterpret_cast<addr_t>(&destination);control.gpr.x30.qword=0xfeedffff;control.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));run(control,"faddp_control_copy");require(source==destination,"neighboring scalar load/store retains real memory effect");raw_state_checks();int result=run_faddp_records(call);if(result)return result;std::puts("FADDP-HOST-SUCCESS memory_control=1 raw_State1200=8 memory_tokens=8");return 0;}catch(const std::exception&e){std::fprintf(stderr,"faddp fixture: %s\n",e.what());return 1;}}
