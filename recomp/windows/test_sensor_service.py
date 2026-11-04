"""Explicit unavailable Android sensor service: retained original callers and NDK ABI."""
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
W = Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN = ['sensor_service.h', 'sensor_service_fixture.h', 'sensor_service_native.S',
       'sensor_service_ref.c', 'sensor_service_guest.c', 'sensor_service_test.cpp', 'test_sensor_service.py']
RANGES = [(0x704119f8, 0x70411a90), (0x704124d8, 0x7041258c)]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def wp(path):
    return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--support', default='d52821f908ecb2cabb0669160b48e13caa2a7ee9')
    parser.add_argument('--toolchain', type=Path, default=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tool = args.toolchain.resolve()
    root = HERE.parent.parent
    commit = subprocess.check_output(['git.exe', '-C', wp(root), 'rev-parse', args.support], text=True).strip()
    assert commit == 'd52821f908ecb2cabb0669160b48e13caa2a7ee9'
    archive = subprocess.check_output(['git.exe', '-C', wp(root), 'archive', commit, 'recomp/windows', 'recomp/whole', 'recomp/fastaes'])
    (out/'support.tar').write_bytes(archive)
    frozen = out/'source'
    frozen.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(frozen)
    source = frozen/'recomp'
    for name in OWN:
        shutil.copy2(HERE/name, source/'windows'/name)
    owned = {'windows/'+name: sha(source/'windows'/name) for name in OWN}
    assert owned['windows/sensor_service.h'] == '5432bf01a11587d51a90547b30974c2b547b6936b100b3e4e08fd40fd92f2642'
    sourcepins = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    parent = W/'windows-first-frame-audio-disabled1'
    assert sha(parent/'game_inputs.json') == '65e496475e6d14b6abb8e4bcfed10ffba88a5e9701f30a8435defa64d7016aae'
    selected_path = W/'audio-disabled1-sensor-boundary1/selected-ir.json'
    assert sha(selected_path) == 'df83e92570ba4485d183ba7a67b5ce20ba6f484fcd2a1cc1d42a0677f303004d'
    selected = json.loads(selected_path.read_text())
    inputs = {str(selected_path): sha(selected_path), str(parent/'game_inputs.json'): sha(parent/'game_inputs.json')}
    commands = []

    def run(command, label):
        command = list(map(str, command))
        commands.append(command)
        print('STAGE '+label, flush=True)
        with (out/(label+'.log')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        if result.returncode:
            (out/'failure.json').write_text(json.dumps({'passed': False, 'stage': label, 'exit': result.returncode}, indent=2)+'\n')
            raise RuntimeError(label+' exit'+str(result.returncode)+'\n'+(out/(label+'.log')).read_text(errors='replace')[-4000:])
        return (out/(label+'.log')).read_text(errors='replace')

    elf = parent/'native/libunity.so'
    assert sha(elf) == '3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
    inputs[str(elf)] = sha(elf)
    original = bytearray()
    with elf.open('rb') as stream:
        image = ELFFile(stream)
        for start, end in RANGES:
            rva = start-0x70000000
            segment = next(s for s in image.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= rva and rva+end-start <= s['p_vaddr']+s['p_filesz'])
            stream.seek(segment['p_offset']+rva-segment['p_vaddr'])
            original += stream.read(end-start)
    original_path = out/'original-callers.bin'
    original_path.write_bytes(original)
    inputs[str(original_path)] = sha(original_path)
    function_pattern = r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}'
    projections = {}
    refs = set()
    for kind in ('raw', 'polled'):
        descriptor = selected[kind+'_ir']
        module_path = Path(descriptor['path'])
        assert sha(module_path) == descriptor['sha256']
        inputs[str(module_path)] = sha(module_path)
        text = module_path.read_text()
        matches = list(re.finditer(function_pattern, text, re.M | re.S))
        bodies = {int(m[1], 16): m[0] for m in matches}
        keep = {start for start, end in RANGES}
        for head in keep:
            expected = selected['bodies'][hex(head)][kind]
            assert hashlib.sha256(bodies[head].encode()).hexdigest() == expected['sha256']
            refs.update(re.findall(r'@sub_([0-9a-f]+)\(', bodies[head]))
        # Fixture-only projection: preserve selected complete bodies and every
        # State/helper/attribute/metadata declaration; remove unrelated guests.
        parts, at = [], 0
        for match in matches:
            parts.append(text[at:match.start()])
            if int(match[1], 16) in keep:
                parts.append(match[0])
            else:
                parts.append('declare ptr @sub_'+match[1]+'(ptr, i64, ptr)')
            at = match.end()
        parts.append(text[at:])
        projection = ''.join(parts)
        projected = out/(kind+'-retained-callers.ll')
        projected.write_text(projection)
        assert {int(m[1], 16) for m in re.finditer(function_pattern, projection, re.M | re.S)} == keep
        assert all(bodies[head] in projection for head in keep)
        projections[kind] = {'path': str(projected), 'sha256': sha(projected), 'complete_selected_bodies_byte_exact': True,
                             'full_selected_COFF_execution_claimed': False, 'source': descriptor}
    fence_heads = sorted(refs-{'704119f8', '704124d8', '700b8660', '700b8440'})
    (out/'sensor_fences.h').write_text(''.join('FENCE('+head+')\n' for head in fence_heads))
    inputs[str(out/'sensor_fences.h')] = sha(out/'sensor_fences.h')
    ndk = Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang')
    qemu = Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static')
    for path in [ndk.resolve(), qemu.resolve(), tool/'remill-lift', tool/'aarch64.bc', Path('/mnt/c/mingw64/bin/g++.exe'), *[Path(shutil.which(name)).resolve() for name in ('clang-18', 'clang++-18')]]:
        inputs[str(path)] = sha(path)
    for path in (tool/'include').rglob('*'):
        if path.is_file():
            inputs[str(path)] = sha(path)
    win = source/'windows'
    run([ndk, '-fno-emulated-tls', '-Wall', '-Wextra', '-Werror', '-fsyntax-only', win/'sensor_service_ref.c'], 'reference-strict')
    run([ndk, '-O2', '-static', '-fno-emulated-tls', '-Wall', '-Wextra', '-Werror', win/'sensor_service_ref.c', win/'sensor_service_native.S', '-o', out/'reference'], 'reference-build')
    library = out/'sensor-caller.so'
    run([ndk, '-shared', '-nostdlib', '-O1', '-fPIC', '-fno-stack-protector', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations', win/'sensor_service_guest.c', '-o', library], 'ndk-build')
    records, observations, binaries = {'arm64': []}, {'arm64': []}, {}

    def collect(key, command, case):
        text = run(command, 'case-'+key+'-'+str(case))
        rows = [line for line in text.splitlines() if line.startswith('RECORD ')]
        obs = [line for line in text.splitlines() if line.startswith('OBSERVATION ')]
        assert len(rows) == len(obs) == 1
        if key != 'arm64':
            assert rows[0] == records['arm64'][case], (key, case)
        records[key].append(rows[0])
        observations[key].append(obs[0])

    for case in range(4):
        collect('arm64', [qemu, out/'reference', original_path, case], case)
    for platform, target, cxx in [('windows', 'x86_64-w64-windows-gnu', '/mnt/c/mingw64/bin/g++.exe'), ('linux', 'x86_64-linux-gnu', 'clang++-18')]:
        build = out/platform
        build.mkdir()
        guest = build/'guest'
        run([sys.executable, source/'whole/compile.py', library, '--out', guest, '--base', '0x78000000', '--lift', tool/'remill-lift', '--semantics-dir', tool, '--target', target, '--cxx', 'clang++-18'], platform+'-ndk-caller-lift')
        manifest = json.loads((guest/'manifest.json').read_text())
        assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        convert = wp if platform == 'windows' else str
        flags = ['-O2', '-std=c++17', '-DADDRESS_SIZE_BITS=64', '-isystem', convert(tool/'include'), '-I'+convert(source/'whole'), '-I'+convert(out), '-I'+convert(guest)]
        loader = build/'elfload.o'
        cc = '/mnt/c/mingw64/bin/gcc.exe' if platform == 'windows' else 'clang-18'
        run([cc, '-O2', '-c', convert(source/'fastaes/elfload.c'), '-o', convert(loader)], platform+'-loader')
        objects = [loader]
        for path in [source/'whole/runtime.cpp', source/'whole/cooperative_poll.cpp', win/'sensor_service_test.cpp']:
            obj = build/(path.stem+'.o')
            run([cxx, *flags, *(['-Wall', '-Wextra', '-Werror'] if path.parent == win else []), f'-DSENSOR_IMAGE="{convert(library)}"', '-c', convert(path), '-o', convert(obj)], platform+'-'+path.stem)
            objects.append(obj)
        for kind in ('raw', 'polled'):
            obj = build/(kind+'-original.o')
            run(['clang-18', '-target', target, '-O2', '-Wno-override-module', '-c', projections[kind]['path'], '-o', obj], platform+'-'+kind+'-original')
            executable = build/(kind+('.exe' if platform == 'windows' else ''))
            run([cxx, *map(convert, objects+[obj]), *map(convert, manifest['objects']), '-Wl,--wrap=__bunker_guest_poll_requested', '-Wl,--wrap=__bunker_guest_poll_slow', '-latomic', '-pthread', *(['-static'] if platform == 'windows' else []), '-o', convert(executable)], platform+'-'+kind+'-link')
            key = platform+'-'+kind
            records[key], observations[key] = [], []
            binaries[key] = {'path': str(executable), 'sha256': sha(executable)}
            for case in range(4):
                collect(key, [executable, int(kind == 'polled'), case], case)
    for name, digest in sourcepins.items():
        assert sha(source/name) == digest
    for name in OWN:
        assert sha(HERE/name) == owned['windows/'+name]
    for path, digest in inputs.items():
        assert sha(path) == digest
    (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    result = {'passed': True, 'commit': commit, 'owned_sources': owned, 'support_sources': sourcepins,
              'records_each': 4, 'platforms': list(records), 'original_ranges': [[hex(a), hex(b)] for a, b in RANGES],
              'complete_original_bodies_preserved_in_projection': True, 'full_selected_COFF_execution_claimed': False,
              'declared_profile': 'Unavailable Android sensor-service backend', 'native_unavailable_manager_seam_test_only': True,
              'actual_Android_failure_equivalence_claimed': False, 'physical_sensor_inventory_claimed': False,
              'nonnull_manager_and_Looper_queue_paths_exercised': False, 'owned_global_bytes': 65536,
              'complete_global_clear_and_canary_oracle': True, 'cross_platform_comparison': 'complete globals/canaries and callee-saved GPR/low64SIMD/SP; caller-clobbered registers excluded',
              'isolated_provider_full_State_bytes': 1200, 'opaque_token_bytes': 64,
              'NDK_direct_and_function_pointer_callers': True, 'provider_errno_preserved': True,
              'Windows_LastError_compared_to_matched_Runtime_control': True,
              'absolute_Runtime_LastError_preservation_claimed': False,
              'current_IR_projections': projections, 'fail_fenced_callees': fence_heads, 'inputs': inputs,
              'binaries': binaries, 'observations': observations,
              'record_digests': {key: hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest() for key, rows in records.items()},
              'limits': 'Native ARM uses a named TEST-only unavailable-manager seam and real Bionic memset. Hosts use actual SensorService plus exact retained caller bodies. No Android runtime/hardware equivalence, queue/Looper implementation, physical sensor absence, game run or presented frame claim.'}
    result['evidence'] = {str(path.relative_to(out)): sha(path) for path in out.rglob('*') if path.is_file() and path.name != 'acceptance.json'}
    (out/'acceptance.json').write_text(json.dumps(result, indent=2)+'\n')
    print('SENSOR-SERVICE-PASS '+sha(out/'acceptance.json'), flush=True)


if __name__ == '__main__':
    main()
