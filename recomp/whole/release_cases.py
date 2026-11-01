"""Aligned release-store probes, including zero sources and SP/base aliases."""
def generate():
    functions = {}
    for op, bits, source in [('stlrb', 8, 'w4'), ('stlrh', 16, 'w4'),
                             ('stlr', 32, 'w4'), ('stlr', 64, 'x4')]:
        for mode in ('normal', 'zero', 'sp', 'base_alias'):
            base = 'sp' if mode == 'sp' else 'x3'
            src = ('xzr' if bits == 64 else 'wzr') if mode == 'zero' else source
            lines = ['sub sp, sp, #16', 'str xzr, [sp]', 'mov x3, sp', 'ldr x4, [x1]']
            if mode == 'base_alias':
                src = 'x3' if bits == 64 else 'w3'
            lines += [f'{op} {src}, [{base}]', 'ldr x4, [sp]']
            if mode == 'base_alias':
                if bits == 64:
                    lines += ['sub x4, x4, x3']
                else:
                    lines += [f'and x5, x3, #{(1 << bits) - 1}', 'sub x4, x4, x5']
            lines += ['str x4, [x0]', 'add sp, sp, #16', 'ret']
            functions[f'{op}_{bits}_{mode}'] = lines
    return functions
