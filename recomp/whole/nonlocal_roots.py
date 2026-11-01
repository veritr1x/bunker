"""Prove AArch64 setjmp import calls and recover their post-call trace roots.

All returned addresses are unrebased ELF virtual addresses. Only direct BL
through a complete relocated-GOT/PLT proof is accepted. A root makes code
available to a future dispatcher; this module implements no nonlocal transfer.
"""
import array
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_MEM, ARM64_OP_REG
from elftools.elf.relocation import RelocationSection
from callback_roots import _constant_step, _reg

_APIS = frozenset(('setjmp', '_setjmp', 'sigsetjmp'))


def recover(elf):
    """Return entries, continuations, unresolved, and conservative scan counts.

    BLR records are deliberately unattributed: an arbitrary indirect call is
    not evidence that its target is a setjmp import. Tail B to a proved import
    is identified but has no local post-call continuation to seed.
    """
    if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
        raise ValueError('Nonlocal continuation recovery requires little-endian AArch64 ELF64')
    allocated = [s for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
    code = [(s, s.data()) for s in allocated
            if s['sh_flags'] & 4 and s['sh_type'] != 'SHT_NOBITS']

    def contains(sections, address, size):
        return any(s['sh_addr'] <= address and size <= s['sh_addr'] + s['sh_size'] - address
                   for s in sections)

    def executable(address):
        return address % 4 == 0 and contains([s for s, _ in code], address, 4)

    got, duplicate, seen = {}, set(), set()
    imported = set()
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection):
            continue
        symbols = elf.get_section(section['sh_link'])
        for relocation in section.iter_relocations():
            if relocation['r_info_type'] not in (1025, 1026) or not relocation['r_info_sym']:
                continue
            symbol = symbols.get_symbol(relocation['r_info_sym'])
            if not symbol.name:
                continue
            undefined = symbol['st_shndx'] == 'SHN_UNDEF'
            if undefined:
                imported.add(symbol.name)
            address = relocation['r_offset']
            if address in seen:
                duplicate.add(address)
            seen.add(address)
            # A nonzero addend is symbol+offset, not the actual imported entry.
            if (symbol['st_info']['type'] not in ('STT_FUNC', 'STT_NOTYPE') or address % 8 or
                    not contains(allocated, address, 8) or
                    relocation.is_RELA() and relocation['r_addend'] != 0):
                continue
            got[address] = dict(api=symbol.name, undefined=undefined, got=address,
                                relocation_type=relocation['r_info_type'],
                                symbol_type=symbol['st_info']['type'])
    for address in duplicate:
        got.pop(address, None)
    summary = dict(relevant_imports=sorted(_APIS & imported), proved_stub_entries=0,
                   direct_calls=0, rejected_tail_calls=0, unattributed_indirect_calls=0,
                   unproved_plt_calls=0, invalid_continuations=0)
    result = dict(entries=[], continuations=[], unresolved=[], summary=summary)
    if not _APIS.intersection(imported):
        return result
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    plt, plt_sections = {}, []
    for section, data in code:
        if not (section.name.startswith('.plt') or section.name == '.iplt'):
            continue
        plt_sections.append(section)
        # No fixed PLT stride. BTI/padding and each complete ADRP-led sequence
        # are independently decoded, and accepted only when reached by a call.
        for offset in range(0, len(data), 4):
            start = section['sh_addr'] + offset
            values, proof, instructions = {}, None, []
            for ins in decoder.disasm(data[offset:offset + 32], start):
                instructions.append(dict(site=ins.address, instruction=f'{ins.mnemonic} {ins.op_str}'))
                ops = ins.operands
                if ins.mnemonic == 'br':
                    if len(ops) == 1 and ops[0].type == ARM64_OP_REG:
                        target = values.get(_reg(ins, ops[0].reg)[0])
                        if target and isinstance(target[0], dict):
                            proof = target[0]
                    break
                if ins.mnemonic in ('bti', 'nop'):
                    continue
                if ins.mnemonic == 'ldr':
                    if (len(ops) != 2 or ops[0].type != ARM64_OP_REG or
                            _reg(ins, ops[0].reg)[1] != 64 or ops[1].type != ARM64_OP_MEM or
                            ops[1].mem.index or ins.writeback):
                        break
                    base = values.get(_reg(ins, ops[1].mem.base)[0])
                    address = (base[0] + ops[1].mem.disp
                               if base and isinstance(base[0], int) and base[2] == 1 else None)
                    if address not in got:
                        break
                    _constant_step(ins, values)
                    values[_reg(ins, ops[0].reg)[0]] = got[address], [], None
                elif ins.mnemonic in ('adrp', 'adr', 'add', 'mov'):
                    _constant_step(ins, values)
                else:
                    # Do not scan across unknown effects, authenticated
                    # branches, resolver calls, or an arbitrary code fragment.
                    break
            if proof:
                plt[start] = dict(**proof, plt=start, stub_instructions=instructions)
    summary['proved_stub_entries'] = sum(p['undefined'] and p['api'] in _APIS for p in plt.values())
    entries, continuations, unresolved = set(), [], []
    for section, data in code:
        words = array.array('I')
        words.frombytes(data[:len(data) // 4 * 4])
        if sys.byteorder != 'little':
            words.byteswap()
        for index, word in enumerate(words):
            pc = section['sh_addr'] + index * 4
            if word & 0xfffffc1f == 0xd63f0000:  # BLR Xn: never guessed.
                summary['unattributed_indirect_calls'] += 1
                unresolved.append(dict(site=pc, api=None, reason='indirect BLR import ownership is unproved',
                                       proof=dict(kind='BLR', register=(word >> 5) & 31)))
                continue
            if word >> 26 not in (5, 37):  # B / BL.
                continue
            delta = word & 0x3ffffff
            if delta & 0x2000000:
                delta -= 0x4000000
            target = pc + delta * 4
            proof = plt.get(target)
            if not proof:
                if word >> 26 == 37 and contains(plt_sections, target, 4):
                    summary['unproved_plt_calls'] += 1
                    unresolved.append(dict(site=pc, api=None, reason='PLT target has no complete relocated import proof',
                                           proof=dict(kind='BL', plt=target)))
                continue
            if not proof['undefined'] or proof['api'] not in _APIS:
                continue
            if word >> 26 == 5:
                summary['rejected_tail_calls'] += 1
                unresolved.append(dict(site=pc, api=proof['api'], reason='tail B has no local post-call continuation',
                                       proof=dict(kind='B', **proof)))
                continue
            entry = pc + 4
            if not executable(entry):
                summary['invalid_continuations'] += 1
                unresolved.append(dict(site=pc, api=proof['api'], reason='post-call PC is not a complete executable instruction',
                                       proof=dict(kind='BL', **proof)))
                continue
            summary['direct_calls'] += 1
            entries.add(entry)
            continuations.append(dict(site=pc, api=proof['api'], entry=entry, proof=dict(kind='BL', **proof)))
    result.update(entries=sorted(entries), continuations=sorted(continuations, key=lambda c: c['site']),
                  unresolved=sorted(unresolved, key=lambda c: c['site']))
    return result
