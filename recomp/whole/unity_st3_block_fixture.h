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
#define BLOCK_HEAD UINT64_C(0x704fd850)
#define BLOCK_STOP UINT64_C(0x704fedc8)
#define BLOCK_STACK UINT64_C(0x600000000)
#define BLOCK_DATA UINT64_C(0x712c0000)
uint64_t port_seeds[31],port_controls[3],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *block_data,*owned_stack,*constant_pages[3];
static uint64_t entry_sp;
static unsigned case_id;
static void die(const char*why){fprintf(stderr,"ST3-BLOCK-FAIL %s\n",why);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static uint8_t*fixed_map(uintptr_t address,size_t size){
#ifdef _WIN32
 void*p=VirtualAlloc((void*)address,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*p=mmap((void*)address,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(p!=(void*)address)die("exact64K-aligned owned mapping");
 return(uint8_t*)p;
}
static void readonly(uint8_t*p,size_t size){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,size,PAGE_READONLY,&old))die("constant protection");
#else
 if(mprotect(p,size,PROT_READ))die("constant protection");
#endif
}
static void setup(unsigned c,const char*constants){
 if(c>=16){die("case range");}case_id=c;unsigned mode=c&3,pattern=c>>2;
 block_data=fixed_map(BLOCK_DATA,65536);owned_stack=fixed_map(BLOCK_STACK,65536);memset(block_data,0xa5^c,65536);memset(owned_stack,0x5c,65536);put64(block_data+0xa798,0);entry_sp=BLOCK_STACK+0x8000;
 const uintptr_t bases[]={0x70eb0000,0x70e70000,0x70f00000};FILE*f=fopen(constants,"rb");if(!f)die("original constant pages");
 for(unsigned i=0;i<3;++i){constant_pages[i]=fixed_map(bases[i],65536);if(fread(constant_pages[i],1,65536,f)!=65536)die("constant page bytes");readonly(constant_pages[i],65536);}if(fgetc(f)!=EOF)die("extra constant bytes");fclose(f);
 for(unsigned i=0;i<31;++i)port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);
 port_seeds[0]=BLOCK_DATA+0x100;port_seeds[1]=BLOCK_DATA+0x200;port_seeds[2]=UINT64_C(0xdeadbeef00000000)|pattern;port_seeds[16]=BLOCK_HEAD;port_seeds[30]=0x7f010000;
 for(unsigned i=0;i<512;++i)port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);
 port_controls[0]=(uint64_t)mode<<22;port_controls[1]=pattern&1?0x9f:0;port_controls[2]=(uint64_t)(mode*5)<<28;
}
static void emit(uint8_t*s,int native,unsigned long polls,int polled){
 uint8_t expected[65536];memset(expected,0xa5^case_id,sizeof(expected));put64(expected+0xa798,0);
 for(unsigned i=1;i<27;++i){int32_t offset;memcpy(&offset,constant_pages[2]+0x4b50+i*4,4);int64_t at=0x62a8+(int64_t)offset;if(at<0||at>=65536)die("bounded original index table");expected[at]=(uint8_t)i;}
 memcpy(expected+0x5fa8,block_data+0x5fa8,768);if(memcmp(expected,block_data,65536))die("all index-table effects/guard/output bounds/allocation canaries");
 for(unsigned lane=0;lane<16;++lane)for(unsigned reg=0;reg<3;++reg)if(block_data[0x5fa8+15*48+lane*3+reg]!=s[256+(20+reg)*16+lane])die("actual lastST3 interleave independent operand oracle");
 unsigned changed=0;for(unsigned i=0;i<768;++i)changed+=block_data[0x5fa8+i]!=(uint8_t)(0xa5^case_id);if(changed<512)die("actual768byte generated table");
 for(unsigned i=0;i<31;++i){uint64_t want=port_seeds[i];int known=1;switch(i){case 8:want=0x300;break;case 9:want=0x712c5fa8;break;case 10:want=0x712c6278;break;case 11:want=0x712c62a8;break;case 12:{int32_t v;memcpy(&v,constant_pages[2]+0x4b50+26*4,4);want=(uint64_t)(int64_t)v;break;}case 13:want=27;break;case 18:want=port_saved_x18;break;case 19:want=port_seeds[1];break;case 20:want=port_seeds[0];break;case 21:want=(uint32_t)port_seeds[2];break;case 30:want=0x704fdb44;break;default:break;}if(known&&get64(s+i*8)!=want){fprintf(stderr,"GPR%u got%llx expected%llx\n",i,(unsigned long long)get64(s+i*8),(unsigned long long)want);die("exact prefix GPR effects");}}
 if(get64(s+248)!=entry_sp-64||get64(s+768)!=0x60000000||get64(s+784)!=port_controls[0]||get64(s+792)!=port_saved_tls)die("SP/NZCV/FPCR/TLS effects");
 for(unsigned r=8;r<32;++r)if((r<16||r>=27)&&memcmp(s+256+r*16,port_qseeds+r*16,16))die("unmodified SIMD register bytes");
 uint64_t frame[]={port_seeds[25],port_seeds[24],port_seeds[23],port_seeds[22],port_seeds[21],port_seeds[20],port_seeds[19],port_seeds[30]};
 if(memcmp(owned_stack+0x8000-64,frame,64))die("exact original64byte saved frame");
 for(unsigned i=0;i<65536;++i){if(i>=0x8000-64&&i<0x8000)continue;if(native&&i>=0x8000-64-800&&i<0x8000-64)continue;if(owned_stack[i]!=0x5c)die("original stack canaries outside frame/native capture");}
 if((!polled&&polls)||(polled&&!polls))die("actual dormant cooperative poll hooks");
 put64(s+18*8,0);put64(s+792,0);
 printf("RECORD case=%u state=",case_id);for(unsigned i=0;i<800;++i)printf("%02x",s[i]);printf(" global=");for(unsigned i=0;i<65536;++i)printf("%02x",block_data[i]);printf(" frame=");for(unsigned i=0;i<64;++i)printf("%02x",owned_stack[0x8000-64+i]);printf(" canaries=exact\n");printf("OBSERVATION original-prefix=1 stopped-at-real-helper-entry=704fedc8 helper-body-executed=0 full-FDE-return=0 native=%d polls=%lu\n",native,polls);fflush(stdout);exit(0);
}
