"""Four unsigned scalar fixed-point forms; same NDK core and complete state oracle."""
import json
RECORDS=r'''
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct {const char*name;unsigned width,rd,rn,outwidth,fbits,pair;} FCVTZU_FIXEDCase;
static const FCVTZU_FIXEDCase cases[]={
#define CASE(n,w,d,s,o,f,p) {#n,w,d,s,o,f,p},
#include "fcvtzu_fixed_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static uint64_t scalar(const uint8_t*p,unsigned w){return w==32?(uint32_t)get64(p):get64(p);}
static uint64_t fixed_expected(uint64_t raw,unsigned w,unsigned out,unsigned fbits,uint64_t fpcr,uint64_t*status){
 const unsigned fraction=w==32?23:52,bias=w==32?127:1023;
 const uint64_t sign=UINT64_C(1)<<(w-1),fm=(UINT64_C(1)<<fraction)-1,em=(w==32?UINT64_C(0x7f800000):UINT64_C(0x7ff0000000000000));
 const uint64_t frac=raw&fm,encoded=(raw&em)>>fraction,max=out==32?UINT64_C(0xffffffff):UINT64_MAX;const int neg=!!(raw&sign);
 if((raw&em)==em){*status|=1;return frac||neg?0:max;}
 if(!encoded&&!frac)return 0;
 if(!encoded&&(fpcr&(UINT64_C(1)<<24))){*status|=128;return 0;}
 const uint64_t sig=frac|(encoded?(UINT64_C(1)<<fraction):0);
 const int shift=(int)(encoded?encoded:1)-(int)bias-(int)fraction+(int)fbits;
 __uint128_t magnitude=0;int remainder=0,overflow=0;
 if(shift>=0){if(shift>=64)overflow=1;else magnitude=(__uint128_t)sig<<(unsigned)shift;}
 else if(shift<=-64){remainder=!!sig;}
 else{unsigned s=(unsigned)-shift;magnitude=sig>>s;remainder=!!(sig&((UINT64_C(1)<<s)-1));}
 if(overflow||magnitude>max||(neg&&magnitude)){*status|=1;return neg?0:max;}
 if(remainder){*status|=16;}return(uint64_t)magnitude;
}
static uint32_t uint_to_single(uint64_t value,uint64_t fpcr,uint64_t*status){
 if(!value){return 0;}unsigned e=0;for(uint64_t v=value;v>>=1;)++e;
 uint64_t sig;int remainder=0,increment=0;
 if(e<=23)sig=value<<(23-e);
 else{unsigned shift=e-23;sig=value>>shift;uint64_t rem=value&((UINT64_C(1)<<shift)-1);remainder=!!rem;unsigned mode=(unsigned)(fpcr>>22)&3;
  increment=mode==1?remainder:mode==0&&(rem>(UINT64_C(1)<<(shift-1))||(rem==(UINT64_C(1)<<(shift-1))&&(sig&1)));}
 if(remainder){*status|=16;}sig+=(unsigned)increment;if(sig==(UINT64_C(1)<<24)){sig>>=1;++e;}
 return(uint32_t)(((uint64_t)(e+127)<<23)|(sig&0x7fffff));
}
static uint64_t input_bits(const FCVTZU_FIXEDCase*c,unsigned pattern,uint64_t random){
 (void)random;const unsigned f=c->width==32?23:52,b=c->width==32?127:1023;const uint64_t sign=UINT64_C(1)<<(c->width-1),fm=(UINT64_C(1)<<f)-1,em=c->width==32?UINT64_C(0x7f800000):UINT64_C(0x7ff0000000000000),quiet=UINT64_C(1)<<(f-1);
 uint64_t q=(uint64_t)(b-c->fbits)<<f,half=(uint64_t)(b-c->fbits-1)<<f,limit=(uint64_t)(b+c->outwidth-c->fbits)<<f;
 uint64_t a[]={0,sign,1,sign|1,fm,sign|fm,UINT64_C(1)<<f,sign|(UINT64_C(1)<<f),q-1,q,q+1,sign|(q-1),sign|q,sign|(q+1),half,sign|half,limit-1,limit,limit+1,sign|(limit-1),sign|limit,sign|(limit+1),em,sign|em,em|quiet,sign|em|quiet,em|1,sign|em|1,em-1,(uint64_t)b<<f,c->width==32?UINT64_C(0x42f00000):UINT64_C(0x405e000000000000),sign|(em-1)};
 return a[pattern]& (c->width==32?UINT64_C(0xffffffff):UINT64_MAX);
}
static int run_fcvtzu_fixed_records(void(*call)(unsigned,uint8_t*,const uint8_t*)){
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<1024;++seed){
  const FCVTZU_FIXEDCase*c=&cases[test];unsigned pattern=seed&31,mode=(seed>>5)&15,flags=(seed>>4)&15;
  uint8_t input[768] __attribute__((aligned(16))),space[1664] __attribute__((aligned(16))),expected[800],original[768];uint8_t*out=space+32;
  memset(input,0x73,sizeof(input));memset(space,0xab,sizeof(space));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
  for(unsigned n=0;n<92;++n){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}
  uint64_t raw=input_bits(c,pattern,random);memcpy(input+224+c->rn*16,&raw,c->width/8);
  put64(input+736,(uint64_t)flags<<28);put64(input+744,(seed>>9)?UINT64_C(0x0800009f):0);put64(input+752,((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22));
  memcpy(original,input,sizeof(input));call(test,out,input);
  if(memcmp(input,original,sizeof(input)))return 20;
  for(unsigned n=0;n<sizeof(space);++n)if((n<32||n>=1632)&&space[n]!=0xab)return 21;
  if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16)return 22;
  for(unsigned r=2;r<30;++r)if(r!=18&&get64(out+r*8)!=get64(input+(r-2)*8))return 23;
  if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 24;
  memcpy(expected,out,800);uint64_t status=get64(out+776),value=fixed_expected(scalar(out+256+c->rn*16,c->width),c->width,c->outwidth,c->fbits,get64(out+784),&status);
  if(c->rd!=31)put64(expected+c->rd*8,value);
  if(c->pair){uint32_t fp=uint_to_single(value,get64(out+784),&status);memset(expected+256,0,16);put64(expected+256,fp);}
  put64(expected+776,status);
  if(memcmp(expected,out+800,800)){fprintf(stderr,"FCVTZU_FIXED bit/state mismatch case=%s seed=%u value=%llx flags=%llx/%llx\n",c->name,seed,(unsigned long long)value,(unsigned long long)status,(unsigned long long)get64(out+800+776));return 25;}
  put64(expected,0);put64(expected+8,0);put64(expected+18*8,0);put64(expected+30*8,0);put64(expected+31*8,0);
  uint64_t hash=UINT64_C(1469598103934665603);for(unsigned n=0;n<800;++n){hash^=expected[n];hash*=UINT64_C(1099511628211);}
  printf("RECORD %s %u %016llx %016llx\n",c->name,seed,(unsigned long long)value,(unsigned long long)hash);++count;
 }
 printf("FCVTZU_FIXED-RECORDS-SUCCESS %u\n",count);return 0;
}
'''
def word(width,outwidth,rd,rn,fbits):
 return 0x1e190000|((outwidth==64)<<31)|((width==64)<<22)|((64-fbits)<<10)|(rn<<5)|rd

def generate(out):
 cases=[]
 for w in(32,64):
  for o in(32,64):
   for f in(1,10,o):
    for d,n in((5,0),(17,31),(31,7)):
     cases.append((f'fixed_{w}_{o}_{f}_{d}_{n}',w,d,n,o,f,0,[word(w,o,d,n,f)]))
 cases += [('original_fixed',32,9,0,64,10,0,[0x9e19d809]),('original_pair',32,9,0,64,10,1,[0x9e19d809,0x9e230120])]
 for name,w,o,d,n in [('unscaled_original_x_s',32,64,8,0),('unscaled_w_s_high',32,32,17,31),('unscaled_w_d_high',64,32,5,31),('unscaled_x_d_high',64,64,17,7)]:
  bits=0x1e390000|((o==64)<<31)|((w==64)<<22)|(n<<5)|d
  cases.append((name,w,d,n,o,0,0,[bits]))
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  b=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  b+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for register,pos in(('fpsr',776),('fpcr',784)):b+=[f'mrs x2,{register}',f'str x2,[x0,#{offset+pos}]']
  return b+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for name,w,d,n,o,f,pair,words in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  for register,pos in(('fpsr',744),('fpcr',752)):body+=[f'ldr x2,[x1,#{pos}]',f'msr {register},x2']
  body +=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  body+=snapshot(0)+[f'.inst 0x{x:08x}'for x in words]+snapshot(800)
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(name,body);function('raw_'+name,[*[f'.inst 0x{x:08x}'for x in words],'ret'])
 function('fcvtzu_fixed_control_copy',['ldr s0,[x0]','str s0,[x1]','ret'])
 (out/'fcvtzu_fixed.S').write_text('\n'.join(lines)+'\n');(out/'fcvtzu_fixed_cases.h').write_text(''.join(f'CASE({n},{w},{d},{rn},{o},{f},{p})\n'for n,w,d,rn,o,f,p,_ in cases));(out/'fcvtzu_fixed_records.h').write_text(RECORDS);(out/'case-oracle.json').write_text(json.dumps(cases,indent=2)+'\n');return cases


