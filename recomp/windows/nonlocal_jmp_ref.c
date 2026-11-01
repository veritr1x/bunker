#include "nonlocal_jmp_checks.h"
#include <stdio.h>
#include <stdlib.h>
extern void nonlocal_probe(uint64_t*,uint64_t*,uint64_t);
uint64_t __bionic_setjmp_cookie_get(uint64_t flag){if(flag>1)abort();return NJ_COOKIE|flag;}
uint64_t __bionic_setjmp_cookie_check(uint64_t cookie){if((cookie&~UINT64_C(1))!=NJ_COOKIE)abort();return cookie&1;}
void __bionic_setjmp_checksum_mismatch(void){abort();}
static uint64_t current_mask=NJ_MASK;
void reference_change_mask(void){current_mask=UINT64_C(0x200000);}
int reference_mask(int how,const void *set,void *old){if(old)memcpy(old,&current_mask,8);if(set){if(how!=2)abort();memcpy(&current_mask,set,8);}return 0;}
int main(void){
  uint64_t records[512];unsigned at=0;
  for(unsigned testcase=0;testcase<128;++testcase)for(unsigned kind=0;kind<4;++kind){
    uint64_t env[33] __attribute__((aligned(16))),before[33],out[66] __attribute__((aligned(16)));
    nj_inputs(env,out,testcase);memcpy(before,env,sizeof(env));
    nonlocal_probe(env,out,kind);records[at++]=nj_check(env,out,before,kind);
    if(records[at-1]){fprintf(stderr,"Bionic reference mismatch case%u kind%u bits%llx\n",testcase,kind,(unsigned long long)records[at-1]);return 1;}
  }
  for(unsigned testcase=0;testcase<32;++testcase)for(unsigned kind=4;kind<6;++kind){
    uint64_t env[33] __attribute__((aligned(16))),out[66] __attribute__((aligned(16)));
    nj_inputs(env,out,testcase);current_mask=NJ_MASK;
    nonlocal_probe(env,out,kind);
    if(out[32]!=(kind==4?UINT32_C(0xfffffff9):1)||out[46]!=out[12]||out[47]!=out[13])return 3;
    for(unsigned n=19;n<=29;++n)if(out[n-18]!=out[34+n-18])return 4;
    if(out[34]!=((UINT64_C(0xdead00000000beef)&~UINT64_C(8191))|(out[0]&8191)))return 5;
    for(unsigned n=8;n<=15;++n)if(out[48+2*(n-8)]!=out[16+2*(n-8)]||out[49+2*(n-8)])return 6;
    if(out[64]!=0x400000||out[65]!=0x9f||current_mask!=(kind==4?NJ_MASK:UINT64_C(0x200000)))return 7;
  }
  // Both variants leave the current FP environment; restore before host libc.
  __asm__ volatile("msr fpcr,xzr;msr fpsr,xzr");
  return fwrite(records,sizeof(records),1,stdout)==1?0:2;
}
