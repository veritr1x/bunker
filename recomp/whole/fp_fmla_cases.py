"""All baseline FP32/64 indexed FMLA shapes, indices, overlaps and high registers."""


def generate():
    cases={}
    aliases=[('normal',0,1,2),('dest_lhs',1,1,2),('dest_rhs',2,1,2),
             ('shared_sources',0,1,1),('all_same',1,1,1),('high_alias',31,16,31)]
    for shape,width,lanes in [('2s',32,2),('4s',32,4),('2d',64,2),('s',32,1),('d',64,1)]:
        for index in range(4 if width==32 else 2):
            for alias,d,n,m in aliases:
                name=f'fmla_{shape}_i{index}_{alias}'
                scalar=len(shape)==1
                dst=f'{shape}{d}' if scalar else f'v{d}.{shape}'
                lhs=f'{shape}{n}' if scalar else f'v{n}.{shape}'
                operand=f'v{m}.{"s" if width==32 else "d"}[{index}]'
                body=_body(d,n,m,f'fmla {dst}, {lhs}, {operand}')
                exhaustive=alias=='normal' and index==0 and shape in ('4s','2d')
                cases[name]=(body,width,exhaustive,d,n,m,lanes,index)
    cases['fmla_unity_4fa01234']=(_body(20,17,0,'.inst 0x4fa01234'),32,False,20,17,0,4,1)
    return cases


def _body(d,n,m,op):
    return ['mrs x9, fpcr','mrs x10, fpsr','msr fpcr, x4','uxtw x12, w5','msr fpsr, x12',
            'cmp xzr, xzr','tbnz x5, #63, 1f','ccmp xzr, xzr, #5, ne','b 2f',
            '1:','ccmp xzr, xzr, #10, ne','2:',f'ldr q{d}, [x1]',f'ldr q{n}, [x2]',f'ldr q{m}, [x3]',op,
            f'str q{d}, [x0]',f'str q{n}, [x0, #16]',f'str q{m}, [x0, #32]',
            'mrs x6, fpsr','str x6, [x0, #48]',
            'cset w6, mi','lsl x6, x6, #31','cset w7, eq','orr x6, x6, x7, lsl #30',
            'cset w7, cs','orr x6, x6, x7, lsl #29','cset w7, vs','orr x6, x6, x7, lsl #28','str x6, [x0, #56]',
            'msr fpcr, x9','msr fpsr, x10','ret']
