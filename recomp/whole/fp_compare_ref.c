#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define CASE(name, width) extern void name(uint8_t *, const uint8_t *, const uint8_t *, uint64_t, uint64_t);
#include "fp_generated_cases.h"
#undef CASE
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
#define CASE(name, width) name,
static void (*functions[])(uint8_t *, const uint8_t *, const uint8_t *, uint64_t, uint64_t) = {
#include "fp_generated_cases.h"
};
#undef CASE
#ifndef FP_CASE_DRIVER
#define FP_CASE_DRIVER "fp_compare_driver.h"
#endif
#include FP_CASE_DRIVER
static void call(const char *name, uint8_t *out, const uint8_t *left, const uint8_t *right, uint64_t fpcr, uint64_t fpsr) {
    for (unsigned i = 0; i < sizeof(fp_case_names) / sizeof(fp_case_names[0]); ++i)
        if (!strcmp(name, fp_case_names[i])) { functions[i](out, left, right, fpcr, fpsr); return; }
    abort();
}
int main(void) { return run_fp_compare_cases(call); }
