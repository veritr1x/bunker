"""Every allocated SSHR/USHR immediate, lane width, and destination alias."""


def generate():
    cases = {}
    forms = [('8b', 8), ('16b', 8), ('4h', 16), ('8h', 16),
             ('2s', 32), ('4s', 32), ('2d', 64), ('d', 64)]
    for op in ('ushr', 'sshr'):
        for form, bits in forms:
            for amount in range(1, bits + 1):
                for alias, dst in [('normal', 2), ('inplace', 0)]:
                    operands = (f'd{dst}, d0' if form == 'd' else
                                f'v{dst}.{form}, v0.{form}')
                    cases[f'{op}_{form}_{amount}_{alias}'] = [
                        'mrs x9, fpsr',
                        'mov x3, #0x9f', 'movk x3, #0x800, lsl #16',
                        'cmp x2, #1', 'csel x3, x3, xzr, eq', 'msr fpsr, x3',
                        'ccmp x2, #16, #15, ne',
                        'ldr q0, [x1]', 'ldr q1, [x1, #64]', 'ldr q2, [x1, #80]',
                        f'{op} {operands}, #{amount}',
                        'stp q0, q1, [x0]', 'str q2, [x0, #32]',
                        'mrs x5, fpsr', 'cset w6, mi', 'cset w7, eq',
                        'orr w6, w6, w7, lsl #1', 'cset w7, cs',
                        'orr w6, w6, w7, lsl #2', 'cset w7, vs',
                        'orr w6, w6, w7, lsl #3', 'stp x5, x6, [x0, #48]',
                        'msr fpsr, x9', 'ret']
    return cases
