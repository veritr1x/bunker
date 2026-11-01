"""Bit-exact vector FABS/FNEG and every floating-immediate encoding.

FP16 operations use verified raw instruction words so the assembly fixture
does not depend on the assembler's default architectural feature selection.
"""


ARRANGEMENTS = [('4h', 16, 0), ('8h', 16, 1), ('2s', 32, 0), ('4s', 32, 1), ('2d', 64, 1)]


def sign_word(op, bits, q, dst, src=0):
    word = 0x0EF8F800 if bits == 16 else 0x0EA0F800 | ((bits == 64) << 22)
    return word | (q << 30) | ((op == 'fneg') << 29) | (src << 5) | dst


def immediate_word(bits, q, imm, dst=2):
    word = 0x0F00F400 | (q << 30) | ((bits == 64) << 29) | ((bits == 16) << 11)
    return word | ((imm >> 5) << 16) | ((imm & 31) << 5) | dst


def load_bits(bits, value):
    reg = 'x4' if bits == 64 else 'w4'
    lines = [f'movz {reg}, #{value & 0xFFFF}']
    for shift in range(16, bits, 16):
        lines += [f'movk {reg}, #{(value >> shift) & 0xFFFF}, lsl #{shift}']
    arr = {16: '8h', 32: '4s', 64: '2d'}[bits]
    return lines + [f'dup v0.{arr}, {reg}']


def generate():
    functions = {}
    patterns = {
        16: [0x0000, 0x8000, 0x7C00, 0xFC00, 0x7E55, 0xFE55, 0x7C01, 0xFC01,
             0x0001, 0x8001, 0x3C00, 0xBC00, 0x7BFF, 0xFBFF],
        32: [0x00000000, 0x80000000, 0x7F800000, 0xFF800000, 0x7FC12345, 0xFFC12345,
             0x7F800001, 0xFF800001, 0x00000001, 0x80000001, 0x3F800000, 0xBF800000,
             0x7F7FFFFF, 0xFF7FFFFF],
        64: [0x0000000000000000, 0x8000000000000000, 0x7FF0000000000000, 0xFFF0000000000000,
             0x7FF8123456789ABC, 0xFFF8123456789ABC, 0x7FF0000000000001, 0xFFF0000000000001,
             0x0000000000000001, 0x8000000000000001, 0x3FF0000000000000, 0xBFF0000000000000,
             0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF],
    }
    for arr, bits, q in ARRANGEMENTS:
        for status in (0, 0x9F):
            fpsr = [f'mov x3, #{status}', 'msr fpsr, x3']
            save_status = ['mrs x3, fpsr', 'str x3, [x0, #112]', 'ret']
            for op in ('fabs', 'fneg'):
                for mode, dst in [('normal', 2), ('source_overlap', 0)]:
                    functions[f'{op}_{arr}_{mode}_fpsr{status}'] = [
                        'ldr q0, [x1]', 'ldr q2, [x1, #80]', *fpsr,
                        f'.inst {sign_word(op, bits, q, dst):#x}',
                        'str q0, [x0]', 'str q2, [x0, #16]', *save_status]
                    for group in range(2):
                        body = list(fpsr)
                        for slot, value in enumerate(patterns[bits][group * 7:group * 7 + 7]):
                            body += ['ldr q2, [x1, #80]', *load_bits(bits, value),
                                     f'.inst {sign_word(op, bits, q, dst):#x}',
                                     f'str q{dst}, [x0, #{slot * 16}]']
                        functions[f'{op}_{arr}_{mode}_bits{group}_fpsr{status}'] = body + save_status
            for group in range(0, 256, 7):
                body = list(fpsr)
                for slot, imm in enumerate(range(group, min(group + 7, 256))):
                    body += ['ldr q2, [x1, #80]', f'.inst {immediate_word(bits, q, imm):#x}',
                             f'str q2, [x0, #{slot * 16}]']
                functions[f'fmov_{arr}_imm{group}_fpsr{status}'] = body + save_status
    return functions
