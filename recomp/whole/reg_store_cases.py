"""Scalar SIMD register-offset STR fixtures with guarded memory/source snapshots."""

def store_word(bits, source, option, scaled, base=3, index=4):
    # STR (SIMD&FP), register offset: size31:30, option15:13, S12.
    return (0x3c200800 | ({8:0,16:1,32:2,64:3}[bits]<<30) |
            (index<<16) | (option<<13) | (scaled<<12) | (base<<5) | source)

def generate():
    result={}
    for element,bits in [('b',8),('h',16),('s',32),('d',64)]:
        for source in range(32):
            for extension,option in [('uxtw',2),('lsl',3),('sxtw',6),('sxtx',7)]:
                for scaled in (0,1):
                    for sp in (False,True):
                        # The full register matrix tests runtime zero/positive/
                        # negative values. Explicit WZR/XZR encodings additionally
                        # test register31 using both ends of the V register bank.
                        for zero in ((False,True) if source in (0,31) else (False,)):
                            code=['sub sp,sp,#320','mov x10,sp',
                                  'stp q8,q9,[sp,#160]','stp q10,q11,[sp,#192]',
                                  'stp q12,q13,[sp,#224]','stp q14,q15,[sp,#256]']
                            if sp:
                                for offset in range(0,128,32):
                                    code += [f'ldp q0,q1,[x0,#{offset}]',f'stp q0,q1,[sp,#{offset+16}]']
                            code += [f'ldr q{source},[x1]','and x4,x2,#3']
                            if extension in ('sxtw','sxtx'):
                                code += ['neg x7,x4','tst x2,#4','csel x4,x7,x4,ne']
                            if extension in ('uxtw','sxtw'):
                                # The top32 bits must be ignored for W indices.
                                code += ['movk x4,#0x1234,lsl #32','movk x4,#0xabcd,lsl #48']
                            code += ['mov x6,x4']
                            if sp:code += ['add x5,x10,#64','mov sp,x5']
                            else:code += ['add x3,x0,#48','mov x5,x3']
                            word=store_word(bits,source,option,scaled,31 if sp else 3,31 if zero else 4)
                            code += [f'.inst {word:#010x} // str {element}{source}, register offset {extension}, S={scaled}']
                            if sp:
                                code += ['mov x3,sp','sub x3,x3,x5','mov sp,x10',f'str q{source},[sp,#96]']
                                for offset in range(0,128,32):
                                    code += [f'ldp q0,q1,[sp,#{offset+16}]',f'stp q0,q1,[x0,#{offset}]']
                            else:code += ['sub x3,x3,x5',f'str q{source},[x0,#80]']
                            code += ['str x3,[x0,#96]','eor x4,x4,x6','str x4,[x0,#104]',
                                     'stp xzr,xzr,[x0,#112]',
                                     'ldp q8,q9,[sp,#160]','ldp q10,q11,[sp,#192]',
                                     'ldp q12,q13,[sp,#224]','ldp q14,q15,[sp,#256]',
                                     'add sp,sp,#320','ret']
                            name=f'strreg_{element}_v{source}_{extension}_S{scaled}_{"sp" if sp else "x"}{"_zr" if zero else ""}'
                            result[name]=code
    return result
