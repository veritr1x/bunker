#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#define U17_BASE UINT64_C(0x57000000)
#define U17_ARENA 65536
#define U17_DATA 49152
#define U17_OBJECT (U17_BASE+0x1000)
#define U17_OUT (U17_BASE+0x7000)
#define U17_CALLBACK UINT64_C(0x6f00fe00)
#define U17_RETURN UINT64_C(0x6f00fffc)
typedef struct u17_abi {uint64_t gpr[11],d[8],v0[2],nzcv,LR_good;}u17_abi;
typedef struct u17_case {unsigned id,type,index,seed,ready,expected,calls,shape;unsigned char output[36];u17_abi before,after;}u17_case;
static void u17_u64(uint64_t a,uint64_t v){memcpy((void*)(uintptr_t)a,&v,8);}
static void u17_u32(uint64_t a,uint32_t v){memcpy((void*)(uintptr_t)a,&v,4);}
static void u17_rel(uint64_t slot,uint64_t target){u17_u64(slot,target-slot);}
static uint64_t u17_hash(const void*p,size_t n){const unsigned char*b=(const unsigned char*)p;uint64_t h=UINT64_C(1469598103934665603);for(size_t i=0;i<n;i++){h^=b[i];h*=UINT64_C(1099511628211);}return h;}
static void u17_setup(u17_case*c,unsigned id){
 memset(c,0,sizeof(*c));c->id=id;c->type=id<64?id/16:0;c->seed=id<64?id%16:id;c->index=c->seed%4;c->ready=1;c->expected=id<64;
 unsigned component=c->seed%4,count=4,enabled=1;
 if(id>=64&&id<76){c->type=(id-64)/3;component=(uint32_t[]){4,0xffffffffu,0x80000000u}[(id-64)%3];}
 else if(id==76){c->type=1;enabled=0;}
 else if(id>=77&&id<81){c->type=id-77;c->ready=0;}
 else if(id>=81&&id<84)c->type=(uint32_t[]){4,0xffffffffu,0x80000000u}[id-81];
 else if(id>=84){c->type=id-84;count=0;}
 unsigned char*p=(unsigned char*)(uintptr_t)U17_BASE;for(unsigned n=0;n<U17_ARENA;n++)p[n]=(unsigned char)(0xadu^(n*13u+c->seed*29u));
 u17_u64(U17_OBJECT,U17_BASE+0x2000);u17_u64(U17_BASE+0x2130,U17_CALLBACK);u17_u64(U17_OBJECT+0x128,U17_BASE+0x3000);u17_u64(U17_OBJECT+0x138,U17_BASE+0x4000);
 u17_u32(U17_BASE+0x3000,4);u17_rel(U17_BASE+0x3008,U17_BASE+0x3100);u17_rel(U17_BASE+0x3018,U17_BASE+0x3200);u17_rel(U17_BASE+0x4008,U17_BASE+0x4100);
 static const uint32_t floatbits[]={0,0x80000000,0x3f800000,0xbf800000,0x7f800000,0xff800000,0x7fc01234,0x7f800001,1,0x007fffff,0x00800000,0x7f7fffff,0x3eaaaaab,0x41234567,0xc1234567,0xffffffff};
 for(unsigned i=0;i<4;i++){
  u17_rel(U17_BASE+0x3100+i*8,U17_BASE+0x3300+i*4);u17_u32(U17_BASE+0x3300+i*4,i);u17_rel(U17_BASE+0x3200+i*8,U17_BASE+0x3400+i*0x80);u17_u32(U17_BASE+0x3400+i*0x80,count);u17_rel(U17_BASE+0x3408+i*0x80,U17_BASE+0x3800+i*0x80);u17_rel(U17_BASE+0x4100+i*8,U17_BASE+0x4200+i*0x100);
  uint64_t v=U17_BASE+0x4200+i*0x100;
  for(unsigned type=0;type<4;type++){
   u17_u32(v+0x10+type*4,component);u17_u32(v+(unsigned[]){0x2c,0x30,0x38,0x34}[type],floatbits[(c->seed+type*3)%16]);u17_u32(v+(unsigned[]){0x3c,0x40,0x48,0x4c}[type],0x12340000u+c->seed*31u+type*0x100u+i);u17_u32(v+0x50+type*4,floatbits[(c->seed+type*5+7)%16]);
   uint64_t r=U17_BASE+0x5000+(i*4+type)*0x80;u17_rel(U17_BASE+0x3800+i*0x80+type*8,r);u17_u64(r+0x30,UINT64_C(0xfedcba9876543210)^((uint64_t)c->seed<<32)^i*0x100u^type);u17_u32(r+0x38,0x13570000u+c->seed*3u+type);u17_u32(r+0x3c,0xabcd0000u+c->seed*7u+type);u17_u32(r+0x50,0x87650000u+c->seed*11u+type);p[r-U17_BASE+0x5a]=(unsigned char)(c->seed*17u+type);
  }
  p[v-U17_BASE+0x71]=(unsigned char)enabled;
 }
 memcpy(c->output,(void*)(uintptr_t)U17_OUT,36);
 if(c->expected){uint64_t v=U17_BASE+0x4200+c->index*0x100,r=U17_BASE+0x5000+(c->index*4+component)*0x80;memcpy(c->output,(void*)(uintptr_t)(r+0x30),8);memcpy(c->output+8,(void*)(uintptr_t)(r+0x38),4);memcpy(c->output+12,(void*)(uintptr_t)(v+(unsigned[]){0x2c,0x30,0x38,0x34}[c->type]),4);memcpy(c->output+16,(void*)(uintptr_t)(v+(unsigned[]){0x3c,0x40,0x48,0x4c}[c->type]),4);memcpy(c->output+20,(void*)(uintptr_t)(r+0x50),4);memcpy(c->output+24,(void*)(uintptr_t)(v+0x50+c->type*4),4);memcpy(c->output+28,(void*)(uintptr_t)(r+0x3c),4);uint32_t byte=p[r-U17_BASE+0x5a];memcpy(c->output+32,&byte,4);}
 for(unsigned n=0;n<11;n++)c->before.gpr[n]=UINT64_C(0xabcddcba00000000)^((uint64_t)(n+1)*UINT64_C(0x102030405060708))^c->seed;
 for(unsigned n=0;n<8;n++)c->before.d[n]=UINT64_C(0x8765432100000000)^((uint64_t)(n+1)*UINT64_C(0x100204081020408))^c->seed;
 for(unsigned n=0;n<8;n++)u17_u64(U17_BASE+0xb000+n*8,UINT64_C(0x123456789abcdef0)*(n+1));u17_u64(U17_BASE+0xa028,UINT64_C(0xaabbccddeeff0011));
}
static int u17_check_memory(const unsigned char*before,const u17_case*c){
 const unsigned char*p=(const unsigned char*)(uintptr_t)U17_BASE;for(unsigned n=0;n<U17_DATA;n++){unsigned char expected=n>=0x7000&&n<0x7024?c->output[n-0x7000]:before[n];if(p[n]!=expected)return 0;}return 1;
}
static void u17_print(const u17_case*c,uint64_t result,uint32_t flags){
 printf("UNITY-117D id=%u type=%08x index=%u result=%llu callbacks=%u shape=%u nzcv=%08x mem=%016llx out=",c->id,c->type,c->index,(unsigned long long)result,c->calls,c->shape,flags,(unsigned long long)u17_hash((void*)(uintptr_t)U17_BASE,U17_DATA));
 const unsigned char*p=(const unsigned char*)(uintptr_t)U17_OUT;for(unsigned n=0;n<36;n++)printf("%02x",p[n]);printf(" v0=%016llx:%016llx\n",(unsigned long long)(c->expected?c->after.v0[0]:0),(unsigned long long)(c->expected?c->after.v0[1]:0));
}
