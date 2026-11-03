#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#define OBJECT_HEAD UINT64_C(0x707bb458)
#define OBJECT_CAPTURE UINT64_C(0x7f010000)
#define OBJECT_DATA UINT64_C(0x500000000)
#define OBJECT_STACK UINT64_C(0x600000000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *object_data,*owned_stack,*global_page;
static uint8_t expected_data[65536],expected_vectors[512];
static uint64_t expected_gpr[32],entry_sp,global_value;
static unsigned case_id,flag_id;
static void die(const char *why){fprintf(stderr,"ST2-OBJECT-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static void put32(void*p,uint32_t v){memcpy(p,&v,4);}
static uint8_t*fixed_map(uintptr_t address,size_t size){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)address,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)address){die("exact owned mapping");}
 return(uint8_t*)p;
}
static void readonly(uint8_t*p,size_t size){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,size,PAGE_READONLY,&old))die("global protection");
#else
 if(mprotect(p,size,PROT_READ))die("global protection");
#endif
}
static void setup(unsigned c,uint64_t lr,uint64_t original_global){
 static const uint32_t w1[]={0,1,0xffffffff,0x80000000},w2[]={0,8,0x12345678,0xffffffff};if(c>=16)die("case range");case_id=c;flag_id=c&3;unsigned pattern=c>>2;
 object_data=fixed_map(OBJECT_DATA,65536);owned_stack=fixed_map(OBJECT_STACK,65536);global_page=fixed_map(0x71230000,65536);memset(object_data,(int)(0xa5^c),65536);memset(owned_stack,0x5c,65536);entry_sp=OBJECT_STACK+0x8000;
 global_value=pattern&1?UINT64_C(0xfedcba9876543210):original_global;put64(global_page+0xcc90,global_value);readonly(global_page,65536);
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[0]=OBJECT_DATA+256;port_seeds[1]=UINT64_C(0xdeadbeef00000000)|w1[pattern];port_seeds[2]=UINT64_C(0xabcdef1200000000)|w2[pattern];port_seeds[16]=OBJECT_HEAD;port_seeds[30]=lr;
 port_controls[0]=(uint64_t)flag_id<<22;port_controls[1]=flag_id&1?0x9f:0;port_controls[2]=(uint64_t)(flag_id*5)<<28;
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}
 memcpy(expected_vectors,port_qseeds,512);uint64_t base=port_seeds[0];put64(expected_vectors,base+0x468);put64(expected_vectors+8,base+0x478);memcpy(expected_vectors+16,expected_vectors,16);
 memcpy(expected_gpr,port_seeds,31*8);expected_gpr[8]=base+0x40;expected_gpr[9]=base+0x30;expected_gpr[10]=base+0x40;expected_gpr[11]=base+0x478;expected_gpr[12]=base+0x480;expected_gpr[13]=base+0x478;expected_gpr[31]=entry_sp;
 memcpy(expected_data,object_data,65536);uint8_t*e=expected_data+256;put32(e,w1[pattern]);put32(e+4,w2[pattern]);memset(e+8,0,0x28);put64(e+0x30,base+0x30);put64(e+0x38,base+0x30);put64(e+0x40,base+0x40);put64(e+0x48,base+0x40);put64(e+0x50,global_value);put64(e+0x58,0);put32(e+0x60,0);put32(e+0x64,w1[pattern]);put64(e+0x68,0);put32(e+0x70,w1[pattern]);put64(e+0x78,0);put64(e+0x80,0);
 for(unsigned i=0;i<64;++i){uint64_t node=base+0x88+i*16;put64(e+0x88+i*16,node);put64(e+0x90+i*16,node);}put64(e+0x488,0);put32(e+0x490,0);e[0x494]=0;e[0x495]=1;
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 if(memcmp(object_data,expected_data,65536))die("independent all0x498 object bytes and complete allocation canaries");
 for(unsigned i=0;i<32;++i){uint64_t want=i==18?port_saved_x18:expected_gpr[i];if(get64(s+i*8)!=want){fprintf(stderr,"GPR%u got%llx expected%llx\n",i,(unsigned long long)get64(s+i*8),(unsigned long long)want);die("all GPR/SP effects");}}
 if(memcmp(s+256,expected_vectors,512)||get64(s+768)!=0x60000000||get64(s+776)!=port_controls[1]||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls)die("full SIMD/NZCV/FPSR/FPCR/TLS effects");
 for(unsigned i=0;i<65536;++i){if(native&&OBJECT_STACK+i>=entry_sp-800&&OBJECT_STACK+i<entry_sp)continue;if(owned_stack[i]!=0x5c)die("leaf original stack unchanged outside native capture");}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant poll hooks");}
 put64(s+18*8,0);put64(s+30*8,OBJECT_CAPTURE);put64(s+792,0);
 printf("RECORD case=%u state=",case_id);for(unsigned i=0;i<800;++i)printf("%02x",s[i]);printf(" object=");for(unsigned i=0;i<0x498;++i)printf("%02x",object_data[256+i]);printf(" allocation-canaries=exact stack=exact\n");printf("OBSERVATION original-complete-return=1 native=%d polls=%lu\n",native,polls);fflush(stdout);exit(0);
}
