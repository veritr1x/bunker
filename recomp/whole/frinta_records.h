#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "frinta_edges.h"
typedef struct{const char*name;unsigned width,rd,rn;}FRINTACase;
static const FRINTACase cases[]={
#define CASE(name,w,d,n) {#name,w,d,n},
#include "frinta_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static uint64_t frinta_expected(uint64_t raw,unsigned width,uint64_t fpcr,uint64_t*fpsr){
 const unsigned frac=width==32?23:52,bias=width==32?127:1023;const uint64_t limit=width==32?UINT64_C(0xffffffff):UINT64_MAX,sign=UINT64_C(1)<<(width-1),fraction_mask=(UINT64_C(1)<<frac)-1,exponent_mask=limit&~(sign|fraction_mask),quiet=UINT64_C(1)<<(frac-1);
 raw&=limit;const uint64_t fraction=raw&fraction_mask;const unsigned encoded=(unsigned)((raw&exponent_mask)>>frac);
 if((raw&exponent_mask)==exponent_mask){if(!fraction)return raw;if(!(fraction&quiet))*fpsr|=1;return fpcr&(UINT64_C(1)<<25)?exponent_mask|quiet:raw|quiet;}
 if(!encoded){if(!fraction)return raw;if(fpcr&(UINT64_C(1)<<24)){*fpsr|=128;return raw&sign;}}
 const int exponent=(int)encoded-(int)bias;
 if(exponent < -1)return raw&sign;
 if(exponent == -1)return(raw&sign)|((uint64_t)bias<<frac);
 if(exponent >= (int)frac)return raw;
 const uint64_t step=UINT64_C(1)<<(frac-(unsigned)exponent),discarded=raw&(step-1);
 // Magnitude truncation followed by a half-or-greater increment rounds both
 // signs away on a tie. All arithmetic is unsigned; FPCR.RMode is irrelevant.
 return(raw&~(step-1))+(discarded>=step/2?step:0);
}
static int run_frinta_records(void(*call)(unsigned,uint8_t*,const uint8_t*)){
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;test++){
  const FRINTACase*c=&cases[test];const uint64_t*edge=c->width==32?frinta_edges_32:frinta_edges_64;const unsigned edge_count=(unsigned)(c->width==32?sizeof(frinta_edges_32)/8:sizeof(frinta_edges_64)/8),patterns=edge_count+64;
  for(unsigned mode=0;mode<16;mode++)for(unsigned status=0;status<2;status++)for(unsigned pattern=0;pattern<patterns;pattern++){
   const unsigned seed=(mode*2+status)*patterns+pattern,flags=(mode^pattern^status*9)&15;
   uint8_t input[768] __attribute__((aligned(16))),output_space[1664] __attribute__((aligned(16))),expected[800],original[768];uint8_t*out=output_space+32;
   memset(input,0x73,sizeof(input));memset(output_space,0xab,sizeof(output_space));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
   for(unsigned n=0;n<92;n++){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}
   uint64_t raw=pattern<edge_count?edge[pattern]:get64(input+224+c->rn*16);if(c->width==32)memcpy(input+224+c->rn*16,&raw,4);else put64(input+224+c->rn*16,raw);
   put64(input+736,(uint64_t)flags<<28);put64(input+744,status?UINT64_C(0x0800009f):0);put64(input+752,((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22));memcpy(original,input,sizeof(input));call(test,out,input);
   if(memcmp(original,input,sizeof(input)))return 20;
   for(unsigned n=0;n<sizeof(output_space);n++)if((n<32||n>=1632)&&output_space[n]!=0xab)return 21;
   if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16)return 22;
   for(unsigned reg=2;reg<30;reg++)if(reg!=18&&get64(out+reg*8)!=get64(input+(reg-2)*8))return 23;
   if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 24;
   memcpy(expected,out,800);uint64_t fpsr=get64(out+776);raw=get64(out+256+c->rn*16);if(c->width==32)raw=(uint32_t)raw;const uint64_t selected=frinta_expected(raw,c->width,get64(out+784),&fpsr);put64(expected+776,fpsr);memset(expected+256+c->rd*16,0,16);put64(expected+256+c->rd*16,selected);
   if(memcmp(expected,out+800,800)){fprintf(stderr,"FRINTA state/bits mismatch case=%s seed=%u raw=%016llx selected=%016llx FPSR=%llx FPCR=%llx\n",c->name,seed,(unsigned long long)raw,(unsigned long long)selected,(unsigned long long)fpsr,(unsigned long long)get64(out+784));return 25;}
   put64(expected,0);put64(expected+8,0);put64(expected+18*8,0);put64(expected+30*8,0);put64(expected+31*8,0);uint64_t hash=UINT64_C(1469598103934665603);for(unsigned n=0;n<800;n++){hash^=expected[n];hash*=UINT64_C(1099511628211);}
   printf("RECORD %s %u %016llx %016llx\n",c->name,seed,(unsigned long long)selected,(unsigned long long)hash);count++;
  }
 }
 printf("FRINTA-RECORDS-SUCCESS %u\n",count);return 0;
}
