"""Scalar numeric minimum/maximum, S/D complete architectural-state oracle."""
import json
RECORDS=r'''
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct {const char*name;unsigned width,rd,rn,rm,maximum;} NumericCase;
static const NumericCase cases[]={
#define CASE(n,w,d,a,b,m) {#n,w,d,a,b,m},
#include "fp_numeric_minmax_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static uint64_t numeric_expected(uint64_t a,uint64_t b,unsigned w,unsigned maximum,uint64_t fpcr,uint64_t*status){
 const uint64_t mask=w==32?UINT64_C(0xffffffff):UINT64_MAX,sign=UINT64_C(1)<<(w-1),frac=w==32?UINT64_C(0x7fffff):UINT64_C(0xfffffffffffff),exp=mask^(sign|frac),quiet=(frac+1)>>1;
 a&=mask;b&=mask;
 if(fpcr&(UINT64_C(1)<<24)){if(!(a&exp)&&(a&frac)){a&=sign;*status|=128;}if(!(b&exp)&&(b&frac)){b&=sign;*status|=128;}}
 unsigned an=(a&exp)==exp&&(a&frac),bn=(b&exp)==exp&&(b&frac),as=an&&!(a&quiet),bs=bn&&!(b&quiet);
 if(as||bs){*status|=1;return(fpcr&(UINT64_C(1)<<25))?exp|quiet:(as?a:b)|quiet;}
 if(an&&bn)return(fpcr&(UINT64_C(1)<<25))?exp|quiet:a;
 if(an){return b;}if(bn){return a;}
 if(!(a&~sign)&&!(b&~sign))return maximum?(a&b&sign):((a|b)&sign);
 const uint64_t ka=a&sign?(~a&mask):(a|sign),kb=b&sign?(~b&mask):(b|sign);
 return maximum?(ka>kb?a:b):(ka<kb?a:b);
}
static void pair_bits(unsigned w,unsigned p,uint64_t*a,uint64_t*b){
 const unsigned f=w==32?23:52,eb=w==32?127:1023;const uint64_t sign=UINT64_C(1)<<(w-1),exp=w==32?UINT64_C(0x7f800000):UINT64_C(0x7ff0000000000000),quiet=UINT64_C(1)<<(f-1),one=(uint64_t)eb<<f;
 const uint64_t pairs[32][2]={{0,sign},{sign,0},{0,0},{sign,sign},{one,one+1},{one+1,one},{sign|one,one},{one,sign|one},{exp,one},{one,exp},{sign|exp,one},{one,sign|exp},{exp,sign|exp},{sign|exp,exp},{exp|quiet|0x123,one},{one,exp|quiet|0x123},{exp|0x456,one},{one,exp|0x456},{exp|quiet|0x123,exp|quiet|0x456},{exp|quiet|0x456,exp|quiet|0x123},{exp|quiet|0x123,sign|exp|0x456},{sign|exp|0x456,exp|quiet|0x123},{exp|0x123,sign|exp|0x456},{sign|exp|0x456,exp|0x123},{1,one},{one,1},{sign|1,0},{0,sign|1},{(UINT64_C(1)<<f)-1,UINT64_C(1)<<f},{UINT64_C(1)<<f,(UINT64_C(1)<<f)-1},{exp|quiet|0x123,1},{1,sign|exp|quiet|0x456}};
 *a=pairs[p][0];*b=pairs[p][1];
}
static int run_numeric_records(void(*call)(unsigned,uint8_t*,const uint8_t*)){
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<1024;++seed){
  const NumericCase*c=&cases[test];const unsigned mode=seed>>6,pattern=seed&31;uint8_t input[768] __attribute__((aligned(16))),original[768],space[1664] __attribute__((aligned(16))),expected[800];uint8_t*out=space+32;
  memset(input,0x73,sizeof(input));memset(space,0xab,sizeof(space));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
  for(unsigned n=0;n<92;++n){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}
  uint64_t a,b;pair_bits(c->width,pattern,&a,&b);memcpy(input+224+c->rn*16,&a,c->width/8);memcpy(input+224+c->rm*16,&b,c->width/8);
  put64(input+736,(uint64_t)(seed&15)<<28);put64(input+744,(seed&32)?UINT64_C(0x0800009f):0);put64(input+752,((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22));
  memcpy(original,input,sizeof(input));call(test,out,input);if(memcmp(input,original,sizeof(input)))return 20;
  for(unsigned n=0;n<sizeof(space);++n)if((n<32||n>=1632)&&space[n]!=0xab)return 21;
  if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16)return 22;
  for(unsigned reg=2;reg<30;++reg)if(reg!=18&&get64(out+reg*8)!=get64(input+(reg-2)*8))return 23;
  if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 24;
  memcpy(expected,out,800);uint64_t status=get64(out+776),value=numeric_expected(get64(out+256+c->rn*16),get64(out+256+c->rm*16),c->width,c->maximum,get64(out+784),&status);
  memset(expected+256+c->rd*16,0,16);memcpy(expected+256+c->rd*16,&value,c->width/8);put64(expected+776,status);
  if(memcmp(expected,out+800,800)){fprintf(stderr,"NUMERIC mismatch %s seed=%u expected=%llx FPSR=%llx actual=%llx FPSR=%llx\n",c->name,seed,(unsigned long long)value,(unsigned long long)status,(unsigned long long)get64(out+800+256+c->rd*16),(unsigned long long)get64(out+800+776));return 25;}
  put64(expected,0);put64(expected+8,0);put64(expected+18*8,0);put64(expected+30*8,0);put64(expected+31*8,0);
  uint64_t hash=UINT64_C(1469598103934665603);for(unsigned n=0;n<800;++n){hash^=expected[n];hash*=UINT64_C(1099511628211);}
  printf("RECORD %s %u %016llx %016llx\n",c->name,seed,(unsigned long long)value,(unsigned long long)hash);++count;
 }
 printf("FP_NUMERIC_MINMAX-RECORDS-SUCCESS %u\n",count);return 0;
}
'''

def generate(out):
 cases=[]
 for w in(32,64):
  for maximum in(0,1):
   for d,n,m in((2,0,1),(0,0,1),(1,0,1),(31,30,29),(31,31,31),(0,31,0)):
    name=f'numeric_{w}_{maximum}_{d}_{n}_{m}'
    bits=0x1e206800|((w==64)<<22)|((not maximum)<<12)|(m<<16)|(n<<5)|d
    cases.append((name,w,d,n,m,maximum,[bits]))
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  b=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  b+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for register,pos in(('fpsr',776),('fpcr',784)):b+=[f'mrs x2,{register}',f'str x2,[x0,#{offset+pos}]']
  return b+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for name,w,d,n,m,maximum,words in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  for register,pos in(('fpsr',744),('fpcr',752)):body+=[f'ldr x2,[x1,#{pos}]',f'msr {register},x2']
  body +=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  body+=snapshot(0)+[f'.inst 0x{x:08x}'for x in words]+snapshot(800)
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(name,body);function('raw_'+name,[*[f'.inst 0x{x:08x}'for x in words],'ret'])
 function('fp_numeric_minmax_control_copy',['ldr s0,[x0]','str s0,[x1]','ret'])
 (out/'fp_numeric_minmax.S').write_text('\n'.join(lines)+'\n')
 (out/'fp_numeric_minmax_cases.h').write_text(''.join(f'CASE({name},{w},{d},{n},{m},{maximum})\n'for name,w,d,n,m,maximum,_ in cases))
 (out/'fp_numeric_minmax_records.h').write_text(RECORDS)
 (out/'case-oracle.json').write_text(json.dumps(cases,indent=2)+'\n')
 return cases
