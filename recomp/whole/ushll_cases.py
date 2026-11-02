"""Every legal USHLL immediate, source half and source/destination overlap."""

def generate():
    result = {}

    def snapshot(instruction):
        return ['ldr q0, [x1]', 'ldr q1, [x1, #16]',
                'ldr q2, [x1, #32]', 'ldr q3, [x1, #48]',
                'ldr q17, [x1, #96]', 'ldr q31, [x1, #112]', instruction,
                'stp q0, q1, [x0]', 'stp q2, q3, [x0, #32]',
                'str q17, [x0, #64]', 'str q31, [x0, #80]', 'ret']

    variants = [('separate', 2, 0), ('overlap', 0, 0),
                ('high_regs', 31, 17), ('high_overlap', 31, 31)]
    for bits, destination, low, high in [(8, '8h', '8b', '16b'),
                                        (16, '4s', '4h', '8h'),
                                        (32, '2d', '2s', '4s')]:
        for upper in (False, True):
            source = high if upper else low
            op = 'ushll2' if upper else 'ushll'
            for shift in range(bits):
                for variant, dst, src in variants:
                    result[f'{op}_{bits}_{shift}_{variant}'] = snapshot(
                        f'{op} v{dst}.{destination}, v{src}.{source}, #{shift}')
            alias = 'uxtl2' if upper else 'uxtl'
            for variant, dst, src in variants:
                result[f'{alias}_{bits}_{variant}'] = snapshot(
                    f'{alias} v{dst}.{destination}, v{src}.{source}')
    result['actual_unity_70413eb0_2f20a400'] = snapshot('.inst 0x2f20a400')
    assert len(result) == 473
    return result
