#include <cstdlib>
#include "runtime.h"
#include "elfload.h"
#include "traces.h"
#define CASE(name, width) #name,
static const char *fp_case_names[] = {
#include "fp_generated_cases.h"
};
#undef CASE
#define CASE(name, width) width,
static const unsigned fp_case_widths[] = {
#include "fp_generated_cases.h"
};
#undef CASE
#ifndef FP_CASE_DRIVER
#define FP_CASE_DRIVER "fp_compare_driver.h"
#endif
#include FP_CASE_DRIVER
static recomp::Runtime runtime;
static elf_image image;
alignas(16) static uint8_t stack[1 << 18];
static void call(const char *name, uint8_t *out, const uint8_t *left, const uint8_t *right, uint64_t fpcr, uint64_t fpsr) {
    State state{};
    state.gpr.x0.qword = reinterpret_cast<addr_t>(out);
    state.gpr.x1.qword = reinterpret_cast<addr_t>(left);
    state.gpr.x2.qword = reinterpret_cast<addr_t>(right);
    state.gpr.x3.qword = fpcr;
    state.gpr.x4.qword = fpsr;
    state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + sizeof(stack));
    state.gpr.x30.qword = 0xfeedffff;
    auto entry = reinterpret_cast<addr_t>(elf_symbol(&image, name));
    if (!entry) std::abort();
    state.gpr.pc.qword = entry;
    runtime.Run(state, entry);
    if (state.gpr.pc.qword != 0xfeedffff || state.gpr.sp.qword != reinterpret_cast<addr_t>(stack + sizeof(stack))) std::abort();
}
int main() {
    if (elf_load(FP_COMPARE_LIBRARY, 0x50000000, [](const char *) -> void * { return nullptr; }, &image)) return 1;
    runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
    return run_fp_compare_cases(call);
}
