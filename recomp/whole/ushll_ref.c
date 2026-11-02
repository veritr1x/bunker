#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define CASE(name) extern void name(uint8_t *, const uint8_t *);
#include "generated_cases.h"
#undef CASE
#define CASE(name) #name,
static const char *case_names[]={
#include "generated_cases.h"
};
#undef CASE
#define CASE(name) name,
static void (*functions[])(uint8_t *,const uint8_t *)={
#include "generated_cases.h"
};
#undef CASE
#include "ushll_records.h"
extern void ushll_native_wrapper(void (*)(uint8_t *,const uint8_t *),uint8_t *,const uint8_t *);
static void call(const char *name,uint8_t *output,const uint8_t *input){
  for(unsigned n=0;n<sizeof(case_names)/sizeof(case_names[0]);++n)
    if(!strcmp(name,case_names[n])){ushll_native_wrapper(functions[n],output,input);return;}
  abort();
}
int main(void){return run_ushll_records(call);}
