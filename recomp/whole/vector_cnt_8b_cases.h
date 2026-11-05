#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct CntGuard{unsigned char bytes[128];};
struct CntProfile{uint64_t fpcr,fpsr,nzcv;};
struct CntStatus{uint64_t fpcr,fpsr,nzcv,abi;};
static const struct CntProfile cnt_profiles[]={{0,0,0},{0x00400000,0x0800009f,0xa0000000},{0x01800000,0x80,0x50000000},{0x03c00000,0x08000000,0xf0000000}};
enum{CNT_SAMPLES=272,CNT_SHAPES=6,CNT_PROFILES=4,CNT_RECORDS=13056};
static void cnt_inputs(unsigned n,uint32_t value[4]){static const unsigned char edges[]={0,255,1,128,127,85,170,3,252,15,240,129,126,51,204,254};unsigned char*bytes=(unsigned char*)value;for(unsigned i=0;i<16;i++)bytes[i]=(unsigned char)(n<256?n+i*37:edges[n-256]);}
static void cnt_seed(unsigned n,struct CntGuard*in,struct CntGuard*out,uint32_t value[4]){for(unsigned i=0;i<128;i++){in->bytes[i]=(unsigned char)(i*37+n*11);out->bytes[i]=(unsigned char)(i*29+n*17+3);}cnt_inputs(n,value);for(unsigned i=0;i<56;i++)in->bytes[16+i]=((unsigned char*)value)[i%16];}
static const unsigned cnt_rd[]={0,3,0,0,3,0},cnt_rn[]={0,5,0,0,5,0};
static void cnt_expected(unsigned shape,const unsigned char*in,unsigned char out[16]){memset(out,0,16);unsigned sum=0;for(unsigned i=0;i<8;i++){unsigned n=0;for(unsigned b=0;b<8;b++)n+=(in[i]>>b)&1;out[i]=(unsigned char)n;sum+=n;}if(shape>=2){if(shape>=3){sum=0;for(unsigned i=0;i<8;i++)sum+=in[i];}if(shape==5){sum=0;for(unsigned i=0;i<56;i++)for(unsigned b=0;b<8;b++)sum+=(in[i]>>b)&1;}memset(out,0,16);out[0]=(unsigned char)sum;out[1]=(unsigned char)(sum>>8);}}
static int cnt_canaries(const struct CntGuard*in,const struct CntGuard*out,const struct CntGuard*before_in,const struct CntGuard*before_out,const uint32_t value[4],unsigned shape,unsigned alias){struct CntGuard a=*before_in,b=*before_out;unsigned char result[16];(void)value;cnt_expected(shape,before_in->bytes+16,result);memcpy((alias?a.bytes:b.bytes)+16,result,shape==5?4:16);return!memcmp(in,&a,sizeof(a))&&!memcmp(out,&b,sizeof(b));}
static void cnt_record(unsigned shape,unsigned n,unsigned alias,unsigned profile,const struct CntGuard*in,const struct CntGuard*out,const struct CntStatus*status){printf("REC %u %u %u %u ",shape,n,alias,profile);const unsigned char*parts[]={(const unsigned char*)in,(const unsigned char*)out,(const unsigned char*)status};const unsigned sizes[]={128,128,32};for(unsigned j=0;j<3;j++){for(unsigned i=0;i<sizes[j];i++)printf("%02x",parts[j][i]);}putchar('\n');}
