#include "vector_neg_4s_cases.h"
extern void neg_actual(const void*,void*),neg_distinct(const void*,void*),neg4_actual(const void*,void*),neg4_distinct(const void*,void*);
extern void neg4_native_call(void(*)(const void*,void*),const void*,void*,const struct NegProfile*,struct NegStatus*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned count=0;void(*kernels[])(const void*,void*)={neg_actual,neg_distinct,neg4_actual,neg4_distinct};
 for(unsigned shape=0;shape<NEG_SHAPES;shape++)for(unsigned n=0;n<NEG_SAMPLES;n++)for(unsigned alias=0;alias<2;alias++)for(unsigned p=0;p<NEG_PROFILES;p++){
  _Alignas(16)struct NegGuard in,out;uint32_t value[4];neg_seed(n,&in,&out,value);struct NegGuard before_in=in,before_out=out;struct NegStatus status={0};neg4_native_call(kernels[shape],in.bytes+16,(alias?in.bytes:out.bytes)+16,&neg_profiles[p],&status);
  if(!neg_canaries(&in,&out,&before_in,&before_out,value,shape,alias)||!status.abi||status.fpcr!=neg_profiles[p].fpcr||status.fpsr!=neg_profiles[p].fpsr||status.nzcv!=neg_profiles[p].nzcv)return 2;neg_record(shape,n,alias,p,&in,&out,&status);++count;
 }printf("NEG4S-ORIGINAL-PASS records=%u TLS=%u\n",count,tls_canary);return tls_canary!=17||count!=NEG_RECORDS;}
