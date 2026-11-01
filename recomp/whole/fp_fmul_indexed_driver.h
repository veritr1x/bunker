#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef void (*multiply_call)(unsigned,uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
static const uint32_t multiply_edges32[]={
  0,0x80000000,0x3f800000,0xbf800000,1,0x80000001,0x007fffff,0x807fffff,
  0x00800000,0x80800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
  0x7fc00000,0xffc00000,0x7fc12345,0x7f800001,0xff800001,0x7fbfffff,
  0x3f800001,0xbf800001,0x3f7fffff,0xbf7fffff,0x00800001,0x80800001,
  0x3f000000,0xbf000000,0x40000000,0xc0000000,0x40400000,0xc0400000,
  0x40800000,0xc0800000,0x33000000,0xb3000000,0x33800000,0xb3800000};
static const uint64_t multiply_edges64[]={
  0,UINT64_C(0x8000000000000000),UINT64_C(0x3ff0000000000000),UINT64_C(0xbff0000000000000),
  1,UINT64_C(0x8000000000000001),UINT64_C(0x000fffffffffffff),UINT64_C(0x800fffffffffffff),
  UINT64_C(0x0010000000000000),UINT64_C(0x8010000000000000),UINT64_C(0x7fefffffffffffff),UINT64_C(0xffefffffffffffff),
  UINT64_C(0x7ff0000000000000),UINT64_C(0xfff0000000000000),UINT64_C(0x7ff8000000000000),UINT64_C(0xfff8000000000000),
  UINT64_C(0x7ff8123456789abc),UINT64_C(0x7ff0000000000001),UINT64_C(0xfff0000000000001),UINT64_C(0x7ff7ffffffffffff),
  UINT64_C(0x3ff0000000000001),UINT64_C(0xbff0000000000001),UINT64_C(0x3fefffffffffffff),UINT64_C(0xbfefffffffffffff),
  UINT64_C(0x0010000000000001),UINT64_C(0x8010000000000001),UINT64_C(0x3fe0000000000000),UINT64_C(0xbfe0000000000000),
  UINT64_C(0x4000000000000000),UINT64_C(0xc000000000000000),UINT64_C(0x4008000000000000),UINT64_C(0xc008000000000000),
  UINT64_C(0x4010000000000000),UINT64_C(0xc010000000000000),UINT64_C(0x3c90000000000000),UINT64_C(0xbc90000000000000),
  UINT64_C(0x3ca0000000000000),UINT64_C(0xbca0000000000000)};
static uint64_t multiply_random(uint64_t *state){*state^=*state<<13;*state^=*state>>7;*state^=*state<<17;return *state;}
static void multiply_vector(uint8_t *out,unsigned width,unsigned index,unsigned stride){
  for(unsigned lane=0;lane<128/width;++lane){
    if(width==32){uint32_t value=multiply_edges32[(index+lane*stride)%38];memcpy(out+lane*4,&value,4);}
    else{uint64_t value=multiply_edges64[(index+lane*stride)%38];memcpy(out+lane*8,&value,8);}
  }
}
static void multiply_random_vector(uint8_t *out,uint64_t *seed){for(unsigned i=0;i<16;i+=8){uint64_t value=multiply_random(seed);memcpy(out+i,&value,8);}}
static void multiply_boundary(uint8_t *lhs,uint8_t *rhs,unsigned width,unsigned sample){
  const unsigned f=width==32?23:52,bias=width==32?127:1023,maximum=width==32?254:2046;
  const uint64_t sign=UINT64_C(1)<<(width-1),fraction=(UINT64_C(1)<<f)-1;
  unsigned e=1+(sample/8)%maximum;uint64_t a=(uint64_t)e<<f,b=(uint64_t)bias<<f;
  switch(sample%8){
    case 0:b=(uint64_t)(bias-1)<<f;break;
    case 1:a|=1;b=(uint64_t)(bias-1)<<f;break;
    case 2:a|=fraction;b|=1;break;
    case 3:a|=1;--b;break;
    case 4:a|=fraction;--b;break;
    case 5:a|=fraction;b=(uint64_t)(bias+1)<<f;break;
    case 6:a|=1;b=((uint64_t)(maximum+1-e)<<f)|fraction;break;
    default:a|=fraction;b=1;break;
  }
  for(unsigned lane=0;lane<128/width;++lane){
    uint64_t x=a^(lane&1?sign:0),y=b;
    if(width==32){uint32_t xx=(uint32_t)x,yy=(uint32_t)y;memcpy(lhs+lane*4,&xx,4);memcpy(rhs+lane*4,&yy,4);}
    else{memcpy(lhs+lane*8,&x,8);memcpy(rhs+lane*8,&y,8);}
  }
}
static int run_multiply_cases(multiply_call call){
#ifdef _WIN32
  _setmode(_fileno(stdout),_O_BINARY);
#endif
  uint8_t old_destination[16],lhs[16],rhs[16],out[64];
  for(unsigned test=0;test<sizeof(multiply_cases)/sizeof(multiply_cases[0]);++test){
    const unsigned width=multiply_cases[test].width;
    for(unsigned mode=0;mode<16;++mode)for(unsigned flags=0;flags<2;++flags){
      const uint64_t fpcr=((uint64_t)(mode/4)<<22)|((uint64_t)(mode%4)<<24);
      const uint64_t status=flags?UINT64_C(0x500000000800009f):UINT64_C(0xa000000000000000);
      for(unsigned a=0;a<38;++a)for(unsigned b=0;b<38;++b){
        multiply_vector(old_destination,width,(a+b*3)%38,11);multiply_vector(lhs,width,a,3);multiply_vector(rhs,width,b,7);
        call(test,out,old_destination,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
      uint64_t seed=UINT64_C(0x464d554c2d494458);
      for(unsigned sample=0;sample<1024;++sample){
        multiply_random_vector(old_destination,&seed);multiply_random_vector(lhs,&seed);multiply_random_vector(rhs,&seed);
        call(test,out,old_destination,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
      const unsigned boundaries=multiply_cases[test].full?(width==32?254:2046)*8:64;
      for(unsigned sample=0;sample<boundaries;++sample){
        multiply_vector(old_destination,width,sample%38,1);multiply_boundary(lhs,rhs,width,sample);
        call(test,out,old_destination,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
    }
  }
  return 0;
}
