"""AArch64 comparison fixtures with visible FPSR and preserved host FP state."""


def generate():
    cases = {}
    shapes = [('2s', 32, False), ('4s', 32, False), ('2d', 64, False),
              ('s', 32, True), ('d', 64, True)]
    for zero in (False, True):
        operations = ('fcmeq', 'fcmgt', 'fcmge', 'fcmlt', 'fcmle') if zero else ('fcmeq', 'fcmgt', 'fcmge')
        for op in operations:
            for shape, width, scalar in shapes:
                for alias, dest in [('normal', 2), ('lhs_overlap', 0), ('rhs_overlap', 1)]:
                    if zero and alias == 'rhs_overlap':
                        continue
                    name = f'{op}_{shape}_{"zero" if zero else "reg"}_{alias}'
                    dst = f'{shape}{dest}' if scalar else f'v{dest}.{shape}'
                    lhs = f'{shape}0' if scalar else f'v0.{shape}'
                    rhs = '#0.0' if zero else (f'{shape}1' if scalar else f'v1.{shape}')
                    instructions = ['mrs x9, fpcr', 'mrs x10, fpsr', 'msr fpcr, x3', 'msr fpsr, x4',
                        'ldr q0, [x1]', 'ldr q1, [x2]', 'ldr q2, [x1, #16]',
                        f'{op} {dst}, {lhs}, {rhs}', f'str q{dest}, [x0]', 'mrs x5, fpsr',
                        'str x5, [x0, #16]', 'msr fpcr, x9', 'msr fpsr, x10', 'ret']
                    cases[name] = (instructions, width)
    return cases
