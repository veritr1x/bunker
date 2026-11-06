#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define NMC_BASE UINT64_C(0x56000000)
#define NMC_ARENA 65536
#define NMC_SP (NMC_BASE+0x2000)
#define NMC_ENTRY UINT64_C(0x841e55d0)
#define NMC_STOP UINT64_C(0x841e55f0)
#define NMC_RETURN UINT64_C(0x6f00fffc)
typedef struct{uint64_t x[32],nzcv,pad,v[64],pc,fpsr,fpcr;}NMCRegisters;
static void nmc_u32(uint64_t address,uint32_t value){memcpy((void*)(uintptr_t)address,&value,4);}
static void nmc_u64(uint64_t address,uint64_t value){memcpy((void*)(uintptr_t)address,&value,8);}
static uint64_t nmc_hash(const void*data,size_t bytes){const unsigned char*p=(const unsigned char*)data;uint64_t h=UINT64_C(1469598103934665603);for(size_t n=0;n<bytes;n++){h^=p[n];h*=UINT64_C(1099511628211);}return h;}
static void nmc_setup(NMCRegisters*r,unsigned pair,unsigned mode,unsigned sticky){
 const unsigned seed=(mode*2+sticky)*32+pair;unsigned char*p=(unsigned char*)(uintptr_t)NMC_BASE;for(unsigned n=0;n<NMC_ARENA;n++)p[n]=(unsigned char)(0xadu^(seed*19u+n*37u));memset(r,0,sizeof(*r));
 for(unsigned n=0;n<31;n++)r->x[n]=UINT64_C(0x123456789abcdef0)^((uint64_t)(n+1)*UINT64_C(0x9e3779b97f4a7c15))^seed;
 for(unsigned n=0;n<64;n++)r->v[n]=UINT64_C(0xfedcba9876543210)^((uint64_t)(n+1)*UINT64_C(0x102040810204081))^seed;
 static const uint32_t values[]={0,0x80000000,0x3f800000,0xbf800000,0x3e800000,0xbe800000,0x7f800000,0xff800000,0x7fc12345,0xffc23456,0x7f800123,0xff800456,1,0x80000001,0x007fffff,0x807fffff};
 uint32_t a=values[pair%16],b=values[pair<16?(pair*5+3)%16:pair%16];memcpy((unsigned char*)r->v+13*16,&a,4);memcpy((unsigned char*)r->v+14*16,&b,4);uint32_t constants[]={0x40800000,0x40000000,0x3f800000};for(unsigned n=0;n<3;n++)memcpy((unsigned char*)r->v+(n+9)*16,&constants[n],4);
 r->x[11]=NMC_BASE+0x4000;r->x[30]=NMC_RETURN;r->x[31]=NMC_SP;r->nzcv=(uint64_t)((pair^mode^sticky*9)&15)<<28;r->fpsr=sticky?UINT64_C(0x0800009f):0;r->fpcr=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22);r->pc=NMC_ENTRY;
 nmc_u32(NMC_SP+0x5c,0x3f000000);nmc_u32(r->x[11]+0x7e0,0x3e800000);for(unsigned n=0;n<8;n++)nmc_u64(NMC_BASE+0xa000+n*8,UINT64_C(0x102030405060708)*(n+1));memcpy((void*)(uintptr_t)NMC_BASE,r,sizeof(*r));memset((void*)(uintptr_t)(NMC_BASE+0x8000),0,sizeof(*r));
}
static uint32_t nmc_maxnum_zero(uint32_t value,uint64_t fpcr,uint64_t*fpsr){
 const uint32_t sign=0x80000000,exponent=0x7f800000,fraction=0x007fffff,quiet=0x00400000;
 if(!(value&exponent)&&(value&fraction)&&(fpcr&(UINT64_C(1)<<24))){*fpsr|=128;value&=sign;}
 if((value&exponent)==exponent&&(value&fraction)){if(!(value&quiet)){*fpsr|=1;return(fpcr&(UINT64_C(1)<<25))?exponent|quiet:value|quiet;}return 0;}
 return value&sign?0:value;
}
static NMCRegisters nmc_expected(const NMCRegisters*input){
 NMCRegisters expected=*input;expected.pc=NMC_STOP;uint32_t raw[6]={0,0,0x3e800000,0x3f000000,0,0x40400000};memcpy(&raw[1],(const unsigned char*)input->v+13*16,4);memcpy(&raw[4],(const unsigned char*)input->v+14*16,4);raw[1]=nmc_maxnum_zero(raw[1],input->fpcr,&expected.fpsr);raw[4]=nmc_maxnum_zero(raw[4],input->fpcr,&expected.fpsr);static const unsigned destinations[]={0,1,2,3,6,7};for(unsigned n=0;n<6;n++){memset((unsigned char*)expected.v+destinations[n]*16,0,16);memcpy((unsigned char*)expected.v+destinations[n]*16,&raw[n],4);}return expected;
}
static int nmc_guards(const unsigned char*before){const unsigned char*p=(const unsigned char*)(uintptr_t)NMC_BASE;for(unsigned n=0;n<NMC_ARENA;n++){if((n>=0x1f00&&n<0x2000)||(n>=0x8000&&n<0x8000+sizeof(NMCRegisters)))continue;if(p[n]!=before[n])return 0;}return 1;}
static void nmc_print(unsigned pair,unsigned mode,unsigned sticky,const NMCRegisters*r){uint32_t inputs[2],outputs[2];memcpy(&inputs[0],(const unsigned char*)r->v+13*16,4);memcpy(&inputs[1],(const unsigned char*)r->v+14*16,4);memcpy(&outputs[0],(const unsigned char*)r->v+1*16,4);memcpy(&outputs[1],(const unsigned char*)r->v+6*16,4);printf("NUMERIC-CLUSTER pair=%u mode=%u sticky=%u input=%08x:%08x output=%08x:%08x FPSR=%08x FPCR=%08x NZCV=%08x snapshot=%016llx\n",pair,mode,sticky,inputs[0],inputs[1],outputs[0],outputs[1],(unsigned)r->fpsr,(unsigned)r->fpcr,(unsigned)r->nzcv,(unsigned long long)nmc_hash(r,sizeof(*r)));}
