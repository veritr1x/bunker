#pragma once
#include <stdint.h>
#include <string.h>
typedef struct {uint8_t face[0x200],context[0x600],root[0x13a0],font[0x100],info[0x440],vector[32],opaque[16];uint32_t bits[2],error,output;uint64_t spill[2];unsigned calls,shape;} sshll_function_case;
static void sshll_function_setup(sshll_function_case*m,unsigned seed){
 static const uint32_t edge[]={0,1,0x7fffffff,0x80000000,0xffffffff,0xaaaaaaaa,0x55555555,0xffff0000,0x0000ffff,0x80000001,0x7ffffffe,0xfffffffe,0x00010000,0xff000000,0x01000000,0x12345678};
 memset(m,0,sizeof(*m));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
 for(unsigned i=0;i<2;i++){random^=random<<13;random^=random>>7;random^=random<<17;m->bits[i]=seed<16?edge[(seed+i*7)%16]:(uint32_t)random;memcpy(m->vector+16+i*4,&m->bits[i],4);}
 const uint32_t errors[]={8,255,0x80000000,0xffffffff};m->error=errors[seed%4];m->output=0xdeadbeef;
 uintptr_t context=(uintptr_t)m->context,root=(uintptr_t)m->root,font=(uintptr_t)m->font,info=(uintptr_t)m->info,old_info=seed&1?0:info;uint32_t flag=1;
 memcpy(m->face+0xf0,&context,8);memcpy(m->face+0xf8,&old_info,8);memcpy(m->face+0xa4,m->bits,8);memcpy(m->context+8,&font,8);memcpy(m->context+0x98,&root,8);memcpy(m->context+0x598,&info,8);memcpy(m->root+0x1390,&flag,4);
}
static uint64_t sshll_function_expected(uint32_t bits){int32_t value;memcpy(&value,&bits,4);return(uint64_t)(int64_t)value;}
static int sshll_function_bytes(sshll_function_case*m,const sshll_function_case*before){
 sshll_function_case expected;memcpy(&expected,before,sizeof(expected));uintptr_t info=(uintptr_t)m->info;memcpy(expected.face+8,&m->error,4);memcpy(expected.face+0xf8,&info,8);
 return!memcmp(m->face,expected.face,sizeof(m->face))&&!memcmp(m->context,before->context,sizeof(m->context))&&!memcmp(m->root,before->root,sizeof(m->root))&&!memcmp(m->font,before->font,sizeof(m->font))&&!memcmp(m->info,before->info,sizeof(m->info))&&!memcmp(m->vector,before->vector,sizeof(m->vector))&&!memcmp(m->opaque,before->opaque,sizeof(m->opaque));
}
