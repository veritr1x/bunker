#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include "elf64.h"
#else
#include <elf.h>
#endif
static const uintptr_t owned=0x50000000,unity=0x70000000,global_guard=0x71249860;
static const uintptr_t heads[]={0x70652c68,0x7066e6c0,0x707877a0,0x70a41660};
static const uint32_t scalar_inputs[]={0xff7fffff,0xc0000000,0xbf800000,0x80000000,0,0x3e800000,0x3f000000,0x3f7fffff,0x3f800000,0x3f800001,0x40000000,0x40800000,0x42f00000,0x7f7fffff,0x00800000,0x3eaaaaab};
static const uint32_t vector_inputs[][6]={
 {0x3f800000,0x40400000,0x40000000,0x3f000000,0xbf000000,0x3f800000},
 {0x40000000,0x40400000,0x3f800000,0xbf800000,0,0x3f000000},
 {0x40400000,0x3f800000,0x40000000,0,0x3f800000,0xbf800000},
 {0x3f800000,0x3f800000,0x3f800000,0x80000000,0x3f800000,0xbf800000},
 {0xbf800000,0x40400000,0xc0000000,0xbf000000,0xbf800000,0x40000000},
 {0,0,0x80000000,0x80000000,0,0xbf800000},
 {0x3eaaaaab,0x40800000,0x3e800000,0x3f000000,0xbf000000,0x3eaaaaab},
 {0xc0000000,0x40000000,0xbf800000,0x40000000,0xc0000000,0x3f000000}
};
struct BatchOutput{uint64_t result,fpsr,nzcv,fpcr;unsigned char vectors[5][16];uint64_t abi_ok;};
static int normal_or_zero(uint32_t x){return (x&0x7f800000U)!=0x7f800000U&&((x&0x7f800000U)!=0||(x&0x007fffffU)==0);}
static unsigned samples(unsigned fn){return fn==1?8:16;}
static unsigned aliases(unsigned fn){return fn==1?3:1;}
static uintptr_t destination(unsigned fn,unsigned alias){return owned+(fn==1?(alias==1?0x100:alias==2?0x200:0):0);}
static uint64_t object_hash(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x1000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void seed(unsigned fn,unsigned sample){
 for(unsigned i=0;i<0x1000;i++)((unsigned char*)owned)[i]=(unsigned char)(i*37+sample*17+fn*11);
 memset((void*)global_guard,0xa5,24);uint32_t flags=0x80000005;memcpy((void*)(owned+0xa0),&flags,4);
 if(fn==1)memcpy((void*)(owned+0x100),vector_inputs[sample],12),memcpy((void*)(owned+0x200),vector_inputs[sample]+3,12);
}
static int writable(unsigned fn,unsigned alias,unsigned offset){if(fn==0)return(offset>=0x50&&offset<0x54)||(offset>=0x58&&offset<0x5c)||(offset>=0xa0&&offset<0xa4);if(fn==1){unsigned start=(unsigned)(destination(fn,alias)-owned);return offset>=start&&offset<start+12;}return fn==3&&offset>=0x370&&offset<0x374;}
static int unchanged_canaries(unsigned fn,unsigned alias,const unsigned char*before){for(unsigned i=0;i<0x1000;i++)if(!writable(fn,alias,i)&&((unsigned char*)owned)[i]!=before[i])return 0;for(unsigned i=0;i<24;i++)if(!(fn==2&&i>=8&&i<12)&&((unsigned char*)global_guard)[i]!=0xa5)return 0;return 1;}
static void record(unsigned fn,unsigned sample,unsigned alias,unsigned mode,unsigned initial,const struct BatchOutput*out){printf("REC %u %u %u %u %u %016llx ",fn,sample,alias,mode,initial,(unsigned long long)object_hash());const unsigned char*g=(const unsigned char*)global_guard;for(unsigned i=0;i<24;i++)printf("%02x",g[i]);putchar(' ');const unsigned char*p=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",p[i]);putchar('\n');}
static int map_original(const char*path){
 FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];
 if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;
 fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)unity,0x3000000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)unity||VirtualAlloc((void*)owned,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)owned)return 4;
#else
 if(mmap((void*)unity,0x3000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)unity||mmap((void*)owned,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(unity+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 5;}
 fclose(f);
#ifndef _WIN32
 __builtin___clear_cache((char*)unity,(char*)unity+0x3000000);
#endif
 return 0;
}
