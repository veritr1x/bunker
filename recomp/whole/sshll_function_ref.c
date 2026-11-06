#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "sshll_function_cases.h"
#include "sshll_function_native.h"
static sshll_function_case*active;
static _Thread_local __attribute__((aligned(64))) volatile unsigned reference_tls;
static void need(int value,const char*why){if(!value){fprintf(stderr,"SSHLL original ARM function: %s\n",why);exit(91);}}
static uint32_t observer(void*font,uint32_t*count,uintptr_t zero,void**data,uintptr_t zero2){
 ++active->calls;active->shape+=(font==active->font&&!zero&&!zero2&&(uint8_t*)count-(uint8_t*)data==12);memcpy(active->spill,(uint8_t*)count-0x1c,16);*count=27;*data=0;return active->error;
}
int main(void){
 reference_tls=17;need(reference_tls==17,"aligned native Bionic TLS");uint8_t*page=mmap((void*)0x708d1000,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(page==(void*)0x708d1000,"original code page");
 memcpy(page+0x3a8,sshll_original_body,sizeof(sshll_original_body));memcpy(page+8,sshll_helper_1008,sizeof(sshll_helper_1008));memcpy(page+0x10,sshll_helper_1010,sizeof(sshll_helper_1010));memcpy(page+0x2c,sshll_helper_102c,sizeof(sshll_helper_102c));memcpy(page+0x970,sshll_helper_1970,sizeof(sshll_helper_1970));
 uint8_t*gate=mmap((void*)0x708cc000,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(gate==(void*)0x708cc000,"owned callback gateway");uint32_t instructions[]={0x58000050,0xd61f0200};uintptr_t address=(uintptr_t)observer;memcpy(gate+0xfc8,instructions,8);memcpy(gate+0xfd0,&address,8);__builtin___clear_cache((char*)page,(char*)page+4096);__builtin___clear_cache((char*)gate,(char*)gate+4096);need(!mprotect(page,4096,PROT_READ|PROT_EXEC)&&!mprotect(gate,4096,PROT_READ|PROT_EXEC),"actual original code RX");
 for(unsigned seed=0;seed<256;seed++){
  sshll_function_case sample,before;sshll_function_setup(&sample,seed);memcpy(&before,&sample,sizeof(before));active=&sample;
  uint64_t result=((uint64_t(*)(void*,void*,void*,void*))0x708d13a8)(sample.face,sample.opaque,sample.vector,&sample.output);int bytes=sshll_function_bytes(&sample,&before);
  need(result==sample.error&&sample.output==0&&sample.calls==1&&sample.shape==1&&sample.spill[0]==sshll_function_expected(sample.bits[0])&&sample.spill[1]==sshll_function_expected(sample.bits[1])&&bytes,"original early-error path and widened spill");
  printf("SSHLL-FDE seed=%u bits=%08x:%08x result=%08x out=%08x spill=%016llx:%016llx callbacks=%u shape=%u bytes=%u\n",seed,sample.bits[0],sample.bits[1],(unsigned)result,sample.output,(unsigned long long)sample.spill[0],(unsigned long long)sample.spill[1],sample.calls,sample.shape,bytes);
 }
 puts("SSHLL-FDE-BIONIC-PASS cases=256 body=940 helpers=68");return 0;
}
