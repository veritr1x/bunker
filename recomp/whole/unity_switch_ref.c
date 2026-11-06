#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#include <sys/mman.h>
#include "unity_switch_cases.h"
#include "unity_switch_native.h"
extern unsigned char us_enter_begin[],us_enter_end[];
extern void us_capture(void);
uint64_t us_host_x18;
static jmp_buf us_stop;
// Bionic ARM64 requires the static executable's PT_TLS alignment to be64.
static _Thread_local __attribute__((aligned(64))) volatile unsigned us_tls_alignment;
static void need(int ok,const char*why){if(!ok){fprintf(stderr,"original switch fixture: %s\n",why);exit(91);}}
void us_captured(void){longjmp(us_stop,1);}
static void*page(uint64_t address,size_t size){void*p=mmap((void*)(uintptr_t)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(p==(void*)(uintptr_t)address,"fixed fixture mapping");return p;}
static void branch(uint64_t from,uint64_t to){int64_t d=(int64_t)to-(int64_t)from;need(!(d&3)&&d>=-0x8000000&&d<0x8000000,"local fixture branch range");us_u32(from,0x14000000u|((uint32_t)(d>>2)&0x03ffffff));}
static void seal(uint64_t address,size_t size,int rx){__builtin___clear_cache((char*)(uintptr_t)address,(char*)(uintptr_t)(address+size));need(!mprotect((void*)(uintptr_t)address,size,rx?PROT_READ|PROT_EXEC:PROT_READ|PROT_WRITE),"fixture code permissions");}
static void veneer(unsigned index,uint64_t target){
 uint64_t v=0x70104000+index*64;uint32_t code[]={0xa9bf47f0,0xd2800011,0xf2a00011,0x58000050,0xd61f0200};
 // STP x16,x17,[SP,#-16]!; MOVZ/MOVK x17,target; LDR x16, literal; BR x16.
 code[1]|=((uint32_t)target&0xffff)<<5;code[2]|=((uint32_t)(target>>16)&0xffff)<<5;
 memcpy((void*)(uintptr_t)v,code,sizeof(code));uint64_t fn=(uintptr_t)us_capture;memcpy((void*)(uintptr_t)(v+20),&fn,8);branch(target,v);
}
static void original(void){seal(0x70106000,8192,0);memcpy((void*)(uintptr_t)0x701068d8,us_original_FDE,sizeof(us_original_FDE));}
static void enter(const us_registers*r,uint64_t entry,us_registers*out){
 memcpy((void*)(uintptr_t)US_BASE,r,sizeof(*r));memset((void*)(uintptr_t)(US_BASE+0x8000),0,sizeof(*out));
 seal(0x70105000,4096,0);size_t bytes=(size_t)(us_enter_end-us_enter_begin);need(bytes<4096&&bytes>=4,"entry fixture code size");memcpy((void*)(uintptr_t)0x70105000,us_enter_begin,bytes);branch(0x70105000+bytes-4,entry);seal(0x70105000,4096,1);
 __asm__ volatile("mov %0,x18":"=r"(us_host_x18));
 if(!setjmp(us_stop))((void(*)(void))0x70105000)();
 memcpy(out,(void*)(uintptr_t)(US_BASE+0x8000),sizeof(*out));
}
int main(int argc,char**argv){
 us_tls_alignment=17;need(us_tls_alignment==17,"Bionic TLS alignment witness");
 need(argc==2,"owned native corpus path argument");FILE*corpus=fopen(argv[1],"wb");need(corpus!=NULL,"create native memory corpus");
 page(US_BASE,US_BYTES);page(0x70104000,16384);page(0x70e7a000,4096);page(0x7123e000,4096);page(0x7036d000,4096);page(0x7036f000,4096);page(0x707f4000,4096);
 memcpy((void*)(uintptr_t)0x70e7a000,us_original_tables,sizeof(us_original_tables));us_u32(0x7123eb40,0x12345678);
 unsigned guards=0;
 for(unsigned group=0;group<3;group++)for(unsigned caseid=0;caseid<us_rows[group]+4;caseid++){
  uint32_t source=caseid<us_rows[group]?caseid+1:(uint32_t[]){0,0xffffffffu,0x80000000u,us_rows[group]+1}[caseid-us_rows[group]];
  us_registers in,out;us_setup(&in,group==0?0:group==1?3:9,caseid);original();seal(0x70104000,4096,0);
  unsigned count=0;uint64_t expected=us_defaults[group];uint32_t idx=source-1;
  for(unsigned n=0;n<us_rows[group];n++){int32_t delta;memcpy(&delta,(void*)(uintptr_t)(us_tables[group]+n*4),4);uint64_t target=us_tables[group]+delta;veneer(count++,target);if(idx==n)expected=target;}
  veneer(count++,us_defaults[group]);
  if(group==0){in.x[19]=US_BASE+0x4000;in.x[24]=us_tables[group];us_u32(US_BASE+0x4004,source);}
  else if(group==1){in.x[0]=US_BASE+0x4500;in.x[19]=us_tables[group];us_u32(US_BASE+0x4518,source);}
  else{in.x[9]=US_BASE+0x4004;in.x[14]=us_tables[group];us_u32(US_BASE+0x4004,source);}
  seal(0x70104000,4096,1);seal(0x70106000,8192,1);enter(&in,us_guard_starts[group],&out);need(out.pc==expected,"original table row/default dispatch");
  printf("UNITY-SWITCH-GUARD group=%u source=%08x target=%llx nzcv=%08x\n",group,source,(unsigned long long)out.pc,(unsigned)out.nzcv);guards++;
 }
 original();seal(0x70104000,4096,0);veneer(32,0x7036fb34);veneer(33,0x707f48cc);veneer(34,0x7036d29c);seal(0x70104000,4096,1);seal(0x70106000,8192,1);seal(0x7036d000,4096,1);seal(0x7036f000,4096,1);seal(0x707f4000,4096,1);
 for(unsigned head=0;head<12;head++)for(unsigned seed=0;seed<32;seed++){
  us_registers in,out;us_setup(&in,head,seed);enter(&in,us_heads[head],&out);need(out.pc==us_observer(head),"expected genuine outgoing call reached");need(out.x[31]==in.x[31],"interior block SP unchanged at observer");need(!memcmp(out.v,in.v,sizeof(in.v)),"all32 original SIMD registers unchanged");need(us_dump_memory(corpus),"write native byte-exact memory corpus");us_print("UNITY-SWITCH",head,seed,&out);
 }
 need(!fclose(corpus),"close native memory corpus");printf("UNITY-SWITCH-BIONIC-PASS guards=%u cases=384 originalFDE=5688\n",guards);return 0;
}
