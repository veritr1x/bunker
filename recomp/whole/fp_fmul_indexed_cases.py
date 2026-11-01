"""Indexed FMUL32/64 only, using the established full-output wrapper ABI."""
from fp_fmla_cases import _body


def generate():
    cases={}
    aliases=[('normal',0,1,2),('dest_lhs',1,1,2),('dest_rhs',2,1,2),
             ('shared_sources',0,1,1),('all_same',1,1,1),('high_alias',31,16,31)]
    for shape,width,lanes in [('2s',32,2),('4s',32,4),('2d',64,2),('s',32,1),('d',64,1)]:
        for index in range(4 if width==32 else 2):
            for alias,d,n,m in aliases:
                scalar=len(shape)==1;dst=f'{shape}{d}'if scalar else f'v{d}.{shape}';lhs=f'{shape}{n}'if scalar else f'v{n}.{shape}'
                operand=f'v{m}.{"s"if width==32 else"d"}[{index}]'
                full=alias=='normal'and index==0 and shape in ('4s','2d')
                cases[f'fmulidx_{shape}_i{index}_{alias}']=(_body(d,n,m,f'fmul {dst}, {lhs}, {operand}'),width,full,d,n,m,lanes,index)
    cases['fmulidx_unity_4f809214']=(_body(20,16,0,'.inst 0x4f809214'),32,False,20,16,0,4,0)
    return cases
