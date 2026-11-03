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
#define OBJECT_HEAD UINT64_C(0x707520c4)
#define OBJECT_CAPTURE UINT64_C(0x7f010000)
#define OBJECT_DATA UINT64_C(0x500000000)
#define OBJECT_STACK UINT64_C(0x600000000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *object_data,*owned_stack,*global_page;
static uint8_t expected_data[65536];
static uint64_t expected_gpr[32],entry_sp,global_value;
static unsigned case_id,flag_id;
static void die(const char *why){fprintf(stderr,"ST2-CONSTRUCTOR-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static void put32(void*p,uint32_t v){memcpy(p,&v,4);}
static uint8_t*fixed_map(uintptr_t address,size_t size){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)address,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)address){die("exact owned mapping");}return(uint8_t*)p;
}
static void protect(uint8_t*p,size_t size,int none){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,size,none?PAGE_NOACCESS:PAGE_READONLY,&old))die("mapping protection");
#else
 if(mprotect(p,size,none?PROT_NONE:PROT_READ))die("mapping protection");
#endif
}
static void load_file(void*dst,size_t size,const char*path){FILE*f=fopen(path,"rb");if(!f||fread(dst,1,size,f)!=size||fgetc(f)!=EOF)die("exact original fixture bytes");fclose(f);}
// literals.bin is exact original Q[70e78fa0] followed by D[70e810e8].
// global.bin is an opaque fixture input, not a claim about the game's mutable slot.
static void setup(unsigned c,uint64_t lr,uint64_t original_global,const uint8_t*literals){
 static const uint32_t w1[]={0,1,0xffffffff,0x80000000},w2[]={0,8,0x12345678,0xffffffff};
 if(c>=16){die("case range");}case_id=c;flag_id=c&3;unsigned pattern=c>>2;
 object_data=fixed_map(OBJECT_DATA,65536);owned_stack=fixed_map(OBJECT_STACK,65536);
 global_page=fixed_map(0x71230000,65536);
 memset(object_data,(int)(0xa5^c),65536);memset(owned_stack,0x5c,65536);entry_sp=OBJECT_STACK+0x8000;
 global_value=pattern&1?UINT64_C(0xfedcba9876543210):original_global;put64(global_page+0xcc90,global_value);
 uint8_t*q=fixed_map(0x70e70000,65536),*d=fixed_map(0x70e80000,65536);
 memcpy(q+0x8fa0,literals,16);memcpy(d+0x10e8,literals+16,8);protect(q,65536,0);protect(d,65536,0);
 for(unsigned i=0;i<31;++i)port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);
 port_seeds[0]=OBJECT_DATA+256;port_seeds[1]=UINT64_C(0xdeadbeef00000000)|w1[pattern];port_seeds[2]=UINT64_C(0xabcdef1200000000)|w2[pattern];port_seeds[16]=OBJECT_HEAD;port_seeds[30]=lr;
 port_controls[0]=(uint64_t)flag_id<<22;port_controls[1]=flag_id&1?0x9f:0;port_controls[2]=(uint64_t)(flag_id*5)<<28;
 for(unsigned i=0;i<512;++i)port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);
 uint64_t b=port_seeds[0];memcpy(expected_gpr,port_seeds,31*8);expected_gpr[0]=b+8;expected_gpr[8]=b+0x530;expected_gpr[9]=b+0x520;expected_gpr[10]=b+0x510;expected_gpr[11]=global_value;expected_gpr[31]=entry_sp;
 memcpy(expected_data,object_data,65536);uint8_t*e=expected_data+256;put32(e,w1[pattern]);put32(e+4,w2[pattern]);memset(e+8,0,0x68);
 put64(e+0x70,b+0x78);put64(e+0x78,0);put64(e+0x80,0);put64(e+0x88,0);put32(e+0x90,0x29);put64(e+0x98,0);put64(e+0xa0,0);put64(e+0xa8,global_value);memcpy(e+0xb0,literals,16);
 put64(e+0xc0,b+0xc8);put64(e+0xc8,0);put64(e+0xd0,0);put64(e+0xd8,0);put32(e+0xe0,0x29);put64(e+0xe8,0);put64(e+0xf0,0);put64(e+0xf8,global_value);put64(e+0x100,0);memcpy(e+0x108,literals+16,8);put64(e+0x110,0);put32(e+0x118,0x29);put64(e+0x120,0);put64(e+0x128,0);
 for(unsigned i=0;i<32;++i){uint64_t p=b+0x130+i*32;put64(e+0x130+i*32,p);put64(e+0x138+i*32,p);put64(e+0x140+i*32,p+16);put64(e+0x148+i*32,p+16);}
 put64(e+0x530,b+0x530);put64(e+0x538,b+0x530);for(unsigned i=0x540;i<=0x570;i+=8)put64(e+i,0);put32(e+0x578,0);put64(e+0x580,0);put32(e+0x588,0);e[0x58c]=0;
 // Real inaccessible stack endpoints; 16KiB below SP is the declared libc/capture budget.
 protect(owned_stack,4096,1);protect(owned_stack+61440,4096,1);
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 if(memcmp(object_data,expected_data,65536))die("complete object/padding and allocation canaries");
 const unsigned defined[]={0,8,9,10,11,19,20,21,22,23,24,25,26,27,28,29,30,31};
 for(unsigned i=0;i<sizeof(defined)/sizeof(*defined);++i){unsigned r=defined[i];if(get64(s+r*8)!=expected_gpr[r]){fprintf(stderr,"x%u\n",r);die("ABI-preserved or post-call-defined GPR/SP");}}
 if(get64(s+18*8)!=port_saved_x18||get64(s+792)!=port_saved_tls)die("platform register/TLS preservation");
 for(unsigned v=0;v<2;++v)if(get64(s+256+v*16)!=port_seeds[0]+0x510||get64(s+264+v*16)!=port_seeds[0]+0x520)die("post-call-defined Q0/Q1");
 for(unsigned v=8;v<=15;++v)if(get64(s+256+v*16)!=get64(port_qseeds+v*16))die("ABI D8-D15 low64 preservation");
 if(get64(s+768)!=0x60000000||(get64(s+784)&UINT64_C(0x00c00000))!=port_controls[0])die("final CMP NZCV/FPCR rounding preservation");
 for(unsigned i=4096;i<61440;++i){uint64_t a=OBJECT_STACK+i;if(a>=entry_sp-0x4000&&a<entry_sp)continue;if(owned_stack[i]!=0x5c)die("bounded stack canaries");}
 if((!polled&&polls)||(polled&&!polls))die("dormant poll hooks");
 // Keep every raw captured byte; only the explicit defined subset forms RECORD.
 printf("OBSERVATION native=%d polls=%lu snapshot800=",native,polls);for(unsigned i=0;i<800;++i)printf("%02x",s[i]);printf("\n");
 printf("RECORD case=%u defined=",case_id);for(unsigned i=0;i<sizeof(defined)/sizeof(*defined);++i){unsigned r=defined[i];uint64_t x=r==30?OBJECT_CAPTURE:get64(s+r*8);printf("%016llx",(unsigned long long)x);}for(unsigned v=0;v<2;++v)for(unsigned j=0;j<16;++j)printf("%02x",s[256+v*16+j]);for(unsigned v=8;v<=15;++v)printf("%016llx",(unsigned long long)get64(s+256+v*16));printf(" nzcv=%016llx rmode=%016llx object=",(unsigned long long)get64(s+768),(unsigned long long)(get64(s+784)&UINT64_C(0x00c00000)));for(unsigned i=0;i<0x590;++i)printf("%02x",object_data[256+i]);printf(" allocation-canaries=exact stack-bounds=exact\n");fflush(stdout);exit(0);
}
