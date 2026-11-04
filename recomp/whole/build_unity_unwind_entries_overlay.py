"""Append only 27 original IL2CPP unwind table destinations; never select them.

All existing objects remain exact. Two inherited LDURSH decoder omissions stay
fail-closed; this does not add ISA semantics or qualify the complete unwinder.
"""
import argparse
import collections
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import traceback

from elftools.elf.elffile import ELFFile

ENTRIES = {0x82625c50, 0x82625c58, 0x82625c60, 0x82625c68,
           0x82625cd0, 0x82625cd8, 0x82625ce0, 0x82625ce8,
           0x82625cf4, 0x82625cfc, 0x82625d04, 0x82625d0c,
           0x82625d14, 0x82625d1c, 0x82625d24, 0x82625d2c,
           0x82625d38, 0x82625d44, 0x82625d50, 0x82625d5c,
           0x82625d6c, 0x82625dac, 0x82625f08, 0x82625f14,
           0x82625f48, 0x82625f78, 0x82625f84}
BASE = 0x80000000
ERROR_PCS = {0x82625a9c, 0x82625d7c}
STATE = '26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2)+'\n')


def descriptor(path):
    return {'path': str(path), 'sha256': sha(path)}


def error_projection(head, body):
    """Interpret only Remill's local PC bookkeeping, never guest registers.

    Both unknown branch outcomes are visited. Branch aliases through the local
    BRANCH_TAKEN byte retain their condition identity, so each CFG edge obtains
    its genuine NEXT_PC. No guest instruction or error path is removed.
    """
    blocks = {'entry': []}; label = 'entry'
    for line in body.splitlines()[1:-1]:
        m = re.match(r'^([-A-Za-z$._0-9]+):', line)
        if m:
            label = m[1]; blocks[label] = []
        else:
            blocks[label].append(line.strip())
    aliases = {'%PC': 'PC', '%NEXT_PC': 'NEXT_PC', '%RETURN_PC': 'RETURN_PC',
               '%BRANCH_TAKEN': 'BRANCH_TAKEN'}
    for line in body.splitlines():
        m = re.match(r'\s*(%[-A-Za-z$._0-9]+) = getelementptr .*ptr %state,.*i32 3, i32 65(?:,|$)', line)
        if m:
            aliases[m[1]] = 'PC'
    initial = {'%program_counter': head}
    todo = [('entry', {}, initial)]; visited = {}; errors = []; reached = set()

    def resolve(value, condition, choice):
        if isinstance(value, tuple) and value[0] == 'select':
            _, c, yes, no = value
            if c == condition:
                return resolve(yes if choice else no, condition, choice)
        return value

    while todo:
        label, mem, values = todo.pop()
        # At an original instruction block the same NEXT_PC must be reached on
        # every path; a disagreement is a proof failure, never a dropped edge.
        key = (mem.get('NEXT_PC'), mem.get('RETURN_PC'))
        if label in visited:
            assert visited[label][0] == key[0], (hex(head), label, visited[label], key)
            continue
        visited[label] = key; reached.add(label)
        def value(token):
            token = token.strip()
            if re.fullmatch(r'-?\d+', token):
                return int(token) & ((1 << 64)-1)
            if token in ('true', 'false'):
                return int(token == 'true')
            return values.get(token)
        for line in blocks[label]:
            if not line or line.startswith(';'):
                continue
            m = re.match(r'(%[-A-Za-z$._0-9]+) = (.*)', line)
            if m:
                name, op = m.groups(); result = None
                x = re.match(r'load i(?:8|64), ptr (%[-A-Za-z$._0-9]+)', op)
                if x and x[1] in aliases:
                    result = mem.get(aliases[x[1]])
                x = re.match(r'(add|sub)(?: [a-z]+)* i64 ([^,]+), ([^,]+)$', op)
                if x:
                    left, right = value(x[2]), value(x[3])
                    if isinstance(left, int) and isinstance(right, int):
                        result = (left+right if x[1] == 'add' else left-right) & ((1 << 64)-1)
                x = re.match(r'select i1 ([^,]+), i64 ([^,]+), i64 ([^,]+)$', op)
                if x:
                    c = value(x[1]); yes, no = value(x[2]), value(x[3])
                    result = yes if c == 1 else no if c == 0 else ('select', c or ('bool', x[1]), yes, no)
                x = re.match(r'zext i1 (%[-A-Za-z$._0-9]+) to i8$', op)
                if x:
                    result = value(x[1]) or ('bool', x[1])
                x = re.match(r'icmp (eq|ne) i8 ([^,]+), ([01])$', op)
                if x:
                    v = value(x[2]); literal = int(x[3])
                    if isinstance(v, tuple) and v[0] == 'bool':
                        assert (x[1], literal) in (('eq', 1), ('ne', 0))
                        result = v
                    elif isinstance(v, int):
                        result = int((v == literal) == (x[1] == 'eq'))
                if 'call' in op and re.search(r'@__remill_compare_\w+\(', op):
                    result = ('bool', name)
                if result is not None:
                    values[name] = result
            m = re.match(r'store i(?:8|64) ([^,]+), ptr (%[-A-Za-z$._0-9]+)', line)
            if m and m[2] in aliases:
                mem[aliases[m[2]]] = value(m[1])
            if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(', line):
                m = re.search(r'@__remill_error\(ptr [^,]+, i64 ([^,]+), ptr ', line)
                assert m is not None, (hex(head), line)
                pc = value(m[1]); assert pc in ERROR_PCS, (hex(head), label, pc, line)
                assert any('store i32 32, ptr %state' in x for x in blocks[label])
                errors.append(hex(pc))
            m = re.match(r'br i1 ([^,]+), label %([^,]+), label %(.+)', line)
            if m:
                condition = value(m[1]) or ('bool', m[1])
                for choice, target in ((True, m[2]), (False, m[3])):
                    mm = {k:resolve(v, condition, choice) for k,v in mem.items()}
                    vv = {k:resolve(v, condition, choice) for k,v in values.items()}
                    todo.append((target, mm, vv))
            m = re.match(r'br label %(.+)', line)
            if m:
                todo.append((m[1], dict(mem), dict(values)))
    expected = len(re.findall(r'call[^\n]*@__remill_(?:error|missing_block)\(', body))
    assert len(errors) == expected, (hex(head), errors, expected, set(blocks)-reached)
    return sorted(set(errors))


def optimized_polls(head, body, expected):
    """Account for real O2 slow-path tail merging, including every site ID."""
    definitions = dict(re.findall(r'^\s*(%[-A-Za-z$._0-9]+) = (.*)$', body, re.M))
    def sites(token, seen=()):
        token = token.strip()
        if token.isdecimal():
            return [int(token)]
        assert token not in seen, (hex(head), token, seen)
        expression = definitions[token]
        assert expression.startswith('phi i64 '), (hex(head), token, expression)
        inputs = re.findall(r'\[ ([^,]+), %[^\]]+\]', expression)
        assert inputs
        return [v for item in inputs for v in sites(item, seen+(token,))]
    calls = []
    for line in body.splitlines():
        if 'call' not in line or '@__bunker_guest_poll_slow(' not in line:
            continue
        m = re.search(r'@__bunker_guest_poll_slow\(ptr ([^,]+), i64 (\d+), i64 ([^,]+), i64 ([^)]+)\)', line)
        assert m and m[1].split()[-1] == '%state' and int(m[2]) == head, (hex(head), line)
        ids = sites(m[3]); assert ids
        assert (m[4] == '%program_counter' if ids == [0] else m[4] == '0')
        calls.append(dict(site_ids=ids, pc_argument=m[4], state_pointer='%state'))
    counts = collections.Counter(v for call in calls for v in call['site_ids'])
    assert counts == collections.Counter(range(expected)), (hex(head), counts, expected)
    requests = len(re.findall(r'call i32 @__bunker_guest_poll_requested\(', body))
    assert requests == expected
    return dict(request_calls=requests, slow_calls=len(calls), slow_call_sites=calls,
                all_original_site_ids_exactly_once=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--plan-sha256', required=True)
    ap.add_argument('--builder-sha256', required=True)
    a = ap.parse_args()
    assert sha(__file__) == a.builder_sha256
    assert sha(a.plan) == a.plan_sha256
    plan = json.loads(Path(a.plan).read_text())
    assert plan['entry_heads'] == [hex(h) for h in sorted(ENTRIES)]
    for path, digest in plan['input_pins'].items():
        assert sha(path) == digest, path
    b = Path(plan['out']); n = Path(plan['native_out'])
    assert not b.exists() and not n.exists()
    b.mkdir(); n.mkdir()
    shutil.copy2(__file__, b/'executed-builder.py')
    shutil.copy2(a.plan, b/'plan.json')
    commands = {}
    try:
        spec = importlib.util.spec_from_file_location('coff_checks', plan['coff_helper'])
        check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)
        retained = check.functions(Path(plan['retained_modules'][0]['polled_ir']['path']).read_text())
        old_error_projection = error_projection(0x82625840, retained[0x82625840])
        assert old_error_projection == sorted(map(hex, ERROR_PCS))
        parent = json.loads(Path(plan['parent_input']).read_text())
        assert len(parent['objects']) == 3578 and parent['union_trace_count'] == 456706
        for obj0 in parent['objects']:
            assert sha(obj0['path']) == obj0['sha256'], obj0['path']
        header = Path(plan['trace_header']).read_text()
        old = {int(h,16) for h in re.findall(r'extern "C" Memory \*sub_([0-9a-f]+)\(', header)}
        assert len(old) == 456706 and not old & ENTRIES
        audit = json.loads(Path(plan['original_audit']['path']).read_text())
        assert sha(plan['original_audit']['path']) == plan['original_audit']['sha256']
        assert audit['passed'] is True
        for group in ('inputs', 'evidence', 'selected_objects'):
            for path, digest in audit[group].items():
                assert sha(path) == digest, path
        tables = json.loads(Path(plan['original_tables']).read_text())
        proposal = json.loads(Path(plan['head_proposal']).read_text())
        assert proposal['heads'] == [hex(h) for h in sorted(ENTRIES)]
        (n/'entries.txt').write_text(''.join(hex(h)+'\n' for h in sorted(ENTRIES)))
        (n/'heads.txt').write_text(''.join(hex(h)+'\n' for h in sorted(old | ENTRIES)))
        elf = ELFFile(io.BytesIO(Path(plan['original_elf']).read_bytes()))
        image = Path(plan['flat_executable']).read_bytes(); executable = []
        loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        image_start = min(s['p_vaddr'] for s in loads if s['p_flags'] & 1)
        assert image_start == 0
        def original_bytes(va, size):
            offset = va - BASE
            seg = next(s for s in loads if s['p_vaddr'] <= offset and
                       offset + size <= s['p_vaddr'] + s['p_filesz'])
            start = offset-seg['p_vaddr']
            return seg.data()[start:start+size]
        absent = set()
        for table in tables:
            data = original_bytes(int(table['table'], 0),
                                  table['count']*table['signed_element_bytes'])
            assert data.hex() == table['table_bytes']
            fmt = {1:'b', 2:'h'}[table['signed_element_bytes']]
            targets = [int(table['target_base'],0)+table['target_stride']*x
                       for x in struct.unpack('<'+fmt*table['count'], data)]
            assert list(map(hex, targets)) == table['targets']
            assert {hex(h) for h in set(targets)-old} == set(table['absent_targets'])
            absent.update(set(targets)-old)
        assert absent == ENTRIES and len(tables) == 6
        for pc in (0x82625a98, 0x82625d78):
            assert original_bytes(pc, 4).hex() == '80108078'
        for section in elf.iter_sections():
            if section['sh_flags'] & 6 == 6 and section['sh_type'] != 'SHT_NOBITS':
                offset = section['sh_addr']; data = section.data()
                assert image[offset:offset+len(data)] == data
                executable.append(dict(section=section.name, offset=offset, bytes=len(data),
                                       sha256=hashlib.sha256(data).hexdigest()))
        assert executable
        tool = Path(plan['toolchain'])

        def run(cmd, label):
            commands[label] = list(map(str, cmd))
            print('STAGE', label, flush=True)
            with (b/(label+'.log')).open('w') as out:
                subprocess.run(commands[label], stdout=out, stderr=subprocess.STDOUT, check=True)

        raw = n/'candidate-unpolled.ll'; polled = n/'candidate-polled.ll'
        obj = n/'candidate.polled.o'
        run([tool/'remill-lift', '--arch', 'aarch64', '--os', 'linux', '--semantics_dir', tool,
             '--bytes_file', plan['flat_executable'], '--address', str(BASE),
             '--entry_addresses_file', n/'entries.txt', '--trace_heads_file', n/'heads.txt',
             '--ir_out', raw], 'twenty-seven-entry-lift')
        rt = raw.read_text(); rf = check.functions(rt)
        assert set(rf) == ENTRIES and check.state(rt) == STATE
        inherited_errors = {}
        for head, body in rf.items():
            pcs = error_projection(head, body)
            if pcs:
                inherited_errors[hex(head)] = pcs
        save(b/'inherited-error-projection.json', inherited_errors)
        assert set(check.errors(rf)) == set(inherited_errors)
        run([plan['poll_instrument'], raw, polled], 'instrument')
        pt = polled.read_text(); pf = check.functions(pt)
        assert set(pf) == ENTRIES and check.state(pt) == STATE
        assert check.errors(pf) == check.errors(rf)
        cov = check.coverage(pf)
        refs = {int(h,16) for h in re.findall(r'@sub_([0-9a-f]+)\(', pt)}-ENTRIES
        assert refs <= old, [hex(h) for h in refs-old]
        optimized = n/'candidate-optimized.ll'
        run([plan['compiler'], '-target', 'x86_64-w64-windows-gnu', '-O2',
             '-Wno-override-module', '-emit-llvm', '-S', polled, '-o', optimized], 'optimized-poll-proof')
        of = check.functions(optimized.read_text()); assert set(of) == ENTRIES
        opt_cov = {hex(h): optimized_polls(h, body, cov[hex(h)]['total']) for h,body in of.items()}
        save(b/'optimized-poll-projection.json', opt_cov)
        run([plan['compiler'], '-target', 'x86_64-w64-windows-gnu', '-O2',
             '-Wno-override-module', '-c', polled, '-o', obj], 'compile')
        symbols = subprocess.check_output([plan['nm'], '--format=posix', '--extern-only', obj], text=True)
        (b/'symbols.txt').write_text(symbols)
        defs = {int(h,16) for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)', symbols, re.M)}
        externs = {int(h,16) for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)', symbols, re.M)}
        assert defs == ENTRIES and externs <= old
        full, disasm, tables = check.coff_projection(plan['objdump'], obj)
        assert set(full) == {hex(h) for h in ENTRIES}
        native_cov = {}
        for head, f in full.items():
            native_cov[head] = {symbol: sum(r['symbol'] == symbol for r in f['relocations'])
                               for symbol in ('__bunker_guest_poll_requested', '__bunker_guest_poll_slow')}
            assert native_cov[head]['__bunker_guest_poll_requested'] == opt_cov[head]['request_calls']
            assert native_cov[head]['__bunker_guest_poll_slow'] == opt_cov[head]['slow_calls']
        (b/'native-disassembly.txt').write_text(disasm)
        save(b/'full-native-projection.json', dict(functions=full, relocation_tables=tables))
        for path in (raw, polled, optimized, obj, n/'entries.txt', n/'heads.txt'):
            shutil.copy2(path, b/path.name)
        for path, digest in plan['input_pins'].items():
            assert sha(path) == digest, path
        for obj0 in parent['objects']:
            assert sha(obj0['path']) == obj0['sha256'], obj0['path']
        assert sha(__file__) == a.builder_sha256
        proof = dict(passed=True, scope='Append-only table entry translation, no ISA or existing object/source repair',
            original_audit=plan['original_audit'], original_tables=descriptor(plan['original_tables']),
            head_proposal=descriptor(plan['head_proposal']),
            entry_heads=[hex(h) for h in sorted(ENTRIES)],
            inherited_unsupported_instruction_bytes='80108078',
            inherited_unsupported_instruction_pcs=['0x82625a98','0x82625d78'],
            inherited_error_advanced_pcs=sorted(map(hex, ERROR_PCS)),
            actual_new_unsupported_heads=check.errors(pf), inherited_error_projection=inherited_errors,
            retained_original_helper_error_projection=old_error_projection,
            diagnostic_projection=descriptor(b/'inherited-error-projection.json'),
            production_raw_ir_unmodified=descriptor(raw), production_polled_ir=descriptor(polled),
            exact_old_selected_objects=[dict(path=o['path'],sha256=o['sha256']) for o in parent['objects']],
            old_selected_objects_verified_before_and_after=True,
            old_object_count=3578, no_existing_source_or_IR_rewrite=True,
            retained_modules=plan['retained_modules'], toolchain=plan['frozen_pair'],
            builder=descriptor(__file__), plan=descriptor(a.plan), input_pins=plan['input_pins'],
            limits='Inherited LDURSH decoder omissions remain fail-closed. No complete interpreter, scheduler, GC delivery or frame claim.')
        save(b/'source-proof.json', proof)
        result = dict(passed=True, status='ADDITIVE COMPONENT; NOT SELECTED; original table-family qualification pending',
            candidate_object=descriptor(b/obj.name), raw_ir=descriptor(b/raw.name), polled_ir=descriptor(b/polled.name),
            entry_heads=[hex(h) for h in sorted(ENTRIES)], definitions=27, definition_count=27,
            parent_input=descriptor(plan['parent_input']), parent_cohort=descriptor(plan['parent_cohort']),
            all_old_objects_preserved=3578, old_head_count=456706, new_head_count=456733,
            proposed_object_count=3579, added_object_index=3578,
            State_type_closure_sha256=STATE, State_size=1200, State_align=16,
            unsupported_heads=check.errors(pf), inherited_error_projection=inherited_errors,
            added_unsupported_heads=check.errors(pf),
            original_error_paths_preserved=True, new_error_instruction_PCs=[],
            inherited_error_sites=[dict(instruction_PC=hex(pc-4), advanced_PC=hex(pc),
                                        instruction_bytes='80108078') for pc in sorted(ERROR_PCS)],
            per_definition_inherited_error_sites={head:[dict(instruction_PC=hex(int(pc,0)-4),
                advanced_PC=pc, instruction_bytes='80108078') for pc in pcs]
                for head,pcs in inherited_errors.items()},
            source_proof=descriptor(b/'source-proof.json'), original_tables=tables,
            external_guest_references=[hex(h) for h in sorted(externs)],
            direct_guest_references=[hex(h) for h in sorted(refs)], all_direct_refs_closed=True,
            all_poll_coverage=cov, native_poll_relocations=native_cov,
            full_native_projection=descriptor(b/'full-native-projection.json'), symbols=descriptor(b/'symbols.txt'),
            selected_dependency_heads=[hex(h) for h in sorted(refs)], retained_modules=plan['retained_modules'],
            retained_dependency_unsupported_heads=['0x82625840'],
            toolchain=plan['frozen_pair'], verified_original_executable_sections=executable,
            optimized_ir=descriptor(b/optimized.name), optimized_poll_projection=opt_cov,
            optimized_poll_proof=descriptor(b/'optimized-poll-projection.json'),
            plan=descriptor(a.plan), builder=descriptor(__file__), input_pins=plan['input_pins'], commands=commands,
            artifacts={str(p):sha(p) for p in b.iterdir() if p.is_file()},
            limits='Original table destinations and complete original suffixes only; all old objects preserved. '
                   'Two old LDURSH decoder omissions remain fail-closed; no complete unwinder or frame claim.')
        save(b/'candidate.json', result)
        print('CANDIDATE', sha(b/'candidate.json'), flush=True)
    except BaseException as error:
        save(b/'failure.json', dict(passed=False, hold_reason=str(error), traceback=traceback.format_exc(),
                                   commands=commands, plan_sha256=a.plan_sha256, builder_sha256=a.builder_sha256))
        raise


if __name__ == '__main__':
    main()
