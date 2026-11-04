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
#define YIELD_HEAD UINT64_C(0x703835a0)
#define YIELD_START UINT64_C(0x703835e4)
#define YIELD_STOP UINT64_C(0x703835f4)
#define YIELD_STACK UINT64_C(0x600000000)
#define YIELD_DATA UINT64_C(0x600010000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *owned_stack,*owned_data;
static uint64_t entry_sp;
static unsigned case_id;
static void die(const char*why){fprintf(stderr,"YIELD-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static uint8_t*fixed_map(uintptr_t address,size_t size){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)address,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)address){die("exact owned mapping");}return(uint8_t*)p;
}
static void setup(unsigned c){
 if(c>=16){die("case range");}case_id=c;
 owned_stack=fixed_map(YIELD_STACK,65536);owned_data=fixed_map(YIELD_DATA,65536);
 memset(owned_stack,0x5c,65536);memset(owned_data,0xa5^c,65536);entry_sp=YIELD_STACK+0x8000;
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[0]=YIELD_DATA+0x100;port_seeds[16]=YIELD_START;port_seeds[30]=UINT64_C(0x7f010000);
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}
 port_controls[0]=(uint64_t)(c&3)<<22;port_controls[1]=c&4?0x9f:0;port_controls[2]=(uint64_t)c<<28;
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 for(unsigned i=0;i<31;++i){const uint64_t expected=i==18?port_saved_x18:port_seeds[i];if(get64(s+i*8)!=expected){die("YIELD and original B preserve GPR including skipped BL/MOV");}}
 if(memcmp(s+256,port_qseeds,512)){die("all32Q preserved");}
 if(get64(s+248)!=entry_sp||get64(s+768)!=port_controls[2]||get64(s+776)!=port_controls[1]||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls){die("SP/NZCV/FPSR/FPCR/TLS preserved");}
 for(unsigned i=0;i<65536;++i){if(owned_data[i]!=(uint8_t)(0xa5^case_id)){die("all data canaries preserved");}if(native&&i>=0x8000-800&&i<0x8000){continue;}if(owned_stack[i]!=0x5c){die("no instruction stack writes/native capture bound");}}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant cooperative polls");}
 put64(s+18*8,0);put64(s+792,0);
 printf("RECORD case=%u state=",case_id);for(unsigned i=0;i<800;++i){printf("%02x",s[i]);}puts(" data-and-stack-canaries=exact");
 printf("OBSERVATION native=%d polls=%lu original-YIELD=703835e4 original-B=703835e8 continuation=703835f4 skipped-BL703835ec=1 full-FDE=0\n",native,polls);fflush(stdout);exit(0);
}
