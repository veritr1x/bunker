#include "st3_records.h"
#define CASE(name,w,e,t,n,m,r,o) extern void name(uint8_t*,const uint8_t*,uint8_t*,uint64_t);
#include "st3_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*,uint8_t*,uint64_t)={
#define CASE(name,w,e,t,n,m,r,o) name,
#include "st3_cases.h"
#undef CASE
};
extern void st3_native_wrapper(void(*)(uint8_t*,const uint8_t*,uint8_t*,uint64_t),uint8_t*,const uint8_t*,uint8_t*,uint64_t);
static void call(unsigned n,uint8_t*out,const uint8_t*in,uint8_t*memory,uint64_t step){st3_native_wrapper(functions[n],out,in,memory,step);}
__thread unsigned char st3_tls_anchor[64]__attribute__((aligned(64)));
int main(void){st3_tls_anchor[0]=39;if(st3_tls_anchor[0]!=39)return 39;int r=run_st3_records(call);if(r){fprintf(stderr,"ST3 reference error %d\n",r);return r;}puts("ST3-REFERENCE-SUCCESS");return 0;}
