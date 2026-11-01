"""TRN1/TRN2 lane arrangements, source identities, and destination overlap."""


def generate():
    cases = {}
    for op in ('trn1', 'trn2'):
        for form in ('8b', '16b', '4h', '8h', '2s', '4s', '2d'):
            for name, dst, lhs, rhs in [('normal', 2, 0, 1), ('lhs_overlap', 0, 0, 1),
                                       ('rhs_overlap', 1, 0, 1), ('same_sources', 2, 0, 0),
                                       ('all_overlap', 0, 0, 0)]:
                cases[f'{op}_{form}_{name}'] = [
                    'ldr q0, [x1]', 'ldr q1, [x1, #64]', 'ldr q2, [x1, #80]',
                    f'{op} v{dst}.{form}, v{lhs}.{form}, v{rhs}.{form}',
                    'stp q0, q1, [x0]', 'str q2, [x0, #32]', 'ret']
    return cases
