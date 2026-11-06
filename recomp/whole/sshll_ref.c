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
#include "sshll_records.h"
extern void sshll_native_wrapper(void (*)(uint8_t *,const uint8_t *),uint8_t *,const uint8_t *);
static void call(const char *name,uint8_t *output,const uint8_t *input){
  static const char *previous;static unsigned cached;
  if(previous==name){sshll_native_wrapper(functions[cached],output,input);return;}
  for(unsigned n=0;n<sizeof(case_names)/sizeof(case_names[0]);++n)
    if(!strcmp(name,case_names[n])){previous=name;cached=n;sshll_native_wrapper(functions[n],output,input);return;}
  abort();
}
static _Thread_local __attribute__((aligned(64))) volatile unsigned sshll_tls;
int main(void){sshll_tls=17;if(sshll_tls!=17)return 9;return run_sshll_records(call);}
