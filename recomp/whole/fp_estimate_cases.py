"""ARM reciprocal-estimate table boundaries, special values, and register aliases."""


def edges(width):
    p, bias = (23, 127) if width == 32 else (52, 1023)
    fraction = (1 << p) - 1
    infinity = ((1 << (width - p - 1)) - 1) << p
    values = {0, 1, fraction, 1 << p, infinity - 1, infinity,
              infinity + 1, infinity + (1 << (p - 1)) - 1,
              infinity + (1 << (p - 1)), infinity + (1 << (p - 1)) + 123,
              infinity + fraction}
    # Every midpoint lookup bucket, both rsqrt exponent parities, either side
    # of each bucket boundary. Include normalized subnormal lookup buckets.
    for k in range(256):
        for exponent in (bias, bias + 1):
            boundary = (exponent << p) + (k << (p - 8))
            values.update((boundary - 1, boundary, boundary + 1))
        boundary = (1 << (p - 1)) + (k << (p - 9))
        values.update((boundary - 1, boundary, boundary + 1))
    for bit in range(p + 1):
        values.update(((1 << bit) - 1, 1 << bit, (1 << bit) + 1))
    for exponent in (1, 2, bias - 1, bias, bias + 1, 2 * bias - 2, 2 * bias - 1, 2 * bias):
        for f in (0, 1, fraction // 2, fraction - 1, fraction):
            values.add((exponent << p) | f)
    positives = sorted(values)
    return positives + [v | (1 << (width - 1)) for v in positives]


EDGES32, EDGES64 = edges(32), edges(64)
EDGE_COUNT = max(len(EDGES32), len(EDGES64))


def generate():
    cases = {}
    for op in ('frecpe', 'frsqrte'):
        for form, width in (('2s', 32), ('4s', 32), ('2d', 64), ('s', 32), ('d', 64)):
            for alias, dest in (('normal', 2), ('inplace', 0)):
                operands = (f'v{dest}.{form}, v0.{form}' if len(form) == 2 else
                            f'{form}{dest}, {form}0')
                cases[f'{op}_{form}_{alias}'] = ([
                    'mrs x9, fpcr', 'mrs x10, fpsr', 'msr fpcr, x3', 'msr fpsr, x4',
                    'ldr q0, [x1]', 'ldr q2, [x1, #16]', f'{op} {operands}',
                    f'str q{dest}, [x0]', 'mrs x5, fpsr', 'str x5, [x0, #16]',
                    'msr fpcr, x9', 'msr fpsr, x10', 'ret'], width)
    return cases
