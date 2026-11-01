#include <cstdlib>
#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#define CASE(name) #name,
static const char *case_names[] = {
#include "generated_cases.h"
};
#undef CASE
#include "semantic_cases.h"

static recomp::Runtime runtime;
static elf_image image;
alignas(16) static uint8_t stack[1 << 20];
static void call(const char *name, uint8_t *out, const uint8_t *in, uint64_t step) {
    State state{};
    state.gpr.x0.qword = reinterpret_cast<addr_t>(out);
    state.gpr.x1.qword = reinterpret_cast<addr_t>(in);
    state.gpr.x2.qword = step;
    state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + sizeof(stack));
    state.gpr.x30.qword = 0xfeedffff;
    auto entry = reinterpret_cast<addr_t>(elf_symbol(&image, name));
    if (!entry) std::abort();
    state.gpr.pc.qword = entry;
    runtime.Run(state, entry);
    if (state.gpr.pc.qword != 0xfeedffff || state.gpr.sp.qword != reinterpret_cast<addr_t>(stack + sizeof(stack)))
        std::abort();
}
int main() {
    if (elf_load(SEMANTIC_LIB, 0x30000000, [](const char *) -> void * { return nullptr; }, &image)) return 1;
    runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
    return run_semantic_cases(call);
}
