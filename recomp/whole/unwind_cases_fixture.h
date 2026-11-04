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
#define FIXTURE_RETURN UINT64_C(0x7f010000)
#define CODE_BASE UINT64_C(0x82620000)
#define TABLE_BASE UINT64_C(0x85b60000)
#define ARCH_BASE UINT64_C(0x879a0000)
#define BLOCK_STACK UINT64_C(0x600000000)
#define BLOCK_DATA UINT64_C(0x600010000)
#define CASES 55
uint64_t port_seeds[31],port_controls[4],port_saved_x18,port_saved_tls;
uint8_t port_qseeds[512];
static uint8_t *owned_stack,*block_data;
static uint8_t initial_data[65536],expected_data[65536];
static uint64_t entry_sp,entry_pc,expected_result;
static unsigned case_id,kind,variant,opcode,rule;
static int expect_abort;
static const unsigned binary_ops[]={0x1a,0x1b,0x1c,0x1d,0x1e,0x21,0x22,0x24,0x25,0x26,0x27,0x2c,0x2a,0x29,0x2b,0x2d,0x2e};
static void die(const char*w){fprintf(stderr,"UNWIND-CASE-FAIL %s\n",w);fflush(stderr);exit(20);}
static uint64_t get64(const void*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(void*p,uint64_t v){memcpy(p,&v,8);}
static void put32(void*p,uint32_t v){memcpy(p,&v,4);}
static uint8_t*fixed_map(uint64_t p,size_t n){
#ifdef _WIN32
 void*value=VirtualAlloc((void*)(uintptr_t)p,n,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 void*value=mmap((void*)(uintptr_t)p,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
#endif
 if(value!=(void*)(uintptr_t)p){die("fixed owned mapping");}
 return(uint8_t*)value;
}
static void read_blob(uint8_t*dst,size_t n,const char*path){FILE*f=fopen(path,"rb");if(!f||fread(dst,1,n,f)!=n||fgetc(f)!=EOF)die("original byte packet");fclose(f);}
static void executable(uint8_t*p,size_t n){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,n,PAGE_EXECUTE_READ,&old))die("executable original mapping");
#else
 if(mprotect(p,n,PROT_READ|PROT_EXEC)){die("executable original mapping");}
 __builtin___clear_cache((char*)p,(char*)p+n);
#endif
}
static void readonly(uint8_t*p,size_t n){
#ifdef _WIN32
 DWORD old=0;if(!VirtualProtect(p,n,PAGE_READONLY,&old))die("readonly original tables");
#else
 if(mprotect(p,n,PROT_READ))die("readonly original tables");
#endif
}
static uint64_t binary_result(unsigned op,uint64_t a,uint64_t b){switch(op){
 case 0x1a:return a&b;case 0x1b:return(uint64_t)((int64_t)a/(int64_t)b);case 0x1c:return a-b;case 0x1d:return a%b;case 0x1e:return a*b;case 0x21:return a|b;case 0x22:return a+b;case 0x24:return a<<(b&63);case 0x25:return a>>(b&63);case 0x26:return(uint64_t)((int64_t)a>>(b&63));case 0x27:return a^b;case 0x2c:return(int64_t)a<=(int64_t)b;case 0x2a:return(int64_t)a>=(int64_t)b;case 0x29:return a==b;case 0x2b:return(int64_t)a>(int64_t)b;case 0x2d:return(int64_t)a<(int64_t)b;case 0x2e:return a!=b;default:die("binary independent oracle");return 0;}}
static void setup(unsigned c,const char*code,const char*tables){
 if(c>=CASES){die("case range");}
 case_id=c;kind=c<34?0:c<42?1:c<54?2:3;variant=(c<42?c:c-42)&1;expect_abort=kind==3;rule=0;opcode=0;
 block_data=fixed_map(BLOCK_DATA,65536);owned_stack=fixed_map(BLOCK_STACK,65536);uint8_t*text=fixed_map(CODE_BASE,65536),*table=fixed_map(TABLE_BASE,65536);fixed_map(ARCH_BASE,65536);read_blob(text,65536,code);read_blob(table,65536,tables);readonly(table,65536);executable(text,65536);
 memset(block_data,0xa5^c,65536);memset(owned_stack,0x5c,65536);entry_sp=BLOCK_STACK+0x8000;entry_pc=kind==2?UINT64_C(0x82625df4):UINT64_C(0x82625840);
 for(unsigned i=0;i<31;++i)port_seeds[i]=UINT64_C(0x13579bdf2468ace0)^((uint64_t)i*UINT64_C(0x9e3779b97f4a7c15))^((uint64_t)c<<32);
 for(unsigned i=0;i<512;++i)port_qseeds[i]=(uint8_t)(i*7+c*29+0x31);
 port_controls[0]=0;port_controls[1]=c&1?0x9f:0;port_controls[2]=(uint64_t)(c&15)<<28;port_controls[3]=UINT64_C(0x71e693b420c8d5a1);
 port_seeds[16]=entry_pc;port_seeds[29]=entry_sp+0x800;port_seeds[30]=FIXTURE_RETURN;
 uint8_t*context=block_data+0x100,*frame=block_data+0x2000,*program=block_data+0x3000;memset(context,0,0x3c0);memset(frame,0,0x680);
 for(unsigned i=0;i<98;++i){put64(context+i*8,BLOCK_DATA+0x1000+i*8);put64(block_data+0x1000+i*8,UINT64_C(0x1020304000000000)+i);}
 put64(context+0x340,UINT64_C(1)<<62);put64(block_data+0x1000,BLOCK_DATA+0x4800);
 if(kind==0){opcode=binary_ops[c/2];uint64_t a=variant?UINT64_C(0xfffffffffffffff1):37,b=variant?3:5;program[0]=0x10;program[1]=(uint8_t)b;program[2]=(uint8_t)opcode;port_seeds[0]=BLOCK_DATA+0x3000;port_seeds[1]=BLOCK_DATA+0x3003;port_seeds[2]=BLOCK_DATA+0x100;port_seeds[3]=a;expected_result=binary_result(opcode,a,b);}
 else if(kind==1||kind==3){static const unsigned widths[]={1,2,4,8};opcode=kind==3?3:widths[(c-34)/2];program[0]=0x94;program[1]=(uint8_t)opcode;for(unsigned i=0;i<8;++i)block_data[0x4003+i]=(uint8_t)(0xf1-i*19-variant*17);port_seeds[0]=BLOCK_DATA+0x3000;port_seeds[1]=BLOCK_DATA+0x3002;port_seeds[2]=BLOCK_DATA+0x100;port_seeds[3]=BLOCK_DATA+0x4003;expected_result=0;for(unsigned i=0;i<opcode&&i<8;++i)expected_result|=(uint64_t)block_data[0x4003+i]<<(i*8);}
 else{
  unsigned v=(c-42)/2;static const unsigned rules[]={1,2,2,3,4,5};rule=rules[v];opcode=v;
  const uint64_t cfa=BLOCK_DATA+0x4808,offset=variant?24:16;put64(frame+0x628,8);put32(frame+0x630,0);put32(frame+0x640,1);frame[0x673]=(uint8_t)variant;
  put32(frame+0x10+8,rule);put64(frame+0x10,offset);if(rule==2)put64(frame+0x10,2);
  if(v==2){context[0x358+2]=1;put64(context+2*8,UINT64_C(0x8877665544332211));}
  if(rule==3||rule==5){program[0]=2;program[1]=0x23;program[2]=(uint8_t)offset;put64(frame+0x10,BLOCK_DATA+0x3000);}
  port_seeds[0]=BLOCK_DATA+0x100;port_seeds[1]=BLOCK_DATA+0x2000;expected_result=0;
  memcpy(expected_data,block_data,65536);uint8_t*out=expected_data+0x100;put64(out+0xf8,0);out[0x377]=0;put64(out+0x310,cfa);put64(out+0x340,(UINT64_C(1)<<62)|(variant?(UINT64_C(1)<<63):0));
  uint64_t value=rule==2?get64(context+2*8):cfa+offset;put64(out+8,value);out[0x359]=(uint8_t)(v==2||rule==4||rule==5);
 }
 memcpy(initial_data,block_data,65536);if(kind!=2)memcpy(expected_data,block_data,65536);
}
static void hex(const uint8_t*p,size_t n){for(size_t i=0;i<n;++i)printf("%02x",p[i]);}
static void emit(const uint8_t*s,int native,unsigned long polls,int polled,int aborted){
 if(aborted!=expect_abort)die("exact original abort-prefix/RET class");
 if(!aborted){
  if(kind!=2&&get64(s)!=expected_result)die("independent expression value");
  if(memcmp(block_data,expected_data,65536))die("independent complete context/data oracle");
  for(unsigned i=19;i<=29;++i)if(get64(s+i*8)!=port_seeds[i])die("original callee-saved register ABI");
  if(get64(s+248)!=entry_sp)die("genuine original RET restores SP");
 }
 if((!polled&&polls)||(polled&&!polls))die("actual dormant polling witness");
 // Import-veneer scratch is explicitly owned below the largest original frame;
 // capture uses the separate upper window, neither may touch outer canaries.
 for(unsigned i=0;i<65536;++i)if(!(i>=0x7800&&i<0x8000)&&!(i>=0x8000&&i<0x9000)&&owned_stack[i]!=0x5c)die("owned stack/capture canaries");
 printf("RECORD case=%u kind=%u selector=%u variant=%u abort_prefix=%d architecture=",case_id,kind,kind==2?rule:opcode,variant,aborted);hex(s,800);printf(" data=");hex(block_data,0x5000);printf(" frame=");hex(owned_stack+0x7800,0x800);puts(" canaries=exact");
 printf("OBSERVATION original_words=1 original_RET=%d abort_body_executed=0 old_LDURSH_const2s_skip_excluded=1 native=%d polls=%lu\n",!aborted,native,polls);fflush(stdout);exit(0);
}
