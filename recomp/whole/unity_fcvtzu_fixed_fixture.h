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
#define OBJECT_HEAD UINT64_C(0x70362a2c)
#define OBJECT_CAPTURE UINT64_C(0x7f010000)
#define OBJECT_DATA UINT64_C(0x500000000)
#define OBJECT_STACK UINT64_C(0x600000000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t*object_data,*owned_stack;
static uint8_t expected_data[65536],expected_vectors[512],expected_stack[65536];
static uint64_t expected_gpr[32],entry_sp,expected_fpsr,expected_nzcv;
static unsigned case_id,flag_id;
static void die(const char*s){fprintf(stderr,"UNITY-FCVTZU-FIXED-FAIL %s\n",s);fflush(stderr);exit(20);}
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
static void protect(uint8_t*p,size_t n,int none){
#ifdef _WIN32
 DWORD old;if(!VirtualProtect(p,n,none?PAGE_NOACCESS:PAGE_READONLY,&old))die("memory protection");
#else
 if(mprotect(p,n,none?PROT_NONE:PROT_READ))die("memory protection");
#endif
}
static void load_file(void*d,size_t n,const char*p){FILE*f=fopen(p,"rb");if(!f||fread(d,1,n,f)!=n||fgetc(f)!=EOF)die("exact original input");fclose(f);}
static void setup(unsigned c,uint64_t lr,const uint8_t*literal){
 // Explicit expected values follow exact binary scaling by2^20, then truncation.
 // The sole inexact integer->float source is old=2^24+1, whose four rounding
 // outcomes are independently enumerated. No host floating-point oracle.
 static const uint32_t input[]={0x35800000,0x35800000,0x35c00000,0x41800000};
 static const uint64_t old[]={1,0,7,16777217},converted[]={1,1,1,16777216};
 static const uint32_t out[]={0x3f800000,0x3f800000,0x3f800000,0x4b800000};
 if(c>=16){die("case range");}case_id=c;flag_id=c&3;unsigned k=c>>2;
 if(memcmp(literal,"\x00\x00\x80\x44",4))die("actual1024 literal");
 object_data=fixed_map(OBJECT_DATA,65536);owned_stack=fixed_map(OBJECT_STACK,65536);uint8_t*page=fixed_map(0x70ec0000,65536);memcpy(page+0xbdf8,literal,4);protect(page,65536,0);
 memset(object_data,(int)(0xa5^c),65536);memset(owned_stack,0x5c,65536);entry_sp=OBJECT_STACK+0x8000;
 for(unsigned i=0;i<31;++i)port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);
 port_seeds[0]=OBJECT_DATA+256;port_seeds[16]=OBJECT_HEAD;port_seeds[30]=lr;
 port_controls[0]=(uint64_t)flag_id<<22;port_controls[1]=flag_id&1?0x9f:0;port_controls[2]=(uint64_t)(flag_id*5)<<28;
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}put32(port_qseeds,input[k]);
 uint32_t old_float=k==0?0x3f800000:k==1?0:k==2?0x40e00000:flag_id==1?0x4b800001:0x4b800000;
 int equal=old_float==out[k];if(!equal&&!converted[k])die("excluded real-callee branch");
 put64(object_data+256+0x20,old[k]);memcpy(expected_data,object_data,65536);
 if(!equal){put64(expected_data+256+0x20,converted[k]);expected_data[256+0xc0]=1;}
 memcpy(expected_vectors,port_qseeds,512);memset(expected_vectors,0,32);put32(expected_vectors,out[k]);put32(expected_vectors+16,old_float);
 memcpy(expected_gpr,port_seeds,31*8);expected_gpr[8]=equal?old[k]:converted[k];expected_gpr[9]=converted[k];expected_gpr[31]=entry_sp;
 expected_nzcv=equal?UINT64_C(0x60000000):old_float<out[k]?UINT64_C(0x80000000):UINT64_C(0x20000000);
 expected_fpsr=port_controls[1]|(k>=2?0x10:0);
 memcpy(expected_stack,owned_stack,65536);put64(expected_stack+0x8000-32,port_seeds[20]);put64(expected_stack+0x8000-16,port_seeds[19]);put64(expected_stack+0x8000-8,lr);
 protect(owned_stack,4096,1);protect(owned_stack+61440,4096,1);
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 if(memcmp(object_data,expected_data,65536))die("complete object and allocation canaries");
 for(unsigned i=0;i<32;++i){uint64_t want=i==18?port_saved_x18:expected_gpr[i];if(get64(s+i*8)!=want){fprintf(stderr,"x%u got%llx expected%llx\n",i,(unsigned long long)get64(s+i*8),(unsigned long long)want);die("all GPR/SP effects");}}
 if(memcmp(s+256,expected_vectors,512)||get64(s+768)!=expected_nzcv||get64(s+776)!=expected_fpsr||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls)die("all SIMD/NZCV/FPSR/FPCR/TLS effects");
 for(unsigned i=4096;i<61440;++i){if(native&&i>=0x8000-800&&i<0x8000)continue;if(owned_stack[i]!=expected_stack[i])die("exact frame and stack canaries outside native capture");}
 if((!polled&&polls)||(polled&&!polls))die("dormant poll hooks");
 printf("OBSERVATION native=%d polls=%lu original-normal-return=1 real-zero-callee-excluded=1\n",native,polls);
 put64(s+18*8,0);put64(s+30*8,OBJECT_CAPTURE);put64(s+792,0);
 printf("RECORD case=%u state=",case_id);for(unsigned i=0;i<800;++i)printf("%02x",s[i]);printf(" object=");for(unsigned i=0;i<0x200;++i)printf("%02x",object_data[256+i]);printf(" allocation-canaries=exact stack=exact\n");fflush(stdout);exit(0);
}
