"""Strict NDK framebuffer callers against real Windows ANGLE and a native oracle.

Run from WSL only after the shared GlHost integration is ready. This is not an
ARM GPU reference or a game/frame qualification. Output directories are fresh.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--semantics-dir', type=Path, required=True)
    parser.add_argument('--remill', type=Path, required=True)
    parser.add_argument('--angle', type=Path, required=True,
                        help='Qualified ANGLE root containing src/include and bundle/bin')
    parser.add_argument('--support-source', type=Path, default=HERE.parent)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit('Refusing to reuse an output directory: ' + str(out))
    out.mkdir(parents=True)
    source = out/'source'
    for directory in ('windows', 'whole', 'fastaes'):
        target = source/directory
        target.mkdir(parents=True)
        for file in (args.support_source/directory).iterdir():
            if file.is_file() and file.suffix in ('.h', '.cpp', '.c', '.inc'):
                shutil.copyfile(file, target/file.name)
    fixture_names = ('gl_framebuffer_commands.inc', 'gl_framebuffer_impl.inc',
                     'gl_framebuffer_fixture.h', 'gl_framebuffer_guest.c',
                     'gl_framebuffer_test.cpp')
    for name in fixture_names:
        shutil.copyfile(HERE/name, source/'windows'/name)
    shutil.copyfile(Path(__file__).resolve(), out/'executed-controller.py')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source_pins = {str(file.relative_to(source)): digest(file)
                   for file in source.rglob('*') if file.is_file()}

    def command(argv):
        subprocess.run(list(map(str, argv)), check=True)

    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()

    cc = args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library = out/'framebuffer.so'
    command([cc, '-Wall', '-Wextra', '-Werror', '-shared', '-nostdlib', '-fPIC', '-O1',
             '-fno-stack-protector', '-fno-builtin', source/'windows/gl_framebuffer_guest.c',
             '-o', library])
    command([sys.executable, args.support_source/'whole/compile.py', library,
             '--out', out/'guest', '--lift', args.lift, '--cxx', 'clang++-18',
             '--base', '0x5c000000', '--target', 'x86_64-w64-windows-gnu',
             '--semantics-dir', args.semantics_dir])
    manifest = json.loads((out/'guest/manifest.json').read_text())
    if manifest['unsupported_traces'] or manifest['unresolved_direct_targets']:
        raise RuntimeError('NDK fixture has unsupported/unclosed traces')
    loader = out/'elfload.o'
    command(['/mnt/c/mingw64/bin/gcc.exe', '-O2', '-c', hp(source/'fastaes/elfload.c'), '-o', hp(loader)])
    dlls = args.angle/'bundle/bin'
    base = ['/mnt/c/mingw64/bin/g++.exe', '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
            '-isystem', hp(args.remill/'include'), '-I'+hp(out/'guest'),
            '-I'+hp(args.angle/'src/include'),
            '-DGL_FRAMEBUFFER_LIBRARY="'+hp(library)+'"',
            '-DGL_FRAMEBUFFER_DLL_DIRECTORY=L"'+hp(dlls)+'"']
    objects = []
    for relative in ('windows/gl_framebuffer_test.cpp', 'windows/gl_host.cpp',
                     'windows/egl_host.cpp', 'windows/native_window.cpp',
                     'windows/jni_host.cpp', 'whole/runtime.cpp'):
        file = source/relative
        obj = out/(file.stem+'.o')
        strict = ['-Wall', '-Wextra', '-Werror'] if file.stem in ('gl_framebuffer_test', 'gl_host') else []
        command([*base, *strict, '-c', hp(file), '-o', hp(obj)])
        objects.append(obj)
    binary = out/'test.exe'
    link = [base[0], '-static', *map(hp, objects), hp(loader),
            *map(hp, manifest['objects']), '-pthread', '-latomic', '-luser32', '-o', hp(binary)]
    command(link)
    run = subprocess.run([str(binary)], timeout=120, capture_output=True, text=True)
    (out/'stdout.txt').write_text(run.stdout)
    (out/'stderr.txt').write_text(run.stderr)
    print(run.stdout, end='')
    print(run.stderr, end='', file=sys.stderr)
    for relative, expected in source_pins.items():
        if digest(source/relative) != expected:
            raise RuntimeError('Frozen source changed: '+relative)
    proof = dict(passed=run.returncode == 0, exit_code=run.returncode,
                 stdout=run.stdout, stderr=run.stderr, traces=len(manifest['traces']),
                 unsupported=manifest['unsupported_traces'],
                 unresolved=manifest['unresolved_direct_targets'],
                 source_sha256=source_pins,
                 controller_sha256=digest(out/'executed-controller.py'),
                 binary_sha256=digest(binary), fixture_sha256=digest(library),
                 driver_sha256={file.name: digest(file) for file in dlls.glob('*.dll')},
                 toolchain=manifest['toolchain'], build_command=link,
                 limits=['No ARM GPU reference or game/window presentation.',
                         'Native-only fixture texture creation and FBO pixel observer.',
                         'Existing guest readPixels restrictions and capture code unchanged.'])
    (out/'acceptance.json').write_text(json.dumps(proof, indent=2)+'\n')
    run.check_returncode()


if __name__ == '__main__':
    main()
