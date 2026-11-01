#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

typedef void (*fmla_call)(unsigned,uint8_t*,const uint8_t*,const uint8_t*,const uint8_t*,uint64_t,uint64_t);
static const uint32_t fmla_edges32[]={
  0,0x80000000,0x3f800000,0xbf800000,1,0x80000001,0x007fffff,0x807fffff,
  0x00800000,0x80800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
  0x7fc12345,0xffc54321,0x7f800001,0xff800003,0x3f800001,0x3f7fffff};
static const uint64_t fmla_edges64[]={
  0,UINT64_C(0x8000000000000000),UINT64_C(0x3ff0000000000000),UINT64_C(0xbff0000000000000),
  1,UINT64_C(0x8000000000000001),UINT64_C(0x000fffffffffffff),UINT64_C(0x800fffffffffffff),
  UINT64_C(0x0010000000000000),UINT64_C(0x8010000000000000),UINT64_C(0x7fefffffffffffff),UINT64_C(0xffefffffffffffff),
  UINT64_C(0x7ff0000000000000),UINT64_C(0xfff0000000000000),UINT64_C(0x7ff8123456789abc),UINT64_C(0xfff8abcde0123456),
  UINT64_C(0x7ff0000000000001),UINT64_C(0xfff0000000000003),UINT64_C(0x3ff0000000000001),UINT64_C(0x3fefffffffffffff)};
static uint64_t fmla_random(uint64_t *state){*state^=*state<<13;*state^=*state>>7;*state^=*state<<17;return *state;}
static void fmla_edge_vector(uint8_t *out,unsigned width,unsigned index,unsigned stride){
  for(unsigned lane=0;lane<128/width;++lane){
    if(width==32){uint32_t value=fmla_edges32[(index+lane*stride)%20];memcpy(out+lane*4,&value,4);}
    else{uint64_t value=fmla_edges64[(index+lane*stride)%20];memcpy(out+lane*8,&value,8);}
  }
}
static void fmla_random_vector(uint8_t *out,uint64_t *seed){
  for(unsigned at=0;at<16;at+=8){uint64_t value=fmla_random(seed);memcpy(out+at,&value,8);}
}

// Construct cancellation/tininess/overflow triples near every finite normal
// exponent. Integer bit patterns keep subnormal and NaN data untouched.
static void fmla_adversary(uint8_t *acc,uint8_t *lhs,uint8_t *rhs,unsigned width,unsigned sample){
  const unsigned f=width==32?23:52,bias=width==32?127:1023;
  const unsigned exponents=width==32?254:2046;
  const uint64_t sign=UINT64_C(1)<<(width-1),fraction=(UINT64_C(1)<<f)-1;
  unsigned e=1+(sample/8)%exponents;
  uint64_t a=((uint64_t)e<<f),b=(uint64_t)bias<<f,c=sign|a;
  switch(sample%8){
    case 0:a|=1;b|=1;c|=2;break; // fused residual after cancellation
    case 1:a|=fraction;b|=1;c|=fraction;break;
    case 2:a|=fraction;b-=1;c|=fraction;break;
    case 3:a|=1;b-=1;c|=1;break;
    case 4:a|=fraction;b|=fraction;c=sign|((uint64_t)(e==exponents?e:e+1)<<f);break;
    case 5:a|=fraction;b=(uint64_t)(bias-1)<<f;c=1;break;
    case 6:a|=1;b=(uint64_t)(bias-1)<<f;c=sign|1;break;
    default:a|=1;b=(uint64_t)(bias+1)<<f;c=sign|((uint64_t)(e==exponents?e:e+1)<<f);break;
  }
  for(unsigned lane=0;lane<128/width;++lane){
    uint64_t x=c^(lane&1?sign:0),y=a^(lane&1?sign:0),z=b;
    if(width==32){uint32_t xx=(uint32_t)x,yy=(uint32_t)y,zz=(uint32_t)z;memcpy(acc+lane*4,&xx,4);memcpy(lhs+lane*4,&yy,4);memcpy(rhs+lane*4,&zz,4);}
    else{memcpy(acc+lane*8,&x,8);memcpy(lhs+lane*8,&y,8);memcpy(rhs+lane*8,&z,8);}
  }
}
static int run_fmla_cases(fmla_call call){
#ifdef _WIN32
  _setmode(_fileno(stdout),_O_BINARY);
#endif
  uint8_t acc[16],lhs[16],rhs[16],out[64];
  for(unsigned test=0;test<sizeof(fmla_cases)/sizeof(fmla_cases[0]);++test){
    const unsigned width=fmla_cases[test].width;
    for(unsigned mode=0;mode<16;++mode)for(unsigned flags=0;flags<2;++flags){
      const uint64_t fpcr=((uint64_t)(mode/4)<<22)|((uint64_t)(mode%4)<<24);
      const uint64_t status=flags?UINT64_C(0x500000000800009f):UINT64_C(0xa000000000000000);
      const unsigned count=fmla_cases[test].exhaustive?8000:400;
      for(unsigned sample=0;sample<count;++sample){
        unsigned a=sample/400,b=(sample/20)%20,c=sample%20;
        if(!fmla_cases[test].exhaustive)a=(b*3+c*7)%20;
        fmla_edge_vector(acc,width,a,1);fmla_edge_vector(lhs,width,b,3);fmla_edge_vector(rhs,width,c,7);
        call(test,out,acc,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
      uint64_t seed=UINT64_C(0x464d4c412d545249);
      for(unsigned sample=0;sample<1024;++sample){
        fmla_random_vector(acc,&seed);fmla_random_vector(lhs,&seed);fmla_random_vector(rhs,&seed);
        call(test,out,acc,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
      const unsigned adversaries=fmla_cases[test].exhaustive?(width==32?254:2046)*8:64;
      for(unsigned sample=0;sample<adversaries;++sample){
        fmla_adversary(acc,lhs,rhs,width,sample);
        call(test,out,acc,lhs,rhs,fpcr,status);if(fwrite(out,1,64,stdout)!=64)return 1;
      }
    }
  }
  return 0;
}
