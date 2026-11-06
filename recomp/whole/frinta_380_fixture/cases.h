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
struct Out {uint64_t fpsr,nzcv,fpcr,pad;unsigned char v[4][16];uint64_t abi_ok;};
struct Case {int32_t w,h,denw,denh,left,top,right,bottom;unsigned api,ready;};
static const struct Case cases[]={
 {100,80,100,80,1,2,3,4,28,1},{101,79,200,160,1,1,2,3,28,1},
 {101,79,202,158,1,1,1,1,28,1},{-101,-79,202,158,1,1,1,1,28,1},
 {300,201,0,0,-3,-5,7,9,28,1},{321,203,200,0,3,-5,-7,9,28,1},
 {321,203,0,200,-3,5,7,-9,28,1},{-13,17,-10,-6,-2,3,4,-5,35,1},
 {0,0,1,1,0,0,0,0,28,1},{1920,1080,1280,720,11,9,13,15,28,1},
 {101,79,202,158,1,1,1,1,27,1},{101,79,202,158,1,1,1,1,28,0}
};
static void put32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}
static void put64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}
static uint32_t get32(uintptr_t p){uint32_t v;memcpy(&v,(void*)p,4);return v;}
static uint64_t globalhash(void){return get32(0x712bfa24)^((uint64_t)get32(0x712c15c0)<<17)^((uint64_t)get32(0x712c1700)<<33);}
static uint64_t hashdata(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0x200;i<0x1000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void seed(unsigned n,uintptr_t width,uintptr_t height){
 const struct Case*c=&cases[n];memset((void*)owned,0,0x1000);
 put64(owned,owned+0x100);put64(owned+0x100+0xb0,width);put64(owned+0x100+0xb8,height);
 put32(owned+0x20,c->w);put32(owned+0x24,c->h);
 put64(0x712c15c0,owned+0x300);put64(0x712c1700,owned+0x400);put32(0x712bfa24,c->api);
 put64(owned+0x300+0x28,owned+0x500);put64(owned+0x500,c->ready?owned+0x600:0);
 put32(owned+0x300+0x20,c->denw);put32(owned+0x300+0x24,c->denh);
 put32(owned+0x400+0x18,c->left);put32(owned+0x400+0x1c,c->top);
 put32(owned+0x400+0x20,c->right);put32(owned+0x400+0x24,c->bottom);
}
static int valid_counts(unsigned n){const struct Case*c=&cases[n];unsigned live=c->api>=28&&c->ready;return get32(owned+0x30)==1U+(live&&c->denw!=0)&&get32(owned+0x34)==1U+(live&&c->denh!=0);}
static void record(unsigned n,unsigned mode,unsigned initial,const struct Out*out){printf("REC %u %u %u %u %u %016llx ",n,mode,initial,get32(owned+0x30),get32(owned+0x34),(unsigned long long)hashdata());const unsigned char*p=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",p[i]);putchar('\n');}
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
