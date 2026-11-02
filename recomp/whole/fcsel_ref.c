#include <stdint.h>
#include <stdio.h>
#include "fcsel_records.h"
#define CASE(name,width,rd,rn,rm,cond,original) extern void name(uint8_t*,const uint8_t*);
#include "fcsel_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*)={
#define CASE(name,width,rd,rn,rm,cond,original) name,
#include "fcsel_cases.h"
#undef CASE
};
extern void fcsel_native_wrapper(void(*)(uint8_t*,const uint8_t*),uint8_t*,const uint8_t*);
extern void fcsel_control_copy(const uint32_t*,uint32_t*);
static void call(unsigned n,uint8_t*out,const uint8_t*in){fcsel_native_wrapper(functions[n],out,in);}
int main(void){uint32_t source=0x7f812345,destination=0;fcsel_control_copy(&source,&destination);if(destination!=source)return 30;int result=run_fcsel_records(call);if(result)return result;puts("FCSEL-REFERENCE-SUCCESS memory_control=1");return 0;}
