"""Real Windows Vulkan typed draw commands through strict Android NDK callers."""
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
    p.add_argument('--regressions', action='store_true', help='Run existing query/scalar/EGL fixtures against the same frozen providers')
    p.add_argument('--remill', type=Path, default=HERE.parent/'work/remill-src')
    p.add_argument('--support-source', type=Path, default=HERE.parent,
                   help='Recomp support source to freeze before building')
    a = p.parse_args()
    out = HERE.parent/'work/gl-draw'
    out.mkdir(parents=True, exist_ok=True)
    source = out/'source'
    for directory in ('windows', 'whole', 'fastaes'):
        target = source/directory
        target.mkdir(parents=True, exist_ok=True)
        for file in (a.support_source/directory).iterdir():
            if file.is_file() and file.suffix in ('.h', '.cpp', '.c', '.inc'):
                shutil.copyfile(file, target/file.name)
    for name in ('gl_host.cpp', 'gl_host.h', 'egl_host.cpp', 'egl_host.h', 'gl_scalar_commands.inc', 'gl_draw_commands.inc', 'gl_draw_fixture.h',
                 'gl_draw_guest.c', 'gl_draw_test.cpp'):
        shutil.copyfile(HERE/name, source/'windows'/name)
    cc = a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library = out/'draw.so'
    subprocess.run([str(cc), '-shared', '-nostdlib', '-fPIC', '-O1',
                    '-fno-stack-protector', '-fno-builtin',
                    str(source/'windows/gl_draw_guest.c'), '-o', str(library)], check=True)
    semantics = a.semantics_dir or (a.lift.parent if (a.lift.parent/'aarch64.bc').is_file() else None)
    subprocess.run([sys.executable, str(HERE.parent/'whole/compile.py'), str(library),
                    '--out', str(out/'guest'), '--lift', str(a.lift), '--cxx', 'clang++-18',
                    '--base', '0x5b000000', '--target', 'x86_64-w64-windows-gnu', '--resume',
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
            f'-DGL_DRAW_LIBRARY="{hp(library)}"', f'-DGL_DRAW_DLL_DIRECTORY=L"{hp(dlls)}"']
    objects = []
    for rel in ('windows/gl_draw_test.cpp', 'windows/gl_host.cpp', 'windows/egl_host.cpp',
                'windows/native_window.cpp', 'windows/jni_host.cpp', 'whole/runtime.cpp'):
        file = source/rel
        obj = out/(file.stem+'.o')
        strict = ['-Wall', '-Wextra', '-Werror'] if file.stem in ('gl_draw_test', 'gl_host') else []
        subprocess.run([*base, *strict, '-c', hp(file), '-o', hp(obj)], check=True)
        objects.append(obj)
    binary = out/'test.exe'
    command = [base[0], '-static', *map(hp, objects), hp(loader),
               *map(hp, manifest['objects']), '-pthread', '-latomic', '-luser32', '-o', hp(binary)]
    subprocess.run(command, check=True)
    run = subprocess.run([str(binary)], timeout=120, capture_output=True, text=True)
    print(run.stdout, end='')
    print(run.stderr, end='', file=sys.stderr)
    run.check_returncode()
    regressions = []
    if a.regressions:
        for folder, test, prefix, lib in (('gl-host', 'gl_host_test', 'GL_HOST', 'queries.so'),
                                        ('gl-scalar', 'gl_scalar_test', 'GL_SCALAR', 'scalar.so'),
                                        ('egl-host', 'egl_host_test', 'EGL_HOST', 'egl.so')):
            previous = HERE.parent/'work'/folder
            prior = json.loads((previous/'guest/manifest.json').read_text())
            assert not prior['unsupported_traces'] and not prior['unresolved_direct_targets']
            target = source/'windows'/(test+'.cpp')
            shutil.copyfile(HERE/target.name, target)
            # The scalar test includes its unchanged C oracle and catalogue.
            if test == 'gl_scalar_test':
                shutil.copyfile(HERE/'gl_scalar_guest.c', source/'windows/gl_scalar_guest.c')
            regression_base = [item for item in base if not item.startswith('-DGL_DRAW_')]
            regression_base = [('-I'+hp(previous/'guest')) if item == '-I'+hp(out/'guest') else item for item in regression_base]
            regression_base += [f'-D{prefix}_LIBRARY="{hp(previous/lib)}"', f'-D{prefix}_DLL_DIRECTORY=L"{hp(dlls)}"']
            obj = out/(test+'-regression.o')
            subprocess.run([*regression_base, '-Wall', '-Wextra', '-Werror', '-c', hp(target), '-o', hp(obj)], check=True)
            exe = out/(test+'-regression.exe')
            subprocess.run([base[0], '-static', hp(obj), *map(hp, objects[1:]), hp(loader),
                            *map(hp, prior['objects']), '-pthread', '-latomic', '-luser32', '-o', hp(exe)], check=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            print(result.stdout, end='');print(result.stderr, end='', file=sys.stderr);result.check_returncode()
            regressions.append(dict(test=test, stdout=result.stdout, stderr=result.stderr,
                                    binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                                    fixture_sha256=hashlib.sha256((previous/lib).read_bytes()).hexdigest()))
    digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
    proof = dict(passed=True, stdout=run.stdout, stderr=run.stderr, regressions=regressions,
                 traces=len(manifest['traces']), unsupported=manifest['unsupported_traces'],
                 unresolved=manifest['unresolved_direct_targets'], binary_sha256=digest(binary),
                 source_sha256={str(f.relative_to(source)): digest(f) for f in source.rglob('*') if f.is_file()},
                 driver_sha256={f.name: digest(f) for f in dlls.glob('*.dll')},
                 toolchain=manifest['toolchain'], build_command=command,
                 boundary='Typed shader/program/VBO/VAO draws and in-bounds RGBA8 default-pbuffer readback; no mapped/client/texture/uniform/FBO APIs, compute execution or game frame.')
    (out/'acceptance.json').write_text(json.dumps(proof, indent=2)+'\n')


if __name__ == '__main__':
    main()
