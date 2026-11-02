#include <cstdlib>
#include "runtime.h"
#include "elfload.h"
#include "guest_memory.h"
#include "traces.h"
#define CASE(name) #name,
static const char *case_names[]={
#include "generated_cases.h"
};
#undef CASE
#include "ushll_records.h"
static recomp::Runtime runtime;
static elf_image image;
alignas(16) static uint8_t stack[65536];
static void call(const char *name,uint8_t *output,const uint8_t *input){
  State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(output);
  uint64_t initial[3]{};recomp::ReadGuestMemory(initial,reinterpret_cast<addr_t>(input+64),sizeof(initial));
  state.nzcv.flat=initial[0];state.sr.n=(initial[0]>>31)&1;state.sr.z=(initial[0]>>30)&1;state.sr.c=(initial[0]>>29)&1;state.sr.v=(initial[0]>>28)&1;
  state.fpsr.flat=initial[1];state.sr.ioc=state.fpsr.ioc;state.sr.dzc=state.fpsr.dzc;state.sr.ofc=state.fpsr.ofc;state.sr.ufc=state.fpsr.ufc;state.sr.ixc=state.fpsr.ixc;state.sr.idc=state.fpsr.idc;
  state.fpcr.flat=initial[2];
  state.gpr.x1.qword=reinterpret_cast<addr_t>(input);
  state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
  state.gpr.x30.qword=0xfeedffff;
  auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));if(!entry)std::abort();
  state.gpr.pc.qword=entry;runtime.Run(state,entry);
  if(state.gpr.pc.qword!=0xfeedffff||state.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))std::abort();
  if(state.nzcv.flat!=initial[0]||state.fpsr.flat!=initial[1]||state.fpcr.flat!=initial[2])std::abort();
  auto fpsr=state.fpsr;fpsr.ioc=state.sr.ioc;fpsr.dzc=state.sr.dzc;fpsr.ofc=state.sr.ofc;fpsr.ufc=state.sr.ufc;fpsr.ixc=state.sr.ixc;fpsr.idc=state.sr.idc;
  uint64_t actual[3]={uint64_t(state.sr.n)<<31|uint64_t(state.sr.z)<<30|uint64_t(state.sr.c)<<29|uint64_t(state.sr.v)<<28,fpsr.flat,state.fpcr.flat};
  recomp::WriteGuestMemory(reinterpret_cast<addr_t>(output+96),actual,sizeof(actual));
}
int main(){
  if(elf_load(SEMANTIC_LIB,0x30000000,[](const char*)->void*{return nullptr;},&image))return 1;
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(kTraces[0]));
  return run_ushll_records(call);
}
