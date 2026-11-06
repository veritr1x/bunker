#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include "elf64.h"
#else
#include <elf.h>
#include <sys/mman.h>
#endif
static const uintptr_t owned=0x50000000,guest=0x80000000;
struct Out{uint64_t target,nzcv,fpcr,fpsr,x8,x9,x10,x22,x27,abi;};
struct Prefix{uintptr_t start,table,default_pc,targets[4];};
static const struct Prefix prefixes[]={
{0x83aaabec,0x85a82634,0x83aaaf5c,{0x83aaac0c,0x83aaae24,0x83aaae98,0x83aaaf28}},
{0x841ebd60,0x85a86a20,0x841ec0d0,{0x841ebd8c,0x841ec024,0x841ebfa0,0x841ec09c}},
};
static const uint32_t indices[]={0,1,2,3,4,7,0x7fffffffU,0x80000000U,0xffffffffU};
static const uint64_t incoming[]={0xdeadbeef01234567ULL,0xabcdef0187654321ULL};
static const uint64_t stack_value=0xcafef00d12345678ULL;
static const uint64_t old_x9=0xbbbbbbbb66666666ULL,old_x10=0xaaaaaaaa55555555ULL,old_x27=0xcccccccc77777777ULL;
static void put32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}
static inline void put64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}
static uint64_t hash_owned(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x1000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void seed(uint32_t index){memset((void*)owned,0xa5,0x1000);put32(owned+0x2f8,index);}
static uint64_t expected_target(unsigned p,uint32_t i){return i<=3?prefixes[p].targets[i]:prefixes[p].default_pc;}
static void record(unsigned p,uint32_t index,unsigned n,const struct Out*out){printf("REC %u %08x %u %016llx ",p,index,n,(unsigned long long)hash_owned());const unsigned char*b=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",b[i]);putchar('\n');}
static int map_original(const char*path){
 FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)guest,0xa000000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)guest||VirtualAlloc((void*)owned,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)owned)return 4;
#else
 if(mmap((void*)guest,0xa000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)guest||mmap((void*)owned,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){if(ph[i].p_vaddr+ph[i].p_memsz>0xa000000)return 5;fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(guest+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 6;}
 fclose(f);
#ifndef _WIN32
 // Transparent branch observers in fixture-owned mapped code; no case suffix executes.
 for(unsigned p=0;p<2;p++)for(unsigned n=0;n<5;n++){uintptr_t pc=n<4?prefixes[p].targets[n]:prefixes[p].default_pc;uint32_t op[]={0x52800000U|((pc&0xffffU)<<5),0x72a00000U|(((pc>>16)&0xffffU)<<5),0xd65f03c0U};memcpy((void*)pc,op,sizeof(op));}
 __builtin___clear_cache((char*)guest,(char*)guest+0xa000000);
#endif
 return 0;
}
