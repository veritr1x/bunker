"""Lift twenty bounded original FMOD nonleaf entries; never select them.

All currently selected objects remain byte-exact; these twenty entries are additive.
Real VM/JNI/owner operations are retained; their protocol/device qualification is separate.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import traceback

from elftools.elf.elffile import ELFFile

ENTRIES = {0x70b311f4,0x70b3b710,0x70b3b9cc,0x70b3bc10,0x70b3bc70,0x70b3bd4c,0x70b3bd70,0x70b3bd80,0x70b3bda8,0x70b3bdb8,0x70b3be10,0x70b3beac,0x70b3bed4,0x70b3bfa0,0x70b3c0d0,0x70b3c1e8,0x70b3c2fc,0x70b3c46c,0x70b3c590,0x70e04670}
STATE = '26ad0f8c6163e8eeae69a5cb4e0325ebf44e7f4dd61fb5b274913f09ce8c9137'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2)+'\n')


def descriptor(path):
    return {'path': str(path), 'sha256': sha(path)}


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
        parent = json.loads(Path(plan['parent_input']).read_text())
        assert len(parent['objects']) == 3578 and parent['union_trace_count'] == 456706
        header = Path(plan['trace_header']).read_text()
        old = {int(h,16) for h in re.findall(r'extern "C" Memory \*sub_([0-9a-f]+)\(', header)}
        assert len(old) == 456706 and not old & ENTRIES
        (n/'entries.txt').write_text(''.join(hex(h)+'\n' for h in sorted(ENTRIES)))
        (n/'heads.txt').write_text(''.join(hex(h)+'\n' for h in sorted(old | ENTRIES)))
        elf = ELFFile(io.BytesIO(Path(plan['original_elf']).read_bytes()))
        image = Path(plan['flat_executable']).read_bytes(); executable = []
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
             '--bytes_file', plan['flat_executable'], '--address', str(0x70000000),
             '--entry_addresses_file', n/'entries.txt', '--trace_heads_file', n/'heads.txt',
             '--ir_out', raw], 'twenty-entry-lift')
        rt = raw.read_text(); rf = check.functions(rt)
        assert set(rf) == ENTRIES and check.state(rt) == STATE
        assert not check.errors(rf), check.errors(rf)
        run([plan['poll_instrument'], raw, polled], 'instrument')
        pt = polled.read_text(); pf = check.functions(pt)
        assert set(pf) == ENTRIES and check.state(pt) == STATE and not check.errors(pf)
        cov = check.coverage(pf)
        refs = {int(h,16) for h in re.findall(r'@sub_([0-9a-f]+)\(', pt)}-ENTRIES
        assert refs <= old and refs <= {int(h,0) for h in plan['expected_external_guest_references']}, [hex(h) for h in refs]
        run([plan['compiler'], '-target', 'x86_64-w64-windows-gnu', '-O2',
             '-Wno-override-module', '-c', polled, '-o', obj], 'compile')
        symbols = subprocess.check_output([plan['nm'], '--format=posix', '--extern-only', obj], text=True)
        (b/'symbols.txt').write_text(symbols)
        defs = {int(h,16) for h in re.findall(r'^sub_([0-9a-f]+) T(?: |$)', symbols, re.M)}
        externs = {int(h,16) for h in re.findall(r'^sub_([0-9a-f]+) U(?: |$)', symbols, re.M)}
        assert defs == ENTRIES and externs <= old and externs <= {int(h,0) for h in plan['expected_external_guest_references']}
        full, disasm, tables = check.coff_projection(plan['objdump'], obj)
        assert set(full) == {hex(h) for h in ENTRIES}
        native_cov = {}
        for head, f in full.items():
            native_cov[head] = {symbol: sum(r['symbol'] == symbol for r in f['relocations'])
                               for symbol in ('__bunker_guest_poll_requested', '__bunker_guest_poll_slow')}
            assert all(count == cov[head]['total'] for count in native_cov[head].values())
        (b/'native-disassembly.txt').write_text(disasm)
        save(b/'full-native-projection.json', dict(functions=full, relocation_tables=tables))
        for path in (raw, polled, obj, n/'entries.txt', n/'heads.txt'):
            shutil.copy2(path, b/path.name)
        for path, digest in plan['input_pins'].items():
            assert sha(path) == digest, path
        assert sha(__file__) == a.builder_sha256
        result = dict(passed=True, status='ADDITIVE COMPONENT; NOT SELECTED; original callback qualification pending',
            candidate_object=descriptor(b/obj.name), raw_ir=descriptor(b/raw.name), polled_ir=descriptor(b/polled.name),
            entry_heads=[hex(h) for h in sorted(ENTRIES)], definitions=20, definition_count=20,
            parent_input=descriptor(plan['parent_input']), parent_cohort=descriptor(plan['parent_cohort']),
            all_old_objects_preserved=3578, old_head_count=456706, new_head_count=456726,
            proposed_object_count=3579, State_type_closure_sha256=STATE, State_size=1200, State_align=16,
            unsupported_heads=[], external_guest_references=[hex(h) for h in sorted(externs)],
            direct_guest_references=[hex(h) for h in sorted(refs)], all_direct_refs_closed=True,
            all_poll_coverage=cov, native_poll_relocations=native_cov,
            full_native_projection=descriptor(b/'full-native-projection.json'), symbols=descriptor(b/'symbols.txt'),
            selected_dependency_heads=[hex(h) for h in sorted(refs)], retained_modules=plan['retained_modules'],
            retained_dependency_unsupported_heads=plan['retained_dependency_unsupported_heads'],
            toolchain=plan['frozen_pair'], verified_original_executable_sections=executable,
            plan=descriptor(a.plan), builder=descriptor(__file__), input_pins=plan['input_pins'], commands=commands,
            artifacts={str(p):sha(p) for p in b.iterdir() if p.is_file()},
            limits='Complete bounded ten original nonleaf callbacks and ten helpers; no unwind FDE claimed; no old module changed. '
                   'Real VM/JNI/owner indirect calls remain and require explicit boundary qualification; no physical audio, complete Java initialization, game or frame claim.')
        save(b/'candidate.json', result)
        print('CANDIDATE', sha(b/'candidate.json'), flush=True)
    except BaseException as error:
        save(b/'failure.json', dict(passed=False, hold_reason=str(error), traceback=traceback.format_exc(),
                                   commands=commands, plan_sha256=a.plan_sha256, builder_sha256=a.builder_sha256))
        raise


if __name__ == '__main__':
    main()
