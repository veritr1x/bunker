"""ST1 scalar-lane stores: source preservation, alignment and writeback aliases."""


def generate():
    functions = {}
    for element, lanes, amount in [('b',16,1), ('h',8,2), ('s',4,4), ('d',2,8)]:
        for lane in range(lanes):
            for source in (0,15,31):
                for sp in (False,True):
                    for mode in ('plain','imm','reg','negative','base_alias'):
                        for memory_alias in (False,True):
                            if mode in ('negative','base_alias') and memory_alias:
                                continue
                            name = f'st1_lane_{element}{lane}_v{source}_{"sp" if sp else "x"}_{mode}_{"alias" if memory_alias else "data"}'
                            # Frame[0:32] is the observed store region. A saved
                            # callee-saved Q15 lives outside it. All snapshots
                            # use X10 while post-indexing may move SP arbitrarily.
                            lines = ['mov x5, sp', 'sub sp, sp, #64', 'mov x10, sp']
                            if source == 15:
                                lines += ['str q15, [x10, #32]']
                            lines += ['ldp q6, q7, [x1]', 'stp q6, q7, [x10]', 'mov x6, x10']
                            if not sp:
                                lines += ['and x4, x2, #7', 'add x6, x6, x4', 'mov x3, x6']
                            lines += [f'ldr q{source}, [x6]' if memory_alias else f'ldr q{source}, [x1, #80]',
                                      'mrs x9, fpsr', 'mov x7, #0x9f', 'movk x7, #0x800, lsl #16',
                                      'msr fpsr, x7', 'cmp x2, #32', 'ccmp xzr, xzr, #9, eq']
                            if mode == 'negative':
                                lines += ['neg x2, x2']
                            if mode == 'base_alias':
                                lines += ['mov x3, x6']
                            base = 'sp' if sp else 'x3'
                            suffix = '' if mode == 'plain' else f', #{amount}' if mode == 'imm' else ', x3' if mode == 'base_alias' else ', x2'
                            lines += [f'st1 {{ v{source}.{element} }}[{lane}], [{base}]{suffix}',
                                      'mov x4, sp' if sp else 'mov x4, x3',
                                      'sub x4, x4, x6, lsl #1' if mode == 'base_alias' else 'sub x4, x4, x6',
                                      f'str q{source}, [x0, #32]', 'ldp q6, q7, [x10]', 'stp q6, q7, [x0]',
                                      'str x4, [x0, #48]', 'str x2, [x0, #56]',
                                      'mrs x7, fpsr', 'str x7, [x0, #64]',
                                      'cset x11, mi', 'cset x12, eq', 'cset x13, cs', 'cset x14, vs',
                                      'stp x11, x12, [x0, #72]', 'stp x13, x14, [x0, #88]', 'msr fpsr, x9']
                            if source == 15:
                                lines += ['ldr q15, [x10, #32]']
                            lines += ['mov sp, x5', 'ret']
                            functions[name] = lines
                            if source == 31 and mode in ('plain','imm','reg') and not memory_alias:
                                regression = name.replace('st1_lane_', 'ld1_lane_regression_', 1)
                                functions[regression] = [line.replace('st1 {', 'ld1 {', 1) if line.startswith('st1 {') else line for line in lines]
    return functions
