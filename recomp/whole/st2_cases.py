"""Representative ST2 multiple-structure arrangements and address modes."""
import json
def generate(out):
 cases=[]
 for q,size,arr in [(0,0,'8b'),(1,0,'16b'),(0,1,'4h'),(1,1,'8h'),(0,2,'2s'),(1,2,'4s'),(1,3,'2d')]:
  width=8<<q
  for mode in range(3):
   for label,rt,rn,rm in [('normal',0,12,20),('wrap',31,12,20),('sp',7,31,20)]:
    word=0x0c008000|(q<<30)|(size<<10)|(rn<<5)|rt
    if mode:word|=0x00800000|((31 if mode==1 else rm)<<16)
    cases.append(dict(name=f'st2_{arr}_{mode}_{label}',width=width,element=1<<size,rt=rt,rn=rn,mode=mode,rm=rm,word=word,original=int(word==0x4c008d80)))
  word=0x0c808000|(q<<30)|(size<<10)|(12<<16)|(12<<5)|2
  cases.append(dict(name=f'st2_{arr}_2_selfbase',width=width,element=1<<size,rt=2,rn=12,mode=2,rm=12,word=word,original=0))
 assert len(cases)==70 and sum(x['original']for x in cases)==1
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  b=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  b+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for reg,pos in [('fpsr',776),('fpcr',784),('tpidr_el0',792)]:b+=[f'mrs x2,{reg}',f'str x2,[x0,#{offset+pos}]']
  return b+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for c in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  body+=['str x2,[x0,#1600]','str x3,[x0,#1608]','mov x4,sp','str x4,[x0,#1616]']
  for reg,pos in [('fpsr',744),('fpcr',752)]:body+=[f'ldr x2,[x1,#{pos}]',f'msr {reg},x2']
  body +=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  if c['rn']==31:body+=['ldr x29,[x0,#1616]','ldr x4,[x0,#1600]','mov sp,x4','ldr x4,[x1,#16]']
  else:body+=[f'ldr x{c["rn"]},[x0,#1600]']
  if c['mode']==2 and c['rm']!=c['rn']:body+=[f'ldr x{c["rm"]},[x0,#1608]']
  body+=snapshot(0)+[f'.inst 0x{c["word"]:08x}']+snapshot(800)
  if c['rn']==31:body+=['mov sp,x29']
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(c['name'],body);function('raw_'+c['name'],[f'.inst 0x{c["word"]:08x}','ret'])
 (out/'st2.S').write_text('\n'.join(lines)+'\n');(out/'st2_cases.h').write_text(''.join(f'CASE({c["name"]},{c["width"]},{c["element"]},{c["rt"]},{c["rn"]},{c["mode"]},{c["rm"]},{c["original"]})\n'for c in cases));(out/'case-oracle.json').write_text(json.dumps(cases,indent=2)+'\n');return cases
