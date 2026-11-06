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
static const uintptr_t regex_owned=0x50000000,regex_sp=0x5001e000;
static void regex_p32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}static void regex_p64(uintptr_t p,uint64_t v){memcpy((void*)p,&v,8);}
static const uint64_t regex_entries[]={0x84315734,0x84316814};
static const uint64_t regex_saved[]={0x2828282828282828ULL,0x2727272727272727ULL,0x2626262626262626ULL,0x2525252525252525ULL,0x2424242424242424ULL,0x2323232323232323ULL,0x2222222222222222ULL,0x2121212121212121ULL,0x2020202020202020ULL,0x1919191919191919ULL,0x2929292929292929ULL};
static void regex_seed(unsigned which,unsigned n,unsigned profile){
 for(unsigned i=0;i<0x4000;i++)((unsigned char*)regex_owned)[i]=(unsigned char)(i*37+n*11+profile*17);
 for(unsigned i=0;i<0x1000;i++)((unsigned char*)(regex_owned+0x1c000))[i]=0xa5;
 for(unsigned i=0;i<31;i++)regex_p64(regex_owned+0x1c000+i*8,0x1234000000000000ULL+i);
 regex_p64(regex_owned+0x1c000,regex_owned);regex_p64(regex_owned+0x1c000+16*8,regex_entries[which]);regex_p64(regex_owned+0x1c000+19*8,regex_owned);
 regex_p64(regex_owned+0x1c000+23*8,0x85a87e7c);regex_p64(regex_owned+0x1c000+25*8,0x85a87df4);regex_p64(regex_owned+0x1c000+27*8,0x85a87d48);regex_p64(regex_owned+0x1c000+29*8,regex_sp+0x50);regex_p64(regex_owned+0x1c000+30*8,0x843167fc);
 for(unsigned i=0;i<512;i++)((unsigned char*)(regex_owned+0x1c100))[i]=(unsigned char)(i*19+0xd9);
 for(unsigned i=0;i<11;i++)regex_p64(regex_sp+i*8,regex_saved[i]);
 regex_p64(regex_owned+0x1c800,profile?0x03c00000:0);regex_p64(regex_owned+0x1c808,profile?0x0800009f:0);regex_p64(regex_owned+0x1c810,0xa0000000);
 regex_p64(regex_owned+0x88,regex_owned+0x1000);regex_p32(regex_owned+0x90,0);regex_p32(regex_owned+0x1000+0x18,3);regex_p32(regex_owned+0x1000+0x20,23|(profile?0x240:0));regex_p32(regex_owned+0x1000+0x24,0);regex_p32(regex_owned+0x1000+0x28,40|(profile?0x240:0));
 regex_p64(regex_owned+0x30,regex_owned+0x2000);regex_p32(regex_owned+0x38,2);regex_p32(regex_owned+0x2000+0x18,2);static const uint32_t positions[]={0,1,31,1024};regex_p32(regex_owned+0x28,positions[n]);((unsigned char*)regex_owned)[0x74]=profile?0:1;regex_p32(regex_owned+0x7c,4);
}
static int regex_check(const unsigned char*before,unsigned which,unsigned profile){unsigned char expected[0x4000];memcpy(expected,before,sizeof(expected));if(!which){uint32_t v=0;memcpy(expected+0x38,&v,4);memcpy(expected+0x2000+0x20,&v,4);memcpy(expected+0x2000+0x24,before+0x28,4);v=2;memcpy(expected+0x90,&v,4);v=40;memcpy(expected+0x80,&v,4);expected[0xbc]=expected[0xbd]=profile?1:0;if(profile){v=2;memcpy(expected+0x7c,&v,4);}}return!memcmp(expected,(void*)regex_owned,sizeof(expected));}
static uint64_t regex_hash(const void*data,unsigned size){uint64_t h=1469598103934665603ULL;const unsigned char*p=(const unsigned char*)data;for(unsigned i=0;i<size;i++)h=(h^p[i])*1099511628211ULL;return h;}
static void regex_record(unsigned which,unsigned n,unsigned profile){printf("REC %u %u %u %016llx ",which,n,profile,(unsigned long long)regex_hash((void*)regex_owned,0x4000));for(unsigned i=0;i<784;i++)printf("%02x",((unsigned char*)(regex_sp+0x60))[i]);putchar('\n');}
static int regex_map(const char*path){FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)0x80000000,0x8000000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)!=(void*)0x80000000||VirtualAlloc((void*)regex_owned,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)!=(void*)regex_owned)return 4;
#else
 if(mmap((void*)0x80000000,0x8000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)0x80000000||mmap((void*)regex_owned,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)regex_owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++){if(ph[i].p_type==PT_LOAD){fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(0x80000000+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 5;}}
 fclose(f);
#ifndef _WIN32
 __builtin___clear_cache((char*)0x80000000,(char*)0x88000000);
#endif
 return 0;}
