"""Immutable optional Windows condition-wait transport + actual NDK reference."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
OWN = ['pthread_host.h', 'pthread_host.cpp', 'pthread_wait_fixture.h',
       'pthread_wait_guest.c', 'pthread_wait_channel.h', 'pthread_wait_ref.c',
       'pthread_wait_test.cpp', 'test_pthread_wait.py', 'pthread_wait.md']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def wp(path):
    return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--support-commit', required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--ndk', type=Path, default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True)  # Never overwrite an earlier candidate.
    git = ['git.exe', '-C', wp(HERE.parent.parent)]
    commit = subprocess.check_output([*git, 'rev-parse', a.support_commit], text=True).strip()
    archive = subprocess.check_output([*git, 'archive', commit, 'recomp/windows', 'recomp/whole', 'recomp/fastaes'])
    (out / 'support.tar').write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out / 'sources', filter='data')
    source = out / 'sources/recomp'
    windows, whole = source / 'windows', source / 'whole'
    own = {name: sha(HERE / name) for name in OWN}
    for name in OWN:
        shutil.copyfile(HERE / name, windows / name)
    sources = {str(f.relative_to(out / 'sources')): sha(f) for f in (out / 'sources').rglob('*') if f.is_file()}
    tools = {str(f.resolve()): sha(f) for f in a.toolchain.rglob('*') if f.is_file()}
    ndk = a.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    qemu = a.reference_root / 'usr/bin/qemu-aarch64-static'
    external = {str(f.resolve()): sha(f.resolve()) for f in [ndk, qemu, Path('/mnt/c/mingw64/bin/g++.exe'), Path('/mnt/c/mingw64/bin/gcc.exe')]}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def run(command, log, timeout=240):
        with (out / log).open('wb') as stream:
            completed = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=timeout)
        if completed.returncode:
            raise RuntimeError(f'{log}: exit {completed.returncode}; preserved {out / log}')

    for label, compiler in [('ndk', ndk), ('windows', '/mnt/c/mingw64/bin/g++.exe'), ('linux', 'clang++-18')]:
        run([compiler, '--version'], label + '-compiler.log')
    core = out / 'pthread-wait-ndk.o'
    run([ndk, '-Wall', '-Wextra', '-Werror', '-O1', '-fPIC', '-fno-stack-protector', '-D_FORTIFY_SOURCE=0', '-c', windows / 'pthread_wait_guest.c', '-o', core], 'ndk-core-build.log')
    library = out / 'pthread-wait.so'
    run([ndk, '-shared', '-nostdlib', core, '-o', library], 'ndk-link.log')
    # Same exact Android object, native ARM64 libc implementation/real signals.
    root = a.reference_root
    sysroot, gcc = root / 'usr/aarch64-linux-gnu', root / 'usr/lib/gcc-cross/aarch64-linux-gnu/13'
    reference = out / 'arm64-reference'
    run(['clang-18', '--target=aarch64-linux-gnu', f'--sysroot={sysroot}', f'-B{gcc}', f'-L{gcc}', '-fuse-ld=lld', '-static', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread', windows / 'pthread_wait_ref.c', core, '-o', reference], 'arm64-reference-build.log')
    run([qemu, reference], 'arm64-reference.log', 30)
    assert 'ARM64 native cond scenario=0 result=0 owns=1' in (out / 'arm64-reference.log').read_text()
    assert 'ARM64 native cond scenario=1 result=110 owns=1' in (out / 'arm64-reference.log').read_text()
    assert 'ARM64 native pthread reference passed' in (out / 'arm64-reference.log').read_text()
    portable = out / 'linux-channel'
    run(['clang++-18', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread', windows / 'pthread_wait_test.cpp', '-o', portable], 'linux-channel-build.log')
    run([portable], 'linux-channel.log', 30)
    assert 'Linux portable wake channel passed:' in (out / 'linux-channel.log').read_text()
    loader = out / 'elfload.o'
    run(['/mnt/c/mingw64/bin/gcc.exe', '-O2', '-c', wp(source / 'fastaes/elfload.c'), '-o', wp(loader)], 'elfload-build.log')

    def lift(lib, directory):
        run([sys.executable, whole / 'compile.py', lib, '--out', directory, '--base', '0x70000000', '--target', 'x86_64-w64-windows-gnu', '--cxx', 'clang++-18', '--lift', a.toolchain / 'remill-lift', '--semantics-dir', a.toolchain], directory.name + '-lift.log', 600)
        manifest = json.loads((directory / 'manifest.json').read_text())
        assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        return manifest

    def binary(label, test, lib, manifest, directory, providers, define):
        executable = directory / (label + '.exe')
        # Werror is scoped to new fixture source; existing providers have
        # pre-existing GetProcAddress cast warnings unrelated to this change.
        flags = ['-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', f'-D{define}="{wp(lib)}"', '-isystem', wp(a.toolchain / 'include'), '-I' + wp(directory)]
        test_obj = directory / 'test.o'
        warnings = ['-Wall', '-Wextra', '-Werror'] if test == 'pthread_wait_test.cpp' else []
        run(['/mnt/c/mingw64/bin/g++.exe', *flags, *warnings, '-c', wp(windows / test), '-o', wp(test_obj)], label + '-test-build.log')
        run(['/mnt/c/mingw64/bin/g++.exe', *flags, '-static', wp(test_obj), *[wp(windows / name) for name in providers], wp(whole / 'runtime.cpp'), wp(loader), *[wp(Path(obj)) for obj in manifest['objects']], '-latomic', '-lbcrypt', '-o', wp(executable)], label + '-build.log', 360)
        run([executable], label + '-actual.log', 120)
        return executable

    focused_dir = out / 'focused'
    focused = lift(library, focused_dir)
    shutil.copyfile(focused_dir / 'traces.h', focused_dir / 'pthread_wait_traces.h')
    binary('pthread-wait', 'pthread_wait_test.cpp', library, focused, focused_dir, ['pthread_host.cpp', 'signal_host.cpp'], 'PTHREAD_WAIT_IMAGE')
    assert 'Windows optional pthread wait passed:' in (out / 'pthread-wait-actual.log').read_text()
    # Existing default/no-hook provider tests, each executed once on Windows.
    old = {}
    for label, guest, test, header, providers, define in [
        ('pthread-default', 'pthread_guest_fixture.c', 'pthread_test.cpp', 'pthread_traces.h', ['pthread_host.cpp'], 'PTHREAD_GUEST_IMAGE'),
        ('worker-lifecycle', 'worker_lifecycle_guest.c', 'worker_lifecycle_test.cpp', 'worker_lifecycle_traces.h', ['pthread_host.cpp', 'signal_host.cpp', 'nonlocal_jmp.cpp', 'libc.cpp', '../whole/format.cpp'], 'WORKER_LIFECYCLE_IMAGE')]:
        directory = out / label
        lib = out / (label + '.so')
        run([ndk, '-shared', '-fPIC', '-nostdlib', '-O1', '-fno-stack-protector', '-D_FORTIFY_SOURCE=0', windows / guest, '-o', lib], label + '-ndk.log')
        manifest = lift(lib, directory)
        shutil.copyfile(directory / 'traces.h', directory / header)
        if label == 'worker-lifecycle':
            with lib.open('rb') as stream:
                elf = ELFFile(stream)
                imports = [s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF']
                ranges = [(0x70000000 + s['sh_addr'], 0x70000000 + s['sh_addr'] + s['sh_size']) for s in elf.iter_sections() if s['sh_flags'] & 4 and s['sh_size']]
            (directory / 'worker_lifecycle_imports.h').write_text('static const char *kWorkerLifecycleImports[]={' + ','.join(json.dumps(x) for x in imports) + '};\nstruct WorkerCodeRange{addr_t low,high;};\nstatic const WorkerCodeRange kWorkerCodeRanges[]={' + ','.join('{' + hex(lo) + ',' + hex(hi) + '}' for lo, hi in ranges) + '};\n')
        executable = binary(label, test, lib, manifest, directory, providers, define)
        text = (out / (label + '-actual.log')).read_text()
        assert 'checks passed' in text
        old[label] = {'executable_sha256': sha(executable), 'traces': len(manifest['traces']), 'result': text.strip()}
    for name, digest in own.items():
        assert sha(HERE / name) == digest and sha(windows / name) == digest
    assert all(sha(out / 'sources' / name) == digest for name, digest in sources.items())
    assert all(sha(name) == digest for name, digest in tools.items())
    assert all(sha(name) == digest for name, digest in external.items())
    evidence = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file() and 'sources' not in f.relative_to(out).parts}
    result = dict(passed=True, support_commit=commit, source_sha256=sources, held_source_sha256=own,
                  tool_sha256=tools, external_sha256=external, evidence_sha256=evidence,
                  focused_traces=len(focused['traces']), focused_objects=len(focused['objects']),
                  regressions=old, scope='Windows actual Pthreads optional condition transport; identical NDK ARM64 object/native signals; Linux portable channel only; no production signal30, collector or root-safety claim')
    (out / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Optional condition wait: Windows provider, ARM64 native reference, Linux channel, two existing Windows regressions passed', flush=True)


if __name__ == '__main__':
    main()
