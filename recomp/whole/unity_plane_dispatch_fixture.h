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
#define DISPATCH_HEAD UINT64_C(0x70ae3f04)
#define FIXTURE_RETURN UINT64_C(0x7f010000)
#define BLOCK_STACK UINT64_C(0x600000000)
#define BLOCK_DATA UINT64_C(0x600010000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t*block_data,*owned_stack,*constant_page,*constant_other;
static uint8_t initial_object[65536];
static uint64_t entry_sp,object_base;
static unsigned case_id;
static uint32_t selector;
static void die(const char*why){fprintf(stderr,"PLANE-DISPATCH-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static uint32_t get32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void put32(void*p,uint32_t v){memcpy(p,&v,4);}
static inline void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static uint8_t*fixed_map(uintptr_t address,size_t size){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)address,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)address){die("exact owned mapping");}return(uint8_t*)p;
}
static void readonly(uint8_t*p,size_t n){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,n,PAGE_READONLY,&old)){die("readonly mapping");}
#else
 if(mprotect(p,n,PROT_READ)){die("readonly mapping");}
#endif
}
static void setup(unsigned c,const char*constants){
 if(c>=16){die("case range");}case_id=c;selector=c<14?c:c==14?UINT32_MAX:2;
 block_data=fixed_map(BLOCK_DATA,65536);owned_stack=fixed_map(BLOCK_STACK,65536);constant_page=fixed_map(0x70fa0000,65536);constant_other=fixed_map(0x70eb0000,65536);memset(block_data,0xa5^c,65536);memset(owned_stack,0x5c,65536);entry_sp=BLOCK_STACK+0x8000;object_base=BLOCK_DATA+0x100;
 FILE*f=fopen(constants,"rb");if(!f||fread(constant_page,1,65536,f)!=65536||fread(constant_other,1,65536,f)!=65536||fgetc(f)!=EOF){die("original table/constants page");}fclose(f);readonly(constant_page,65536);readonly(constant_other,65536);
 // Finite preset domain: no pre-existing active planes and no optional resource.
 uint8_t*object=block_data+0x100;memset(object+0x97e8,0,0xa000-0x97e8);put32(object+0x7d4,0);object[0x21]=(uint8_t)(c==15);memcpy(initial_object,block_data,65536);
 if(get64(object+0x9b70)){die("optional resource must be NULL");}
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[0]=object_base;port_seeds[1]=UINT64_C(0xdeadbeef00000000)|selector;port_seeds[16]=DISPATCH_HEAD;port_seeds[30]=FIXTURE_RETURN;
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}
 port_controls[0]=0;port_controls[1]=c&1?0x9f:0;port_controls[2]=(uint64_t)c<<28;
}
static void check_object(uint32_t result){
 uint8_t*object=block_data+0x100;uint32_t want_result=case_id==15?0x20:(selector>=13||(selector>=7&&selector<=9))?0x50:0;
 if(result!=want_result){die("genuine original return value");}
 if(case_id==15){if(memcmp(block_data,initial_object,65536)){die("disabled object must remain unchanged");}return;}
 uint32_t mode=selector>=13||(selector>=7&&selector<=9)?2:selector;
 static const uint32_t counts[]={0,1,2,4,5,6,8,0,0,0,8,12,14};
 if(get32(object+0x97e8)!=mode||get32(object+0x7d4)!=counts[mode]||get64(object+0x9b70)){die("independent mode/count/resource effects");}
 if(mode==0||mode==1||mode>=10){uint8_t expected[65536];memcpy(expected,initial_object,65536);put32(expected+0x100+0x97e8,mode);put32(expected+0x100+0x7d4,counts[mode]);if(memcmp(expected,block_data,65536)){die("simple-case complete independent object oracle");}}
 for(unsigned i=0;i<65536;++i){int allowed=(i>=0x100+0x7d4&&i<0x100+0x7d8)||(i>=0x100+0x97e8&&i<0x100+0x9990);if(!allowed&&block_data[i]!=initial_object[i]){die("object allocation/padding/canary bounds");}}
 for(unsigned i=0;i<8;++i){uint64_t p=get64(object+0x9950+i*8);if(p&&(p<object_base+0x97ec||p>=object_base+0x97ec+8*0x2c||(p-object_base-0x97ec)%0x2c)){die("owned record pointer range/alignment");}}
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 check_object((uint32_t)get64(s));
 for(unsigned i=19;i<=29;++i){if(get64(s+i*8)!=port_seeds[i]){die("callee-saved GPR ABI");}}
 for(unsigned i=8;i<=15;++i){if(memcmp(s+256+i*16,port_qseeds+i*16,8)){die("callee-saved low64 SIMD ABI");}}
 if(get64(s+248)!=entry_sp||get64(s+784)!=0){die("original return SP/FPCR ABI");}
 for(unsigned i=0;i<65536;++i){if(i>=0x7000&&i<0x8000){continue;}if(native&&i>=0x9000-800&&i<0x9000){continue;}if(owned_stack[i]!=0x5c){die("owned stack bounded frames/canaries");}}
 uint64_t frame[]={get64(port_qseeds+9*16),get64(port_qseeds+8*16),port_seeds[20],port_seeds[19],port_seeds[29],port_seeds[30]};
 if(memcmp(owned_stack+0x8000-0x30,frame,0x30)){die("original dispatcher saved frame");}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant poll hooks");}
 // Helpers may legitimately differ in caller-clobbered registers and upper
 // halves of v8..v15. Compare complete object and specified return/ABI only.
 printf("RECORD case=%u selector=%08x result=%08x sp=%016llx callee=",case_id,selector,(unsigned)get64(s),(unsigned long long)get64(s+248));for(unsigned i=19;i<=29;++i){printf("%016llx",(unsigned long long)get64(s+i*8));}printf(" d8-d15=");for(unsigned i=8;i<=15;++i)for(unsigned j=0;j<8;++j){printf("%02x",s[256+i*16+j]);}printf(" object=");for(unsigned i=0;i<65536;++i){printf("%02x",block_data[i]);}puts(" canaries=exact");
 printf("OBSERVATION original-dispatcher=1 genuine-RET=1 optional-resource=NULL sqrt-fallback-executed=0 full-caller-clobber-equality=0 native=%d polls=%lu\n",native,polls);fflush(stdout);exit(0);
}
