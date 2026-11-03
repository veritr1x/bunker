"""Real Windows Vulkan typed draw commands through strict Android NDK callers."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--lift', type=Path, required=True)
    p.add_argument('--semantics-dir', type=Path)
    p.add_argument('--regressions', action='store_true', help='Run existing query/scalar/EGL fixtures against the same frozen providers')
    p.add_argument('--remill', type=Path, default=HERE.parent/'work/remill-src')
    p.add_argument('--support-source', type=Path, default=HERE.parent,
                   help='Live owned files and central composition to overlay on the committed support archive')
    p.add_argument('--support-commit', default='1c5c247fa310e3a567b959181148490a5fc56ee3')
    p.add_argument('--out', type=Path, required=True, help='Fresh directory; historical gl-draw is never reused')
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
    def hp(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip()
    repo = hp(a.support_source.resolve().parent)
    commit = subprocess.check_output(['git.exe', '-C', repo, 'rev-parse', a.support_commit], text=True).strip()
    archive = subprocess.check_output(['git.exe', '-C', repo, 'archive', commit,
                                       'recomp/windows', 'recomp/whole', 'recomp/fastaes'])
    (out/'support.tar').write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert tar.pax_headers.get('comment') == commit
        tar.extractall(out/'source', filter='data')
    source = out/'source/recomp'
    old_cpp = (source/'windows/gl_host.cpp').read_text()
    groups = ('texture', 'uniform', 'framebuffer', 'misc', 'indexed',
              'internalformat', 'sampler', 'buffer_indexed')
    draw = re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types', old_cpp, re.S)
    assert draw
    old_names = ['glGetString', 'glGetStringi', 'glGetIntegerv', 'glGetFloatv', 'glGetBooleanv', 'glGetError']
    old_names += re.findall(r'GL_SCALAR\((gl\w+),', (source/'windows/gl_scalar_commands.inc').read_text())
    old_names += re.findall(r'X\((gl\w+),', draw[1])
    old_fragments = {}
    for group in groups:
        old_names += re.findall(r'GL_'+group.upper()+r'_COMMAND\((gl\w+),', (source/'windows'/('gl_'+group+'_commands.inc')).read_text())
        for kind in ('commands', 'impl'):
            file = source/'windows'/('gl_'+group+'_'+kind+'.inc')
            old_fragments[file.name] = digest(file)
    assert len(old_names) == len(set(old_names)) == 121
    (out/'gl_draw_old_commands.h').write_text('#pragma once\nstatic const char*const kOldDrawCommands[]={'+','.join(map(json.dumps, old_names))+'};\n')
    owned = ('gl_object_commands.inc', 'gl_draw_guest.c', 'gl_draw_test.cpp', 'test_gl_draw.py')
    composition = {'gl_host.cpp', 'gl_host.h', 'gl_scalar_commands.inc'} | {
        file.name for pattern in ('gl_*_commands.inc', 'gl_*_impl.inc') for file in HERE.glob(pattern)}
    for name in set(owned) | composition:
        shutil.copyfile(HERE/name, source/'windows'/name)
    for name, expected in old_fragments.items():
        assert digest(source/'windows'/name) == expected, name
    protected = {name: digest(source/name) for name in ('whole/runtime.cpp', 'whole/runtime.h',
                 'windows/egl_host.cpp', 'windows/egl_host.h', 'windows/jni_host.cpp', 'windows/jni_host.h')}
    for name, expected in protected.items():
        assert digest(a.support_source/name) == expected, name
    assert protected['whole/runtime.cpp'] == '56c28270e218dcb62ddecc6048dda9e9e727a876478eaa4b0f87823881c5ace1'
    new_cpp = (source/'windows/gl_host.cpp').read_text()
    blocks = ['#define GL_OBJECT_COMMAND(name,native_type,signature) #name,\n#include "gl_object_commands.inc"\n#undef GL_OBJECT_COMMAND\n',
              '#define GL_OBJECT_COMMAND(name,native_type,signature) {using GuestSignature=signature;static_assert(std::is_same_v<native_type,GuestSignature*>);Bind<signature>(#name,Symbol<native_type>(module,#name));}\n#include "gl_object_commands.inc"\n#undef GL_OBJECT_COMMAND\n']
    projected = new_cpp
    for block in blocks:
        assert projected.count(block) == 1
        projected = projected.replace(block, '', 1)
    assert projected == old_cpp, 'unexpected production change outside six registration lines'
    pattern = r'const std::vector<GlHost::Query> queries=\{(.*?)\n\};'
    assert re.search(pattern, old_cpp, re.S)[1] == re.search(pattern, new_cpp, re.S)[1]
    source_pins = {str(file.relative_to(source)): digest(file) for file in source.rglob('*') if file.is_file()}
    live_pins = {str(HERE/name): digest(HERE/name) for name in set(owned) | composition}
    (out/'source-pin.json').write_text(json.dumps(dict(commit=commit, archive_sha256=digest(out/'support.tar'),
        sources=source_pins, live=live_pins, protected=protected, old_fragments=old_fragments,
        owned={name: digest(source/'windows'/name) for name in owned},
        composition={name: digest(source/'windows'/name) for name in sorted(composition)}), indent=2)+'\n')
    cc = a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    semantics = a.semantics_dir or (a.lift.parent if (a.lift.parent/'aarch64.bc').is_file() else None)
    assert semantics is not None
    angle = HERE.parent/'work/angle-native'
    dlls = angle/'bundle/bin'
    input_pins = {str(file.resolve()): digest(file.resolve()) for file in
                  (cc, a.lift, semantics/'aarch64.bc', Path('/mnt/c/mingw64/bin/g++.exe'),
                   Path('/mnt/c/mingw64/bin/gcc.exe'), Path(shutil.which('clang++-18')))}
    for directory in (a.remill/'include', angle/'src/include', dlls):
        for file in directory.rglob('*'):
            if file.is_file():
                input_pins[str(file)] = digest(file)
    (out/'tool-inputs.json').write_text(json.dumps(input_pins, indent=2)+'\n')
    library = out/'draw.so'
    subprocess.run([str(cc), '-Wall', '-Wextra', '-Werror', '-shared', '-nostdlib', '-fPIC', '-O1',
                    '-fno-stack-protector', '-fno-builtin',
                    str(source/'windows/gl_draw_guest.c'), '-o', str(library)], check=True)
    subprocess.run([sys.executable, str(source/'whole/compile.py'), str(library),
                    '--out', str(out/'guest'), '--lift', str(a.lift), '--cxx', 'clang++-18',
                    '--base', '0x5b000000', '--target', 'x86_64-w64-windows-gnu',
                    *(['--semantics-dir', str(semantics)] if semantics else [])], check=True)
    manifest = json.loads((out/'guest/manifest.json').read_text())
    assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    loader = out/'elfload.o'
    subprocess.run(['/mnt/c/mingw64/bin/gcc.exe', '-O2', '-c',
                    hp(source/'fastaes/elfload.c'), '-o', hp(loader)], check=True)
    base = ['/mnt/c/mingw64/bin/g++.exe', '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
            '-isystem', hp(a.remill/'include'), '-I'+hp(out/'guest'), '-I'+hp(out), '-I'+hp(angle/'src/include'),
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
               *map(hp, manifest['objects']), '-pthread', '-latomic', '-luser32', '-lgdi32', '-lole32', '-luuid', '-o', hp(binary)]
    subprocess.run(command, check=True)
    run = subprocess.run([str(binary)], timeout=120, capture_output=True, text=True)
    print(run.stdout, end='')
    print(run.stderr, end='', file=sys.stderr)
    (out/'stdout.txt').write_text(run.stdout)
    (out/'stderr.txt').write_text(run.stderr)
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
            if test == 'gl_host_test':
                catalog = re.search(pattern, new_cpp, re.S)[1]
                start = catalog.index('  {GL_RED_BITS,1},')
                (out/'gl_query_expected.h').write_text('#pragma once\nstatic const bunker::windows::GlHost::Query kOldQueries[]={'+catalog[:start]+'\n};\nstatic const GLenum kAddedScalarQueries[]={0xd52,0xd53,0xd54,0xd55,0xd56,0xd57};\n')
            regression_base = [item for item in base if not item.startswith('-DGL_DRAW_')]
            regression_base = [('-I'+hp(previous/'guest')) if item == '-I'+hp(out/'guest') else item for item in regression_base]
            regression_base += [f'-D{prefix}_LIBRARY="{hp(previous/lib)}"', f'-D{prefix}_DLL_DIRECTORY=L"{hp(dlls)}"']
            obj = out/(test+'-regression.o')
            subprocess.run([*regression_base, '-Wall', '-Wextra', '-Werror', '-c', hp(target), '-o', hp(obj)], check=True)
            exe = out/(test+'-regression.exe')
            subprocess.run([base[0], '-static', hp(obj), *map(hp, objects[1:]), hp(loader),
                            *map(hp, prior['objects']), '-pthread', '-latomic', '-luser32', '-lgdi32', '-lole32', '-luuid', '-o', hp(exe)], check=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            print(result.stdout, end='');print(result.stderr, end='', file=sys.stderr);result.check_returncode()
            regressions.append(dict(test=test, stdout=result.stdout, stderr=result.stderr,
                                    binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                                    fixture_sha256=hashlib.sha256((previous/lib).read_bytes()).hexdigest()))
    for name, expected in source_pins.items():
        assert digest(source/name) == expected, name
    for name, expected in live_pins.items():
        assert digest(Path(name)) == expected, name
    for name, expected in input_pins.items():
        assert digest(Path(name)) == expected, name
    proof = dict(passed=True, stdout=run.stdout, stderr=run.stderr, regressions=regressions,
                 commit=commit, owned_sources={name: digest(source/'windows'/name) for name in owned},
                 composition_sources={name: digest(source/'windows'/name) for name in sorted(composition)},
                 protected_sources=protected, source_pin_sha256=digest(out/'source-pin.json'),
                 tool_inputs_sha256=digest(out/'tool-inputs.json'),
                 traces=len(manifest['traces']), unsupported=manifest['unsupported_traces'],
                 unresolved=manifest['unresolved_direct_targets'], binary_sha256=digest(binary),
                 source_sha256={str(f.relative_to(source)): digest(f) for f in source.rglob('*') if f.is_file()},
                 driver_sha256={f.name: digest(f) for f in dlls.glob('*.dll')},
                 toolchain=manifest['toolchain'], build_command=command,
                 boundary='Existing typed shader/program/VBO/VAO draws and in-bounds default-pbuffer readback plus one native GLboolean VAO predicate; real NDK direct/pointer/procedure calls and lifecycle oracle. No guest compute execution, client/mapped memory expansion or game/presented-frame claim.')
    (out/'acceptance.json').write_text(json.dumps(proof, indent=2)+'\n')


if __name__ == '__main__':
    main()
