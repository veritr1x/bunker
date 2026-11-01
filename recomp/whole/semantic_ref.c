#include <stdlib.h>
#include <string.h>
#define CASE(name) extern void name(uint8_t *, const uint8_t *, uint64_t);
#include <stdint.h>
#include "generated_cases.h"
#undef CASE
#define CASE(name) #name,
static const char *case_names[] = {
#include "generated_cases.h"
};
#undef CASE
#include "semantic_cases.h"
#define CASE(name) name,
static void (*functions[])(uint8_t *, const uint8_t *, uint64_t) = {
#include "generated_cases.h"
};
#undef CASE
static void call(const char *name, uint8_t *out, const uint8_t *in, uint64_t step) {
    for (unsigned i = 0; i < sizeof(case_names) / sizeof(case_names[0]); ++i)
        if (!strcmp(name, case_names[i])) { functions[i](out, in, step); return; }
    abort();
}
int main(void) { return run_semantic_cases(call); }
