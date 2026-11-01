"""Recover bounded AArch64 relative switch tables; addresses are ELF-relative.

No data is treated as code without an indirect-branch dataflow chain, a
dominating unsigned index guard, file-backed table bytes, and case destinations
inside both executable sections and the containing symbol/FDE function.
Requires pyelftools and capstone 5.
"""
from collections import defaultdict
from dataclasses import dataclass
import re

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_REG, ARM64_OP_IMM, ARM64_OP_MEM, ARM64_SFT_LSL, ARM64_EXT_UXTW, ARM64_EXT_SXTW
from elftools.dwarf.callframe import FDE
from elftools.elf.sections import SymbolTableSection

_BR_ENCODING = re.compile(rb'[\x00\x20\x40\x60\x80\xa0\xc0\xe0][\x00-\x03]\x1f\xd6')


@dataclass(frozen=True)
class MaskedIndex:
    register: str
    source_width: int
    mask: int
    before: int


@dataclass(frozen=True)
class Table:
    address: int
    size: int
    signed: bool
    index: object
    stride: int
    load: int


@dataclass(frozen=True)
class Target:
    base: int
    table: Table
    shift: int


def _register(ins, reg):
    name = ins.reg_name(reg)
    if name in ('wzr', 'xzr'):
        return 'zero', 32 if name[0] == 'w' else 64
    if name == 'fp':
        return '29', 64
    if name == 'lr':
        return '30', 64
    if name and name[0] in 'xw' and name[1:].isdigit():
        return name[1:], 32 if name[0] == 'w' else 64
    return name, 64


class Function:
    def __init__(self, instructions, lo, hi, indirect_edges=None, reachable_only=False):
        self.lo, self.hi = lo, hi
        self.reachable_only = reachable_only
        self.ins = {i.address: i for i in instructions}
        self.pred = defaultdict(set)
        self.succ = {}
        self.cache = {}
        self.reaching_cache = {}
        self.active = set()
        for pc, ins in self.ins.items():
            name = ins.mnemonic
            conditional = name.startswith('b.') or name in ('cbz', 'cbnz', 'tbz', 'tbnz')
            edges = []
            if name == 'b' or conditional:
                edges.append(ins.operands[-1].imm)
            elif name == 'br' and indirect_edges:
                edges.extend(indirect_edges.get(pc, ()))
            if conditional or name not in ('b', 'br', 'ret', 'eret'):
                edges.append(pc + 4)
            self.succ[pc] = {a for a in edges if a in self.ins}
            for edge in self.succ[pc]:
                self.pred[edge].add(pc)
        # Dominators only for reachable instructions. Bit sets make large
        # functions needlessly expensive; immediate straight-line stretches
        # share the sparse graph's block-level dominator calculation instead.
        leaders = {lo}
        for pc, edges in self.succ.items():
            if len(edges) != 1 or self.ins[pc].mnemonic == 'b' or self.ins[pc].mnemonic.startswith('b.') or self.ins[pc].mnemonic in ('cbz', 'cbnz', 'tbz', 'tbnz'):
                leaders.update(edges)
                if pc + 4 in self.ins:
                    leaders.add(pc + 4)
        leaders.update(a for a in self.ins if len(self.pred[a]) != 1)
        self.block = {}
        current = lo
        for pc in sorted(self.ins):
            if pc in leaders:
                current = pc
            self.block[pc] = current
        bp = defaultdict(set)
        bs = defaultdict(set)
        for pc, edges in self.succ.items():
            for edge in edges:
                a, b = self.block[pc], self.block[edge]
                if a != b:
                    bp[b].add(a)
                    bs[a].add(b)
        reachable, todo = set(), [lo]
        while todo:
            b = todo.pop()
            if b in reachable:
                continue
            reachable.add(b)
            todo.extend(bs[b])
        self.dom = {b: ({lo} if b == lo else set(reachable)) for b in reachable}
        changed = True
        while changed:
            changed = False
            for b in sorted(reachable - {lo}):
                parents = [self.dom[p] for p in bp[b] if p in reachable]
                new = {b} | set.intersection(*parents)
                if new != self.dom[b]:
                    self.dom[b] = new
                    changed = True

    def dominates(self, a, b):
        return self.block.get(a) in self.dom.get(self.block.get(b), ()) and (
            self.block[a] != self.block[b] or a <= b)

    def read(self, operand, before, ins, width=None):
        reg, bits = _register(ins, operand)
        return self.resolve(reg, width or bits, before)

    def parents(self, before):
        parents = self.pred.get(before, ())
        return [pc for pc in parents if self.block[pc] in self.dom] if self.reachable_only else parents

    @staticmethod
    def writes_register(ins, reg):
        writes = {_register(ins, r)[0] for r in ins.regs_access()[1]}
        # Capstone 5 reports a spurious GPR write for these ZR-destination aliases.
        if ins.mnemonic in ('cmp', 'cmn', 'tst', 'ccmp', 'ccmn'):
            writes = {'nzcv'}
        if ins.mnemonic in ('bl', 'blr'):
            writes.update(str(r) for r in range(19))
            writes.add('30')
        return reg in writes

    def unchanged_between(self, reg, earlier, later):
        if not self.dominates(earlier, later):
            return False
        pending, visited, reached = [later], set(), False
        while pending:
            before = pending.pop()
            if before in visited:
                continue
            visited.add(before)
            for pc in self.pred.get(before, ()):
                # The first mask reads its input before its own destination
                # write, so an in-place mask must also count as a clobber.
                if self.writes_register(self.ins[pc], reg):
                    return False
                if pc == earlier:
                    reached = True
                else:
                    pending.append(pc)
        return reached

    def equivalent_index(self, lhs, rhs):
        if lhs == rhs:
            return True
        if not isinstance(lhs, MaskedIndex) or not isinstance(rhs, MaskedIndex):
            return False
        if lhs.register != rhs.register or lhs.mask != rhs.mask:
            return False
        # A W read loses bits above 31; equality with an X read is valid only
        # when the effective AND mask already removes every such bit.
        if lhs.mask >> min(lhs.source_width, rhs.source_width):
            return False
        return (self.unchanged_between(lhs.register, lhs.before, rhs.before) or
                self.unchanged_between(lhs.register, rhs.before, lhs.before))

    def unique_reaching_definition(self, reg, before):
        key = reg, before
        if key in self.reaching_cache:
            return self.reaching_cache[key]
        pending, visited, writers = [before], set(), set()
        result = None
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            # A value reaching the initial ABI input is not initialized by a
            # unique local writer. Bound exploration rather than guessing if
            # a very large function exhausts the analysis budget.
            if current == self.lo or not self.parents(current) or len(visited) > 4096:
                break
            for pc in self.parents(current):
                if self.writes_register(self.ins[pc], reg):
                    writers.add(pc)
                else:
                    pending.append(pc)
            if len(writers) > 1:
                break
        else:
            if len(writers) == 1:
                candidate = next(iter(writers))
                if self.dominates(candidate, before):
                    result = candidate
        self.reaching_cache[key] = result
        return result

    def resolve(self, reg, width, before):
        if reg == 'zero':
            return ('constant', 0)
        key = reg, width, before
        if key in self.cache:
            return self.cache[key]
        if key in self.active or len(self.active) > 96:
            return None
        self.active.add(key)
        parents = self.parents(before)
        # A backedge into the function entry must not erase the initial ABI
        # input path when joining reaching definitions.
        values = [('input', reg, width)] if before == self.lo else []
        if not parents:
            result = ('input', reg, width)
        else:
            for pc in parents:
                ins = self.ins[pc]
                values.append(self.definition(ins, reg, width) if self.writes_register(ins, reg) else self.resolve(reg, width, pc))
            result = values[0] if all(v == values[0] for v in values) else None
        if result is None:
            # A loop with no writes to this register need not destroy an
            # earlier constant table address. Re-evaluate only a unique,
            # dominating last writer, and retain only a proven constant.
            writer = self.unique_reaching_definition(reg, before)
            if writer is not None:
                value = self.definition(self.ins[writer], reg, width)
                if isinstance(value, tuple) and value[0] == 'constant':
                    result = value
        self.active.remove(key)
        self.cache[key] = result
        return result

    def definition(self, ins, reg, width):
        ops, name = ins.operands, ins.mnemonic
        if not ops or ops[0].type != ARM64_OP_REG or _register(ins, ops[0].reg)[0] != reg:
            return None
        written_width = _register(ins, ops[0].reg)[1]
        result = None
        if name in ('adr', 'adrp') and ops[1].type == ARM64_OP_IMM:
            result = ('constant', ops[1].imm)
        elif name == 'mov':
            result = ('constant', ops[1].imm) if ops[1].type == ARM64_OP_IMM else self.read(ops[1].reg, ins.address, ins)
        elif name == 'and' and len(ops) == 3 and ops[2].type == ARM64_OP_IMM:
            source, source_width = _register(ins, ops[1].reg)
            mask = ops[2].imm & ((1 << min(width, written_width)) - 1)
            result = ('constant', 0) if source == 'zero' else MaskedIndex(source, source_width, mask, ins.address)
        elif name in ('add', 'sub') and len(ops) == 3:
            lhs = self.read(ops[1].reg, ins.address, ins)
            rhs = ('constant', ops[2].imm << ops[2].shift.value) if ops[2].type == ARM64_OP_IMM else self.read(
                ops[2].reg, ins.address, ins, 32 if ops[2].ext in (ARM64_EXT_UXTW, ARM64_EXT_SXTW) else None)
            shift = ops[2].shift.value if ops[2].type == ARM64_OP_REG else 0
            if lhs and rhs and isinstance(lhs, tuple) and isinstance(rhs, tuple) and lhs[0] == rhs[0] == 'constant':
                result = ('constant', (lhs[1] + (rhs[1] << shift) * (1 if name == 'add' else -1)) & ((1 << written_width) - 1))
            elif name == 'add' and lhs and isinstance(lhs, tuple) and lhs[0] == 'constant' and isinstance(rhs, Table) and ops[2].shift.type in (0, ARM64_SFT_LSL):
                result = Target(lhs[1], rhs, shift)
            elif name == 'add' and isinstance(lhs, Table) and rhs and isinstance(rhs, tuple) and rhs[0] == 'constant' and shift == 0:
                result = Target(rhs[1], lhs, 0)
            elif lhs and rhs and isinstance(rhs, tuple) and rhs[0] == 'constant':
                result = (name, lhs, rhs[1], written_width)
        elif name in ('ldrb', 'ldrh', 'ldrsw') and ops[1].type == ARM64_OP_MEM:
            mem = ops[1].mem
            base = self.read(mem.base, ins.address, ins)
            if mem.index and base and isinstance(base, tuple) and base[0] == 'constant':
                index = self.read(mem.index, ins.address, ins, 32 if ops[1].ext in (ARM64_EXT_UXTW, ARM64_EXT_SXTW) else None)
                result = Table(base[1] + mem.disp, {'ldrb': 1, 'ldrh': 2, 'ldrsw': 4}[name], name == 'ldrsw', index,
                               1 << ops[1].shift.value, ins.address)
        if result is None:
            result = ('definition', ins.address, reg, min(width, written_width))
        elif width == 32 and written_width == 64 and not isinstance(result, MaskedIndex):
            result = ('truncate32', result)
        return result

    def bound(self, table):
        for pc, branch in sorted(self.ins.items(), reverse=True):
            if branch.mnemonic not in ('b.hi', 'b.hs', 'b.ls', 'b.lo'):
                continue
            if branch.operands[0].imm == pc + 4:
                continue  # Both outcomes take the same edge: this is no guard.
            allowed = pc + 4 if branch.mnemonic in ('b.hi', 'b.hs') else branch.operands[0].imm
            if self.pred.get(allowed) != {pc} or not self.dominates(allowed, table.load):
                continue
            compare = None
            previous = pc
            for _ in range(64):
                parents = self.pred.get(previous, ())
                if len(parents) != 1:
                    break
                previous = next(iter(parents))
                candidate = self.ins[previous]
                if candidate.mnemonic == 'cmp':
                    compare = candidate
                    break
                if candidate.update_flags or 'nzcv' in {candidate.reg_name(r) for r in candidate.regs_access()[1]} or candidate.mnemonic in ('bl', 'blr'):
                    break
            if compare is None or compare.operands[1].type != ARM64_OP_IMM:
                continue
            index = self.read(compare.operands[0].reg, compare.address, compare)
            if not self.equivalent_index(index, table.index):
                continue
            count = compare.operands[1].imm << compare.operands[1].shift.value
            count += branch.mnemonic in ('b.hi', 'b.ls')
            if 0 < count <= 65536:
                return count, pc
        return None


def _recover_table(function, ins, read, code):
    pc, lo, hi = ins.address, function.lo, function.hi
    target = function.read(ins.operands[0].reg, pc, ins)
    if not isinstance(target, Target):
        return None, 'indirect target is not a supported relative-table expression'
    if target.table.index is None:
        return None, 'table index has ambiguous reaching definitions'
    proof = function.bound(target.table)
    if proof is None:
        return None, 'no dominating unsigned index bound proven'
    if target.table.stride != target.table.size:
        return None, 'indexed load stride does not match table element size'
    count, guard = proof
    raw = read(target.table.address, count * target.table.size)
    if raw is None:
        return None, 'bounded table is outside file-backed allocated sections'
    targets = [target.base + (int.from_bytes(raw[i:i + target.table.size], 'little', signed=target.table.signed) << target.shift)
               for i in range(0, len(raw), target.table.size)]
    if not all(lo <= address < hi and code(address) for address in targets):
        return None, 'table contains a target outside the containing executable function'
    return dict(site=pc, function=lo, function_end=hi, table=target.table.address,
                count=count, entry_size=target.table.size, signed=target.table.signed,
                case_base=target.base, shift=target.shift, guard=guard, targets=targets), None


def recover(elf):
    """Return entries/tables/unresolved, using unrebased ELF virtual addresses."""
    if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
        raise ValueError('Jump-table recovery requires a little-endian AArch64 ELF64 image')
    sections = [s for s in elf.iter_sections() if s['sh_size'] and s['sh_type'] != 'SHT_NOBITS']
    executable = [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in sections if s['sh_flags'] & 4]
    section_bytes = {}

    def code(address):
        return address % 4 == 0 and any(lo <= address < hi for lo, hi in executable)

    def read(address, size):
        for section in sections:
            offset = address - section['sh_addr']
            if section['sh_flags'] & 2 and 0 <= offset <= section['sh_size'] - size:
                key = section['sh_offset'], section['sh_addr'], section['sh_size']
                if key not in section_bytes:
                    section_bytes[key] = section.data()
                return section_bytes[key][offset:offset + size]
        return None

    bounds = set()
    for section in elf.iter_sections():
        if isinstance(section, SymbolTableSection):
            for symbol in section.iter_symbols():
                lo, size = symbol['st_value'], symbol['st_size']
                if symbol['st_info']['type'] == 'STT_FUNC' and size and code(lo):
                    bounds.add((lo, lo + size))
    if elf.get_section_by_name('.eh_frame'):
        for record in elf.get_dwarf_info().EH_CFI_entries():
            if isinstance(record, FDE) and code(record['initial_location']):
                bounds.add((record['initial_location'], record['initial_location'] + record['address_range']))
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    tables, unresolved, entries, seen = [], [], set(), set()
    for lo, hi in sorted(bounds, key=lambda pair: (pair[1] - pair[0], pair[0])):
        data = read(lo, hi - lo)
        if data is None:
            continue
        # BR xN has a fixed encoding; most functions contain no candidate.
        if not any(match.start() % 4 == 0 for match in _BR_ENCODING.finditer(data)):
            continue
        instructions = list(decoder.disasm(data, lo))
        function = Function(instructions, lo, hi)
        branches = [ins for ins in instructions if ins.mnemonic == 'br']
        for pc, ins in function.ins.items():
            if ins.mnemonic != 'br' or pc in seen:
                continue
            seen.add(pc)
            record, reason = _recover_table(function, ins, read, code)
            if record is None and len(branches) == 1:
                # A loop may have case roots disconnected until its sole BR
                # is known. Derive a candidate from entry-reachable paths,
                # then close the CFG with exactly those bounded table edges.
                # No seed is emitted unless the full proof remains identical
                # with every candidate case path included.
                trial = Function(instructions, lo, hi, reachable_only=True)
                candidate, _ = _recover_table(trial, ins, read, code)
                if candidate and all(address in function.ins for address in candidate['targets']):
                    closed = Function(instructions, lo, hi, indirect_edges={pc: candidate['targets']})
                    verified, _ = _recover_table(closed, ins, read, code)
                    if verified == candidate:
                        record, reason = verified, None
                        record['closed_cfg'] = True
            if record:
                entries.update(record['targets'])
                tables.append(record)
            if reason:
                unresolved.append(dict(site=pc, function=lo, reason=reason))
    # A stripped thunk/assembly fragment may lack both symbols and unwind
    # bounds. Surface its BR without inventing a containing function or seeds.
    for lo, hi in executable:
        data = read(lo, hi - lo)
        if data is None:
            continue
        for match in _BR_ENCODING.finditer(data):
            pc = lo + match.start()
            if pc % 4 == 0 and pc not in seen:
                unresolved.append(dict(site=pc, function=None, reason='no containing symbol/FDE function bound'))
    return dict(entries=sorted(entries), tables=sorted(tables, key=lambda item: item['site']),
                unresolved=sorted(unresolved, key=lambda item: item['site']))
