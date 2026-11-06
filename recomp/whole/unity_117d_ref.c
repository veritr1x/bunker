#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "unity_117d_cases.h"
#include "unity_117d_native.h"
static u17_case*active;
static _Thread_local __attribute__((aligned(64))) volatile unsigned u17_tls_alignment;
extern uint64_t u17_call(uint64_t,void*,uint32_t,uint32_t,void*,u17_abi*);
static void need(int ok,const char*why){if(!ok){fprintf(stderr,"Unity117d native case%u: %s\n",active?active->id:999,why);exit(91);}}
static uint32_t test_ready(void*object){++active->calls;active->shape+=object==(void*)(uintptr_t)U17_OBJECT;return active->ready;}
static void*page(uint64_t address,size_t size){void*p=mmap((void*)(uintptr_t)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(p==(void*)(uintptr_t)address,"fixture fixed map");return p;}
int main(int argc,char**argv){
 u17_tls_alignment=17;need(u17_tls_alignment==17,"real aligned Bionic TLS witness");need(argc==2,"owned corpus argument");FILE*corpus=fopen(argv[1],"wb");need(corpus!=NULL,"native corpus create");
 page(U17_BASE,U17_ARENA);unsigned char*code=page(0x70117000,4096);memcpy(code+0xc5c,u17_original_outer,sizeof(u17_original_outer));memcpy(code+0x2fc,u17_original_helper,sizeof(u17_original_helper));page(0x70e7a000,4096);memcpy((void*)(uintptr_t)0x70e7a000,u17_original_tables,sizeof(u17_original_tables));
 unsigned char*callback=page(0x6f00f000,4096);uint32_t instructions[]={0x58000050,0xd61f0200};uint64_t address=(uintptr_t)test_ready;memcpy(callback+0xe00,instructions,8);memcpy(callback+0xe08,&address,8);__builtin___clear_cache((char*)code,(char*)code+4096);__builtin___clear_cache((char*)callback,(char*)callback+4096);need(!mprotect(code,4096,PROT_READ|PROT_EXEC)&&!mprotect(callback,4096,PROT_READ|PROT_EXEC),"authentic code RX");
 static unsigned char before[U17_DATA];
 for(unsigned id=0;id<88;id++){
  u17_case sample;u17_setup(&sample,id);active=&sample;memcpy(before,(void*)(uintptr_t)U17_BASE,U17_DATA);sample.after=sample.before;
  uint64_t result=u17_call(0x70117c5c,(void*)(uintptr_t)U17_OBJECT,sample.index,sample.type,(void*)(uintptr_t)U17_OUT,&sample.after);
  need(result==sample.expected&&sample.calls==(sample.ready?2u:1u)&&sample.shape==sample.calls,"real helper validation and outer result");need(!memcmp(sample.before.gpr,sample.after.gpr,sizeof(sample.before.gpr))&&!memcmp(sample.before.d,sample.after.d,sizeof(sample.before.d))&&sample.after.LR_good==1,"genuine outer/helper callee-save ABI and normal LR");need(u17_check_memory(before,&sample),"every fixture data byte/guard and output oracle");need(fwrite((void*)(uintptr_t)U17_BASE,1,U17_DATA,corpus)==U17_DATA,"native corpus write");u17_print(&sample,result,(uint32_t)sample.after.nzcv);
 }
 need(!fclose(corpus),"native corpus close");puts("UNITY-117D-BIONIC-PASS cases=88 success=64 failure=24 outer=504 helper=280");return 0;
}
