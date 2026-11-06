#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#include <sys/mman.h>
#include <unistd.h>
#include "font_cmap_cases.h"
#include "font_cmap_native_bytes.h"
static unsigned saves,validations,creations,good,same;static uintptr_t last;
static _Thread_local __attribute__((aligned(64))) volatile unsigned font_tls;
static void need(int v,const char*n){if(!v){fprintf(stderr,"font ARM: %s\n",n);exit(91);}}
static uint64_t word(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static uint32_t dword(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void validator(const uint8_t*table,uint8_t*env){
 ++validations;good+=(word(env+0x100)==(uintptr_t)table&&word(env+0x108)>(uintptr_t)table&&dword(env+0x110)==0&&dword(env+0x114)==0&&dword(env+0x118)==44);
 if(!last||last==(uintptr_t)env)++same;last=(uintptr_t)env;
}
static uint64_t creator(void*clazz,void*table,void*record,void*slot){(void)clazz;(void)table;(void)record;(void)slot;++creations;return 1;}
static void*page(uintptr_t p){void*r=mmap((void*)p,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(r==(void*)p,"owned fixture page");return r;}
static void gate(uint8_t*p,uintptr_t function){uint32_t words[]={0x58000050,0xd61f0200};memcpy(p,words,8);memcpy(p+8,&function,8);}
int main(void){
 font_tls=17;need(font_tls==17,"real aligned Bionic TLS initialized");
 uint8_t*outer=page(0x708d9000);memcpy(outer+0x5c,font_outer_bytes,sizeof(font_outer_bytes));
 uint8_t*init=page(0x708e6000);memcpy(init+0xe98,font_init_bytes,sizeof(font_init_bytes));
 uint8_t*create=page(0x708e8000);gate(create+0xf70,(uintptr_t)creator);
 uint8_t*save=page(0x700b9000);uint32_t observed[]={0x580000c9,0xb940012a,0x1100054a,0xb900012a,0x58000090,0xd61f0200};memcpy(save+0x2b0,observed,sizeof(observed));uintptr_t counter=(uintptr_t)&saves,real=(uintptr_t)setjmp;memcpy(save+0x2c8,&counter,8);memcpy(save+0x2d0,&real,8);
 uint8_t*list=page(0x7121d000);uint8_t classes[2][0x60]={{0}};uint32_t f4=4,f6=6;uintptr_t fn=(uintptr_t)validator,pointers[]={(uintptr_t)classes[0],(uintptr_t)classes[1],0};memcpy(classes[0]+0x50,&f4,4);memcpy(classes[1]+0x50,&f6,4);memcpy(classes[0]+0x58,&fn,8);memcpy(classes[1]+0x58,&fn,8);memcpy(list+0x858,pointers,sizeof(pointers));
 for(unsigned i=0;i<4;i++){uint8_t*p=(uint8_t*[]){outer,init,create,save}[i];__builtin___clear_cache((char*)p,(char*)p+4096);need(!mprotect(p,4096,PROT_READ|PROT_EXEC),"fixture code RX");}
 need(!mprotect(list,4096,PROT_READ),"fixture class array readonly");
 for(unsigned c=0;c<FONT_CMAP_CASES;c++){
  uint8_t face[0x400],table[FONT_CMAP_TABLE_BYTES];font_cmap_case(c,face,table);saves=validations=creations=good=same=0;last=0;
  uint64_t result=((uint64_t(*)(void*))0x708d905c)(face);
  unsigned wanted=c==5?2:c==4?1:0;need(result==(c==0?8:0)&&saves==wanted&&validations==wanted&&creations==wanted&&good==wanted&&same==wanted,"original outer/reference record");
  printf("FONT-REF case=%u result=%llu saves=%u validations=%u creations=%u fields=%u same=%u\n",c,(unsigned long long)result,saves,validations,creations,good,same);
 }
 puts("FONT-CMAP-BIONIC-PASS cases=6 original_outer=588 original_init=20 real_setjmp=1");return 0;
}
