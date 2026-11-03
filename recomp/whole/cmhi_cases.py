"""Same-object unsigned higher comparison full-state fixture."""
import json
RECORDS='\n#pragma once\n#include <stdint.h>\n#include <stdio.h>\n#include <string.h>\ntypedef struct{const char*name;unsigned width,rd,rn,rm,cond,original;} CMHICase;\nstatic const CMHICase cases[]={\n#define CASE(name,w,d,n,m,c,o) {#name,w,d,n,m,c,o},\n#include "cmhi_cases.h"\n#undef CASE\n};\n#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))\nstatic uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}\nstatic void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}\nstatic uint64_t lane_mask(unsigned bits){return bits==64?UINT64_MAX:(UINT64_C(1)<<bits)-1;}\nstatic uint64_t lane_get(const uint8_t*p,unsigned bits,unsigned i){uint64_t v=0;memcpy(&v,p+i*(bits/8),bits/8);return v;}\nstatic void lane_put(uint8_t*p,unsigned bits,unsigned i,uint64_t v){v&=lane_mask(bits);memcpy(p+i*(bits/8),&v,bits/8);}\nstatic uint64_t compare_edge(unsigned bits,unsigned pattern,unsigned lane,unsigned second){uint64_t mask=lane_mask(bits),sign=UINT64_C(1)<<(bits-1);switch(pattern){case 0:return 0;case 1:return second?0:mask;case 2:return second?mask:0;case 3:return second?sign-1:sign;case 4:return second?sign:sign-1;case 5:return mask;case 6:return (lane&1)^second?mask:0;default:return ((lane+second)&1)?sign:sign-1;}}\nstatic int run_cmhi_records(void(*call)(unsigned,uint8_t*,const uint8_t*)){\n unsigned count=0;\n for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<256;++seed){\n  const CMHICase*c=&cases[test];unsigned pattern=seed&15,flags=seed>>4,mode=pattern;\n  uint8_t input[768] __attribute__((aligned(16))),output_space[1664] __attribute__((aligned(16))),expected[800],original[768];uint8_t*out=output_space+32;\n  memset(input,0x73,sizeof(input));memset(output_space,0xab,sizeof(output_space));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;\n  for(unsigned n=0;n<92;++n){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}\n  unsigned bits=c->width,lanes=(c->cond==2?64:(c->cond?128:64))/bits;\n  if(pattern<8){for(unsigned i=0;i<128/bits;++i)lane_put(input+224+c->rn*16,bits,i,compare_edge(bits,pattern,i,0));for(unsigned i=0;i<128/bits;++i)lane_put(input+224+c->rm*16,bits,i,compare_edge(bits,pattern,i,1));}\n  put64(input+736,(uint64_t)flags<<28);put64(input+744,(pattern&1)?UINT64_C(0x0800009f):0);put64(input+752,((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22));\n  memcpy(original,input,sizeof(input));call(test,out,input);\n  if(memcmp(original,input,sizeof(input)))return 20;\n  for(unsigned n=0;n<sizeof(output_space);++n)if((n<32||n>=1632)&&output_space[n]!=0xab)return 21;\n  if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16)return 22;\n  for(unsigned reg=2;reg<30;++reg)if(reg!=18&&get64(out+reg*8)!=get64(input+(reg-2)*8))return 23;\n  if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 24;\n  memcpy(expected,out,800);memset(expected+256+c->rd*16,0,16);\n  for(unsigned i=0;i<lanes;++i){uint64_t a=lane_get(out+256+c->rn*16,bits,i),b=lane_get(out+256+c->rm*16,bits,i);lane_put(expected+256+c->rd*16,bits,i,a>b?lane_mask(bits):0);}\n  uint64_t selected=get64(expected+256+c->rd*16);\n  if(memcmp(expected,out+800,800)){fprintf(stderr,"CMHI bit/state mismatch case=%s seed=%u\\n",c->name,seed);return 25;}\n  put64(expected,0);put64(expected+8,0);put64(expected+18*8,0);put64(expected+30*8,0);put64(expected+31*8,0);\n  uint64_t hash=UINT64_C(1469598103934665603);for(unsigned n=0;n<800;++n){hash^=expected[n];hash*=UINT64_C(1099511628211);}\n  printf("RECORD %s %u %016llx %016llx\\n",c->name,seed,(unsigned long long)selected,(unsigned long long)hash);++count;\n }\n printf("CMHI-RECORDS-SUCCESS %u\\n",count);return 0;\n}\n'

def generate(out):
 cases=[]
 for size,bits in enumerate((8,16,32,64)):
  for q in(0,1):
   if size==3 and not q:continue
   for rd,rn,rm in((0,1,2),(1,1,2),(2,1,2),(3,1,1),(7,7,7),(31,16,31),(8,15,8),(15,8,15)):
    word=0x2e203400|(size<<22)|(q<<30)|(rm<<16)|(rn<<5)|rd
    cases.append((f'cmhi_{bits}_{q}_{rd}_{rn}_{rm}',bits,rd,rn,rm,q,0,[word]))
 for rd,rn,rm in((0,1,2),(1,1,2),(2,1,2),(3,1,1),(7,7,7),(31,16,31),(8,15,8),(15,8,15)):
  word=0x7ee03400|(rm<<16)|(rn<<5)|rd
  cases.append((f'cmhi_scalar_{rd}_{rn}_{rm}',64,rd,rn,rm,2,0,[word]))
 cases.append(('original_8261b694',32,16,5,16,1,0,[0x6eb034b0]))
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  b=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  b+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for register,pos in(('fpsr',776),('fpcr',784)):b+=[f'mrs x2,{register}',f'str x2,[x0,#{offset+pos}]']
  return b+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for name,w,d,n,m,c,kind,words in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  for register,pos in(('fpsr',744),('fpcr',752)):body+=[f'ldr x2,[x1,#{pos}]',f'msr {register},x2']
  body +=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  body+=snapshot(0)+[f'.inst 0x{x:08x}'for x in words]+snapshot(800)
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(name,body);function('raw_'+name,[*[f'.inst 0x{x:08x}'for x in words],'ret'])
 function('cmhi_control_copy',['ldr s0,[x0]','str s0,[x1]','ret'])
 (out/'cmhi.S').write_text('\n'.join(lines)+'\n');(out/'cmhi_cases.h').write_text(''.join(f'CASE({n},{w},{d},{rn},{rm},{c},{o})\n'for n,w,d,rn,rm,c,o,_ in cases));(out/'cmhi_records.h').write_text(RECORDS);(out/'case-oracle.json').write_text(json.dumps(cases,indent=2)+'\n');return cases
