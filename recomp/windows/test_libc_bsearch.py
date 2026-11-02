"""Strict NDK translated-comparator bsearch, exact Android13 ARM64 reference and fences."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OWN = ('libc_bsearch_fixture.h', 'libc_bsearch_guest.c', 'libc_bsearch_guest.S',
       'libc_bsearch_test.cpp', 'libc_bsearch_ref.c', 'test_libc_bsearch.py', 'libc_bsearch_fixture.md')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def oracle(count, key, duplicate, original, zero=False):
    start, remaining, trace = 0, count, []
    found = -1
    while remaining:
        index = 0 if zero else start + remaining // 2
        value = (index // 3 if duplicate else index) * 2
        delta = (key - value) & 0xffffffff
        comparison = (delta if delta < 0x80000000 else delta - 0x100000000) if original else (-2147483648 if key < value else 2147483647 if key > value else 0)
        trace.append((index, comparison))
        if not comparison:
            found = index
            break
        if comparison > 0:
            start = index + 1
            remaining -= 1
        remaining //= 2
    return found, trace


def validate(text):
    lines = text.splitlines()
    records = []
    for line in lines:
        fields = line.split()
        if not fields or fields[0] not in ('RECORD', 'ZERO', 'NESTED'):
            continue
        records.append(line)
        if fields[0] == 'RECORD':
            kind, duplicate, count, key, size, found, calls, before, after, post, nested = map(int, fields[1:12])
            expected, trace = oracle(count, key, duplicate, kind & 1)
            assert size == (32 if duplicate else 16) and found == expected and calls == len(trace)
            assert before == 777 and after == (900 + calls if calls else 777)
            assert post == (0x31415926 if found >= 0 else 0) and nested == 0
            assert [tuple(map(int, x.split(':'))) for x in fields[12:]] == trace
        elif fields[0] == 'ZERO':
            kind, key, found, calls, after = map(int, fields[1:6])
            expected, trace = oracle(7, key, False, kind & 1, True)
            assert found == expected and calls == len(trace) and after == 900 + calls
            assert [tuple(map(int, x.split(':'))) for x in fields[6:]] == trace
        else:
            assert fields == ['NESTED', '11', '3', '1', '1']
    counts = [0, 1, 2, 3, 4, 5, 8, 16, 17, 31, 33]
    expected_count = 4 * 2 * sum(2 * n + 5 for n in counts) + 12 + 1
    assert len(records) == expected_count
    assert f'BSEARCH-RECORDS-SUCCESS {expected_count}' in lines
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--support-commit', default='56232c9')
    p.add_argument('--ndk', type=Path, default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(['git', 'rev-parse', a.support_commit], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', commit, 'recomp/windows', 'recomp/whole', 'recomp/fastaes'], cwd=ROOT)
    (out / 'support.tar').write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out / 'host', filter='data')
    source = out / 'host/recomp'
    overlays = {}
    for name in ('libc.h', 'libc.cpp', *OWN):
        overlays[name] = sha(HERE / name)
        shutil.copy2(HERE / name, source / 'windows' / name)
    source_pins = {str(f.relative_to(source)): sha(f) for f in source.rglob('*') if f.is_file()}
    tool_pins = {str(f): sha(f) for f in a.toolchain.rglob('*') if f.is_file()}
    primary_dir = HERE.parent / 'work/game15-bsearch-peer1'
    primary = primary_dir / 'bionic-bsearch.c'
    compat = primary_dir / 'netbsd-compat.h'
    assert sha(primary) == '0205e72ac3c3555e26c86c59324c29cec66ccbcb058739e6cd46840ec1000cdc'
    assert sha(compat) == '6dab3b245625802238fd5aac2a2e8f258cbda00c8a485997216d161305918be6'
    shutil.copy2(primary, out / 'bionic-bsearch.c')
    shutil.copy2(compat, out / 'netbsd-compat.h')
    original = primary_dir / '2580bd0-original.json'
    evidence = json.loads(original.read_text())
    original_bytes = bytes.fromhex(''.join(x['bytes'] for x in evidence['instructions']))
    assert original_bytes == bytes.fromhex('080040b9290040b90001094bc0035fd6')
    external = {str(f): sha(f) for f in (primary, compat, original)}
    frozen = {'passed': False, 'support_commit': commit, 'overlays': overlays,
              'support_sources': source_pins, 'tool_inputs': tool_pins,
              'primary_original_inputs': external, 'support_archive_sha256': sha(out / 'support.tar')}
    (out / 'source-pin.json').write_text(json.dumps(frozen, indent=2) + '\n')

    def run(command, name, timeout=300):
        with (out / name).open('w') as log:
            result = subprocess.run(list(map(str, command)), stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'{name}: exit{result.returncode}\n{(out/name).read_text(errors="replace")[-5000:]}')

    def wp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()

    ndk = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    for compiler in (ndk, Path('/usr/bin/clang++-18'), Path('/mnt/c/mingw64/bin/g++.exe')):
        run([compiler, '--version'], compiler.name + '-version.log')
        external[str(compiler.resolve())] = sha(compiler.resolve())
    core_objects = []
    for filename in ('libc_bsearch_guest.c', 'libc_bsearch_guest.S'):
        obj = out / (filename + '.o')
        run([ndk, '-c', '-O1', '-fPIC', '-fno-stack-protector', '-fno-builtin', '-Wall', '-Wextra', '-Werror',
             source / 'windows' / filename, '-o', obj], filename + '-build.log')
        core_objects.append(obj)
    with core_objects[1].open('rb') as stream:
        elf = ELFFile(stream)
        symbol = elf.get_section_by_name('.symtab').get_symbol_by_name('bsearch_original_comparator')[0]
        raw = elf.get_section(symbol['st_shndx']).data()[symbol['st_value']:symbol['st_value'] + symbol['st_size']]
        assert raw == original_bytes
    library = out / 'bsearch.so'
    run([ndk, '-shared', '-nostdlib', *core_objects, '-o', library], 'guest-link.log')
    bionic_obj = out / 'bionic-reference.o'
    run([ndk, '-c', '-O1', '-fno-builtin', '-include', out / 'netbsd-compat.h', out / 'bionic-bsearch.c', '-o', bionic_obj], 'bionic-reference-build.log')
    sys.path.insert(0, str(source / 'whole'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('frozen_reference', source / 'whole/test_fastaes.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    reference = out / 'arm64-reference'
    helper.build_reference('clang-18', a.reference_root, [source / 'windows/libc_bsearch_ref.c', *core_objects, bionic_obj], reference, [source / 'windows'])
    qemu = a.reference_root / 'usr/bin/qemu-aarch64-static'
    external[str(qemu)] = sha(qemu)
    run([qemu, reference], 'arm64-records.log')
    native_text = (out / 'arm64-records.log').read_text()
    assert 'BSEARCH-REFERENCE-SUCCESS empty=1' in native_text
    expected = validate(native_text)
    platforms = {}
    for windows in (False, True):
        label = 'windows' if windows else 'linux'
        build = out / label
        run([sys.executable, source / 'whole/compile.py', library, '--out', build,
             '--base', '0x5d000000', '--lift', a.toolchain / 'remill-lift', '--semantics-dir', a.toolchain,
             '--target', 'x86_64-w64-windows-gnu' if windows else 'x86_64-linux-gnu', '--cxx', 'clang++-18'], label + '-compile.log')
        manifest = json.loads((build / 'manifest.json').read_text())
        assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        path = wp if windows else str
        cc = '/mnt/c/mingw64/bin/gcc.exe' if windows else 'clang-18'
        cxx = '/mnt/c/mingw64/bin/g++.exe' if windows else 'clang++-18'
        flags = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', '-isystem', path(a.toolchain / 'include'), '-I' + path(build)]
        loader = build / 'elfload.o'
        run([cc, '-O2', '-c', path(source / 'fastaes/elfload.c'), '-o', path(loader)], label + '-loader.log')
        objects = []
        for name in ('windows/libc.cpp', 'whole/runtime.cpp', *(['windows/pthread_host.cpp'] if windows else [])):
            obj = build / (Path(name).stem + '.o')
            run([cxx, *flags, '-c', path(source / name), '-o', path(obj)], label + '-' + Path(name).stem + '-build.log')
            objects.append(obj)
        test_obj = build / 'test.o'
        run([cxx, *flags, '-Wall', '-Wextra', '-Werror', f'-DBSEARCH_LIBRARY="{path(library)}"', '-c', path(source / 'windows/libc_bsearch_test.cpp'), '-o', path(test_obj)], label + '-test-build.log')
        binary = build / ('bsearch.exe' if windows else 'bsearch')
        run([cxx, path(test_obj), *map(path, objects), path(loader), *map(path, manifest['objects']), '-latomic', '-pthread', *(['-static'] if windows else []), '-o', path(binary)], label + '-link.log')
        run([binary], label + '-records.log')
        text = (out / (label + '-records.log')).read_text()
        assert validate(text) == expected and 'BSEARCH-HOST-SUCCESS ' in text
        boundaries = {}
        for mode, message in {'span-overflow': 'array span is not representable',
                              'pointer-overflow': 'array span is not representable',
                              'zero-target': 'requires a guest comparator runner',
                              'missing-runner': 'requires a guest comparator runner',
                              'unknown-target': 'callback',
                              'throw-standard': 'TEST comparator runner exception',
                              'throw-unknown': 'non-standard C++ exception'}.items():
            result = subprocess.run([str(binary), mode], capture_output=True, timeout=30)
            log = result.stdout + result.stderr
            (out / (label + '-' + mode + '.log')).write_bytes(log)
            decoded = log.decode(errors='replace')
            assert result.returncode and all(s in decoded for s in ('libc import bsearch failed', 'guest libc fatal: bsearch', message)) and 'UNEXPECTED-BSEARCH-BOUNDARY-RETURN' not in decoded, (label, mode, result.returncode, decoded)
            boundaries[mode] = {'returncode': result.returncode, 'log_sha256': sha(out / (label + '-' + mode + '.log'))}
        platforms[label] = {'records': len(expected), 'binary_sha256': sha(binary), 'traces': len(manifest['traces']),
                            'objects': len(manifest['objects']), 'boundaries': boundaries, 'toolchain': manifest['toolchain']}
        print(label + ': actual translated comparator records match Android13 reference; seven fences pass', flush=True)
    for name, pin in overlays.items():
        assert sha(HERE / name) == pin and sha(source / 'windows' / name) == pin
    for name, pin in source_pins.items():
        assert sha(source / name) == pin
    for name, pin in {**tool_pins, **external}.items():
        assert sha(name) == pin
    frozen.update({'passed': True, 'platforms': platforms, 'reference_sha256': sha(reference),
                   'ndk_core_objects': {str(f): sha(f) for f in core_objects}, 'fixture_sha256': sha(library),
                   'records_each': len(expected), 'external_inputs': external,
                   'limits': 'Standalone original-body comparator gate; no original caller/init/managed/GC/frame claim; no reservation claim across callback Run'})
    frozen['evidence'] = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file() and 'host' not in f.relative_to(out).parts and f.name != 'acceptance.json'}
    (out / 'acceptance.json').write_text(json.dumps(frozen, indent=2) + '\n')
    print('BSEARCH-ALL-HOSTS-SUCCESS ' + str(out / 'acceptance.json'), flush=True)


if __name__ == '__main__':
    main()
