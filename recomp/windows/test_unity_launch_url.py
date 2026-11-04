"""Retained UnityPlayer launch URI snapshot, actual NDK JNI and Intent/AR regressions."""
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE = '14aa64f0a0f2e67e7066aca1f5a9531086f31c59'
OWN = ['jni_host.h', 'jni_host.cpp', 'android_context.cpp', 'java_init_test.cpp', 'unity_launch_url_guest.c',
       'unity_launch_url_test.cpp', 'test_unity_launch_url.py']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def wp(path):
    return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-proof', type=Path, required=True)
    parser.add_argument('--source-proof-sha', required=True)
    parser.add_argument('--dex-proof', type=Path, required=True)
    parser.add_argument('--dex-proof-sha', required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for path, digest in [(args.source_proof, args.source_proof_sha), (args.dex_proof, args.dex_proof_sha)]:
        assert sha(path) == digest and json.loads(path.read_text())['passed'] is True
    root = HERE.parent.parent
    archive = subprocess.check_output(['git.exe', '-C', wp(root), 'archive', BASE, 'recomp/windows', 'recomp/whole', 'recomp/fastaes'])
    (out/'support.tar').write_bytes(archive)
    frozen = out/'source'
    frozen.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(frozen)
    source = frozen/'recomp'
    for name in OWN:
        shutil.copy2(HERE/name, source/'windows'/name)
    owned = {'windows/'+name: sha(source/'windows'/name) for name in OWN}
    assert owned['windows/android_context.cpp'] == '333b9dce476661722899b8216f61c4b8f5b0b3e3adf6180dda5eceb8e5c3a3e6'
    assert owned == json.loads(args.source_proof.read_text())['owned_sources']
    sources = {str(path.relative_to(source)): sha(path) for path in source.rglob('*') if path.is_file()}
    tool = W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4'
    ndkroot = Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018')
    ndk = ndkroot/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    prior = W/'java-init-candidate4'
    old = json.loads((prior/'acceptance.json').read_text())
    assert old['passed'] is True and sha(prior/'sample.h') == old['generated_sample_sha256']
    shutil.copy2(prior/'sample.h', out/'sample.h')
    jni = ndkroot/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/jni.h'
    shutil.copy2(jni, out/'jni.h')
    inputs = {str(path): sha(path) for path in [args.source_proof, args.dex_proof, prior/'acceptance.json', prior/'sample.h', jni, ndk.resolve(), tool/'remill-lift', tool/'aarch64.bc', Path('/mnt/c/mingw64/bin/g++.exe'), Path('/mnt/c/mingw64/bin/gcc.exe'), Path(shutil.which('clang++-18')).resolve(), Path(shutil.which('clang-18')).resolve()]}
    dex_methods = args.dex_proof.parent/'dex-methods.json'
    dex_disassembly = args.dex_proof.parent/'dex-disassembly.txt'
    inputs[str(dex_methods)] = sha(dex_methods)
    inputs[str(dex_disassembly)] = sha(dex_disassembly)
    methods = json.loads(dex_methods.read_text())
    apk = W/'windows-first-frame-sensors1/game-audio-disabled.apk'
    assert sha(apk) == '36e15676053734a225f55bdf89acd375adaf298872d4d1dfc06c140e5a0ed394'
    inputs[str(apk)] = sha(apk)
    with zipfile.ZipFile(apk) as package:
        dex = package.read('classes2.dex')
    assert hashlib.sha256(dex).hexdigest() == methods['dex_sha256']
    for item in methods['code_items'].values():
        offset = int(item['code_item'], 16)+16
        code = dex[offset:offset+item['instruction_words']*2]
        assert code.hex() == item['code_hex'] and hashlib.sha256(code).hexdigest() == item['code_sha256']
    for path in (tool/'include').rglob('*'):
        if path.is_file():
            inputs[str(path)] = sha(path)
    zlib = W/'zlib-native/zlib-1.3.2'
    for path in zlib.glob('*.h'):
        inputs[str(path)] = sha(path)
    commands = []

    def run(command, label, expected_failure=None):
        command = list(map(str, command))
        commands.append(command)
        print('STAGE '+label, flush=True)
        with (out/(label+'.log')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        text = (out/(label+'.log')).read_text(errors='replace')
        passed = bool(result.returncode and expected_failure in text) if expected_failure else result.returncode == 0
        if not passed:
            (out/'failure.json').write_text(json.dumps({'passed': False, 'stage': label, 'exit': result.returncode}, indent=2)+'\n')
            raise RuntimeError(label+' exit'+str(result.returncode)+'\n'+text[-5000:])
        return {'stdout': text, 'exit_code': result.returncode}

    win = source/'windows'
    images = {'launch': (out/'launch-url.so', ['unity_launch_url_guest.c', 'context_guest_fixture.c'], '0x73000000'),
              'java': (out/'java-init.so', ['package_guest_fixture.c', 'java_init_guest.c'], '0x74000000')}
    run([ndk, '-Wall', '-Wextra', '-Werror', '-fsyntax-only', win/'unity_launch_url_guest.c'], 'new-guest-strict')
    for name, (library, files, base) in images.items():
        run([ndk, '-shared', '-nostdlib', '-O1', '-fPIC', '-fno-stack-protector', '-fno-builtin', '-Wall', '-Wextra', *[win/f for f in files], '-o', library], name+'-ndk-build')
    results = {}
    manifests = {}
    for windows in (True, False):
        platform = 'windows' if windows else 'linux'
        build = out/platform
        build.mkdir()
        convert = wp if windows else str
        cxx = '/mnt/c/mingw64/bin/g++.exe' if windows else 'clang++-18'
        cc = '/mnt/c/mingw64/bin/gcc.exe' if windows else 'clang-18'
        flags = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', '-isystem', convert(tool/'include'), '-I'+convert(out), '-I'+convert(zlib)]
        loader = build/'elfload.o'
        run([cc, '-O2', '-c', convert(source/'fastaes/elfload.c'), '-o', convert(loader)], platform+'-loader')
        objects = [loader]
        for relative in ['windows/jni_host.cpp', 'windows/android_context.cpp', 'windows/windows_android_id.cpp', 'windows/android_assets.cpp', 'windows/apk_assets.cpp', 'whole/runtime.cpp']:
            obj = build/(Path(relative).stem+'.o')
            run([cxx, *flags, '-c', convert(source/relative), '-o', convert(obj)], platform+'-'+obj.stem)
            objects.append(obj)
        backend = W/('zlib-native/libz-inflate.a' if windows else 'zlib-linux/backend/libz-inflate.a')
        inputs[str(backend)] = sha(backend)
        translated = {}
        for name, (library, files, base) in images.items():
            guest = build/(name+'-guest')
            run([sys.executable, source/'whole/compile.py', library, '--out', guest, '--base', base, '--lift', tool/'remill-lift', '--semantics-dir', tool, '--target', 'x86_64-w64-windows-gnu' if windows else 'x86_64-linux-gnu', '--cxx', 'clang++-18'], platform+'-'+name+'-translate')
            manifest = json.loads((guest/'manifest.json').read_text())
            assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
            translated[name] = (guest, manifest)
            manifests[platform+'-'+name] = {'traces': len(manifest['traces']), 'objects': len(manifest['objects']), 'manifest_sha256': sha(guest/'manifest.json')}
        tests = {}
        for name, image_name in [('unity_launch_url', 'launch'), ('context_intent', 'launch'), ('java_init', 'java'), ('jni_host', 'java'), ('jni_callback_frame', 'java'), ('jni_constructor_frame', 'java')]:
            guest, manifest = translated[image_name]
            library = images[image_name][0]
            executable = build/(name+('.exe' if windows else ''))
            macros = [f'-DLAUNCH_IMAGE="{convert(library)}"', f'-DCONTEXT_IMAGE="{convert(library)}"', f'-DPACKAGE_IMAGE="{convert(library)}"']
            run([cxx, *flags, '-I'+convert(guest), *macros, '-Wall', '-Wextra', *(['-Werror'] if name == 'unity_launch_url' else []), convert(win/(name+'_test.cpp')), *map(convert, objects), *map(convert, manifest['objects']), convert(backend), '-latomic', '-pthread', *(['-static', '-ladvapi32'] if windows else []), '-o', convert(executable)], platform+'-'+name+'-link')
            tests[name] = run([executable], platform+'-'+name)
            tests[name]['binary_sha256'] = sha(executable)
            if name == 'unity_launch_url':
                assert 'UNITY-LAUNCH-URL-PASS' in tests[name]['stdout']
                tests[name]['checks'] = int(re.search(r'checks=(\d+)', tests[name]['stdout'])[1])
            if name == 'java_init':
                tests[name]['enabled_AR_expected_failure'] = run([executable, '--enabled-ar'], platform+'-enabled-AR', 'enabled Google ARCore requires original native initialize/resume side effects; no host implementation')
        results[platform] = {'tests': tests}
        (out/'progress.json').write_text(json.dumps(results, indent=2)+'\n')
    for name, digest in sources.items():
        assert sha(source/name) == digest
    for name, digest in owned.items():
        assert sha(HERE.parent/name) == digest
    for path, digest in inputs.items():
        assert sha(path) == digest
    (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    result = {'passed': True, 'commit': BASE, 'owned_sources': owned, 'support_sources': sources,
              'source_proof': {'path': str(args.source_proof), 'sha256': args.source_proof_sha},
              'DEX_audit': {'path': str(args.dex_proof), 'sha256': args.dex_proof_sha},
              'platforms': results, 'manifests': manifests, 'inputs': inputs,
              'actual_NDK_JNI_direct_V_A_and_field_get_set': True,
              'launch_profiles': ['absent', 'empty', 'UTF16_embedded_NUL_and_nonBMP'],
              'constructor_Uri_snapshot_identity_and_ownership': True,
              'field_NULL_restore_and_TEST_subclass_replacement': True,
              'Context_retirement_and_currentActivity_changes_do_not_live_reread_Intent': True,
              'virtual_toString_exception_and_pending_exception_preserved': True,
              'prior_Intent_test_body_unchanged': True, 'prior_AR_test_only_getLaunchURL_metadata_row': True,
              'new_BindObjectMethod_strict_declaration_negative_controls': True,
              'existing_JNI_core_and_callback_constructor_frames_rechecked': True,
              'limits': 'JNI host implementation of exact configured constructor snapshot/getter semantics. TEST Uri subtype probes virtual dispatch/ownership only; no new URI parser, external intent delivery/newIntent native event, input/audio service, physical device or original-game run claim.'}
    result['evidence'] = {str(path.relative_to(out)): sha(path) for path in out.rglob('*') if path.is_file() and path.name not in ('acceptance.json', 'progress.json')}
    (out/'acceptance.json').write_text(json.dumps(result, indent=2)+'\n')
    print('UNITY-LAUNCH-URL-QUALIFIED '+sha(out/'acceptance.json'), flush=True)


if __name__ == '__main__':
    main()
