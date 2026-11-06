#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "guest_memory.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include "sshll_function_cases.h"
#include "sshll_function_traces.h"
static sshll_function_case*active=nullptr;static unsigned checks=0;
static recomp::Runtime*active_runtime=nullptr;
extern "C" Memory*SSHLLFunctionImport(State&s,addr_t pc,Memory*m){return active_runtime->Dispatch(s,pc,m);}
static void check(bool value,const char*why){++checks;if(!value)throw std::runtime_error(why);}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);try{
 static_assert(sizeof(State)==1200&&sizeof(Memory*)==8);recomp::Runtime runtime;active_runtime=&runtime;runtime.AddTraces(sshll_function_traces,std::size(sshll_function_traces));runtime.AddImport(0x708ccfc8,[](State&s){++active->calls;active->shape+=s.gpr.x0.qword==reinterpret_cast<addr_t>(active->font)&&!s.gpr.x2.qword&&!s.gpr.x4.qword&&s.gpr.x1.qword-s.gpr.x3.qword==12;recomp::ReadGuestMemory(active->spill,s.gpr.x1.qword-0x1c,16);uint32_t count=27;uint64_t data=0;recomp::WriteGuestMemory(s.gpr.x1.qword,&count,4);recomp::WriteGuestMemory(s.gpr.x3.qword,&data,8);s.gpr.x0.qword=active->error;});
 alignas(16)std::array<uint8_t,65536> stack{};
 for(unsigned seed=0;seed<256;seed++){
  sshll_function_case sample,before;sshll_function_setup(&sample,seed);std::memcpy(&before,&sample,sizeof(before));active=&sample;State state{};for(unsigned n=0;n<31;++n){uint64_t value=UINT64_C(0x9e3779b97f4a7c15)*(n+1)^seed;std::memcpy(reinterpret_cast<uint8_t*>(&state.gpr)+n*16+8,&value,8);}state.gpr.x0.qword=reinterpret_cast<addr_t>(sample.face);state.gpr.x1.qword=reinterpret_cast<addr_t>(sample.opaque);state.gpr.x2.qword=reinterpret_cast<addr_t>(sample.vector);state.gpr.x3.qword=reinterpret_cast<addr_t>(&sample.output);state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.x30.qword=0x6f00fffc;State original;std::memcpy(&original,&state,sizeof(original));std::array<uint64_t,8>memory{};for(unsigned n=0;n<memory.size();n++)memory[n]=UINT64_C(0x123456789abcdef0)*(n+1);auto saved=memory;auto*opaque=reinterpret_cast<Memory*>(memory.data());
  check(runtime.Run(state,0x708d13a8,opaque)==opaque&&memory==saved,"actual function preserves opaque Memory64 token/content");check(state.gpr.pc.qword==original.gpr.x30.qword&&state.gpr.sp.qword==original.gpr.sp.qword&&state.gpr.x30.qword==original.gpr.x30.qword,"actual original epilogue returns SP/LR/PC");
  for(unsigned n=19;n<=29;n++){uint64_t old=0,now=0;std::memcpy(&old,reinterpret_cast<const uint8_t*>(&original.gpr)+n*16+8,8);std::memcpy(&now,reinterpret_cast<const uint8_t*>(&state.gpr)+n*16+8,8);check(old==now,"actual original callee-save GPR restored");}
  const auto result=state.gpr.x0.qword;const int bytes=sshll_function_bytes(&sample,&before);check(result==sample.error&&sample.output==0&&sample.calls==1&&sample.shape==1&&sample.spill[0]==sshll_function_expected(sample.bits[0])&&sample.spill[1]==sshll_function_expected(sample.bits[1])&&bytes,"repaired original body, signed spill and defined memory outputs");uint64_t vector[2]{};std::memcpy(vector,&state.simd.v[0],16);check(vector[0]==sample.spill[0]&&vector[1]==sample.spill[1],"original q0 and actual STR q0 spill agree");
  std::printf("SSHLL-FDE seed=%u bits=%08x:%08x result=%08x out=%08x spill=%016llx:%016llx callbacks=%u shape=%u bytes=%u\n",seed,sample.bits[0],sample.bits[1],unsigned(result),sample.output,(unsigned long long)sample.spill[0],(unsigned long long)sample.spill[1],sample.calls,sample.shape,bytes);
 }
 std::printf("SSHLL-FDE-PASS checks=%u cases=256 State=1200 Memory64=8\n",checks);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"SSHLL original-function fixture: %s\n",e.what());return 91;}}
