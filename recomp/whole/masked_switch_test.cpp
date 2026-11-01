#include <cstdlib>
#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#include "masked_switch_driver.h"
static recomp::Runtime runtime;
static elf_image image;
alignas(16) static uint8_t stack[1<<18];
static uint64_t call(uint64_t selector,uint64_t value) {
    State state{};
    state.gpr.x0.qword=selector;state.gpr.x1.qword=value;
    state.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
    state.gpr.x30.qword=0xfeedffff;
    auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,"masked_switch_dispatch"));
    runtime.Run(state,entry);
    if(state.gpr.pc.qword!=0xfeedffff||state.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))std::abort();
    return state.gpr.x0.qword;
}
int main() {
    if(elf_load(SWITCH_LIBRARY,0x50000000,[](const char*)->void*{return nullptr;},&image))return 1;
    runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(kTraces[0]));
    return run_masked_switch(call);
}
