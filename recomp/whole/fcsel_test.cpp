#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "fcsel_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;static elf_image image;
alignas(16)static uint8_t stack[65536];
static void require(bool b,const char*why){if(!b)throw std::runtime_error(why);}
static void run(State&s,const char*name){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"actual fixture export");runtime.Run(s,entry);require(s.gpr.pc.qword==0xfeedffff,"actual core normal PC return");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(in);s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;const auto flags=get64(in+736);s.nzcv.flat=flags;s.sr.n=flags>>31&1;s.sr.z=flags>>30&1;s.sr.c=flags>>29&1;s.sr.v=flags>>28&1;const auto sp=s.gpr.sp.qword;run(s,cases[n].name);require(s.gpr.sp.qword==sp,"owned SP restored");}
static void regression(){
 for(unsigned bit=0;bit<2;++bit){State s{};std::memset(&s.simd,0xa7,sizeof(s.simd));s.gpr.x20.qword=bit;s.gpr.x30.qword=0xfeedffff;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));run(s,"raw_original_sequence");uint8_t expected[16]{};put64(expected,bit?0:0x3f800000);require(!std::memcmp(&s.simd.v[0],expected,16),"original mute bit selects raw one/zero with upper clear");}
 std::puts("FCSEL-ORIGINAL-SEQUENCE-SUCCESS W20=0,1");
}
int main(){try{if(elf_load(FCSEL_LIB,0x38000000,[](const char*)->void*{return nullptr;},&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));regression();uint32_t source=0x7f812345,destination=0;State control{};control.gpr.x0.qword=reinterpret_cast<addr_t>(&source);control.gpr.x1.qword=reinterpret_cast<addr_t>(&destination);control.gpr.x30.qword=0xfeedffff;control.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));run(control,"fcsel_control_copy");require(source==destination,"neighboring scalar load/store retains real memory effect");int result=run_fcsel_records(call);if(result)return result;std::puts("FCSEL-HOST-SUCCESS memory_control=1");return 0;}catch(const std::exception&e){std::fprintf(stderr,"fcsel fixture: %s\n",e.what());return 1;}}
