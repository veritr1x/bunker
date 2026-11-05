#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct NegGuard{unsigned char bytes[64];};
struct NegProfile{uint64_t fpcr,fpsr,nzcv;};
struct NegStatus{uint64_t fpcr,fpsr,nzcv,abi;};
static const struct NegProfile neg_profiles[]={{0,0,0},{0x00400000,0x0800009f,0xa0000000},{0x01800000,0x80,0x50000000},{0x03c00000,0x08000000,0xf0000000}};
static const uint32_t neg_edges[]={0,1,0xffffffffU,0x80000000U,0x7fffffffU,0x80000001U,0x00008000U,0xffff8000U,0x12345678U,0x89abcdefU,8,16};
enum{NEG_SAMPLES=272,NEG_SHAPES=2,NEG_PROFILES=4,NEG_RECORDS=4352};
static uint32_t neg_random(uint32_t*x){*x^=*x<<13;*x^=*x>>17;*x^=*x<<5;return*x;}
static void neg_inputs(unsigned n,uint32_t value[4]){if(n<144){value[0]=neg_edges[n/12];value[1]=neg_edges[n%12];}else{uint32_t x=0x9e3779b9U^(n*0x85ebca6bU);value[0]=neg_random(&x);value[1]=neg_random(&x);}value[2]=0x89abcdefU^n;value[3]=0xfedcba98U^(n*17);}
static void neg_seed(unsigned n,struct NegGuard*in,struct NegGuard*out,uint32_t value[4]){for(unsigned i=0;i<64;i++){in->bytes[i]=(unsigned char)(i*37+n*11);out->bytes[i]=(unsigned char)(i*29+n*17+3);}neg_inputs(n,value);memcpy(in->bytes+16,value,16);}
static void neg_expected(const uint32_t value[4],unsigned char out[16]){uint32_t result[4]={0U-value[0],0U-value[1],0,0};memcpy(out,result,16);}
static int neg_canaries(const struct NegGuard*in,const struct NegGuard*out,const struct NegGuard*before_in,const struct NegGuard*before_out,const uint32_t value[4],unsigned alias){struct NegGuard a=*before_in,b=*before_out;unsigned char result[16];neg_expected(value,result);memcpy((alias?a.bytes:b.bytes)+16,result,16);return!memcmp(in,&a,sizeof(a))&&!memcmp(out,&b,sizeof(b));}
static void neg_record(unsigned shape,unsigned n,unsigned alias,unsigned profile,const struct NegGuard*in,const struct NegGuard*out,const struct NegStatus*status){printf("REC %u %u %u %u ",shape,n,alias,profile);const unsigned char*parts[]={(const unsigned char*)in,(const unsigned char*)out,(const unsigned char*)status};const unsigned sizes[]={64,64,32};for(unsigned j=0;j<3;j++){for(unsigned i=0;i<sizes[j];i++)printf("%02x",parts[j][i]);}putchar('\n');}
