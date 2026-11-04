"""Recheck both exact APK profiles with saved qualified NDK translations, no relift."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path('/mnt/c/GitRepos/bunker/recomp/work')
ORIGINAL = '9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209'
CATALOG = 'b2be67185a866f3489146d9864ca40d1de5c2668037f026609890afe12940689'
NEGATIVES = {'--changed-apk': 'complete APK code-catalog profile',
             '--unknown-code': 'complete APK code-catalog profile',
             '--present-code': 'complete APK code-catalog profile',
             '--open-scope': 'complete APK code-catalog profile',
             '--visible-factory': 'availability/class-loader profile',
             '--path': 'Java method has no host implementation',
             '--get-instance': 'Java method has no host implementation',
             '--retired-owner': 'adapter owner expired'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(command, log, success=True):
    with log.open('w') as output:
        result = subprocess.run(list(map(str, command)), stdout=output,
                                stderr=subprocess.STDOUT, timeout=120)
    text = log.read_text(errors='replace')
    if success and result.returncode:
        raise RuntimeError(f'{log}: {result.returncode}\n{text[-6000:]}')
    return result.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--derived-apk', type=Path, required=True)
    parser.add_argument('--derived-apk-sha', required=True)
    parser.add_argument('--asset-proof', type=Path, required=True)
    parser.add_argument('--asset-proof-sha', required=True)
    parser.add_argument('--support', default='62b20a57225487edf00e2dc5709c3e8580bb2f2b')
    parser.add_argument('--reuse', type=Path, default=WORK/'asset-pack-wrapper2')
    parser.add_argument('--include', type=Path, default=WORK/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4/include')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    assert len(args.derived_apk_sha) == 64 and args.derived_apk_sha != ORIGINAL
    assert sha(args.derived_apk) == args.derived_apk_sha
    assert sha(args.asset_proof) == args.asset_proof_sha
    asset_proof = json.loads(args.asset_proof.read_text())
    assert asset_proof['passed'] is True
    assert asset_proof['source_apk']['sha256'] == ORIGINAL
    assert asset_proof['derived_apk']['sha256'] == args.derived_apk_sha
    assert asset_proof['entry_count'] == 4968 and asset_proof['uncompressed_entries_changed'] == 1
    assert asset_proof['all_other_uncompressed_entries_exact'] is True
    assert asset_proof['DEX_and_native_entries_uncompressed_byte_exact'] is True
    assert asset_proof['mutation'] == {'field': 'AudioManager.m_DisableAudio', 'path_id': 4,
        'class_id': 11, 'asset_byte_offset': 223600, 'old': 0, 'new': 1,
        'changed_asset_bytes': 1, 'all_other_asset_bytes_exact': True}
    old_receipt_path = args.reuse/'acceptance.json'
    old = json.loads(old_receipt_path.read_text())
    assert old['passed'] is True and old['profile_sha256'] == CATALOG
    root = HERE.parent.parent
    windows_root = subprocess.check_output(['wslpath', '-m', str(root)], text=True).strip()
    commit = subprocess.check_output(['git.exe', '-C', windows_root, 'rev-parse', args.support], text=True).strip()
    frozen = out/'source/recomp'
    dependencies = ['windows/jni_host.cpp', 'windows/jni_host.h', 'whole/runtime.cpp',
                    'whole/runtime.h', 'fastaes/elfload.c', 'fastaes/elfload.h']
    owned_names = ['android_asset_pack_wrapper.h', 'android_asset_pack_wrapper.cpp',
                   'asset_pack_wrapper_guest.c', 'asset_pack_wrapper_test.cpp', Path(__file__).name]
    # Snapshot current sources and headers; rebuild all support objects. Only the
    # already-qualified translated guest object is reused, never old JNI/runtime.
    for directory in ('windows', 'whole', 'fastaes'):
        destination = frozen/directory
        destination.mkdir(parents=True, exist_ok=True)
        for path in (HERE.parent/directory).glob('*.h'):
            shutil.copy2(path, destination/path.name)
    for relative in dependencies:
        shutil.copy2(HERE.parent/relative, frozen/relative)
    for name in owned_names:
        shutil.copy2(HERE/name, frozen/'windows'/name)
    owned = {f'windows/{name}': sha(HERE/name) for name in owned_names}
    assert sha(HERE/'asset_pack_wrapper_guest.c') == old['owned']['asset_pack_wrapper_guest.c']
    reused = {}
    for relative in ('asset-wrapper.so', 'asset_pack_proof.h', 'jni.h', 'sample.h'):
        assert sha(args.reuse/relative) == old['evidence'][relative]
        shutil.copy2(args.reuse/relative, out/relative)
        reused[relative] = sha(out/relative)
    proof_text = (out/'asset_pack_proof.h').read_text()
    assert ORIGINAL in proof_text and CATALOG in proof_text
    source_pins = {str(p.relative_to(frozen)): sha(p) for p in frozen.rglob('*') if p.is_file()}
    include_pins = {str(p.relative_to(args.include)): sha(p) for p in args.include.rglob('*') if p.is_file()}
    assert include_pins and (args.include/'remill/Arch/AArch64/Runtime/State.h').is_file()
    current_candidate = WORK/'unity-fmod-pure-entries-overlay1/candidate.json'
    assert sha(current_candidate) == 'd003701628ab5a25d1dd0c8807d9140e10d90f1a34fc921d7a40b8581553ba24'
    current = json.loads(current_candidate.read_text())
    state_reference = Path(current['raw_ir']['path'])
    assert sha(state_reference) == current['raw_ir']['sha256']
    assert current['State_size'] == 1200 and current['State_align'] == 16
    def state_graph(path):
        definitions = dict(re.findall(r'^(%[-\w.$]+) = type (.+)$', path.read_text(), re.M))
        graph, pending = {}, ['%struct.State']
        while pending:
            name = pending.pop()
            if name in graph:
                continue
            graph[name] = definitions[name]
            pending.extend(re.findall(r'%[-\w.$]+', graph[name]))
        return graph
    expected_state = state_graph(state_reference)
    result = {'passed': False, 'commit': commit, 'original_apk_sha256': ORIGINAL,
              'derived_apk_sha256': args.derived_apk_sha, 'code_catalog_sha256': CATALOG,
              'asset_proof': {'path': str(args.asset_proof), 'sha256': args.asset_proof_sha},
              'prior_qualification': {'path': str(old_receipt_path), 'sha256': sha(old_receipt_path)},
              'owned_sources': owned, 'support_sources': source_pins, 'include_sources': include_pins,
              'reused_guest_inputs': reused, 'support_objects_rebuilt': True,
              'State_reference_candidate_sha256': sha(current_candidate),
              'saved_guest_State_graph_exact_to_current_1200': True,
              'relift_performed': False, 'platforms': {}}
    (out/'source-pin.json').write_text(json.dumps(result, indent=2)+'\n')
    for windows in (True, False):
        platform = 'windows' if windows else 'linux'
        build = out/platform
        build.mkdir()
        guest = args.reuse/platform/'guest'
        manifest = json.loads((guest/'manifest.json').read_text())
        assert state_graph(guest/'shard-00000.ll') == expected_state
        assert len(manifest['traces']) == 13 and not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        for path in [guest/'manifest.json', guest/'traces.h', *map(Path, manifest['objects'])]:
            relative = str(path.relative_to(args.reuse))
            assert sha(path) == old['evidence'][relative]
            reused[relative] = sha(path)
        def hp(path):
            if windows:
                return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
            return str(path)
        cxx = '/mnt/c/mingw64/bin/g++.exe' if windows else 'clang++-18'
        cc = '/mnt/c/mingw64/bin/gcc.exe' if windows else 'clang-18'
        flags = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', '-isystem', hp(args.include), '-I'+hp(out)]
        objects = []
        for relative in ('windows/jni_host.cpp', 'windows/android_asset_pack_wrapper.cpp', 'whole/runtime.cpp'):
            obj = build/(Path(relative).stem+'.o')
            execute([cxx, *flags, '-c', hp(frozen/relative), '-o', hp(obj)], build/(obj.stem+'-build.log'))
            objects.append(obj)
        loader = build/'elfload.o'
        execute([cc, '-O2', '-c', hp(frozen/'fastaes/elfload.c'), '-o', hp(loader)], build/'loader-build.log')
        executable = build/('asset-wrapper.exe' if windows else 'asset-wrapper')
        execute([cxx, *flags, '-I'+hp(guest), f'-DASSET_LIBRARY="{hp(out/"asset-wrapper.so")}"',
                 f'-DASSET_DERIVED_APK_SHA256="{args.derived_apk_sha}"', hp(frozen/'windows/asset_pack_wrapper_test.cpp'),
                 *map(hp, objects), hp(loader), *map(hp, manifest['objects']), '-pthread', '-latomic',
                 *(['-static'] if windows else []), '-o', hp(executable)], build/'link.log')
        profiles = {}
        for derived in (False, True):
            name = 'derived' if derived else 'original'
            prefix = [executable, *(['--derived-profile'] if derived else [])]
            code, text = execute(prefix, build/(name+'-positive.log'))
            assert '209 checks passed' in text
            negatives = {}
            for mode, needle in NEGATIVES.items():
                code, text = execute([*prefix, mode], build/(name+mode+'.log'), success=False)
                assert code and needle in text, (platform, name, mode, code, text)
                negatives[mode] = code
            profiles[name] = {'positive_checks': 209, 'negative_boundaries': negatives}
        result['platforms'][platform] = {'profiles': profiles, 'traces': 13, 'objects': 1,
                                         'binary_sha256': sha(executable)}
        (out/'progress.json').write_text(json.dumps(result, indent=2)+'\n')
        print(platform+': both profiles passed209 +8 boundaries each', flush=True)
    for relative, digest in source_pins.items():
        assert sha(frozen/relative) == digest
    for relative, digest in owned.items():
        assert sha(HERE.parent/relative) == digest
    for relative, digest in include_pins.items():
        assert sha(args.include/relative) == digest
    for relative, digest in reused.items():
        assert sha(args.reuse/relative) == digest
    assert sha(args.derived_apk) == args.derived_apk_sha and sha(args.asset_proof) == args.asset_proof_sha
    result['passed'] = True
    result['limits'] = 'Actual translated NDK JNI wrapper/lifecycle tests; no PlayCore delivery, asset backend, or original-game execution. APK code-equivalence is separately pinned evidence.'
    result['evidence'] = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file() and 'source' not in p.relative_to(out).parts and p.name not in ('acceptance.json', 'progress.json')}
    (out/'acceptance.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS '+str(out/'acceptance.json'), flush=True)


if __name__ == '__main__':
    main()
