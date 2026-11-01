"""Recover constant AArch64 __cxa_atexit/atexit callback roots.

Addresses are unrebased ELF virtual addresses. Only local, bounded constant
definitions are accepted: a direct control-flow join, an intervening call or
an unsupported writer loses the value. This deliberately leaves cross-block,
indirect-call, memory-loaded and dynamically computed callbacks unresolved.
PLT identification follows real undefined-symbol GOT relocations and decoded
ADRP/LDR/BR instructions, rather than assuming a PLT entry size or ordering.
"""
import array
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG, ARM64_SFT_LSL
from elftools.elf.relocation import RelocationSection

_APIS = {'__cxa_atexit', 'atexit'}
_WINDOW = 96  # Instructions; an exhausted window is an unknown input boundary.


def _reg(ins, identifier):
    name = ins.reg_name(identifier)
    if name in ('xzr', 'wzr'):
        return 'zero', 32 if name[0] == 'w' else 64
    if name == 'fp':
        return '29', 64
    if name == 'lr':
        return '30', 64
    if name.startswith(('x', 'w')) and name[1:].isdigit():
        return name[1:], 32 if name[0] == 'w' else 64
    return name, 64


def _control(ins):
    return ins.mnemonic in ('b', 'bl', 'blr', 'br', 'ret', 'eret', 'cbz', 'cbnz', 'tbz', 'tbnz',
                            'svc', 'hvc', 'smc', 'brk', 'hlt', 'retaa', 'retab') or ins.mnemonic.startswith('b.')


def _constant_step(ins, values):
    """Values are (ELF number, instruction proof, load-base coefficient).

    ADR/ADRP produce Base+RVA; numeric immediates have coefficient zero.
    Truncating/bit-patching an image-relative address destroys its proof.
    """
    ops, name = ins.operands, ins.mnemonic
    previous = values.copy()
    writes = {_reg(ins, r)[0] for r in ins.regs_access()[1]}
    for register in writes:
        values.pop(register, None)
    if not ops or ops[0].type != ARM64_OP_REG:
        return
    dst, width = _reg(ins, ops[0].reg)
    if dst not in writes or dst == 'zero':
        return

    def read(operand):
        if operand.shift.type not in (0, ARM64_SFT_LSL):
            return None
        if operand.type == ARM64_OP_IMM:
            return operand.imm << operand.shift.value, [], 0
        if operand.type == ARM64_OP_REG:
            key, bits = _reg(ins, operand.reg)
            value = (0, [], 0) if key == 'zero' else previous.get(key)
            if value is not None and isinstance(value[0], int):
                if value[2] and (bits != 64 or operand.shift.value):
                    return None
                return (value[0] & ((1 << bits) - 1)) << operand.shift.value, value[1], value[2]
        return None

    value = None
    if name in ('adr', 'adrp') and len(ops) == 2 and ops[1].type == ARM64_OP_IMM:
        value = ops[1].imm, [], 1
    elif name in ('mov', 'movz') and len(ops) == 2:
        value = read(ops[1])
    elif name == 'movn' and len(ops) == 2:
        item = read(ops[1])
        if item is not None:
            value = ~item[0], item[1], 0
    elif name == 'movk' and len(ops) == 2 and ops[1].type == ARM64_OP_IMM and dst in previous and previous[dst][2] == 0:
        shift = ops[1].shift.value
        value = (previous[dst][0] & ~(0xffff << shift)) | (ops[1].imm << shift), previous[dst][1], 0
    elif name in ('add', 'sub', 'adds', 'subs') and len(ops) == 3 and not ops[2].ext:
        left, right = read(ops[1]), read(ops[2])
        if left is not None and right is not None:
            sign = -1 if name in ('sub', 'subs') else 1
            value = left[0] + right[0] * sign, left[1] + right[1], left[2] + right[2] * sign
    if value is not None and (width == 64 or value[2] == 0):
        values[dst] = value[0] & ((1 << width) - 1), sorted(set(value[1] + [ins.address])), value[2]


def recover(elf):
    """Return entries/registrations/unresolved for constant exit callbacks."""
    if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
        raise ValueError('Callback recovery requires a little-endian AArch64 ELF64 image')
    sections = [(s, s.data()) for s in elf.iter_sections()
                if s['sh_flags'] & 2 and s['sh_size'] and s['sh_type'] != 'SHT_NOBITS']
    code = [(s, data) for s, data in sections if s['sh_flags'] & 4]

    def executable(address):
        return address % 4 == 0 and any(s['sh_addr'] <= address < s['sh_addr'] + len(data) for s, data in code)

    got = {}
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection):
            continue
        symbols = elf.get_section(section['sh_link'])
        for relocation in section.iter_relocations():
            # R_AARCH64_GLOB_DAT / JUMP_SLOT; an arbitrary data relocation is
            # insufficient evidence that an executable stub imports a function.
            if relocation['r_info_type'] not in (1025, 1026) or not relocation['r_info_sym']:
                continue
            symbol = symbols.get_symbol(relocation['r_info_sym'])
            if symbol['st_shndx'] == 'SHN_UNDEF' and symbol.name:
                got[relocation['r_offset']] = symbol.name
    if not _APIS.intersection(got.values()):
        return dict(entries=[], registrations=[], unresolved=[])
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    plt = {}
    # Names select possible import-stub regions; every accepted entry still
    # requires a complete decoded jump-through-relocated-GOT proof.
    for section, data in code:
        if not (section.name.startswith('.plt') or section.name == '.iplt'):
            continue
        for offset in range(0, len(data), 4):
            start = section['sh_addr'] + offset
            values = {}
            for ins in decoder.disasm(data[offset:offset + 32], start):
                ops = ins.operands
                if ins.mnemonic == 'br':
                    value = values.get(_reg(ins, ops[0].reg)[0])
                    if value and isinstance(value[0], str):
                        plt[start] = dict(api=value[0], plt=start, got=value[1])
                    break
                if _control(ins):
                    break
                if (ins.mnemonic == 'ldr' and len(ops) == 2 and _reg(ins, ops[0].reg)[1] == 64 and
                        ops[1].type == ARM64_OP_MEM and not ops[1].mem.index):
                    base = values.get(_reg(ins, ops[1].mem.base)[0])
                    address = base[0] + ops[1].mem.disp if base and isinstance(base[0], int) and base[2] == 1 else None
                    _constant_step(ins, values)
                    if address in got:
                        values[_reg(ins, ops[0].reg)[0]] = got[address], address, None
                elif ins.mnemonic not in ('bti', 'nop'):
                    _constant_step(ins, values)
    # Raw branch encodings permit a cheap whole-image scan without decoding
    # millions of unrelated instructions. Every code range supplies an unknown
    # entry boundary, as do all direct branch/call targets and fallthroughs.
    incoming, candidates = set(), []
    for section, data in code:
        lo = section['sh_addr']
        incoming.add(lo)
        words = array.array('I')
        words.frombytes(data[:len(data) // 4 * 4])
        for index, word in enumerate(words):
            pc = lo + index * 4
            target = None
            if word >> 26 in (5, 37):  # B / BL
                delta = word & 0x3ffffff
                if delta & 0x2000000:
                    delta -= 0x4000000
                target = pc + delta * 4
                proof = plt.get(target)
                if proof and proof['api'] in _APIS:
                    candidates.append((pc, index * 4, section, data, proof))
            elif word & 0xff000010 == 0x54000000 or word & 0x7e000000 == 0x34000000:
                delta = (word >> 5) & 0x7ffff
                if delta & 0x40000:
                    delta -= 0x80000
                target = pc + delta * 4
            elif word & 0x7e000000 == 0x36000000:
                delta = (word >> 5) & 0x3fff
                if delta & 0x2000:
                    delta -= 0x4000
                target = pc + delta * 4
            if target is not None:
                incoming.update((target, pc + 4))
    entries, registrations, unresolved = set(), [], []
    for site, offset, section, data, import_proof in candidates:
        begin = offset
        for _ in range(_WINDOW):
            if section['sh_addr'] + begin in incoming or begin < 4:
                break
            previous = list(decoder.disasm(data[begin - 4:begin], section['sh_addr'] + begin - 4))
            if len(previous) != 1 or _control(previous[0]):
                break
            begin -= 4
        instructions = list(decoder.disasm(data[begin:offset], section['sh_addr'] + begin))
        values = {}
        for ins in instructions:
            _constant_step(ins, values)
        callback = values.get('0')
        if callback is None or callback[2] != 1 or not executable(callback[0]):
            unresolved.append(dict(site=site, api=import_proof['api'],
                reason=('callback has no bounded local constant definition' if callback is None else
                        'callback is not proven load-base-relative (numeric/ambiguous/truncated address)' if callback[2] != 1 else
                        'constant callback is not aligned executable code'),
                proof={**import_proof, 'basic_block_start': section['sh_addr'] + begin}))
            continue
        entry = callback[0]
        argument = values.get('1') if import_proof['api'] == '__cxa_atexit' else None
        dso = values.get('2') if import_proof['api'] == '__cxa_atexit' else None
        definitions = [{'site': ins.address, 'instruction': f'{ins.mnemonic} {ins.op_str}'}
                       for ins in instructions if ins.address in callback[1]]
        registrations.append(dict(site=site, api=import_proof['api'], entry=entry,
            argument=argument[0] if argument else None, dso=dso[0] if dso else None,
            proof={**import_proof, 'base_coefficient': 1,
                   'argument_base_coefficient': argument[2] if argument else None,
                   'dso_base_coefficient': dso[2] if dso else None,
                   'basic_block_start': section['sh_addr'] + begin, 'definitions': definitions}))
        entries.add(entry)
    return dict(entries=sorted(entries), registrations=sorted(registrations, key=lambda r: r['site']),
                unresolved=sorted(unresolved, key=lambda r: r['site']))
