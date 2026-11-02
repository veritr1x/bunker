#define _GNU_SOURCE
#include <sys/mman.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "prefetch_records.h"
#define CASE(name,word,rn,misalign) extern void name(uint8_t*,const uint8_t*);
#include "prefetch_cases.h"
#undef CASE
static void (*const functions[])(uint8_t*,const uint8_t*)={
#define CASE(name,word,rn,misalign) name,
#include "prefetch_cases.h"
#undef CASE
};
extern void prefetch_native_wrapper(void(*)(uint8_t*,const uint8_t*),uint8_t*,const uint8_t*);
extern uint64_t prefetch_control_load(const void*);
extern void prefetch_control_store(void*,uint64_t);
#define CASE(name,word,rn,misalign) extern uint32_t exclusive_##name(uint64_t*);
#include "prefetch_cases.h"
#undef CASE
static uint32_t(*const exclusive_functions[])(uint64_t*)={
#define CASE(name,word,rn,misalign) exclusive_##name,
#include "prefetch_cases.h"
#undef CASE
};
static void call(unsigned n,uint8_t*out,const uint8_t*in){prefetch_native_wrapper(functions[n],out,in);}
int main(int argc,char**argv){
 void*guard=mmap(0,65536,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(guard==MAP_FAILED)return 10;
 if(argc==2&&!strcmp(argv[1],"--fault-load")){
  uint64_t value=prefetch_control_load(guard);
  printf("UNEXPECTED-LOAD-RETURN %llu\n",(unsigned long long)value);return 11;
 }
 int result=run_prefetch_records(call,(uintptr_t)guard);
 if(result)return result;
 uint64_t memory=UINT64_C(0x76543210abcdef98);
 if(prefetch_control_load(&memory)!=memory)return 13;
 prefetch_control_store(&memory,UINT64_C(0x1122446688aaccff));
 if(memory!=UINT64_C(0x1122446688aaccff))return 14;
 unsigned failures=0;
 for(unsigned n=0;n<CASE_COUNT;++n){unsigned retry;
  for(retry=0;retry<10000;++retry){
   if(!exclusive_functions[n](&memory))break;
   ++failures;
  }
  if(retry==10000||memory!=UINT64_C(0x1122446688aaccff))return 15;
 }
 if(munmap(guard,65536))return 12;
 printf("PREFETCH-REFERENCE-SUCCESS exclusive=%u retries=%u ordinary=2\n",CASE_COUNT,failures);
 return result;
}
