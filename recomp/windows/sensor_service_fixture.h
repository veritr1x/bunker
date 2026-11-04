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
#define SENSOR_HEAD UINT64_C(0x704119f8)
#define FIXTURE_RETURN UINT64_C(0x7f010000)
#define BLOCK_STACK UINT64_C(0x600000000)
#define GLOBAL_BASE UINT64_C(0x712b0000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *globals,*owned_stack;
static uint8_t initial_globals[65536];
static uint64_t entry_sp;
static unsigned case_id,sensor_calls,memset_calls,capability_checks;
static unsigned provider_errno_checked,provider_last_error,control_last_error;
static const uint32_t capability_types[]={0,1,4,9,11,35,36,UINT32_MAX};
static void die(const char*why){fprintf(stderr,"SENSOR-SERVICE-FAIL %s\n",why);fflush(stderr);exit(20);}
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
 if(c>=4){die("case range");}case_id=c;
 globals=fixed_map(GLOBAL_BASE,65536);owned_stack=fixed_map(BLOCK_STACK,65536);
 for(unsigned i=0;i<65536;++i){globals[i]=(uint8_t)(i*17+c*31+0xa5);}memset(owned_stack,0x5c,65536);
 put64(globals+0xe040,c==2?UINT64_C(0x1234abcd5678ef00):0);memcpy(initial_globals,globals,65536);entry_sp=BLOCK_STACK+0x8000;
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[16]=SENSOR_HEAD;port_seeds[30]=FIXTURE_RETURN;
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}
 port_controls[0]=0;port_controls[1]=c&1?0x9f:0;port_controls[2]=(uint64_t)c<<28;
}
static void check_effects(unsigned invocations){
 uint8_t expected[65536];memcpy(expected,initial_globals,65536);if(case_id!=2){memset(expected+0xe048,0,0x240);}
 if(memcmp(globals,expected,65536)){die("independent complete globals/zero240/canary oracle");}
 if(sensor_calls!=(case_id==2?0:invocations)||memset_calls!=sensor_calls){die("exact unavailable-manager and real-memset call counts");}
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 check_effects(case_id==3?2:1);
 for(unsigned i=19;i<=29;++i){if(get64(s+i*8)!=port_seeds[i]){die("callee-saved GPR ABI");}}
 for(unsigned i=8;i<=15;++i){if(memcmp(s+256+i*16,port_qseeds+i*16,8)){die("callee-saved low64 SIMD ABI");}}
 if(get64(s+248)!=entry_sp||get64(s+784)!=port_controls[0]){die("genuine original return SP/FPCR");}
 for(unsigned i=0;i<65536;++i){if(i>=0x7000&&i<0x8000){continue;}if(native&&i>=0x9000-800&&i<0x9000){continue;}if(owned_stack[i]!=0x5c){die("owned stack bounded frames/canaries");}}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant poll hooks");}
 printf("RECORD case=%u calls=%u memset=%u sp=%016llx callee=",case_id,sensor_calls,memset_calls,(unsigned long long)get64(s+248));for(unsigned i=19;i<=29;++i){printf("%016llx",(unsigned long long)get64(s+i*8));}printf(" d8-d15=");for(unsigned i=8;i<=15;++i)for(unsigned j=0;j<8;++j){printf("%02x",s[256+i*16+j]);}printf(" globals=");for(unsigned i=0;i<65536;++i){printf("%02x",globals[i]);}puts(" canaries=exact");
 printf("OBSERVATION capability-checks=%u complete-original-caller=1 genuine-RET=1 unavailable-service=1 native-test-seam=%d android-failure-equivalence=0 physical-sensor-claim=0 polls=%lu errno-preserved=%u provider-control-LastError=%u/%u absolute-Runtime-error-preservation=0\n",capability_checks,native,polls,provider_errno_checked,provider_last_error,control_last_error);fflush(stdout);exit(0);
}
