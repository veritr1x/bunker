#define WIN32_LEAN_AND_MEAN
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "prefetch_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;
static elf_image image;
alignas(16)static uint8_t stack[65536];
static const std::array<Reg GPR::*,31>regs={
 &GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7,
 &GPR::x8,&GPR::x9,&GPR::x10,&GPR::x11,&GPR::x12,&GPR::x13,&GPR::x14,&GPR::x15,
 &GPR::x16,&GPR::x17,&GPR::x18,&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,
 &GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29,&GPR::x30};
static void require(bool b,const char*why){if(!b)throw std::runtime_error(why);}
static void run(State&s,const char*name){auto address=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(address!=0,"export exists");runtime.Run(s,address);require(s.gpr.pc.qword==0xfeedffff,"normal original return PC");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;const auto nzcv=get64(in+736);s.nzcv.flat=nzcv;s.sr.n=(nzcv>>31)&1;s.sr.z=(nzcv>>30)&1;s.sr.c=(nzcv>>29)&1;s.sr.v=(nzcv>>28)&1;auto sp=s.gpr.sp.qword;run(s,cases[n].name);require(s.gpr.sp.qword==sp,"strict NDK core restores stack");}
static unsigned raw_checks(uintptr_t guard){
 unsigned checked=0;
 for(unsigned n=0;n<CASE_COUNT;++n){
  State s{};for(unsigned reg=0;reg<31;++reg)(s.gpr.*regs[reg]).qword=UINT64_C(0xfedcba9876543210)^uint64_t(reg)*UINT64_C(0x123456789ab);
  for(unsigned byte=0;byte<sizeof(s.simd);++byte)reinterpret_cast<uint8_t*>(&s.simd)[byte]=uint8_t(byte*17+9);
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack))-cases[n].misalign;
  s.gpr.x30.qword=0xfeedffff;
  if(cases[n].rn<30)(s.gpr.*regs[cases[n].rn]).qword=guard;
  s.nzcv.flat=0xb0000000;s.sr.n=1;s.sr.z=0;s.sr.c=1;s.sr.v=1;s.fpcr.flat=0x01400000;s.fpsr.flat=0x08000000;
  const auto before=s;
  std::string name="raw_"+std::string(cases[n].name);run(s,name.c_str());
  for(unsigned reg=0;reg<31;++reg)require((s.gpr.*regs[reg]).qword==(before.gpr.*regs[reg]).qword,"raw hint preserves every GPR");
  require(s.gpr.sp.qword==before.gpr.sp.qword&&!std::memcmp(&s.simd,&before.simd,sizeof(s.simd)),"raw hint preserves SP/full SIMD");
  require(s.nzcv.flat==before.nzcv.flat&&!std::memcmp(&s.sr,&before.sr,sizeof(s.sr))&&s.fpcr.flat==before.fpcr.flat&&s.fpsr.flat==before.fpsr.flat,"raw hint preserves canonical/split flags and FP state");
  alignas(8)uint64_t memory=0xaabbccddeeff1122ULL;State ex{};ex.gpr.x0.qword=reinterpret_cast<addr_t>(&memory);ex.gpr.x20.qword=guard;ex.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));ex.gpr.x30.qword=0xfeedffff;
  name="exclusive_"+std::string(cases[n].name);run(ex,name.c_str());require(ex.gpr.x0.dword==0&&memory==0xaabbccddeeff1122ULL,"real LDXR/hint/STXR preserves reservation and bytes");++checked;
 }
 return checked;
}
int main(int argc,char**argv){try{
 if(elf_load(PREFETCH_LIB,0x36000000,[](const char*)->void*{return nullptr;},&image))return 1;
 runtime.AddTraces(kTraces,std::size(kTraces));
#ifdef _WIN32
 auto guard=VirtualAlloc(nullptr,65536,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);require(guard!=nullptr,"real Windows guard");
#else
 auto guard=mmap(nullptr,65536,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);require(guard!=MAP_FAILED,"real Linux guard");
#endif
 if(argc==2&&!std::strcmp(argv[1],"--fault-load")){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(guard);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;run(s,"prefetch_control_load");return 11;}
 alignas(8)uint64_t value=0x76543210abcdef98ULL;State load{};load.gpr.x0.qword=reinterpret_cast<addr_t>(&value);load.gpr.x30.qword=0xfeedffff;run(load,"prefetch_control_load");require(load.gpr.x0.qword==value,"ordinary real load retains effect");
 State store{};store.gpr.x0.qword=reinterpret_cast<addr_t>(&value);store.gpr.x1.qword=0x1122446688aaccffULL;store.gpr.x30.qword=0xfeedffff;run(store,"prefetch_control_store");require(value==0x1122446688aaccffULL,"ordinary real store retains effect");
 auto count=raw_checks(reinterpret_cast<uintptr_t>(guard));int result=run_prefetch_records(call,reinterpret_cast<uintptr_t>(guard));if(result)return result;
#ifdef _WIN32
 require(VirtualFree(guard,0,MEM_RELEASE)!=0,"guard released");
#else
 require(!munmap(guard,65536),"guard released");
#endif
 std::printf("PREFETCH-HOST-SUCCESS raw=%u exclusive=%u ordinary=2\n",count,count);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"prefetch host: %s\n",e.what());return 1;}}
