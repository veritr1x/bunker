#include <cstdlib>
#include <array>
#include <cstring>
#include "runtime.h"
#include "elfload.h"
#include "guest_memory.h"
#include "traces.h"
#define CASE(name) #name,
static const char *case_names[]={
#include "generated_cases.h"
};
#undef CASE
#include "sshll_records.h"
static recomp::Runtime runtime;
static elf_image image;
alignas(16) static uint8_t stack[65536];
static void call(const char *name,uint8_t *output,const uint8_t *input){
  static_assert(sizeof(State)==1200&&sizeof(Memory*)==8);
  State state{};state.gpr.x0.qword=reinterpret_cast<addr_t>(output);
  uint64_t initial[3]{};recomp::ReadGuestMemory(initial,reinterpret_cast<addr_t>(input+64),sizeof(initial));
  for(unsigned n=0;n<31;++n){uint64_t value=UINT64_C(0x9e3779b97f4a7c15)*(n+1)^initial[0];std::memcpy(reinterpret_cast<uint8_t*>(&state.gpr)+n*16+8,&value,8);}
  for(unsigned n=0;n<32;++n){uint64_t value[2]={UINT64_C(0xcafebabe12340000)^n,UINT64_C(0x1020304050607080)^(uint64_t(n)<<32)};std::memcpy(&state.simd.v[n],value,16);}
  state.gpr.x0.qword=reinterpret_cast<addr_t>(output);
  state.nzcv.flat=initial[0];state.sr.n=(initial[0]>>31)&1;state.sr.z=(initial[0]>>30)&1;state.sr.c=(initial[0]>>29)&1;state.sr.v=(initial[0]>>28)&1;
  state.fpsr.flat=initial[1];state.sr.ioc=state.fpsr.ioc;state.sr.dzc=state.fpsr.dzc;state.sr.ofc=state.fpsr.ofc;state.sr.ufc=state.fpsr.ufc;state.sr.ixc=state.fpsr.ixc;state.sr.idc=state.fpsr.idc;
  state.fpcr.flat=initial[2];
  state.gpr.x1.qword=reinterpret_cast<addr_t>(input);
  state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
  state.gpr.x30.qword=0xfeedffff;
  static const char*previous=nullptr;static addr_t cached=0;
  auto entry=previous==name?cached:reinterpret_cast<addr_t>(elf_symbol(&image,name));if(!entry)std::abort();previous=name;cached=entry;
  state.gpr.pc.qword=entry;State before;std::memcpy(&before,&state,sizeof(state));
  std::array<uint64_t,8> memory{};for(unsigned n=0;n<memory.size();++n)memory[n]=UINT64_C(0x1928374655aa7733)*(n+1);auto untouched=memory;auto*opaque=reinterpret_cast<Memory*>(memory.data());
  if(runtime.Run(state,entry,opaque)!=opaque||memory!=untouched)std::abort();
  if(state.gpr.pc.qword!=0xfeedffff||state.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))std::abort();
  if(state.nzcv.flat!=initial[0]||state.fpsr.flat!=initial[1]||state.fpcr.flat!=initial[2])std::abort();
  State normalized;std::memcpy(&normalized,&state,sizeof(state));normalized.gpr.pc.qword=before.gpr.pc.qword;
  for(unsigned n:{0u,1u,2u,3u,17u,31u})std::memcpy(&normalized.simd.v[n],&before.simd.v[n],16);
  if(std::memcmp(&normalized,&before,sizeof(State)))std::abort();
  auto fpsr=state.fpsr;fpsr.ioc=state.sr.ioc;fpsr.dzc=state.sr.dzc;fpsr.ofc=state.sr.ofc;fpsr.ufc=state.sr.ufc;fpsr.ixc=state.sr.ixc;fpsr.idc=state.sr.idc;
  uint64_t actual[3]={uint64_t(state.sr.n)<<31|uint64_t(state.sr.z)<<30|uint64_t(state.sr.c)<<29|uint64_t(state.sr.v)<<28,fpsr.flat,state.fpcr.flat};
  recomp::WriteGuestMemory(reinterpret_cast<addr_t>(output+96),actual,sizeof(actual));
}
int main(){
  if(elf_load(SEMANTIC_LIB,0x30000000,[](const char*)->void*{return nullptr;},&image))return 1;
  runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(kTraces[0]));
  return run_sshll_records(call);
}
