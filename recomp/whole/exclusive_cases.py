"""AArch64 single-element exclusives, including split-trace reservations."""


def generate(baseline=False):
    functions, public = {}, []
    modes = ['success', 'clear', 'noload', 'repeat', 'loadzero', 'storezero',
             'statuszero', 'base_overlap', 'sp', 'cross_trace']
    for size, suffix in [(1, 'b'), (2, 'h'), (4, 'w'), (8, 'x')]:
        reg = 'x' if size == 8 else 'w'
        for acquire in (False, True):
            for release in (False, True):
                load = ('ldaxr' if acquire else 'ldxr') + (suffix if size < 4 else '')
                store = ('stlxr' if release else 'stxr') + (suffix if size < 4 else '')
                selections = modes + [f'clear_imm{i}' for i in range(16)] if not acquire and not release else modes
                for mode in selections:
                    if baseline and (size, acquire, release, mode) != (8, False, True, 'cross_trace'):
                        continue
                    name = f'exclusive_{suffix}_{"acquire" if acquire else "plain"}_{"release" if release else "plain"}_{mode}'
                    prefix = ['clrex', 'mrs x9, fpsr', 'mov x7, #0x9f', 'movk x7, #0x800, lsl #16',
                              'msr fpsr, x7', 'ldr x2, [x1, #80]', 'cmp x2, #32',
                              'add x6, x1, #7', 'and x6, x6, #0xfffffffffffffff8',
                              'mov x3, #0', 'mov x4, #-1', 'mov x8, #-1']
                    if baseline:
                        prefix.remove('clrex')
                    if mode == 'sp':
                        prefix += ['mov x5, sp', 'sub sp, sp, #16', 'ldr x7, [x6]', 'str x7, [sp]', 'mov x6, sp']
                    post = ['str x3, [x0]', 'str x4, [x0, #8]', 'str x8, [x0, #16]',
                            'ldr x7, [x6]', 'str x7, [x0, #24]', 'str x2, [x0, #32]',
                            'cset x10, mi', 'cset x11, eq', 'cset x12, cs', 'cset x13, vs',
                            'stp x10, x11, [x0, #40]', 'stp x12, x13, [x0, #56]',
                            'mrs x7, fpsr', 'str x7, [x0, #72]', 'msr fpsr, x9']
                    if mode == 'sp':
                        post += ['mov sp, x5']
                    post += ['ret']
                    instructions = []
                    if mode != 'noload':
                        if mode == 'base_overlap':
                            instructions += ['mov x7, x6', f'{load} {reg}7, [x7]', 'mov x3, x7']
                        else:
                            instructions += [f'{load} {reg + "zr" if mode == "loadzero" else reg + "3"}, [{"sp" if mode == "sp" else "x6"}]']
                    if mode.startswith('clear'):
                        instructions += [f'clrex #{mode.removeprefix("clear_imm")}' if mode.startswith('clear_imm') else 'clrex']
                    instruction = f'{store} {"wzr" if mode == "statuszero" else "w4"}, {reg + "zr" if mode == "storezero" else reg + "2"}, [{"sp" if mode == "sp" else "x6"}]'
                    if mode == 'cross_trace':
                        helper = name + '_finish'
                        functions[name] = prefix + instructions + [f'b {helper}']
                        functions[helper] = [instruction] + post
                    else:
                        instructions += [instruction]
                        if mode == 'repeat':
                            instructions += [f'{store} w8, {reg}zr, [x6]']
                        functions[name] = prefix + instructions + post
                    public.append(name)
    return functions, public


def generate_pairs():
    functions, public = {}, []
    modes = ['success', 'clear', 'noload', 'repeat', 'loadzero_first', 'loadzero_second',
             'storezero_first', 'storezero_second', 'storezero_both', 'same_source',
             'statuszero', 'base_overlap_first', 'base_overlap_second', 'sp', 'cross_trace', 'retry']
    for element, reg in [(4, 'w'), (8, 'x')]:
        for acquire in (False, True):
            for release in (False, True):
                load = 'ldaxp' if acquire else 'ldxp'
                store = 'stlxp' if release else 'stxp'
                for mode in modes:
                    name = f'exclusive_pair_{reg}_{"acquire" if acquire else "plain"}_{"release" if release else "plain"}_{mode}'
                    prefix = ['clrex', 'mrs x17, fpsr', 'mov x7, #0x9f', 'movk x7, #0x800, lsl #16',
                              'msr fpsr, x7', 'ldr x2, [x1, #80]', 'ldr x14, [x1, #88]', 'cmp x2, #32',
                              'mov x3, #0', 'mov x7, #0', 'mov x4, #-1', 'mov x8, #-1',
                              # The caller's byte buffer has no 16-byte ABI
                              # alignment guarantee. Copy the same bytes into
                              # an aligned frame instead of rounding its address
                              # and choosing different bytes on different hosts.
                              'mov x5, sp', 'sub sp, sp, #16', 'ldp x10, x11, [x1]',
                              'stp x10, x11, [sp]', 'mov x6, sp']
                    post = ['str x3, [x0]', 'str x7, [x0, #8]', 'str x4, [x0, #16]', 'str x8, [x0, #24]',
                            'ldp x10, x11, [x6]', 'stp x10, x11, [x0, #32]', 'stp x2, x14, [x0, #48]',
                            'cset x10, mi', 'cset x11, eq', 'cset x12, cs', 'cset x13, vs',
                            'stp x10, x11, [x0, #64]', 'stp x12, x13, [x0, #80]',
                            'mrs x7, fpsr', 'str x7, [x0, #96]', 'msr fpsr, x17']
                    post += ['mov sp, x5']
                    post += ['ret']
                    instructions = []
                    if mode == 'retry':
                        # Match the actual Unity ctor71 x10/x11 load followed
                        # by stxp w9,x8,x8,[x0], including its retry branch.
                        instructions = ['mov x15, x0', 'mov x0, x6', 'mov x8, x2', '1:',
                                        f'{load} {reg}10, {reg}11, [x0]',
                                        f'{store} w9, {reg}8, {reg}8, [x0]', 'cbnz w9, 1b',
                                        'mov x4, x9', 'mov x3, x10', 'mov x7, x11',
                                        'mov x8, #-1', 'mov x0, x15']
                        functions[name] = prefix + instructions + post
                        public.append(name)
                        continue
                    base = 'sp' if mode == 'sp' else 'x6'
                    if mode == 'base_overlap_first':
                        instructions += ['mov x15, x6', f'{load} {reg}6, {reg}7, [x6]', 'mov x3, x6', 'mov x6, x15']
                    elif mode == 'base_overlap_second':
                        instructions += ['mov x15, x6', f'{load} {reg}3, {reg}6, [x6]', 'mov x7, x6', 'mov x6, x15']
                    elif mode != 'noload':
                        first = reg + ('zr' if mode == 'loadzero_first' else '3')
                        second = reg + ('zr' if mode == 'loadzero_second' else '7')
                        instructions += [f'{load} {first}, {second}, [{base}]']
                    if mode == 'clear':
                        instructions += ['clrex #7']
                    first = reg + ('zr' if mode in ('storezero_first', 'storezero_both') else '2')
                    second = reg + ('zr' if mode in ('storezero_second', 'storezero_both') else '2' if mode == 'same_source' else '14')
                    instruction = f'{store} {"wzr" if mode == "statuszero" else "w4"}, {first}, {second}, [{base}]'
                    if mode == 'cross_trace':
                        helper = name + '_finish'
                        functions[name] = prefix + instructions + [f'b {helper}']
                        functions[helper] = [instruction] + post
                    else:
                        instructions += [instruction]
                        if mode == 'repeat':
                            instructions += [f'{store} w8, {reg}zr, {reg}zr, [x6]']
                        functions[name] = prefix + instructions + post
                    public.append(name)
    return functions, public
