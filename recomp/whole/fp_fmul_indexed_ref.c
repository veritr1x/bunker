#include <stdint.h>
typedef void (*multiply_fn)(uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
#define CASE(name,width,full) extern void name(uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
#include "fp_fmul_indexed_generated.h"
#undef CASE
struct Case{multiply_fn call;unsigned width,full;};
static const struct Case multiply_cases[]={
#define CASE(name,width,full) {name,width,full},
#include "fp_fmul_indexed_generated.h"
#undef CASE
};
#include "fp_fmul_indexed_driver.h"
static void invoke(unsigned index,uint8_t*out,const uint8_t*old,const uint8_t*lhs,const uint8_t*rhs,uint64_t fpcr,uint64_t status){multiply_cases[index].call(out,old,lhs,rhs,fpcr,status);}
int main(void){return run_multiply_cases(invoke);}
