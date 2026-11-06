#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define US_BASE UINT64_C(0x56000000)
#define US_BYTES 65536
#define US_SP (US_BASE+0x2000)
#define US_FP (US_BASE+0x2800)
#define US_RETURN UINT64_C(0x6f00fffc)
typedef struct us_registers {uint64_t x[32];uint64_t nzcv;uint64_t reserved;uint64_t v[64];uint64_t pc;} us_registers;
static const uint64_t us_heads[]={0x70106fc0,0x70107030,0x70107058,0x701078e8,0x701078f0,0x701078f8,0x70107920,0x70107948,0x70107954,0x70107be4,0x70107bf4,0x70107c04};
static const uint64_t us_guard_starts[]={0x70106fa4,0x701078cc,0x70107bc4};
static const uint64_t us_tables[]={0x70e7a0b4,0x70e7a0c4,0x70e7a0e4};
static const uint64_t us_defaults[]={0x70107080,0x70107954,0x70107c18};
static const unsigned us_rows[]={4,8,4};
static void us_u64(uint64_t address,uint64_t value){memcpy((void*)(uintptr_t)address,&value,8);}
static void us_u32(uint64_t address,uint32_t value){memcpy((void*)(uintptr_t)address,&value,4);}
static uint64_t us_hash(const void*data,size_t bytes){const unsigned char*p=(const unsigned char*)data;uint64_t h=UINT64_C(1469598103934665603);for(size_t i=0;i<bytes;i++){h^=p[i];h*=UINT64_C(1099511628211);}return h;}
static uint64_t us_memory_hash(void){
 const unsigned char*p=(const unsigned char*)(uintptr_t)US_BASE;uint64_t h=UINT64_C(1469598103934665603);
 for(unsigned i=0;i<US_BYTES;i++){if(i<0x1000||(i>=0x1f00&&i<0x2000)||(i>=0x8000&&i<0x9000))continue;h^=p[i];h*=UINT64_C(1099511628211);}return h;
}
static int us_dump_memory(FILE*f){
 const unsigned char*p=(const unsigned char*)(uintptr_t)US_BASE;
 return fwrite(p+0x1000,1,0xf00,f)==0xf00&&fwrite(p+0x2000,1,0x6000,f)==0x6000&&fwrite(p+0x9000,1,0x7000,f)==0x7000;
}
static unsigned us_group(unsigned head){return head<3?0:head<9?1:2;}
static uint64_t us_observer(unsigned head){return us_group(head)==0?0x7036fb34:us_group(head)==1?0x707f48cc:0x7036d29c;}
static void us_setup(us_registers*r,unsigned head,unsigned seed){
 unsigned char*p=(unsigned char*)(uintptr_t)US_BASE;for(unsigned i=0;i<US_BYTES;i++)p[i]=(unsigned char)(0xa5u^(i*37u+seed*17u));memset(r,0,sizeof(*r));
 for(unsigned n=0;n<31;n++)r->x[n]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)(n+1)*UINT64_C(0x9e3779b97f4a7c15))^seed;
 for(unsigned n=0;n<64;n++)r->v[n]=UINT64_C(0xfedcba9876543210)^((uint64_t)(n+1)*UINT64_C(0x0102040810204081))^seed;
 r->x[29]=US_FP;r->x[30]=US_RETURN;r->x[31]=US_SP;r->nzcv=(seed&15u)<<28;r->pc=us_heads[head];
 static const uint64_t edges[]={0,1,0x7fffffff,0x80000000,0xffffffff,UINT64_C(0xffffffffffffffff),0xfffe,0x10000};uint64_t edge=edges[seed%8];
 unsigned group=us_group(head);
 if(group==0){
  r->x[25]=US_BASE+0x4000;r->x[20]=0;r->x[21]=1;r->x[22]=1;r->x[23]=0;r->x[26]=7;r->x[27]=8;r->x[28]=3;
  us_u64(US_BASE+0x4018,US_BASE+0x5000);p[0x4011]=0;
  us_u64(US_FP-0xb8,1);us_u64(US_FP-0xc8,US_BASE+0x4000);us_u64(US_FP-0xd0,0);
  us_u64(US_FP-0x188,edge);us_u64(US_FP-0x1a8,edge);us_u64(US_FP-0x1b0,edge);
 }else if(group==1){
  r->x[0]=US_BASE+0x4500;r->x[19]=us_tables[1];r->x[21]=US_BASE+0x4200;r->x[22]=US_BASE+0x4300;r->x[23]=0;r->x[24]=US_BASE+0x4100;r->x[25]=edge;r->x[26]=0;r->x[27]=US_BASE+0x4400;r->x[28]=US_BASE+0x4400;
  us_u64(US_BASE+0x4200,US_BASE+0x4400);us_u64(US_BASE+0x4210,1);us_u64(US_BASE+0x4300,US_BASE+0x5600);us_u64(US_BASE+0x4100,US_BASE+0x4800);
  static const unsigned slots[]={0x10,0x20,0x28,0x30,0x38,0x48};for(unsigned n=0;n<6;n++)us_u64(US_BASE+0x4100+slots[n],US_BASE+0x5000+n*0x100);
  us_u32(US_BASE+0x4518,1+(seed%8));us_u32(US_BASE+0x451c,seed%8);us_u32(US_BASE+0x4520,seed%2?3:0);
  us_u32(US_BASE+0x4404,seed%4+1);us_u32(US_BASE+0x440c,seed%2?0x12345678:0x87654321);p[0x4410]=(unsigned char)(seed*19u);p[0x4411]=(unsigned char)(seed%2);
  us_u64(US_FP-0x1a0,US_BASE+0x4700);us_u64(US_BASE+0x4700,US_BASE+0x5700);
 }else{
  r->x[8]=US_BASE+0x5000;r->x[9]=US_BASE+0x4004;r->x[10]=edge;r->x[11]=edge;r->x[12]=12;r->x[13]=edge;r->x[15]=seed%8;r->x[19]=US_BASE+0x4900;r->x[21]=1;r->x[22]=seed%8;
  us_u64(US_FP-0x1c8,US_BASE+0x4a00);
 }
 for(unsigned n=0;n<8;n++)us_u64(US_BASE+0xa000+n*8,UINT64_C(0x1122334455667788)*(n+1));
}
static void us_print(const char*tag,unsigned head,unsigned seed,const us_registers*r){
 printf("%s head=%llx seed=%u pc=%llx nzcv=%08x mem=%016llx regs=",tag,(unsigned long long)us_heads[head],seed,(unsigned long long)r->pc,(unsigned)r->nzcv,(unsigned long long)us_memory_hash());
 for(unsigned n=0;n<32;n++)printf("%s%016llx",n?":":"",(unsigned long long)r->x[n]);
 printf(" simd=%016llx\n",(unsigned long long)us_hash(r->v,sizeof(r->v)));
}
