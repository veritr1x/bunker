#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "snapshot_switch_driver.h"
#include <cstdlib>
static recomp::Runtime runtime;
static elf_image image;
alignas(16)static uint8_t stack[1<<18];
static uint64_t Call(uint64_t index,uint64_t seed){
 State state{};state.gpr.x0.qword=index;state.gpr.x1.qword=seed;
 state.gpr.x19.qword=UINT64_C(0x9876543210abcdef);
 state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));state.gpr.x30.qword=0xfeedffff;
 runtime.Run(state,reinterpret_cast<addr_t>(elf_symbol(&image,"snapshot_switch_dispatch")));
 if(state.gpr.pc.qword!=0xfeedffff||state.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack))||state.gpr.x19.qword!=UINT64_C(0x9876543210abcdef))std::abort();
 return state.gpr.x0.qword;
}
int main(){
 if(elf_load(SWITCH_LIBRARY,0x50000000,[](const char*)->void*{return nullptr;},&image))return 1;
 runtime.AddTraces(kTraces,std::size(kTraces));return run_snapshot_switch(Call);
}
