#include <stdint.h>
typedef void (*fmla_fn)(uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
#define CASE(name,width,exhaustive,d,n,m,lanes,index) extern void name(uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
#include "fp_fmla_generated.h"
#undef CASE
struct Case{fmla_fn call;unsigned width,exhaustive;};
static const struct Case fmla_cases[]={
#define CASE(name,width,exhaustive,d,n,m,lanes,index) {name,width,exhaustive},
#include "fp_fmla_generated.h"
#undef CASE
};
#include "fp_fmla_driver.h"
static void invoke(unsigned index,uint8_t*out,const uint8_t*acc,const uint8_t*lhs,const uint8_t*rhs,uint64_t fpcr,uint64_t status){
  fmla_cases[index].call(out,acc,lhs,rhs,fpcr,status);
}
int main(void){return run_fmla_cases(invoke);}
