#include "st2_records.h"
#define CASE(name,w,e,t,n,m,r,o) extern void name(uint8_t*,const uint8_t*,uint8_t*,uint64_t);
#include "st2_cases.h"
#undef CASE
static void(*const functions[])(uint8_t*,const uint8_t*,uint8_t*,uint64_t)={
#define CASE(name,w,e,t,n,m,r,o) name,
#include "st2_cases.h"
#undef CASE
};
extern void st2_native_wrapper(void(*)(uint8_t*,const uint8_t*,uint8_t*,uint64_t),uint8_t*,const uint8_t*,uint8_t*,uint64_t);
static void call(unsigned n,uint8_t*out,const uint8_t*in,uint8_t*memory,uint64_t step){st2_native_wrapper(functions[n],out,in,memory,step);}
__thread unsigned char st2_tls_anchor[64]__attribute__((aligned(64)));
int main(void){st2_tls_anchor[0]=39;if(st2_tls_anchor[0]!=39)return 39;int r=run_st2_records(call);if(r){fprintf(stderr,"ST2 reference error %d\n",r);return r;}puts("ST2-REFERENCE-SUCCESS");return 0;}
