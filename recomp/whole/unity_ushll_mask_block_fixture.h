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
#define BLOCK_HEAD UINT64_C(0x702b3d34)
#define BLOCK_START UINT64_C(0x702b3e98)
#define BLOCK_STOP UINT64_C(0x702b3f78)
#define BLOCK_STACK UINT64_C(0x600000000)
#define BLOCK_DATA UINT64_C(0x600010000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *block_data,*owned_stack,*constant_page;
static uint64_t entry_sp,output_base;
static unsigned case_id;
static void die(const char*why){fprintf(stderr,"USHLL-MASK-BLOCK-FAIL %s\n",why);fflush(stderr);exit(20);}
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
static void readonly(uint8_t*p,size_t size){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,size,PAGE_READONLY,&old)){die("constant protection");}
#else
 if(mprotect(p,size,PROT_READ)){die("constant protection");}
#endif
}
static void setup(unsigned c,const char*constants){
 if(c>=16){die("case range");}case_id=c;unsigned mode=c&3,pattern=c>>2;
 block_data=fixed_map(BLOCK_DATA,65536);owned_stack=fixed_map(BLOCK_STACK,65536);memset(block_data,0xa5^c,65536);memset(owned_stack,0x5c,65536);entry_sp=BLOCK_STACK+0x8000;output_base=BLOCK_DATA+0x100+pattern;
 constant_page=fixed_map(0x70eb0000,65536);FILE*f=fopen(constants,"rb");if(!f||fread(constant_page+0xe840,1,16,f)!=16||fgetc(f)!=EOF){die("exact original16byte table");}fclose(f);readonly(constant_page,65536);
 for(unsigned i=0;i<31;++i){port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);}
 port_seeds[0]=output_base;port_seeds[16]=BLOCK_START;port_seeds[30]=UINT64_C(0x7f010000);
 for(unsigned i=0;i<512;++i){port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);}
 port_controls[0]=(uint64_t)mode<<22;port_controls[1]=pattern&1?0x9f:0;port_controls[2]=(uint64_t)c<<28;
}
// Independent unsigned-byte threshold model. The instruction chain only widens,
// compares, narrows and packs these truth masks; it performs no floating math.
static void vector_oracle(uint8_t*out){
 memcpy(out,port_qseeds,512);uint8_t mask[16];for(unsigned j=0;j<16;++j){mask[j]=7>constant_page[0xe840+j]?255:0;}
 put64(out,7);put64(out+8,7);for(unsigned j=0;j<16;++j){out[16+j]=(uint8_t)~mask[j];out[32+j]=mask[j];}
 const unsigned regsD[]={3,4};const unsigned indicesD[]={2,10};
 for(unsigned r=0;r<2;++r)for(unsigned j=0;j<2;++j){put64(out+regsD[r]*16+j*8,mask[indicesD[r]+j]?UINT64_MAX:0);}
 const unsigned regsS[]={5,6,7,16};const unsigned indicesS[]={0,4,8,12};
 for(unsigned r=0;r<4;++r)for(unsigned j=0;j<4;++j){uint32_t v=mask[indicesS[r]+j]?UINT32_MAX:0;memcpy(out+regsS[r]*16+j*4,&v,4);}
}
static uint64_t expected_gpr(unsigned i){switch(i){case 8:return 8;case 9:return output_base+0x70;case 10:return 0x70ebe840;case 11:return output_base+0x80;case 12:return 16;case 18:return port_saved_x18;case 19:return output_base;default:return port_seeds[i];}}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 uint8_t expected[65536];memset(expected,0xa5^case_id,sizeof(expected));unsigned at=(unsigned)(output_base-BLOCK_DATA);
 for(unsigned row=0;row<8;++row)for(unsigned j=0;j<16;++j){uint8_t v=row>constant_page[0xe840+j]?255:0;expected[at+row*16+j]=v;expected[at+(15-row)*16+j]=(uint8_t)~v;}
 if(memcmp(expected,block_data,65536)){die("independent complete256byte output and all allocation canaries");}
 for(unsigned i=0;i<31;++i){if(get64(s+i*8)!=expected_gpr(i)){fprintf(stderr,"GPR%u got%llx want%llx\n",i,(unsigned long long)get64(s+i*8),(unsigned long long)expected_gpr(i));die("exact block GPR effects");}}
 uint8_t q[512];vector_oracle(q);if(memcmp(s+256,q,512)){die("independent complete SIMD effects/preservation");}
 if(get64(s+248)!=entry_sp||get64(s+768)!=0x60000000||get64(s+776)!=port_controls[1]||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls){die("SP/NZCV/FPSR/FPCR/TLS effects");}
 for(unsigned i=0;i<65536;++i){if(native&&i>=0x8000-800&&i<0x8000){continue;}if(owned_stack[i]!=0x5c){die("no original stack writes/native capture bound");}}
 if((!polled&&polls)||(polled&&!polls)){die("actual dormant poll hooks");}
 put64(s+18*8,0);put64(s+792,0);printf("RECORD case=%u state=",case_id);for(unsigned i=0;i<800;++i){printf("%02x",s[i]);}printf(" output=");for(unsigned i=0;i<256;++i){printf("%02x",block_data[at+i]);}puts(" canaries=exact");
 printf("OBSERVATION original-block=1 start=702b3e98 capture-before-BL=702b3f78 helper70346214-executed=0 full-FDE-return=0 native=%d polls=%lu\n",native,polls);fflush(stdout);exit(0);
}
