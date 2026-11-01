"""Additional ARM64 assembly fixtures for unsigned SIMD shifts and narrowing.

The shared semantic case runner varies all 256 seeds. Shift-vector low bytes
therefore cover every signed 8-bit shift while the higher bytes vary too.
"""


def generate():
    from float_bits_cases import generate as float_bits_generate
    functions = {}

    def snapshot(instruction):
        return ['ldr q0, [x1]', 'ldr q1, [x1, #64]', 'ldr q2, [x1, #80]',
                instruction, 'stp q0, q1, [x0]', 'str q2, [x0, #32]', 'ret']

    arrangements = [('8b', 8), ('16b', 8), ('4h', 16), ('8h', 16),
                    ('2s', 32), ('4s', 32), ('2d', 64)]
    for arr, bits in arrangements:
        for name, dst in [('normal', 2), ('source_overlap', 0), ('shift_overlap', 1)]:
            functions[f'ushl_{arr}_{name}'] = snapshot(f'ushl v{dst}.{arr}, v0.{arr}, v1.{arr}')
        # Every allocated immediate, including zero and element-width minus one.
        for amount in range(bits):
            for name, dst in [('normal', 2), ('source_overlap', 0)]:
                functions[f'shl_{arr}_{amount}_{name}'] = snapshot(f'shl v{dst}.{arr}, v0.{arr}, #{amount}')
    for name, dst in [('normal', 2), ('source_overlap', 0), ('shift_overlap', 1)]:
        functions[f'ushl_scalar_{name}'] = snapshot(f'ushl d{dst}, d0, d1')
    for amount in range(64):
        for name, dst in [('normal', 2), ('source_overlap', 0)]:
            functions[f'shl_scalar_{amount}_{name}'] = snapshot(f'shl d{dst}, d0, #{amount}')

    for dst_arr, src_arr in [('8b', '8h'), ('4h', '4s'), ('2s', '2d')]:
        for high in (False, True):
            narrow_arr = f'{int(dst_arr[:-1]) * 2}{dst_arr[-1]}' if high else dst_arr
            op = 'xtn2' if high else 'xtn'
            for name, dst in [('normal', 2), ('source_overlap', 0)]:
                functions[f'{op}_{dst_arr}_{name}'] = snapshot(f'{op} v{dst}.{narrow_arr}, v0.{src_arr}')

    for arr, bits in arrangements:
        for op in ('zip1', 'zip2', 'uzp1', 'uzp2'):
            for name, dst, lhs, rhs in [('normal', 2, 0, 1), ('lhs_overlap', 0, 0, 1),
                                       ('rhs_overlap', 1, 0, 1), ('same_sources', 2, 0, 0),
                                       ('all_overlap', 0, 0, 0)]:
                functions[f'{op}_{arr}_{name}'] = snapshot(f'{op} v{dst}.{arr}, v{lhs}.{arr}, v{rhs}.{arr}')
        for container in (16, 32, 64):
            if bits >= container:
                continue
            for name, dst in [('normal', 2), ('source_overlap', 0)]:
                functions[f'rev{container}_{arr}_{name}'] = snapshot(f'rev{container} v{dst}.{arr}, v0.{arr}')
    functions.update(float_bits_generate())
    return functions
