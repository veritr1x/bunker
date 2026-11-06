#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <sys/mman.h>
#include "unity_decode_native_bytes.h"
static unsigned mode,calls,cleanup,saves;static uintptr_t expected;
static _Thread_local __attribute__((aligned(64))) volatile unsigned decode_tls;
static void need(int yes,const char *why){if(!yes){fprintf(stderr,"decode ARM: %s\n",why);exit(91);}}
static uint64_t callback(void *decoder,void *callbacks,void *environment){need((uintptr_t)environment==expected&&(uintptr_t)decoder==expected+0x158&&(uintptr_t)callbacks==0x712265e0,"original callback arguments");++calls;return (mode%3)*17;}
static uint64_t finish(void *environment){need((uintptr_t)environment==expected,"original cleanup argument");++cleanup;return 0;}
static void gate(uint8_t *p,uintptr_t fn){uint32_t ins[]={0x58000050,0xd61f0200};memcpy(p,ins,8);memcpy(p+8,&fn,8);}
static uint8_t *page(uintptr_t address){uint8_t*p=mmap((void*)address,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(p==(void*)address,"test-owned code page");return p;}
int main(void){decode_tls=17;need(decode_tls==17,"Bionic TLS");uint8_t *inner=page(0x70a8a000);memcpy(inner+0xa08,decode_inner_bytes,sizeof(decode_inner_bytes));gate(inner+0xa64,(uintptr_t)finish);uint8_t *cb=page(0x70a82000);gate(cb+0x428,(uintptr_t)callback);
 uint8_t *save=page(0x700b9000);uint32_t ins[]={0x580000c9,0xb940012a,0x1100054a,0xb900012a,0x58000090,0xd61f0200};memcpy(save+0x2b0,ins,sizeof(ins));uintptr_t count=(uintptr_t)&saves,real=(uintptr_t)setjmp;memcpy(save+0x2c8,&count,8);memcpy(save+0x2d0,&real,8);
 for(unsigned i=0;i<3;i++){uint8_t*p=(uint8_t*[]){inner,cb,save}[i];__builtin___clear_cache((char*)p,(char*)p+4096);need(!mprotect(p,4096,PROT_READ|PROT_EXEC),"code RX");}
 for(mode=0;mode<6;mode++){_Alignas(16)uint8_t object[0x400];memset(object,0xa5,sizeof(object));expected=(uintptr_t)object;uint32_t skip=mode/3;memcpy(object+0x120,&skip,4);calls=cleanup=saves=0;uint64_t result=((uint64_t(*)(void*))0x70a8aa08)(object);need(result==(mode%3)*17&&calls==1&&cleanup==!skip&&saves==1,"normal original inner path");printf("DECODE-REF case=%u result=%llu saves=%u calls=%u cleanup=%u\n",mode,(unsigned long long)result,saves,calls,cleanup);}
 puts("UNITY-DECODE-BIONIC-PASS original_inner=92 real_setjmp=1 outer_executed=0");return 0;}
