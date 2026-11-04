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
#define CALLBACK_STACK UINT64_C(0x600000000)
#define CALLBACK_DATA UINT64_C(0x600010000)
#define CALLBACK_RETURN UINT64_C(0x7f010000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t*owned_memory,*owned_stack;
static uint8_t initial_memory[65536],expected_memory[65536];
static uint64_t oracle_regs[31],oracle_flags;
static uint64_t entry_sp,owner,output,ring;
static unsigned case_id;
static void die(const char*why){fprintf(stderr,"FMOD-PURE-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put32(void*p,uint32_t v){memcpy(p,&v,4);}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static uint8_t*fixed_map(uintptr_t a,size_t n){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)a,n,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)a,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)a){die("exact owned mapping");}return(uint8_t*)p;
}
struct PureCase{unsigned kind,optional;uint32_t a,b,offset,request;uint64_t value;};
static const uint64_t heads[6]={0x70b3bbfc,0x70b3bc5c,0x70b3bd90,0x70b3be80,0x70b3bef8,0x70b3bf1c};
static const struct PureCase cases[]={
 {0,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {0,1,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {1,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {1,1,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {2,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {2,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x1)},
 {2,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x1122334455667788)},
 {2,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0xfedcba9876543210)},
 {3,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,1,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,2,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,3,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,4,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,5,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,6,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,7,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {3,8,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x3e8),UINT32_C(0x10),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0xfffffc18),UINT32_C(0x10),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x3e8),UINT32_C(0xfffffff0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0xfffffc18),UINT32_C(0xfffffff0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x80000000),UINT32_C(0xffffffff),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x80000000),UINT32_C(0x1),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x1),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {4,0,UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT32_C(0x0),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x0),UINT32_C(0x10),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x3c),UINT32_C(0x8),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x10),UINT32_C(0x64),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x40),UINT32_C(0x8),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x41),UINT32_C(0x8),UINT64_C(0x0)},
 {5,0,UINT32_C(0x0),UINT32_C(0x8),UINT32_C(0x0),UINT32_C(0x8),UINT64_C(0x0)},
 {5,0,UINT32_C(0x10000001),UINT32_C(0x10),UINT32_C(0x4),UINT32_C(0x14),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x20),UINT32_C(0x0),UINT64_C(0x0)},
 {5,0,UINT32_C(0x8),UINT32_C(0x8),UINT32_C(0x0),UINT32_C(0xffffffff),UINT64_C(0x0)},
 {5,0,UINT32_C(0x80000000),UINT32_C(0x1),UINT32_C(0x0),UINT32_C(0x1),UINT64_C(0x0)},
};
#define PURE_CASE_COUNT (sizeof(cases)/sizeof(cases[0]))
static void setup(unsigned c){
 if(c>=PURE_CASE_COUNT){die("case range");}case_id=c;const struct PureCase*t=&cases[c];owned_memory=fixed_map(CALLBACK_DATA,65536);owned_stack=fixed_map(CALLBACK_STACK,65536);memset(owned_memory,0xa5^c,65536);memset(owned_stack,0x5c,65536);entry_sp=CALLBACK_STACK+0x8000;owner=CALLBACK_DATA+0x1000;output=CALLBACK_DATA+0x2000;ring=CALLBACK_DATA+0x4000;
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[0]=owner+0x38;port_seeds[16]=heads[t->kind];port_seeds[30]=CALLBACK_RETURN;
 if(t->kind==0){port_seeds[1]=t->optional?output+1:0;}
 if(t->kind==1){port_seeds[2]=t->optional?output+3:0;}
 if(t->kind==2){port_seeds[1]=t->value;}
 if(t->kind==3){unsigned mask=t->optional==8?7:t->optional;port_seeds[2]=mask&1?output+1:0;port_seeds[3]=mask&2?output+9:0;port_seeds[4]=mask&4?output+17:0;if(t->optional==8){port_seeds[2]=port_seeds[3]=port_seeds[4]=output+1;}}
 if(t->kind==4){put32(owned_memory+0x1000+0x27c,t->a);put32(owned_memory+0x1000+0x288,t->b);port_seeds[2]=output+3;}
 if(t->kind==5){put32(owned_memory+0x1000+0x278,t->a);put32(owned_memory+0x1000+0x288,t->b);put64(owned_memory+0x1000+0x280,ring);port_seeds[2]=UINT64_C(0xdeadbeef00000000)|t->offset;port_seeds[3]=UINT64_C(0xcafe123400000000)|t->request;port_seeds[4]=output+1;port_seeds[5]=output+17;port_seeds[6]=output+33;port_seeds[7]=output+45;}
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}port_controls[0]=(uint64_t)(c&3)<<22;port_controls[1]=c&1?0x9f:0;port_controls[2]=(uint64_t)(c&15)<<28;memcpy(initial_memory,owned_memory,65536);
}
static void write32(uint64_t a,uint32_t v){if(a<CALLBACK_DATA||a-CALLBACK_DATA>65536-4){die("oracle write32 bound");}put32(expected_memory+a-CALLBACK_DATA,v);}
static void write64(uint64_t a,uint64_t v){if(a<CALLBACK_DATA||a-CALLBACK_DATA>65536-8){die("oracle write64 bound");}put64(expected_memory+a-CALLBACK_DATA,v);}
static uint64_t sub_flags(uint64_t a,uint64_t b,unsigned bits){uint64_t mask=bits==32?UINT32_MAX:UINT64_MAX;uint64_t sign=UINT64_C(1)<<(bits-1);a&=mask;b&=mask;uint64_t r=(a-b)&mask;return((r&sign)?UINT64_C(1)<<31:0)|(r==0?UINT64_C(1)<<30:0)|(a>=b?UINT64_C(1)<<29:0)|(((a^b)&(a^r)&sign)?UINT64_C(1)<<28:0);}
static void oracle(void){
 const struct PureCase*t=&cases[case_id];memcpy(oracle_regs,port_seeds,sizeof(oracle_regs));oracle_flags=port_controls[2];memcpy(expected_memory,initial_memory,65536);oracle_regs[0]=0;
 if(t->kind==0){if(port_seeds[1]){oracle_regs[8]=1;write32(port_seeds[1],1);}}
 if(t->kind==1){if(port_seeds[2]){oracle_regs[8]=16;write32(port_seeds[2],16);}}
 if(t->kind==2){oracle_regs[8]=owner;oracle_flags=sub_flags(port_seeds[0],0,64);write64(owner+0x270,port_seeds[1]);}
 if(t->kind==3){if(port_seeds[3]){oracle_regs[8]=44100;write32(port_seeds[3],44100);}if(port_seeds[4]){oracle_regs[8]=44100;write32(port_seeds[4],44100);}if(port_seeds[2]){oracle_regs[8]=16;write32(port_seeds[2],16);}}
 if(t->kind==4){int64_t a=(int32_t)t->a,b=(int32_t)t->b;uint32_t q=b?(uint32_t)(a/b):0;oracle_regs[8]=q;oracle_regs[9]=t->a;oracle_flags=sub_flags(port_seeds[0],0,64);write32(port_seeds[2],q);}
 if(t->kind==5){uint32_t capacity=t->a*t->b,requested=capacity<t->request?capacity:t->request;uint32_t remaining=capacity-t->offset;oracle_regs[8]=owner;oracle_regs[9]=requested;oracle_regs[10]=remaining;oracle_regs[11]=capacity;oracle_flags=sub_flags(capacity,t->offset,32);
  if(capacity<=t->offset){oracle_regs[0]=37;write64(port_seeds[5],0);write64(port_seeds[4],0);write32(port_seeds[7],0);write32(port_seeds[6],0);}
  else{uint32_t end=t->offset+requested;oracle_regs[12]=ring+t->offset;oracle_regs[13]=end;oracle_flags=sub_flags(end,capacity,32);write64(port_seeds[4],ring+t->offset);
   if(end<=capacity){oracle_regs[8]=0;write32(port_seeds[6],requested);write64(port_seeds[5],0);write32(port_seeds[7],0);}
   else{uint32_t tail=requested-remaining;oracle_regs[8]=tail;write32(port_seeds[6],remaining);write64(port_seeds[5],ring);write32(port_seeds[7],tail);}
  }
 }
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 oracle();if(memcmp(expected_memory,owned_memory,65536)){for(unsigned i=0;i<65536;++i){if(expected_memory[i]!=owned_memory[i]){fprintf(stderr,"memory%u got%02x want%02x\n",i,owned_memory[i],expected_memory[i]);break;}}die("complete independent struct/output/allocation oracle");}
 oracle_regs[18]=port_saved_x18;for(unsigned i=0;i<31;++i){if(get64(s+i*8)!=oracle_regs[i]){fprintf(stderr,"GPR%u got%llx want%llx\n",i,(unsigned long long)get64(s+i*8),(unsigned long long)oracle_regs[i]);die("complete GPR oracle");}}
 if(get64(s+248)!=entry_sp||memcmp(s+256,port_qseeds,512)||get64(s+768)!=oracle_flags||get64(s+776)!=port_controls[1]||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls){die("complete SP/SIMD/NZCV/FPSR/FPCR/TLS oracle");}
 for(unsigned i=0;i<65536;++i){if(native&&i>=0x9000-800&&i<0x9000){continue;}if(owned_stack[i]!=0x5c){die("leaf stack/capture bound");}}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant poll hooks");}put64(s+18*8,0);put64(s+30*8,CALLBACK_RETURN);put64(s+792,0);
 printf("RECORD case=%u entry=%llx state=",case_id,(unsigned long long)heads[cases[case_id].kind]);for(unsigned i=0;i<800;++i){printf("%02x",s[i]);}printf(" memory=");for(unsigned i=0;i<65536;++i){printf("%02x",owned_memory[i]);}puts(" canaries=exact");printf("OBSERVATION complete-callfree-callback=1 genuine-RET=1 audio-device=0 native=%d polls=%lu\n",native,polls);fflush(stdout);exit(0);
}
