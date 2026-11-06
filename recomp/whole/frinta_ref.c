#include <stdint.h>
#include <stdio.h>
#include "frinta_records.h"
static _Thread_local __attribute__((aligned(64))) volatile unsigned frinta_tls_alignment;
#define CASE(name,width,rd,rn) extern void name(uint8_t*,const uint8_t*);
#include "frinta_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*)={
#define CASE(name,width,rd,rn) name,
#include "frinta_cases.h"
#undef CASE
};
extern void frinta_native_wrapper(void(*)(uint8_t*,const uint8_t*),uint8_t*,const uint8_t*);
extern void frinta_control_copy(const uint32_t*,uint32_t*);
static void call(unsigned n,uint8_t*out,const uint8_t*in){frinta_native_wrapper(functions[n],out,in);}
int main(void){frinta_tls_alignment=17;if(frinta_tls_alignment!=17)return 31;uint32_t source=0x7f812345,destination=0;frinta_control_copy(&source,&destination);if(destination!=source)return 30;int result=run_frinta_records(call);if(result)return result;puts("FRINTA-REFERENCE-SUCCESS actual_Bionic=1 memory_control=1");return 0;}
