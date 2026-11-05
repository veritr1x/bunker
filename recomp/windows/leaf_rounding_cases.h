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
static const uintptr_t owned=0x50000000,unity=0x70000000;
struct LeafInput{uint32_t value,scale;};
static const struct LeafInput leaf_inputs[]={
 {0,0x3f800000},{0x80000000,0x3f800000},{0x3f800000,0x80000000},
 {0xbf800000,0x3f800000},{0xc0000000,0x3f800000},{0x3f800000,0xbf800000},
 {0x3fffffff,0x3f800000},{0x40000000,0x3f800000},{0x40000001,0x3f800000},
 {0x40000000,0x3f000000},{0x3f800000,0x3f000000},{0x40200000,0x40000000},
 {0x4efffffe,0x3f800000},{0x4effffff,0x3f800000},{0x4f000000,0x3f800000},
 {0x4f000001,0x3f800000},{0x4f000000,0xbf800000},{0x4f000001,0xbf800000},
 {0x7f7fffff,0x3f800000},{0x7f7fffff,0xbf800000},{0x7f7fffff,0x7f7fffff},
 {0x00800000,0x3f800000},{0x3e800000,0x3f000000},{0x3eaaaaab,0x40e00000}
};
struct FrameOutput{uint64_t result,fpsr,nzcv,fpcr;unsigned char vectors[4][16];uint64_t abi_ok;};
static uint64_t object_hash(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x1000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void seed(unsigned sample){for(unsigned i=0;i<0x1000;i++)((unsigned char*)owned)[i]=(unsigned char)(i*37+sample*17+11);}
static int normal_or_zero(uint32_t x){return (x&0x7f800000U)!=0x7f800000U&&((x&0x7f800000U)!=0||(x&0x007fffffU)==0);}
static void record(unsigned sample,unsigned mode,unsigned initial,const struct FrameOutput*out){printf("REC %u %u %u %016llx ",sample,mode,initial,(unsigned long long)object_hash());const unsigned char*p=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",p[i]);putchar('\n');}
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
