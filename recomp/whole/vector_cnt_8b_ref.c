#include "vector_cnt_8b_cases.h"
extern void cnt_actual(const void*,void*),cnt_distinct(const void*,void*),cnt_sum(const void*,void*),uadd_actual(const void*,void*),uadd_distinct(const void*,void*),cnt_loop56(const void*,void*);
extern void cnt8_native_call(void(*)(const void*,void*),const void*,void*,const struct CntProfile*,struct CntStatus*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned count=0;void(*kernels[])(const void*,void*)={cnt_actual,cnt_distinct,cnt_sum,uadd_actual,uadd_distinct,cnt_loop56};
 for(unsigned shape=0;shape<CNT_SHAPES;shape++)for(unsigned n=0;n<CNT_SAMPLES;n++)for(unsigned alias=0;alias<2;alias++)for(unsigned p=0;p<CNT_PROFILES;p++){
  _Alignas(16)struct CntGuard in,out;uint32_t value[4];cnt_seed(n,&in,&out,value);struct CntGuard before_in=in,before_out=out;struct CntStatus status={0};cnt8_native_call(kernels[shape],in.bytes+16,(alias?in.bytes:out.bytes)+16,&cnt_profiles[p],&status);
  if(!cnt_canaries(&in,&out,&before_in,&before_out,value,shape,alias)||!status.abi||status.fpcr!=cnt_profiles[p].fpcr||status.fpsr!=cnt_profiles[p].fpsr||status.nzcv!=(shape==5?0x60000000:cnt_profiles[p].nzcv))return 2;cnt_record(shape,n,alias,p,&in,&out,&status);++count;
 }printf("CNT8B-ORIGINAL-PASS records=%u TLS=%u\n",count,tls_canary);return tls_canary!=17||count!=CNT_RECORDS;}
