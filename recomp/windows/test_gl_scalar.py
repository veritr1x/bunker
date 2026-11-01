"""Real Windows Vulkan GL scalar commands through strict Android NDK callers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--semantics-dir', type=Path)
    p.add_argument('--remill', type=Path, default=HERE.parent/'work/remill-src')
    p.add_argument('--support-source', type=Path, default=HERE.parent,
                   help='Recomp support source to freeze before building')
    a = p.parse_args()
    out = HERE.parent/'work/gl-scalar'
    out.mkdir(parents=True, exist_ok=True)
    source = out/'source'
    for directory in ('windows', 'whole', 'fastaes'):
        target = source/directory
        target.mkdir(parents=True, exist_ok=True)
        for file in (a.support_source/directory).iterdir():
            if file.is_file() and file.suffix in ('.h', '.cpp', '.c', '.inc'):
                shutil.copyfile(file, target/file.name)
    for name in ('gl_host.cpp', 'gl_host.h', 'egl_host.cpp', 'egl_host.h', 'gl_host_test.cpp',
                 'gl_scalar_commands.inc', 'gl_scalar_guest.c', 'gl_scalar_test.cpp'):
        shutil.copyfile(HERE/name, source/'windows'/name)
    cc = a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library = out/'scalar.so'
    subprocess.run([str(cc), '-shared', '-nostdlib', '-fPIC', '-O1',
                    '-fno-stack-protector', '-fno-builtin',
                    str(source/'windows/gl_scalar_guest.c'), '-o', str(library)], check=True)
    semantics = a.semantics_dir or (a.lift.parent if (a.lift.parent/'aarch64.bc').is_file() else None)
    subprocess.run([sys.executable, str(HERE.parent/'whole/compile.py'), str(library),
                    '--out', str(out/'guest'), '--lift', str(a.lift), '--cxx', 'clang++-18',
                    '--base', '0x5c000000', '--target', 'x86_64-w64-windows-gnu', '--resume',
                    *(['--semantics-dir', str(semantics)] if semantics else [])], check=True)
    manifest = json.loads((out/'guest/manifest.json').read_text())
    assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
    loader = out/'elfload.o'
    subprocess.run(['/mnt/c/mingw64/bin/gcc.exe', '-O2', '-c',
                    hp(source/'fastaes/elfload.c'), '-o', hp(loader)], check=True)
    angle = HERE.parent/'work/angle-native'
    dlls = angle/'bundle/bin'
    base = ['/mnt/c/mingw64/bin/g++.exe', '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
            '-isystem', hp(a.remill/'include'), '-I'+hp(out/'guest'), '-I'+hp(angle/'src/include'),
            f'-DGL_SCALAR_LIBRARY="{hp(library)}"', f'-DGL_SCALAR_DLL_DIRECTORY=L"{hp(dlls)}"']
    objects = []
    for rel in ('windows/gl_scalar_test.cpp', 'windows/gl_host.cpp', 'windows/egl_host.cpp',
                'windows/native_window.cpp', 'windows/jni_host.cpp', 'whole/runtime.cpp'):
        file = source/rel
        obj = out/(file.stem+'.o')
        strict = ['-Wall', '-Wextra', '-Werror'] if file.stem in ('gl_scalar_test', 'gl_host') else []
        subprocess.run([*base, *strict, '-c', hp(file), '-o', hp(obj)], check=True)
        objects.append(obj)
    binary = out/'test.exe'
    command = [base[0], '-static', *map(hp, objects), hp(loader),
               *map(hp, manifest['objects']), '-pthread', '-latomic', '-luser32', '-o', hp(binary)]
    subprocess.run(command, check=True)
    run = subprocess.run([str(binary)], timeout=65, capture_output=True, text=True)
    print(run.stdout, end='')
    print(run.stderr, end='', file=sys.stderr)
    run.check_returncode()
    digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
    proof = dict(passed=True, stdout=run.stdout, stderr=run.stderr,
                 traces=len(manifest['traces']), unsupported=manifest['unsupported_traces'],
                 unresolved=manifest['unresolved_direct_targets'], binary_sha256=digest(binary),
                 source_sha256={str(f.relative_to(source)): digest(f) for f in source.rglob('*') if f.is_file()},
                 driver_sha256={f.name: digest(f) for f in dlls.glob('*.dll')},
                 toolchain=manifest['toolchain'], build_command=command,
                 boundary='Scalar state/clear only; no guest readPixels, shader, draw, buffer or mapped APIs; no game frame.')
    (out/'acceptance.json').write_text(json.dumps(proof, indent=2)+'\n')


if __name__ == '__main__':
    main()
