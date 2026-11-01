"""FP32/FP64 precision conversion boundary and alias fixtures."""
import struct


def f64(x):
    return struct.unpack('<Q', struct.pack('<d', x))[0]


BASE64 = [0, 1, 0xfffffffffffff, 0x10000000000000, f64(1), f64(1) + (1 << 28) - 1,
          f64(1) + (1 << 28), f64(1) + (1 << 28) + 1,
          f64(1) + (3 << 28), f64(2) - 1,
          f64(2.0**-149), f64(2.0**-150) - 1, f64(2.0**-150), f64(2.0**-150) + 1,
          f64(2.0**-126), f64(2.0**-126) - 1, f64(2.0**-126) - (1 << 28),
          f64(2.0**-126) - (1 << 28) - 1, f64(2.0**-126) - (1 << 29),
          f64(2.0**128), f64(2.0**128) - 1, f64(2.0**128) - (1 << 28),
          f64(2.0**128) - (1 << 29), 0x7fefffffffffffff,
          0x7ff0000000000000, 0x7ff0000000000001, 0x7ff000001fffffff,
          0x7ff0000020000000, 0x7ff8000000000000, 0x7ff8123456789abc,
          0x7fffffffffffffff]
BASE32 = [0, 1, 2, 0x3fffff, 0x7fffff, 0x800000, 0x800001, 0x3f800000, 0x3f800001,
          0x3fffffff, 0x40000000, 0x7f7fffff, 0x7f800000, 0x7f800001,
          0x7fbfffff, 0x7fc00000, 0x7fc12345, 0x7fffffff]
EDGES64 = BASE64 + [v | 0x8000000000000000 for v in BASE64]
EDGES32 = BASE32 + [v | 0x80000000 for v in BASE32]
EDGE_COUNT = max(len(EDGES64), len(EDGES32))


def generate():
    cases = {}
    for op, width in [('fcvtn', 64), ('fcvtn2', 64), ('fcvtl', 32), ('fcvtl2', 32),
                      ('scalar_narrow', 64), ('scalar_widen', 32)]:
        for alias, dest in [('normal', 2), ('inplace', 0)]:
            if op.startswith('fcvtn'):
                insn = f'{op} v{dest}.{"4s" if op.endswith("2") else "2s"}, v0.2d'
            elif op.startswith('fcvtl'):
                insn = f'{op} v{dest}.2d, v0.{"4s" if op.endswith("2") else "2s"}'
            else:
                insn = f'fcvt {"s" if width == 64 else "d"}{dest}, {"d" if width == 64 else "s"}0'
            cases[f'{op}_{alias}'] = ([
                'mrs x9, fpcr', 'mrs x10, fpsr', 'msr fpcr, x3', 'msr fpsr, x4',
                'ldr q0, [x1]', 'ldr q2, [x1, #16]', insn,
                f'str q{dest}, [x0]', 'mrs x5, fpsr', 'str x5, [x0, #16]',
                'msr fpcr, x9', 'msr fpsr, x10', 'ret'], width)
    return cases
