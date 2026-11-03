#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "fcvtzu_fixed_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;static elf_image image;
alignas(16)static uint8_t stack[65536];
static void require(bool b,const char*why){if(!b)throw std::runtime_error(why);}
static void run(State&s,const char*name){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"actual fixture export");runtime.Run(s,entry);require(s.gpr.pc.qword==0xfeedffff,"actual core normal PC return");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;const auto flags=get64(in+736);s.nzcv.flat=flags;s.sr.n=flags>>31&1;s.sr.z=flags>>30&1;s.sr.c=flags>>29&1;s.sr.v=flags>>28&1;const auto sp=s.gpr.sp.qword;run(s,cases[n].name);require(s.gpr.sp.qword==sp,"owned SP restored");}

static void set_result(State&s,unsigned r,uint64_t value){switch(r){case 5:s.gpr.x5.qword=value;break;case 8:s.gpr.x8.qword=value;break;case 9:s.gpr.x9.qword=value;break;case 17:s.gpr.x17.qword=value;break;case 31:break;default:throw std::runtime_error("unexpected raw destination");}}
static void raw_state_checks(){
 static_assert(sizeof(State)==1200&&alignof(State)==16,"actual State ABI");
 for(unsigned n=0;n<CASE_COUNT;++n){const auto&c=cases[n];State s{},expected{};std::memset(&s.simd,0xa5,sizeof(s.simd));s.gpr.x5.qword=s.gpr.x8.qword=s.gpr.x9.qword=s.gpr.x17.qword=UINT64_C(0xdeadbeefc0ffee00);s.gpr.x30.qword=0xfeedffff;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.nzcv.flat=UINT64_C(0xa0000000);s.sr.n=1;s.sr.c=1;
  uint64_t raw=c.width==32?UINT64_C(0x3fc00000):UINT64_C(0x3ff8000000000000);std::memcpy(&s.simd.v[c.rn],&raw,c.width/8);std::memcpy(&expected,&s,sizeof(s));uint64_t flags=0,value=fixed_expected(raw,c.width,c.outwidth,c.fbits,0,&flags);set_result(expected,c.rd,value);
  if(c.pair){uint32_t fp=uint_to_single(value,0,&flags);std::memset(&expected.simd.v[0],0,16);std::memcpy(&expected.simd.v[0],&fp,4);}
  expected.sr.ioc=flags&1;expected.sr.ixc=(flags>>4)&1;expected.sr.idc=(flags>>7)&1;expected.gpr.pc.qword=0xfeedffff;
  auto token=reinterpret_cast<Memory*>(uintptr_t(0x12345678));auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,(std::string("raw_")+c.name).c_str()));require(entry!=0,"raw actual export");require(runtime.Run(s,entry,token)==token,"pure conversion keeps memory token");require(std::memcmp(&s,&expected,sizeof(s))==0,"raw full1200 State unnormalized exact preservation");
 }
}
int main(){try{if(elf_load(FCVTZU_FIXED_LIB,0x38000000,[](const char*)->void*{return nullptr;},&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));uint32_t source=0x7f812345,destination=0;State control{};control.gpr.x0.qword=reinterpret_cast<addr_t>(&source);control.gpr.x1.qword=reinterpret_cast<addr_t>(&destination);control.gpr.x30.qword=0xfeedffff;control.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));run(control,"fcvtzu_fixed_control_copy");require(source==destination,"neighboring scalar load/store retains real memory effect");raw_state_checks();int result=run_fcvtzu_fixed_records(call);if(result)return result;std::puts("FCVTZU_FIXED-HOST-SUCCESS memory_control=1 raw_State1200=42 memory_tokens=42");return 0;}catch(const std::exception&e){std::fprintf(stderr,"fcvtzu_fixed fixture: %s\n",e.what());return 1;}}
