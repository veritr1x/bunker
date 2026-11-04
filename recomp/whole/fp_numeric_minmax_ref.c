#include <stdint.h>
#include <stdio.h>
#include "fp_numeric_minmax_records.h"
#define CASE(name,width,rd,rn,rm,maximum) extern void name(uint8_t*,const uint8_t*);
#include "fp_numeric_minmax_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*)={
#define CASE(name,width,rd,rn,rm,maximum) name,
#include "fp_numeric_minmax_cases.h"
#undef CASE
};
extern void fp_numeric_minmax_native_wrapper(void(*)(uint8_t*,const uint8_t*),uint8_t*,const uint8_t*);
extern void fp_numeric_minmax_control_copy(const uint32_t*,uint32_t*);
static void call(unsigned n,uint8_t*out,const uint8_t*in){fp_numeric_minmax_native_wrapper(functions[n],out,in);}
int main(void){uint32_t source=0x7f812345,destination=0;fp_numeric_minmax_control_copy(&source,&destination);if(destination!=source)return 30;int result=run_numeric_records(call);if(result)return result;puts("FP_NUMERIC_MINMAX-REFERENCE-SUCCESS memory_control=1");return 0;}
