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
static const uintptr_t owned=0x50000000,guest=0x70000000;
static const uintptr_t dispatch_pc=0x70ddd584,table_pc=0x70fef300,default_pc=0x70dddad4;
static const uintptr_t targets[]={0x70ddd5a0,0x70ddd614,0x70ddd634,0x70ddd648,0x70ddd934,0x70ddd998,0x70ddda64,0x70dddac8};
static const int32_t offsets[]={-2170208,-2170092,-2170060,-2170040,-2169292,-2169192,-2168988,-2168888};
static const uint32_t indices[]={0,1,2,3,4,5,6,7,8,9,255,0x7fffffffU,0x80000000U,0xfffffffeU,0xffffffffU};
static const uint64_t incoming[]={0xdeadbeef01234567ULL,0xabcdef0187654321ULL};
static const uint64_t old_x9=0xbbbbbbbb66666666ULL,old_x10=0xaaaaaaaa55555555ULL,old_x22=0xcccccccc77777777ULL;
struct Out{uint64_t target,nzcv,fpcr,fpsr,x8,x9,x10,x22,x27,abi;};
static void put32(uintptr_t p,uint32_t v){memcpy((void*)p,&v,4);}
static uint64_t hash_owned(void){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x1000;i++)h=(h^((unsigned char*)owned)[i])*1099511628211ULL;return h;}
static void seed(uint32_t index){memset((void*)owned,0xa5,0x1000);put32(owned+0x300,index);}
static uint64_t expected_target(uint32_t i){return i<=7?targets[i]:default_pc;}
// An invalid table address on one default profile proves that the unsigned
// guard reaches its genuine direct default without loading a table row.
static uint64_t input_table(uint32_t i,unsigned n){return i>7&&n?0x28:table_pc;}
static void record(uint32_t index,unsigned n,const struct Out*out){printf("REC %08x %u %016llx ",index,n,(unsigned long long)hash_owned());const unsigned char*b=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);i++)printf("%02x",b[i]);putchar('\n');}
static int map_original(const char*path){
 FILE*f=fopen(path,"rb");if(!f)return 1;Elf64_Ehdr e;Elf64_Phdr ph[32];if(fread(&e,1,sizeof(e),f)!=sizeof(e)||e.e_phnum>32||e.e_machine!=183)return 2;fseek(f,e.e_phoff,SEEK_SET);if(fread(ph,sizeof(*ph),e.e_phnum,f)!=e.e_phnum)return 3;
#ifdef _WIN32
 if(VirtualAlloc((void*)guest,0x2000000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)guest||VirtualAlloc((void*)owned,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE)!=(void*)owned)return 4;
#else
 if(mmap((void*)guest,0x2000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)guest||mmap((void*)owned,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)owned)return 4;
#endif
 for(unsigned i=0;i<e.e_phnum;i++)if(ph[i].p_type==PT_LOAD){if(ph[i].p_vaddr+ph[i].p_memsz>0x2000000)return 5;fseek(f,ph[i].p_offset,SEEK_SET);if(fread((void*)(guest+ph[i].p_vaddr),1,ph[i].p_filesz,f)!=ph[i].p_filesz)return 6;}
 fclose(f);
 for(unsigned n=0;n<8;n++){int32_t value;memcpy(&value,(void*)(table_pc+4*n),4);if(value!=offsets[n]||(uint64_t)((int64_t)table_pc+(int64_t)value)!=targets[n])return 7;}
#ifndef _WIN32
 // TEST destination observers in fixture-owned mapped code. The original
 // ELF on disk, exact28B dispatch prefix and signed table stay unchanged.
 for(unsigned n=0;n<9;n++){uintptr_t pc=n<8?targets[n]:default_pc;uint32_t op[]={0x52800000U|((pc&0xffffU)<<5),0x72a00000U|(((pc>>16)&0xffffU)<<5),0xd65f03c0U};memcpy((void*)pc,op,sizeof(op));}
 __builtin___clear_cache((char*)guest,(char*)guest+0x2000000);
#endif
 return 0;
}
