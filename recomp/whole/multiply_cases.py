"""Integer MUL/MLA/MLS arrangements, all lane/register encodings and aliases."""


def generate():
    functions = {}
    arrangements = [('8b',8),('16b',8),('4h',16),('8h',16),('2s',32),('4s',32)]

    def fixture(instruction,dst,lhs,rhs,constants=None):
        # One initial value per physical register, including aliased operands.
        registers={lhs:0,rhs:64,dst:80}
        saved=[reg for reg in registers if 8<=reg<=15]
        stack_bytes=16*len(saved)
        prologue=([f'sub sp, sp, #{stack_bytes}']+[f'str q{reg}, [sp, #{slot*16}]'for slot,reg in enumerate(saved)])if saved else[]
        epilogue=([f'ldr q{reg}, [sp, #{slot*16}]'for slot,reg in enumerate(saved)]+[f'add sp, sp, #{stack_bytes}'])if saved else[]
        lines=['mrs x9, fpsr','mov x3, #0x9f','movk x3, #0x800, lsl #16',
               'msr fpsr, x3','cmp x2, #32']
        for reg,offset in sorted(registers.items()):
            if constants is None:
                lines.append(f'ldr q{reg}, [x1, #{offset}]')
            else:
                value=constants[{0:0,64:1,80:2}[offset]]
                lines.append(f'mov x3, #{value&65535}')
                for chunk in range(1,4):lines.append(f'movk x3, #{(value>>(chunk*16))&65535}, lsl #{chunk*16}')
                lines += ['str x3, [x0, #64]','str x3, [x0, #72]',f'ldr q{reg}, [x0, #64]']
        return prologue+lines+[instruction,f'str q{dst}, [x0]',f'str q{lhs}, [x0, #16]',f'str q{rhs}, [x0, #32]',
                      'mrs x7, fpsr','str x7, [x0, #48]',
                      'cset x3, mi','cset x4, eq','cset x5, cs','cset x6, vs',
                      'stp x3, x4, [x0, #56]','stp x5, x6, [x0, #72]',
                      'msr fpsr, x9']+epilogue+['ret']

    aliases=[('normal',2,0,1),('lhs_overlap',0,0,1),('rhs_overlap',1,0,1),
             ('same_sources',2,0,0),('all_overlap',0,0,0),('high_registers',31,30,29)]
    edges=[(0xffffffffffffffff,0xffffffffffffffff,0xffffffffffffffff),
           (0x8000000080000000,0x8000000080000000,0x7fffffff7fffffff),
           (0x0001000100010001,0xffffffffffffffff,0),
           (0x8000800080008000,0x8000800080008000,0x7fff7fff7fff7fff),
           (0,0xffffffffffffffff,0xffffffffffffffff)]
    for op in ('mul','mla','mls'):
        for arr,bits in arrangements:
            for alias,dst,lhs,rhs in aliases:
                instruction=f'{op} v{dst}.{arr}, v{lhs}.{arr}, v{rhs}.{arr}'
                name=f'{op}_{arr}_{alias}'
                functions[name]=fixture(instruction,dst,lhs,rhs)
                if alias in ('normal','all_overlap'):
                    for edge,values in enumerate(edges):functions[f'{name}_edge{edge}']=fixture(instruction,dst,lhs,rhs,values)
            if bits==8:continue
            for lane in range(128//bits):
                # Every encoded Vm field; H forms restrict Vm to V0..V15.
                for rhs in range(16 if bits==16 else 32):
                    functions[f'{op}_{arr}_lane{lane}_reg{rhs}']=fixture(
                        f'{op} v31.{arr}, v30.{arr}, v{rhs}.{arr[-1]}[{lane}]',31,30,rhs)
                for alias,dst,lhs,rhs in aliases[:5]:
                    functions[f'{op}_{arr}_lane{lane}_{alias}']=fixture(
                        f'{op} v{dst}.{arr}, v{lhs}.{arr}, v{rhs}.{arr[-1]}[{lane}]',dst,lhs,rhs)
    return functions
