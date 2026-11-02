#include <stdint.h>
#include <stdio.h>
#include "frint_records.h"
#define CASE(name,width,rd,rn,rm,cond,original) extern void name(uint8_t*,const uint8_t*);
#include "frint_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*)={
#define CASE(name,width,rd,rn,rm,cond,original) name,
#include "frint_cases.h"
#undef CASE
};
extern void frint_native_wrapper(void(*)(uint8_t*,const uint8_t*),uint8_t*,const uint8_t*);
extern void frint_control_copy(const uint32_t*,uint32_t*);
static void call(unsigned n,uint8_t*out,const uint8_t*in){frint_native_wrapper(functions[n],out,in);}
int main(void){uint32_t source=0x7f812345,destination=0;frint_control_copy(&source,&destination);if(destination!=source)return 30;int result=run_frint_records(call);if(result)return result;puts("FRINT-REFERENCE-SUCCESS memory_control=1");return 0;}
