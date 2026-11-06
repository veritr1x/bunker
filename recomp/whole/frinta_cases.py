"""FRINTA S/D register fixtures and exact half-tie neighbors at every fractional exponent."""
import json
def edges(width):
 frac,bias=(23,127)if width==32 else(52,1023);sign=1<<(width-1);exp=((1<<(width-frac-1))-1)<<frac;quiet=1<<(frac-1)
 positive=[0,1,2,(1<<frac)-1,1<<frac,((bias-2)<<frac),((bias-1)<<frac)-1,((bias-1)<<frac),((bias-1)<<frac)+1,(bias<<frac)-1,bias<<frac,(bias<<frac)+1,((bias+1)<<frac)-1,(bias+1)<<frac,((bias+1)<<frac)+1,((bias+frac)<<frac)-1,(bias+frac)<<frac,((bias+frac)<<frac)+1,exp-1,exp,exp+1,exp+quiet-1,exp+quiet,exp+quiet+0x12345,exp+(1<<frac)-1]
 for exponent in range(frac):
  tie=((bias+exponent)<<frac)|(1<<(frac-exponent-1));positive.extend([tie-1,tie,tie+1])
 return sorted({value|s for value in positive for s in [0,sign]})
def generate(out):
 cases=[]
 for width in [32,64]:
  for rd,rn in [(0,1),(8,8),(31,17),(16,31)]:cases.append((f'frinta_{width}_{rd}_{rn}',width,rd,rn,(0x1e264000 if width==32 else 0x1e664000)|(rn<<5)|rd))
 cases.append(('actual_unity_70828c24_1e264063',32,3,3,0x1e264063))
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  body=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  body+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for register,pos in [('fpsr',776),('fpcr',784)]:body+=[f'mrs x2,{register}',f'str x2,[x0,#{offset+pos}]']
  return body+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for name,width,rd,rn,word in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  for register,pos in [('fpsr',744),('fpcr',752)]:body+=[f'ldr x2,[x1,#{pos}]',f'msr {register},x2']
  body+=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  body+=snapshot(0)+[f'.inst 0x{word:08x}']+snapshot(800)
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(name,body);function('raw_'+name,[f'.inst 0x{word:08x}','ret'])
 function('frinta_control_copy',['ldr s0,[x0]','str s0,[x1]','ret'])
 (out/'frinta.S').write_text('\n'.join(lines)+'\n');(out/'frinta_cases.h').write_text(''.join(f'CASE({name},{width},{rd},{rn})\n'for name,width,rd,rn,_ in cases))
 (out/'frinta_edges.h').write_text('\n'.join('static const uint64_t frinta_edges_'+str(width)+'[]={'+','.join('UINT64_C(0x'+format(v,'x')+')'for v in edges(width))+'};'for width in [32,64])+'\n')
 (out/'case-oracle.json').write_text(json.dumps(dict(cases=cases,edges={str(w):[hex(v)for v in edges(w)]for w in [32,64]},modes=16,initial_FPSR_profiles=2,random_patterns=64,records=sum((len(edges(width))+64)*32 for _,width,_,_,_ in cases)),indent=2)+'\n');return cases
