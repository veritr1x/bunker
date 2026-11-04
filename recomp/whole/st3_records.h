#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct{const char*name;unsigned width,element,rt,rn,mode,rm,original;} ST3Case;
static const ST3Case cases[]={
#define CASE(name,w,e,t,n,m,r,o) {#name,w,e,t,n,m,r,o},
#include "st3_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static uint64_t hash_bytes(const uint8_t*p,unsigned n){uint64_t h=UINT64_C(1469598103934665603);for(unsigned i=0;i<n;++i){h^=p[i];h*=UINT64_C(1099511628211);}return h;}
static void seed_input(uint8_t*input,unsigned seed){
 memset(input,0x73,768);uint64_t x=UINT64_C(0x9e3779b97f4a7c15)^seed;for(unsigned i=0;i<92;++i){x^=x<<13;x^=x>>7;x^=x<<17;put64(input+i*8,x);}
 unsigned pattern=seed&3;for(unsigned r=0;r<32;++r)for(unsigned j=0;j<16;++j){if(pattern==0)input[224+r*16+j]=0;else if(pattern==1)input[224+r*16+j]=(uint8_t)(r*29+j*11+1);else if(pattern==2)input[224+r*16+j]=(uint8_t)((j&1)?0x80:(0xff^(r*3)));}
 const unsigned flags[4]={0,15,5,10};put64(input+736,(uint64_t)flags[seed>>2]<<28);put64(input+744,(pattern&1)?UINT64_C(0x0800009f):0);put64(input+752,((uint64_t)pattern<<22)|((uint64_t)(pattern&1)<<24)|((uint64_t)(pattern&2)<<24));
}
static void memory_oracle(uint8_t*expected,const uint8_t*sources,const ST3Case*c,unsigned offset){
 for(unsigned lane=0;lane<c->width/c->element;++lane)for(unsigned part=0;part<3;++part)memcpy(expected+offset+(lane*3+part)*c->element,sources+((c->rt+part)&31)*16+lane*c->element,c->element);
}
static int run_st3_records(void(*call)(unsigned,uint8_t*,const uint8_t*,uint8_t*,uint64_t)){
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<16;++seed){
  const ST3Case*c=&cases[test];uint8_t input[768]__attribute__((aligned(16))),original[768],space[1696]__attribute__((aligned(16))),memory[192]__attribute__((aligned(16))),expected_memory[192],expected_state[800];uint8_t*out=space+32;
  seed_input(input,seed);memcpy(original,input,768);memset(space,0xab,sizeof(space));memset(memory,0xcd,sizeof(memory));memcpy(expected_memory,memory,sizeof(memory));unsigned offset=64+(c->rn==31?0:(seed&1));uint64_t base=(uintptr_t)(memory+offset),step=7;
  call(test,out,input,memory+offset,step);memory_oracle(expected_memory,input+224,c,offset);
  if(memcmp(input,original,768)||memcmp(memory,expected_memory,192))return 20;
  for(unsigned i=0;i<sizeof(space);++i)if((i<32||i>=1664)&&space[i]!=0xab)return 21;
  if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||get64(out+1600)!=base||get64(out+1608)!=step)return 22;
  for(unsigned r=2;r<30;++r){if(r==18||r==c->rn||(c->mode==2&&r==c->rm)||(c->rn==31&&r==29))continue;if(get64(out+r*8)!=get64(input+(r-2)*8))return 23;}
  if(get64(out+c->rn*8)!=base)return 24;
  if(c->rn==31&&(get64(out+29*8)!=get64(out+1616)||(get64(out+29*8)&15)))return 25;
  if(c->mode==2&&c->rm!=c->rn&&get64(out+c->rm*8)!=step)return 26;
  if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 27;
  memcpy(expected_state,out,800);uint64_t increment=c->mode==1?3*c->width:c->mode==2?(c->rm==c->rn?base:step):0;put64(expected_state+c->rn*8,base+increment);
  if(memcmp(out+800,expected_state,800)){fprintf(stderr,"ST3 State mismatch case=%s seed=%u\n",c->name,seed);return 28;}
  // Normalize only pointer carriers after exact local effect assertions.
  put64(expected_state,0);put64(expected_state+8,0);put64(expected_state+18*8,0);put64(expected_state+30*8,0);put64(expected_state+31*8,0);put64(expected_state+c->rn*8,0);put64(expected_state+792,0);if(c->rn==31)put64(expected_state+29*8,0);
  uint64_t normalized_delta=c->mode==2&&c->rm==c->rn?UINT64_MAX:increment;
  printf("RECORD %s %u %016llx %016llx ",c->name,seed,(unsigned long long)normalized_delta,(unsigned long long)hash_bytes(expected_state,800));for(unsigned i=0;i<192;++i)printf("%02x",memory[i]);putchar('\n');++count;
 }
 printf("ST3-RECORDS-SUCCESS %u\n",count);return 0;
}
