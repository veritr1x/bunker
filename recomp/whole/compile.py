"""Lift an AArch64 ELF library into sharded x86_64 objects and an address table.

The original ELF remains the data image. Function pointers retain their guest
addresses; runtime.cpp dispatches those addresses to the compiled functions.
Requires pyelftools and the fork's file/multi-entry Remill lifter.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import os
import shutil
import subprocess

from elftools.dwarf.callframe import FDE
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection

PIPELINE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def inspect(path, base, recover_jumps=True, recover_callbacks=True):
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected a little-endian AArch64 ELF64 image')
        loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        segments = [s for s in loads if s['p_flags'] & 1]
        if not segments:
            raise ValueError('ELF has no executable load segments')
        start = min(s['p_vaddr'] for s in segments)
        end = max(s['p_vaddr'] + s['p_filesz'] for s in segments)
        span = max(s['p_vaddr'] + s['p_memsz'] for s in loads)
        if base < 0 or span > (1 << 64) - base:
            raise ValueError('Guest image exceeds the 64-bit address space')
        image = bytearray(end - start)
        for seg in segments:
            offset = seg['p_vaddr'] - start
            image[offset:offset + seg['p_filesz']] = seg.data()

        # Android linkers commonly place .rodata and unwind tables in the RX
        # load segment. A relocation to a string is not a function pointer.
        code_sections = [s for s in elf.iter_sections()
                         if s['sh_flags'] & 4 and s['sh_size'] and s['sh_type'] != 'SHT_NOBITS']
        ranges = [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in code_sections]
        if not ranges:
            ranges = [(s['p_vaddr'], s['p_vaddr'] + s['p_filesz']) for s in segments]
        if any(not any(s['p_vaddr'] <= lo < hi <= s['p_vaddr'] + s['p_filesz'] for s in segments)
               for lo, hi in ranges):
            raise ValueError('Executable sections lie outside file-backed executable segments')

        def executable(addr):
            return addr % 4 == 0 and any(lo <= addr < hi for lo, hi in ranges)

        entries, exports, initializers, imports = set(), {}, [], set()
        for section in elf.iter_sections():
            if isinstance(section, SymbolTableSection):
                for sym in section.iter_symbols():
                    if sym['st_shndx'] == 'SHN_UNDEF':
                        if sym.name:
                            imports.add(sym.name)
                    else:
                        if sym['st_info']['type'] == 'STT_FUNC' and executable(sym['st_value']):
                            entries.add(base + sym['st_value'])
                        if (section.name == '.dynsym' and sym.name and
                            sym['st_info']['bind'] in ('STB_GLOBAL', 'STB_WEAK') and
                            sym['st_info']['type'] not in ('STT_SECTION', 'STT_FILE')):
                            exports[sym.name] = sym['st_value'] + (0 if sym['st_shndx'] == 'SHN_ABS' else base)
        if elf.get_section_by_name('.eh_frame') is not None:
            for record in elf.get_dwarf_info().EH_CFI_entries():
                if isinstance(record, FDE) and executable(record['initial_location']):
                    entries.add(base + record['initial_location'])
        arrays = {}
        for name in ('.init_array', '.fini_array'):
            section = elf.get_section_by_name(name)
            if section:
                arrays[name] = (section, [int.from_bytes(section.data()[i:i + 8], 'little')
                                         for i in range(0, section['sh_size'], 8)])
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection):
                continue
            symbols = elf.get_section(section['sh_link'])
            for relocation in section.iter_relocations():
                symbol = symbols.get_symbol(relocation['r_info_sym']) if relocation['r_info_sym'] else None
                target = relocation.entry.get('r_addend', 0)
                if symbol is not None:
                    if symbol['st_shndx'] == 'SHN_UNDEF':
                        continue
                    target += symbol['st_value']
                if executable(target):
                    entries.add(base + target)
                for array, values in arrays.values():
                    if array['sh_addr'] <= relocation['r_offset'] < array['sh_addr'] + array['sh_size']:
                        values[(relocation['r_offset'] - array['sh_addr']) // 8] = target
        initializers = arrays.get('.init_array', (None, []))[1]
        # ModuleRegistry executes finalizers in reverse registration order.
        finalizers = list(arrays.get('.fini_array', (None, []))[1])
        dynamic = elf.get_section_by_name('.dynamic')
        if dynamic:
            for tag in dynamic.iter_tags():
                if tag.entry.d_tag == 'DT_INIT' and executable(tag['d_ptr']):
                    initializers.insert(0, tag['d_ptr'])
                elif tag.entry.d_tag == 'DT_FINI' and executable(tag['d_ptr']):
                    finalizers.insert(0, tag['d_ptr'])
        initializers = [base + addr for addr in initializers if addr and executable(addr)]
        finalizers = [base + addr for addr in finalizers if addr and executable(addr)]
        entries.update(initializers)
        entries.update(finalizers)
        jump_tables = {'entries': [], 'tables': [], 'unresolved': []}
        if recover_jumps:
            from jump_tables import recover
            jump_tables = recover(elf)
            entries.update(base + addr for addr in jump_tables['entries'] if executable(addr))
        callback_roots = {'enabled': recover_callbacks, 'entries': [], 'registrations': [], 'unresolved': []}
        if recover_callbacks:
            from callback_roots import recover
            callback_roots.update(recover(elf))
            if any(not executable(addr) for addr in callback_roots['entries']):
                raise ValueError('Callback recovery returned a non-executable or unaligned entry')
            entries.update(base + addr for addr in callback_roots['entries'])
        if not entries:
            raise ValueError('No function entries found in symbols, relocations or unwind records')
        return image, start, sorted(entries), {
            'source': str(path.resolve()), 'sha256': digest(path),
            'base': base, 'image_start': base + start, 'image_span': (span + 0xffff) & ~0xffff,
            'executable_ranges': [[base + lo, base + hi] for lo, hi in ranges],
            'exports': exports, 'imports': sorted(imports), 'initializers': initializers, 'finalizers': finalizers,
            'jump_tables': jump_tables,
            'callback_roots': callback_roots,
        }


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def freeze_toolchain(lift, semantics_dir, out):
    lift = lift.resolve()
    if semantics_dir is None:
        candidates = [lift.parent.parent.parent / 'lib/Arch/AArch64/Runtime']
        candidates += list((lift.parent.parent / 'share/remill').glob('*/semantics'))
        semantics_dir = next((p for p in candidates if (p / 'aarch64.bc').is_file()), None)
    if semantics_dir is None or not (semantics_dir / 'aarch64.bc').is_file():
        raise ValueError('Provide --semantics-dir containing aarch64.bc for a reproducible compiler snapshot')
    semantics = (semantics_dir / 'aarch64.bc').resolve()
    hashes = {'lifter': digest(lift), 'semantics': digest(semantics)}
    directory = out / '.toolchain' / (hashes['lifter'][:16] + '-' + hashes['semantics'][:16])
    directory.mkdir(parents=True, exist_ok=True)
    for source, name, expected in [(lift, 'remill-lift', hashes['lifter']), (semantics, 'aarch64.bc', hashes['semantics'])]:
        target = directory / name
        if not target.is_file() or digest(target) != expected:
            temporary = target.with_suffix(f'.new-{os.getpid()}')
            shutil.copyfile(source, temporary)
            if digest(temporary) != expected:
                temporary.unlink()
                raise RuntimeError('Compiler changed while copying its snapshot; retry after the build finishes')
            temporary.chmod(0o755 if name == 'remill-lift' else 0o644)
            temporary.replace(target)
    return directory / 'remill-lift', directory, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--base', type=lambda s: int(s, 0), default=0x10000000)
    parser.add_argument('--shard-size', type=int, default=128)
    parser.add_argument('--jobs', type=int, default=1, help='Independent lifter/compiler processes (each uses its own LLVM context)')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--target', choices=['x86_64-linux-gnu', 'x86_64-w64-windows-gnu'], default='x86_64-linux-gnu')
    parser.add_argument('--semantics-dir', type=Path, help='Directory containing aarch64.bc; native build layout is detected automatically')
    parser.add_argument('--resume', action='store_true', help='Reuse hash-verified shards built with the same input/compiler snapshot')
    parser.add_argument('--plan-only', action='store_true', help='Write the complete image/entry plan without lifting')
    parser.add_argument('--no-callback-recovery', action='store_true',
                        help='Diagnostic baseline only: omit statically proven callback entry roots')
    parser.add_argument('--allow-unsupported', action='store_true', help='Exploratory builds only: retain traces with unliftable instructions')
    parser.add_argument('--poll-instrument', type=Path,
                        help='Opt-in LLVM18 poll-instrument executable; inserts trace-entry and cycle-cut State escape barriers')
    args = parser.parse_args()
    if args.shard_size < 1 or args.jobs < 1:
        parser.error('--shard-size and --jobs must be positive')
    alignment = 65536 if args.target == 'x86_64-w64-windows-gnu' else 4096
    if args.base < 0 or args.base % alignment:
        parser.error(f'--base must be nonnegative and aligned to {alignment} bytes')
    if args.no_callback_recovery:
        image, offset, pending, manifest = inspect(args.library, args.base, recover_callbacks=False)
    else:
        image, offset, pending, manifest = inspect(args.library, args.base)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = out / 'executable.bin'
    raw.write_bytes(image)
    image = None
    manifest.update(seed_entries=list(pending), target=args.target, cooperative_polls=bool(args.poll_instrument))
    (out / 'plan.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if args.plan_only:
        print(f'{args.library.name}: {len(pending):,} seed entries, {len(manifest["initializers"])} constructors, {len(manifest["imports"])} imports')
        return
    lift, semantics_dir, hashes = freeze_toolchain(args.lift, args.semantics_dir, out)
    compiler_version = subprocess.check_output([args.cxx, '--version'], text=True)
    manifest['toolchain'] = {**hashes, 'compiler_version': compiler_version, 'pipeline': PIPELINE_HASH}
    poll_instrument = None
    if args.poll_instrument:
        poll_hash = digest(args.poll_instrument)
        poll_instrument = out / '.toolchain' / ('poll-' + poll_hash) / 'poll-instrument'
        poll_instrument.parent.mkdir(parents=True, exist_ok=True)
        if not poll_instrument.exists():
            shutil.copy2(args.poll_instrument, poll_instrument)
        if digest(poll_instrument) != poll_hash:
            raise RuntimeError('Frozen poll instrument hash mismatch')
        manifest['toolchain']['poll_instrument'] = poll_hash
    lifted, unsupported, missing, objects = set(), set(), set(), {}

    def compile_shard(job):
        index, seeds, heads_hash = job
        prefix = out / f'shard-{index:05d}'
        seed_file = prefix.with_suffix('.entries')
        seed_file.write_text(''.join(f'{addr:#x}\n' for addr in seeds))
        ir = prefix.with_suffix('.ll')
        obj = prefix.with_suffix('.o')
        cache_file = prefix.with_suffix('.cache.json')
        cache_key = {'source': manifest['sha256'], 'base': args.base, 'target': args.target,
                     'entries': seeds, 'trace_heads': heads_hash, 'toolchain': manifest['toolchain']}
        try:
            cache = json.loads(cache_file.read_text()) if args.resume and cache_file.is_file() else {}
        except (OSError, ValueError):
            cache = {}
        if not isinstance(cache, dict):
            cache = {}
        cached = (cache.get('key') == cache_key and ir.is_file() and obj.is_file() and
                  cache.get('ir') == digest(ir) and cache.get('object') == digest(obj))
        if not cached:
            with prefix.with_suffix('.log').open('w') as log:
                subprocess.run([str(lift), '--arch', 'aarch64', '--os', 'linux',
                                '--semantics_dir', str(semantics_dir), '--bytes_file', str(raw),
                                '--address', str(args.base + offset), '--entry_addresses_file', str(seed_file),
                                '--trace_heads_file', str(out / 'trace-heads.txt'),
                                '--ir_out', str(ir)], stdout=log, stderr=subprocess.STDOUT, check=True)
                if poll_instrument:
                    modified = prefix.with_suffix('.poll.ll')
                    subprocess.run([str(poll_instrument), str(ir), str(modified)], stdout=log, stderr=subprocess.STDOUT, check=True)
                    modified.replace(ir)
        text = ir.read_text()
        definitions = {int(addr, 16) for addr in re.findall(r'^define[^\n]*@sub_([0-9a-f]+)\(', text, re.M)}
        if not set(seeds) <= definitions:
            raise RuntimeError('Lifter omitted requested trace entries')
        errors = set()
        for match in re.finditer(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}', text, re.M | re.S):
            if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(', match.group()):
                errors.add(int(match.group(1), 16))
        declarations = {int(addr, 16) for addr in re.findall(r'^declare[^\n]*@sub_([0-9a-f]+)\(', text, re.M)}
        if not cached:
            subprocess.run([args.cxx, '-target', args.target, '-O2', '-Wno-override-module',
                            '-c', str(ir), '-o', str(obj)], check=True)
            cache_file.write_text(json.dumps({'key': cache_key, 'ir': digest(ir), 'object': digest(obj)}, indent=2) + '\n')
        return index, definitions, declarations, errors, str(obj), cached

    next_index = 0
    while pending:
        # Keep every known function/block boundary external. Otherwise a tail
        # branch can inline an entire call graph into each individual shard.
        heads = sorted(lifted | set(pending))
        heads_file = out / 'trace-heads.txt'
        heads_file.write_text(''.join(f'{addr:#x}\n' for addr in heads))
        heads_hash = digest(heads_file)
        jobs = [(next_index + i // args.shard_size, pending[i:i + args.shard_size], heads_hash)
                for i in range(0, len(pending), args.shard_size)]
        next_index += len(jobs)
        discovered = set()
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(compile_shard, job) for job in jobs]
            try:
                for future in as_completed(futures):
                    index, definitions, declarations, errors, obj, cached = future.result()
                    if definitions & lifted:
                        raise RuntimeError('Lifter duplicated trace definitions between shards')
                    lifted.update(definitions)
                    discovered.update(declarations)
                    unsupported.update(errors)
                    objects[index] = obj
                    print(f'{args.library.name}: shard {index}, {len(lifted):,} traces, {len(unsupported):,} unsupported'
                          + (' (cached)' if cached else ''), flush=True)
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
        pending = []
        for addr in discovered - lifted:
            if any(lo <= addr < hi for lo, hi in manifest['executable_ranges']):
                pending.append(addr)
            else:
                missing.add(addr)
        pending.sort()
    manifest.update(target=args.target, traces=sorted(lifted), objects=[objects[i] for i in sorted(objects)],
                    unsupported_traces=sorted(unsupported), unresolved_direct_targets=sorted(missing))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    lines = ['// Generated by recomp/whole/compile.py; include after runtime.h.']
    for addr in sorted(lifted):
        lines.append(f'extern "C" Memory *sub_{addr:x}(State &, addr_t, Memory *);')
    lines.append('static const recomp::Trace kTraces[] = {')
    lines.extend(f'  {{{addr:#x}, sub_{addr:x}}},' for addr in sorted(lifted))
    lines.append('};')
    lines.append('static const addr_t kInitializers[] = {')
    lines.extend(f'  {addr:#x},' for addr in manifest['initializers'])
    lines.extend(['};', ''])
    (out / 'traces.h').write_text('\n'.join(lines))
    if missing or (unsupported and not args.allow_unsupported):
        raise SystemExit(f'Incomplete library: {len(unsupported)} unsupported traces, {len(missing)} unresolved direct targets; see manifest.json')


if __name__ == '__main__':
    main()
