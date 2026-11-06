#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "frinta_records.h"
#include <array>
#include <cstring>
#include <stdexcept>
static recomp::Runtime runtime;static elf_image image;
alignas(16)static uint8_t stack[65536];
static void require(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static void run(State&s,const char*name,Memory*m){auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));require(entry!=0,"real fixture export");require(runtime.Run(s,entry,m)==m,"nonnull Memory64 identity");require(s.gpr.pc.qword==0xfeedffff,"actual fixture normal PC return");}
static void call(unsigned n,uint8_t*out,const uint8_t*in){
 State state;std::memset(&state,0x5a,sizeof(state));const auto flags=get64(in+736);state.nzcv.flat=flags;state.fpcr.flat=0;state.fpsr.flat=0;state.sr.n=flags>>31&1;state.sr.z=flags>>30&1;state.sr.c=flags>>29&1;state.sr.v=flags>>28&1;state.sr.ixc=state.sr.ofc=state.sr.ufc=state.sr.idc=state.sr.ioc=state.sr.dzc=0;state.sr.tpidr_el0.qword=0x123456789abcdef0;state.sr.tpidrro_el0.qword=0xfedcba9876543210;
 state.gpr.x0.qword=reinterpret_cast<addr_t>(out);state.gpr.x1.qword=reinterpret_cast<addr_t>(in);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;State before;std::memcpy(&before,&state,sizeof(state));std::array<uint64_t,8>memory={1,3,7,15,31,63,127,255};auto saved=memory;run(state,cases[n].name,reinterpret_cast<Memory*>(memory.data()));require(memory==saved,"opaque Memory64 bytes");require(state.gpr.sp.qword==before.gpr.sp.qword,"actual fixture normal stack restore");
 State permitted=before;for(unsigned reg=0;reg<33;reg++)std::memcpy(reinterpret_cast<uint8_t*>(&permitted.gpr)+reg*16+8,reinterpret_cast<const uint8_t*>(&state.gpr)+reg*16+8,8);std::memcpy(&permitted.simd,&state.simd,sizeof(state.simd));permitted.fpcr.flat=state.fpcr.flat;permitted.fpsr.flat=state.fpsr.flat;
 permitted.sr.n=state.sr.n;permitted.sr.z=state.sr.z;permitted.sr.c=state.sr.c;permitted.sr.v=state.sr.v;permitted.sr.ixc=state.sr.ixc;permitted.sr.ofc=state.sr.ofc;permitted.sr.ufc=state.sr.ufc;permitted.sr.idc=state.sr.idc;permitted.sr.ioc=state.sr.ioc;permitted.sr.dzc=state.sr.dzc;require(!std::memcmp(&permitted,&state,sizeof(state)),"all unrelated1200 State bytes, TLS and padding unchanged");
}
int main(){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Memory*)==8);if(elf_load(FRINTA_LIB,0x38000000,[](const char*)->void*{return nullptr;},&image))return 1;runtime.AddTraces(kTraces,std::size(kTraces));uint32_t source=0x7f812345,destination=0;State control{};control.gpr.x0.qword=reinterpret_cast<addr_t>(&source);control.gpr.x1.qword=reinterpret_cast<addr_t>(&destination);control.gpr.x30.qword=0xfeedffff;control.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));uint64_t token=0x123456789abcdef0;run(control,"frinta_control_copy",reinterpret_cast<Memory*>(&token));require(source==destination&&token==0x123456789abcdef0,"neighboring scalar memory copy real effect");int result=run_frinta_records(call);if(result)return result;std::puts("FRINTA-HOST-SUCCESS memory_control=1 State1200=1 Memory64=1");return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FRINTA fixture: %s\n",e.what());return 1;}}
