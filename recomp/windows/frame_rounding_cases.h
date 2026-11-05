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
struct FrameInput{uint32_t a,b,scale;};
static const struct FrameInput frame_inputs[]={
 {0,0,0},{0x3f800000,0x40000000,0},{0x40000000,0x3f800000,0},
 {0xbf800000,0xc0000000,0x3f800000},{0xc0000000,0xbf800000,0x3f800000},
 {0x3fffffff,0x3f800000,0x3f800000},{0x40000000,0,0x3f800000},
 {0x40000001,0,0x3f800000},{0x42efffff,0,0x3f800000},
 {0x42f00000,0,0x3f800000},{0x42f20000,0,0x3f800000},
 {0x7f7fffff,0,0x7f7fffff},{0x7f800000,0,0x3f800000},
 {0xff800000,0xbf800000,0x3f800000},{0x7fc12345,0x40000000,0x3f800000},
 {0x40000000,0x7fc12345,0x3f800000},{0x7f812345,0x40000000,0x3f800000},
 {0x40000000,0x7f812345,0x3f800000},{0x80000000,0,0x80000000},
 {0x40000000,0,0xbf800000},{0x40000000,0,0x7fc12345},
 {0x40000000,0,0x7f812345},{1,0,0x3f800000},
 {0x007fffff,0,0x3f800000},{0x00800000,0,0x3f800000},
 {0x3f800000,0,1},{0x7f7fffff,0,1},{0x3f800000,0,0x7f800000},
 {0x3eaaaaab,0x3e800000,0x40e00000},{0x3fffffff,0,0x3f000000},
 {0x40000001,0,0x3f7fffff},{0x43a00000,0x42f00000,0x3f000000}
};
static int normal_or_zero(uint32_t x){return (x&0x7f800000U)!=0x7f800000U&&((x&0x7f800000U)!=0||(x&0x007fffffU)==0);}
static int normal_geometry(unsigned sample){return sample>=32||(normal_or_zero(frame_inputs[sample].a)&&normal_or_zero(frame_inputs[sample].b)&&normal_or_zero(frame_inputs[sample].scale));}
struct FrameOutput{uint64_t result,fpsr,nzcv,fpcr;unsigned char vectors[4][16];uint64_t abi_ok;};
static void put32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}
static void put64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}
static uint64_t get64(uintptr_t p){uint64_t v;memcpy(&v,(void*)p,8);return v;}
static uint64_t object_hash(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x1800;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static unsigned lookup_profile(unsigned sample){return sample<32?1:(sample-32)*2;}
static void seed(unsigned sample,unsigned chain){
 const struct FrameInput*c=&frame_inputs[sample<32?sample:0];
 for(unsigned i=0;i<0x1800;i++)((unsigned char*)owned)[i]=(unsigned char)(i*37+chain*17+11);
 put64(owned+0x30,owned+0x800);put64(owned+0x1a0,chain?owned+0x400:0);
 put64(owned+0x400+0x1a0,0);put32(owned+(chain?0x400:0)+0x1e0,c->scale);
 if(chain)put32(owned+0x1e0,0x7f812345);
 put64(owned+0x800+0x30,owned+0xc00);put64(owned+0x800+0x40,lookup_profile(sample)==0?0:2);
 put32(owned+0xc00,0x5ff);put64(owned+0xc08,owned+0x1000);
 put32(owned+0xc10,lookup_profile(sample)==1?0x604:0x610);put64(owned+0xc18,owned+0x1000);
 put64(owned+0x1000+0x38,0);((unsigned char*)owned)[0x1000+0xf1]=0;
 put32(owned+0x1000+0xc0,c->a);put32(owned+0x1000+0xc4,c->b);
 put32(0x7123fcf8+0x30,0x600);put32(0x7123fcf8+0x34,8);put32(0x712b8b5c,0);
}
static void record(unsigned sample,unsigned chain,unsigned mode,unsigned initial,const struct FrameOutput*out){
 printf("REC %u %u %u %u %u %016llx ",sample,chain,mode,initial,lookup_profile(sample),(unsigned long long)object_hash());
 const unsigned char*p=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",p[i]);putchar('\n');
}
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
