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
static const uintptr_t owned=0x50000000,unity=0x80000000;
struct FormatCase{uint32_t start,end,offset,count;};
struct FormatProfile{uint64_t fpcr,fpsr;};
static const struct FormatProfile format_profiles[]={{0,0},{0x03c00000,0x0800009f}};
struct FormatStatus{uint64_t result,fpcr,fpsr,nzcv,abi;};
static void p32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}static void p64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}
static struct FormatCase format_case(unsigned n){if(n<32){struct FormatCase c={(n/8)*8,(n/8)*8+n%8+1,0,(n%3)*3};return c;}static const struct FormatCase more[]={{0,32,0,0},{3,29,0,3},{7,26,0,6},{8,8,0,7},{20,18,0,2},{27,32,0,3},{31,32,0,0},{32,40,0,5},{0,23,5,4},{0,9,31,3}};return more[n-32];}
static void format_seed(unsigned n,unsigned profile){for(unsigned i=0;i<0x2000;i++)((unsigned char*)owned)[i]=(unsigned char)(i*37+n*11+profile*17);struct FormatCase c=format_case(n);p64(owned+0x18,owned+0x1000);p32(owned+0x34,c.offset);p32(owned+0x4c,c.count);p32(owned+0x1000+0x18,128);static const uint32_t words[2][4]={{0x01234567,0x89abcdef,0xfedcba98,0x76543210},{0xffffffff,0x80000000,0x12345678,0}};for(unsigned i=0;i<4;i++)p32(owned+0x3c+i*4,words[profile][i]);}
static int format_check(const unsigned char*before,unsigned n){unsigned char expected[0x2000];memcpy(expected,before,sizeof(expected));struct FormatCase c=format_case(n);if((int32_t)(c.end-c.start)>0){uint32_t count=c.count+c.end-c.start;memcpy(expected+0x4c,&count,4);for(uint32_t j=0;j<c.end-c.start;j++){uint32_t digit=c.offset+c.start+j,word=0;if(digit/8<4)memcpy(&word,before+0x3c+digit/8*4,4);uint16_t value=(uint16_t)(0x30|((word>>((digit%8)*4))&15));memcpy(expected+0x1000+0x20+(count-1-j)*2,&value,2);}}return!memcmp(expected,(void*)owned,sizeof(expected));}
static uint64_t format_hash(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x2000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void format_record(unsigned n,unsigned profile,const struct FormatStatus*s){printf("REC %u %u %016llx ",n,profile,(unsigned long long)format_hash());const unsigned char*parts[]={(const unsigned char*)owned,(const unsigned char*)(owned+0x1000),(const unsigned char*)s};const unsigned sizes[]={0x80,0x140,sizeof(*s)};for(unsigned p=0;p<3;p++)for(unsigned i=0;i<sizes[p];i++)printf("%02x",parts[p][i]);putchar('\n');}
static int map_original(const char*path){
 FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];
 if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;
 fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)unity,0x8000000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)unity||VirtualAlloc((void*)owned,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)owned)return 4;
#else
 if(mmap((void*)unity,0x8000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)unity||mmap((void*)owned,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(unity+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 5;}
 fclose(f);
#ifndef _WIN32
 __builtin___clear_cache((char*)unity,(char*)unity+0x8000000);
#endif
 return 0;
}
