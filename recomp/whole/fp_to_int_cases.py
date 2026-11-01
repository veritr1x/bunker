"""FCVTZS/ZU fixtures and boundaries where saturation differs from a C++ cast."""
import struct


def f64(value):
    return struct.unpack('<Q', struct.pack('<d', value))[0]


EDGES32 = [0, 0x80000000, 0x3e800000, 0xbe800000, 0x3f000000, 0xbf000000,
           0x3f7fffff, 0xbf7fffff, 0x3f800000, 0xbf800000, 0x3fc00000, 0xbfc00000,
           0x40000000, 0xc0000000, 0x4effffff, 0x4f000000, 0xcf000000, 0xcf000001,
           0x4f7fffff, 0x4f800000, 0xcf800000,
           0x5effffff, 0x5f000000, 0xdf000000, 0xdf000001, 0x5f7fffff, 0x5f800000,
           0xdf800000, 1, 0x80000001, 0x007fffff, 0x807fffff, 0x00800000, 0x80800000,
           0x7f7fffff, 0xff7fffff, 0x7f800000, 0xff800000,
           0x7fc00000, 0xffc00000, 0x7fc12345, 0x7f800001, 0xff800001, 0x7fbfffff]
EDGES64 = [f64(x) for x in (0.0, -0.0, 0.25, -0.25, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5,
                           2.0, -2.0, 2**31 - 0.5, 2**31, -(2**31), -(2**31) - 0.5,
                           -(2**31) - 1.0, 2**32 - 0.5, 2**32, -(2**32))]
EDGES64 += [0x3fefffffffffffff, 0xbfefffffffffffff, 0x43dfffffffffffff,
            0x43e0000000000000, 0xc3e0000000000000, 0xc3e0000000000001,
            0x43efffffffffffff, 0x43f0000000000000, 0xc3f0000000000000,
            1, 0x8000000000000001, 0x000fffffffffffff, 0x800fffffffffffff,
            0x0010000000000000, 0x8010000000000000, 0x7fefffffffffffff, 0xffefffffffffffff,
            0x7ff0000000000000, 0xfff0000000000000, 0x7ff8000000000000, 0xfff8000000000000,
            0x7ff8123456789abc, 0x7ff0000000000001, 0xfff0000000000001, 0x7ff7ffffffffffff]
EDGE_COUNT = max(len(EDGES32), len(EDGES64))
EDGES32 += [0] * (EDGE_COUNT - len(EDGES32))
EDGES64 += [0] * (EDGE_COUNT - len(EDGES64))


def generate():
    cases = {}

    def function(instruction, dest, after=()):
        return ['mrs x9, fpcr', 'mrs x10, fpsr', 'msr fpcr, x3', 'msr fpsr, x4',
                'ldr q0, [x1]', 'ldr q2, [x1, #16]', instruction,
                *(after or [f'str q{dest}, [x0]']), 'mrs x5, fpsr', 'str x5, [x0, #16]',
                'msr fpcr, x9', 'msr fpsr, x10', 'ret']

    for op in ('fcvtzs', 'fcvtzu'):
        for shape, width, scalar in [('2s', 32, False), ('4s', 32, False),
                                      ('2d', 64, False), ('s', 32, True), ('d', 64, True)]:
            for alias, dest in [('normal', 2), ('inplace', 0)]:
                dst = f'{shape}{dest}' if scalar else f'v{dest}.{shape}'
                src = f'{shape}0' if scalar else f'v0.{shape}'
                cases[f'{op}_{shape}_{alias}'] = (function(f'{op} {dst}, {src}', dest), width)
        for result in ('w', 'x'):
            for source, width in [('s', 32), ('d', 64)]:
                for zero in (False, True):
                    dst = f'{result}zr' if zero else f'{result}5'
                    name = f'{op}_gpr_{result}_{source}_{"zero" if zero else "normal"}'
                    cases[name] = (function(f'{op} {dst}, {source}0', 2,
                                           [f'stp {"xzr" if zero else "x5"}, xzr, [x0]']), width)
    return cases
