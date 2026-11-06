#define _GNU_SOURCE
#include <stdlib.h>
#include <setjmp.h>
#include <sys/mman.h>
#include "numeric_minmax_cluster_cases.h"
#include "numeric_minmax_cluster_native.h"
extern unsigned char nmc_enter_begin[],nmc_enter_end[];
extern void nmc_capture(void);
uint64_t nmc_host_x18,nmc_host_fpcr,nmc_host_fpsr,nmc_host_nzcv;
static jmp_buf nmc_exit;
static _Thread_local __attribute__((aligned(64)))volatile unsigned nmc_tls;
static unsigned case_id;
static void need(int ok,const char*why){if(!ok){fprintf(stderr,"Numeric cluster native case%u: %s\n",case_id,why);exit(91);}}
void nmc_captured(void){longjmp(nmc_exit,1);}
static void*page(uint64_t address,size_t bytes){void*p=mmap((void*)(uintptr_t)address,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);need(p==(void*)(uintptr_t)address,"fixture fixed page");return p;}
static void branch(uint64_t from,uint64_t to){int64_t delta=(int64_t)to-(int64_t)from;need(!(delta&3)&&delta>=-0x8000000&&delta<0x8000000,"nearby fixture branch");uint32_t word=0x14000000u|((uint32_t)(delta>>2)&0x3ffffffu);memcpy((void*)(uintptr_t)from,&word,4);}
int main(int argc,char**argv){
 nmc_tls=17;need(nmc_tls==17,"Bionic aligned real TLS witness");need(argc==2,"owned native snapshots filename");FILE*file=fopen(argv[1],"wb");need(file!=NULL,"create native snapshot corpus");page(NMC_BASE,NMC_ARENA);page(0x841e2000,16384);memcpy((void*)(uintptr_t)NMC_ENTRY,nmc_original_bytes,32);
 const uint64_t veneer=0x841e3000;uint32_t code[]={0xa9bf47f0,0xd2800011,0xf2a00011,0x58000050,0xd61f0200};code[1]|=((uint32_t)NMC_STOP&0xffff)<<5;code[2]|=((uint32_t)(NMC_STOP>>16)&0xffff)<<5;memcpy((void*)(uintptr_t)veneer,code,sizeof(code));uint64_t callback=(uintptr_t)nmc_capture;memcpy((void*)(uintptr_t)(veneer+20),&callback,8);branch(NMC_STOP,veneer);
 size_t bytes=(size_t)(nmc_enter_end-nmc_enter_begin);need(bytes>4&&bytes<4096,"owned entry wrapper size");memcpy((void*)(uintptr_t)0x841e2000,nmc_enter_begin,bytes);branch(0x841e2000+bytes-4,NMC_ENTRY);__builtin___clear_cache((char*)(uintptr_t)0x841e2000,(char*)(uintptr_t)0x841e6000);need(!mprotect((void*)(uintptr_t)0x841e2000,16384,PROT_READ|PROT_EXEC),"original32B and separate fixture boundary RX");
 static unsigned char before[NMC_ARENA];
 for(unsigned mode=0;mode<16;mode++)for(unsigned sticky=0;sticky<2;sticky++)for(unsigned pair=0;pair<32;pair++){
  case_id=(mode*2+sticky)*32+pair;NMCRegisters input,actual;nmc_setup(&input,pair,mode,sticky);NMCRegisters expected=nmc_expected(&input);memcpy(before,(void*)(uintptr_t)NMC_BASE,NMC_ARENA);
  __asm__ volatile("mov %0,x18":"=r"(nmc_host_x18));__asm__ volatile("mrs %0,fpcr":"=r"(nmc_host_fpcr));__asm__ volatile("mrs %0,fpsr":"=r"(nmc_host_fpsr));__asm__ volatile("mrs %0,nzcv":"=r"(nmc_host_nzcv));
  if(!setjmp(nmc_exit))((void(*)(void))0x841e2000)();
  memcpy(&actual,(void*)(uintptr_t)(NMC_BASE+0x8000),sizeof(actual));need(!memcmp(&expected,&actual,sizeof(actual)),"full real8instruction GPR/SIMD/FP snapshot equals bit oracle");need(nmc_guards(before),"read-only load/source/opaque-memory guards");need(fwrite(&actual,1,sizeof(actual),file)==sizeof(actual),"native complete snapshot write");nmc_print(pair,mode,sticky,&actual);
 }
 need(!fclose(file),"native corpus close");puts("NUMERIC-CLUSTER-BIONIC-PASS cases=1024 original_bytes=32 exact_fallthrough=841e55f0");return 0;
}
