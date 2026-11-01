#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define NJ_COOKIE UINT64_C(0x9a876543210abcde)
#define NJ_MASK UINT64_C(0x10001000000000)
static uint64_t nj_bits(uint64_t *seed){
  *seed^=*seed<<13;*seed^=*seed>>7;*seed^=*seed<<17;return *seed;
}
static void nj_inputs(uint64_t *env,uint64_t *out,unsigned testcase){
  uint64_t seed=UINT64_C(0xfedcba9876543210)+testcase;
  for(unsigned i=0;i<33;++i)env[i]=nj_bits(&seed);
  for(unsigned i=0;i<66;++i)out[i]=nj_bits(&seed);
}
// Raw words are checked against independently captured actual pre-call state.
// Dynamic addresses are not replaced with arbitrary expected constants.
static uint64_t nj_check(const uint64_t *env,const uint64_t *out,const uint64_t *before,unsigned kind){
  uint64_t bad=0;int save=kind==0||kind==3;
  if(env[0]!=(NJ_COOKIE|save))bad|=1;
  if(env[1]!=(save?NJ_MASK:before[1]))bad|=2;
  if((env[2]^NJ_COOKIE)!=out[13]||(env[3]^NJ_COOKIE)!=out[12])bad|=4;
  for(unsigned n=20;n<=28;n+=2){unsigned at=4+28-n;
    if((env[at]^NJ_COOKIE)!=out[n-18]||(env[at+1]^NJ_COOKIE)!=out[n-17])bad|=8;}
  if((env[14]^NJ_COOKIE)!=(out[0]&8191)||(env[15]^NJ_COOKIE)!=out[1])bad|=16;
  for(unsigned n=8;n<=14;n+=2){unsigned at=16+14-n;
    if(env[at]!=out[16+2*(n-8)]||env[at+1]!=out[18+2*(n-8)])bad|=32;}
  uint64_t checksum=0;for(unsigned i=0;i<24;++i)checksum^=env[i];if(checksum!=env[24])bad|=64;
  for(unsigned i=25;i<33;++i)if(env[i]!=before[i])bad|=128;
  if(out[32])bad|=256;
  for(unsigned n=18;n<=29;++n)if(out[n-18]!=out[34+n-18])bad|=512;
  if(memcmp(out+16,out+48,128))bad|=1024;
  if(out[12]!=out[46]||out[13]!=out[47])bad|=2048;
  if(out[14]!=out[64]||out[15]!=out[65])bad|=4096;
  return bad;
}
