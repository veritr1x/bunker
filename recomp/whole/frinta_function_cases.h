#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define FF_BASE UINT64_C(0x58000000)
#define FF_LEFT (FF_BASE+16)
#define FF_INTEGRAL (FF_BASE+20)
typedef struct{uint64_t gpr[11],d[8];uint32_t result,fpsr;uint64_t nzcv,LR_good,fpcr;}FFABI;
typedef struct{uint32_t flags0,flags3,s[6],id;FFABI before,after;}FFCase;
typedef struct{uint32_t input,fraction,integral,before;}FFModfRecord;
static void ff_setup(FFCase*c,unsigned id){
 memset(c,0,sizeof(*c));c->id=id;unsigned v=id,offset=v%2;v/=2;unsigned quant=v%2;v/=2;unsigned range=v%2;v/=2;unsigned progress=v%6;v/=6;unsigned sign=v%2;v/=2;c->flags3=v%2;v/=2;c->flags0=v%2;
 static const uint32_t a[]={0xbe800000,0x80000000,0x3d800000,0x3e000000,0x3ec00000,0x3fa00000};c->s[0]=a[progress];c->s[1]=range?0xbf800000:0;c->s[2]=range?0x40400000:0x3f800000;c->s[3]=offset?0x3e800000:0;c->s[4]=sign?0xbf800000:0x3f800000;c->s[5]=quant?0x40800000:0x40000000;
 for(unsigned n=0;n<64;n++)((unsigned char*)(uintptr_t)FF_BASE)[n]=(unsigned char)(0x69u^(id*17u+n*29u));
 for(unsigned n=0;n<11;n++)c->before.gpr[n]=UINT64_C(0xaabbccdd00000000)^((uint64_t)(n+1)*UINT64_C(0x102030405060708))^id;
 for(unsigned n=0;n<8;n++){c->before.d[n]=UINT64_C(0x123456789abcdef0)^((uint64_t)(n+1)*UINT64_C(0x100204081020408))^id;}
 c->after=c->before;
}
static int ff_guards(const unsigned char*before){const unsigned char*p=(const unsigned char*)(uintptr_t)FF_BASE;for(unsigned n=0;n<64;n++)if((n<16||n>=24)&&p[n]!=before[n])return 0;return 1;}
static void ff_print(const FFCase*c,unsigned calls,unsigned shape,const FFModfRecord*r){uint32_t outputs[2];memcpy(outputs,(void*)(uintptr_t)FF_LEFT,8);printf("FRINTA-FUNCTION id=%u f0=%u f3=%u sign=%08x result=%08x outputs=%08x:%08x FPSR=%08x NZCV=%08x callbacks=%u shape=%u modff=%08x:%08x:%08x:%08x\n",c->id,c->flags0,c->flags3,c->s[4],c->after.result,outputs[0],outputs[1],c->after.fpsr,(unsigned)c->after.nzcv,calls,shape,r->input,r->fraction,r->integral,r->before);}
