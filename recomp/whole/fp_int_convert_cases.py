"""Integer-to-IEEE fixtures and exact/inexact rounding boundary inputs."""
EDGES = [0, 1, 2, 3, 0x7fffff, 0xffffff, 0x1000000, 0x1000001, 0x1000002,
         0x1000003, 0x1ffffff, 0x2000001, 0x7fffffff, 0x80000000, 0xffffffff,
         0x100000001, 0xffffffffffffffff, 0xfffffffffffffffe,
         0x000fffffffffffff, 0x0010000000000000, 0x0010000000000001,
         0x001fffffffffffff, 0x0020000000000000, 0x0020000000000001,
         0x0020000000000002, 0x0020000000000003,
         0x0040000000000001, 0x0040000000000002, 0x0040000000000003,
         0x7ffffffffffffffe, 0x7fffffffffffffff, 0x8000000000000000,
         0x8000000000000001, 0xffffffffff000001, 0xffffffffff000000,
         0xfffffffffeffffff, 0xfffffffffefffffe, 0xffe0000000000001,
         0xffe0000000000000, 0xffdfffffffffffff, 0xffbfffffffffffff]


def generate():
    cases = {}

    def function(instruction, dest, before=()):
        return ['mrs x9, fpcr', 'mrs x10, fpsr', 'msr fpcr, x3', 'msr fpsr, x4',
                'ldr q0, [x1]', 'ldr q2, [x1, #16]', *before, instruction,
                f'str q{dest}, [x0]', 'mrs x5, fpsr', 'str x5, [x0, #16]',
                'msr fpcr, x9', 'msr fpsr, x10', 'ret']

    for op in ('scvtf', 'ucvtf'):
        for shape, width, scalar in [('2s', 32, False), ('4s', 32, False),
                                      ('2d', 64, False), ('s', 32, True), ('d', 64, True)]:
            for alias, dest in [('normal', 2), ('inplace', 0)]:
                dst = f'{shape}{dest}' if scalar else f'v{dest}.{shape}'
                src = f'{shape}0' if scalar else f'v0.{shape}'
                cases[f'{op}_{shape}_{alias}'] = (function(f'{op} {dst}, {src}', dest), width)
        for output in ('s', 'd'):
            for source, width in [('w', 32), ('x', 64)]:
                for zero in (False, True):
                    src = f'{source}zr' if zero else f'{source}5'
                    name = f'{op}_gpr_{output}_{source}_{"zero" if zero else "normal"}'
                    cases[name] = (function(f'{op} {output}2, {src}', 2, [] if zero else [f'ldr {source}5, [x1]']), width)
    return cases
