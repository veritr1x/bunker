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
struct CleanupInput{uint64_t size;uint32_t base,delta;};
static const struct CleanupInput cleanup_inputs[]={
 {0,5,0},{0,5,8},{0,5,9},{0,5,58},{0,5,59},{0,5,60},{1,5,58},{1,5,59},
 {5999,5,58},{6000,5,58},{6001,5,58},{299999,5,8},{299999,5,9},{300000,5,8},{300000,5,9},{300001,5,8},{300001,5,9},
 {0xffffffffULL,5,0},{0xffffffffULL,5,9},{0x100000000ULL,5,8},{0x100000001ULL,5,8},{0x10000000000ULL,5,8},
 {0x7fffffffffffffffULL,5,8},{0x8000000000000000ULL,5,8},{0xffffffffffffffffULL,5,0},{0xffffffffffffffffULL,5,9},
 {1,5,16777215},{1,5,16777216},{1,5,16777217},{300000,0xfffffff0U,8},{300000,0xfffffff0U,9},{0,1,0}};
enum{CLEANUP_SAMPLES=sizeof(cleanup_inputs)/sizeof(cleanup_inputs[0]),CLEANUP_RECORDS=CLEANUP_SAMPLES*2*16*2};
struct CleanupOutput{uint64_t result,fpsr,nzcv,fpcr;unsigned char vectors[7][16];uint64_t abi_ok;};
static void put32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}static void put64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}static uint64_t get64(uintptr_t p){uint64_t v;memcpy(&v,(void*)p,8);return v;}
static void seed(unsigned sample,unsigned layout){
 const struct CleanupInput*c=&cleanup_inputs[sample];for(unsigned i=0;i<0x10000;i++)((unsigned char*)owned)[i]=(unsigned char)(i*37+sample*11+layout*17);
 put64(0x7123d688,0);for(unsigned i=0;i<11;i++){uintptr_t field=owned+0x28+i*24,sentinel=field+8,node=owned+0x1000+i*0x100,entity=owned+0x4000+i*0x100,counters=owned+0x8000+i*0x200;int active=layout||i==sample%11;
 put64(field,active?node:sentinel);put64(sentinel,active?node:0);put64(field+16,active?1:0);
 put64(node,0);put64(node+8,0);put64(node+16,sentinel);put64(node+0x28,entity);put64(entity,counters);put64(entity+0x10,c->size);put32(entity+0x2c,c->base);put32(counters,c->base+c->delta);put32(counters+0x148,c->base-1);
 }}
static void record(unsigned sample,unsigned layout,unsigned mode,unsigned initial,const struct CleanupOutput*out){printf("REC %u %u %u %u ",sample,layout,mode,initial);const unsigned char*p=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",p[i]);putchar('\n');}
static int map_original(const char*path){
 FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];
 if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;
 fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)unity,0x3000000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)unity||VirtualAlloc((void*)owned,0x40000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)owned)return 4;
#else
 if(mmap((void*)unity,0x3000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)unity||mmap((void*)owned,0x40000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(unity+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 5;}
 fclose(f);
#ifndef _WIN32
 __builtin___clear_cache((char*)unity,(char*)unity+0x3000000);
#endif
 return 0;
}
