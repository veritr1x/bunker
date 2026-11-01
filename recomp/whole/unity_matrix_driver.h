#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#else
#include <sys/mman.h>
#endif

#define MATRIX_RECORD_BYTES 792
typedef void (*matrix_call)(uint8_t*,const uint8_t*,const uint8_t*,uint8_t*,uint64_t,uint64_t);
static uint64_t matrix_random(uint64_t *state){*state^=*state<<13;*state^=*state>>7;*state^=*state<<17;return *state;}
static uint32_t matrix_bits(float value){uint32_t bits;memcpy(&bits,&value,4);return bits;}
static uint64_t matrix_u64(const uint8_t *bytes){uint64_t value;memcpy(&value,bytes,8);return value;}
static void matrix_require(int good,const char *reason){if(!good){fprintf(stderr,"Unity matrix invariant failed: %s\n",reason);abort();}}
static void matrix_fill(uint8_t *arena,unsigned a,unsigned b,unsigned sample,unsigned profile){
  uint64_t random=UINT64_C(0x4d41545249582d41)^sample;
  static const uint32_t edges[]={0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc12345,0xffc54321,0x7f800001,0xff800003,0x3f800000,0xbf800000,0x40000000};
  memset(arena,0xa7,512);
  for(unsigned which=0;which<2;++which)for(unsigned i=0;i<16;++i){
    uint32_t bits;
    if(profile==0){
      int value=(int)(matrix_random(&random)%9)-4;
      if(sample%4==0&&which==0)value=i%5==0;
      if(sample%4==1&&which==1)value=i%5==0;
      bits=matrix_bits((float)value);
    }else if(profile==1){
      uint64_t value=matrix_random(&random);bits=((uint32_t)value&0x807fffffU)|((123U+(unsigned)(value%9))<<23);
    }else bits=edges[(sample*(which?3:1)+i*(which?5:7))%16];
    memcpy(arena+(which?b:a)+i*4,&bits,4);
  }
}
static void matrix_integer_expected(const uint8_t *a,const uint8_t *b,int expected[16]){
  for(unsigned column=0;column<4;++column)for(unsigned row=0;row<4;++row){
    int sum=0;
    for(unsigned k=0;k<4;++k){float x,y;memcpy(&x,a+(k*4+row)*4,4);memcpy(&y,b+(column*4+k)*4,4);sum+=(int)x*(int)y;}
    expected[column*4+row]=sum;
  }
}
static void matrix_validate(const uint8_t *record,const uint8_t *a,const uint8_t *b,const uint8_t *c,uint64_t fpcr,uint64_t status,unsigned profile){
  for(unsigned i=0;i<3;++i)matrix_require(matrix_u64(record+i*8)==64,"each original pointer advances64 bytes");
  for(unsigned i=3;i<30;++i)matrix_require(matrix_u64(record+i*8)==(UINT64_C(0x1020304050600000)|i),"unrelated GPR preserved");
  matrix_require(!matrix_u64(record+240)&&!matrix_u64(record+248),"original LR and SP preserved");
  for(unsigned i=0;i<32;++i){
    const uint8_t *actual=record+256+i*16;
    if(i<4)matrix_require(!memcmp(actual,b+i*16,16),"Q0..3 are exact original B loads");
    else if(i>=16&&i<20)matrix_require(!memcmp(actual,a+(i-16)*16,16),"Q16..19 are exact original A loads");
    else if(i>=20&&i<24)matrix_require(!memcmp(actual,c+(i-20)*16,16),"Q20..23 match output stores");
    else matrix_require(matrix_u64(actual)==(UINT64_C(0x1122334455660000)|i)&&matrix_u64(actual+8)==(UINT64_C(0x8877665544330000)|i),"unrelated full SIMD register preserved");
  }
  matrix_require(matrix_u64(record+768)==fpcr&&matrix_u64(record+784)==(status>>32),"FPCR and full NZCV preserved");
  if(profile==0)matrix_require(matrix_u64(record+776)==(uint32_t)status,"exact integer pipeline preserves cumulative FPSR");
  else if(profile==1)matrix_require((matrix_u64(record+776)&~UINT64_C(16))==((uint32_t)status&~UINT64_C(16)),"finite-normal pipeline changes only IXC");
}
static void matrix_emit(unsigned test,unsigned profile,unsigned control,const uint8_t *record,const void *memory,unsigned size){
  uint32_t header[]={test,profile,control,size};
  matrix_require(fwrite(header,1,16,stdout)==16&&fwrite(record,1,792,stdout)==792&&fwrite(memory,1,size,stdout)==size,"binary record write");
}
static uint8_t *matrix_pages(void){
#ifdef _WIN32
  uint8_t *p=(uint8_t*)VirtualAlloc(NULL,12288,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);
  DWORD old;matrix_require(p&&VirtualProtect(p+4096,4096,PAGE_READWRITE,&old),"native Windows guarded pages");return p;
#else
  uint8_t *p=(uint8_t*)mmap(NULL,12288,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  matrix_require(p!=MAP_FAILED&&!mprotect(p+4096,4096,PROT_READ|PROT_WRITE),"ARM64/Linux guarded pages");return p;
#endif
}
static void matrix_free_pages(uint8_t *p){
#ifdef _WIN32
  matrix_require(VirtualFree(p,0,MEM_RELEASE)!=0,"free native guard allocation");
#else
  matrix_require(!munmap(p,12288),"free native guard allocation");
#endif
}
static int run_matrix_cases(matrix_call call,int diagnostic){
#ifdef _WIN32
  _setmode(_fileno(stdout),_O_BINARY);
#endif
  static const unsigned layouts[][3]={{32,128,224},{32,128,32},{32,128,128},{32,128,36},{32,128,132},{32,128,28},{32,128,124},{32,32,224},{32,36,224},{32,128,64},{32,128,160},{32,32,32},{33,129,225},{35,131,227},{40,136,44},{47,143,239},{32,92,64},{32,128,68}};
  unsigned test=0;
  uint8_t arena[512],before[512],a[64],b[64],guarded[16+792+16];
  for(unsigned profile=diagnostic?2:0;profile<(diagnostic?3:2);++profile)
  for(unsigned sample=0;sample<32;++sample)
  for(unsigned layout=0;layout<sizeof(layouts)/sizeof(layouts[0]);++layout)
  for(unsigned mode=0;mode<16;++mode)for(unsigned flags=0;flags<2;++flags){
    const unsigned aa=layouts[layout][0],bb=layouts[layout][1],cc=layouts[layout][2];
    const uint64_t fpcr=((uint64_t)(mode/4)<<22)|((uint64_t)(mode%4)<<24);
    const uint64_t status=flags?UINT64_C(0x500000000800009f):UINT64_C(0xa000000000000000);
    matrix_fill(arena,aa,bb,sample,profile);memcpy(before,arena,512);memcpy(a,arena+aa,64);memcpy(b,arena+bb,64);memset(guarded,0xcd,sizeof(guarded));
    call(guarded+16,arena+aa,arena+bb,arena+cc,fpcr,status);
    matrix_validate(guarded+16,a,b,arena+cc,fpcr,status,profile);
    for(unsigned i=0;i<16;++i)matrix_require(guarded[i]==0xcd&&guarded[16+792+i]==0xcd,"register snapshot record canaries");
    memcpy(before+cc,arena+cc,64);matrix_require(!memcmp(before,arena,512),"entire arena untouched outside exact64-byte destination");
    if(profile==0){int expected[16];matrix_integer_expected(a,b,expected);for(unsigned i=0;i<16;++i){float actual;memcpy(&actual,arena+cc+i*4,4);matrix_require(actual==(float)expected[i],"independent bounded integer matrix formula");}}
    matrix_emit(test++,profile,mode*2+flags,guarded+16,arena,512);
  }
  if(!diagnostic){
    uint8_t *pages[3]={matrix_pages(),matrix_pages(),matrix_pages()};uint8_t initial[512],payload[12288];
    for(unsigned edge=0;edge<2;++edge)for(unsigned mode=0;mode<16;++mode)for(unsigned flags=0;flags<2;++flags){
      const unsigned offset=edge?4096-64:0;const uint64_t fpcr=((uint64_t)(mode/4)<<22)|((uint64_t)(mode%4)<<24);
      const uint64_t status=flags?UINT64_C(0x500000000800009f):UINT64_C(0xa000000000000000);
      matrix_fill(initial,32,128,edge,0);for(unsigned i=0;i<3;++i)memset(pages[i]+4096,0xa7,4096);
      memcpy(pages[0]+4096+offset,initial+32,64);memcpy(pages[1]+4096+offset,initial+128,64);
      memcpy(a,initial+32,64);memcpy(b,initial+128,64);memset(guarded,0xcd,sizeof(guarded));
      call(guarded+16,pages[0]+4096+offset,pages[1]+4096+offset,pages[2]+4096+offset,fpcr,status);
      matrix_validate(guarded+16,a,b,pages[2]+4096+offset,fpcr,status,0);
      matrix_require(!memcmp(a,pages[0]+4096+offset,64)&&!memcmp(b,pages[1]+4096+offset,64),"guarded source buffers unchanged");
      for(unsigned i=0;i<3;++i)memcpy(payload+i*4096,pages[i]+4096,4096);
      for(unsigned i=0;i<4096;++i){
        if(i<offset||i>=offset+64)for(unsigned j=0;j<3;++j)matrix_require(pages[j][4096+i]==0xa7,"guarded page bytes outside each64-byte range unchanged");
      }
      matrix_emit(test++,3+edge,mode*2+flags,guarded+16,payload,12288);
    }
    for(unsigned i=0;i<3;++i)matrix_free_pages(pages[i]);
  }
  fprintf(stderr,"Unity exact104-byte matrix %s: %u records, full registers/memory/guards checked\n",diagnostic?"nonfinite/FZ diagnostic":"finite acceptance",test);
  return 0;
}
