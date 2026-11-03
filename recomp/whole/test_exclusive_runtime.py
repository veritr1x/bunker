"""Check persistent reservations and synchronized host/guest memory access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--remill-include', type=Path, default=HERE.parent / 'work/remill-src/include')
    args = parser.parse_args()
    out = args.out.resolve() if args.out else HERE.parent / 'work/exclusive-runtime'
    out.mkdir(parents=True, exist_ok=args.out is None)
    def sha(path):
        with Path(path).open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    sources = {str(HERE / name): sha(HERE / name) for name in
               ('runtime.cpp', 'runtime.h', 'exclusive_runtime_test.cpp', 'test_exclusive_runtime.py')}
    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    binary = out / ('exclusive.exe' if args.windows else 'exclusive')
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    command = [str(cxx), '-O2', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread', '-DADDRESS_SIZE_BITS=64',
               '-isystem', host(args.remill_include), f'-I{host(HERE)}',
               host(HERE / 'exclusive_runtime_test.cpp'), host(HERE / 'runtime.cpp'),
               '-latomic', '-o', host(binary)]
    if args.windows:
        command.insert(1, '-static')
        # Existing Remill declarations use Clang-specific inline attributes.
        command.insert(1, '-Wno-attributes')
    elif 'clang' in str(cxx):
        # The unchanged 16-byte operations deliberately use linked libatomic.
        command.insert(1, '-Wno-atomic-alignment')
    (out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    compiled = subprocess.run(command, capture_output=True)
    (out / 'compile.stdout').write_bytes(compiled.stdout)
    (out / 'compile.stderr').write_bytes(compiled.stderr)
    assert compiled.returncode == 0, (compiled.returncode, compiled.stderr)
    positive = subprocess.run([str(binary)], capture_output=True)
    (out / 'positive.stdout').write_bytes(positive.stdout)
    (out / 'positive.stderr').write_bytes(positive.stderr)
    assert positive.returncode == 0 and re.search(rb'\d+ exclusive runtime checks passed', positive.stdout)
    print(positive.stdout.decode(), end='')
    def aborted(returncode):
        # Windows execution is through WSL interoperability, which reports
        # either CRT exit3 or status9; neither is a full native DWORD witness.
        return returncode in (3, 9) if args.windows else returncode == -signal.SIGABRT
    negatives = {}
    for argument, reason in [('alignment', b'unaligned exclusive access'), ('width', b'unsupported exclusive access width'),
                             ('pair-align', b'unaligned exclusive access'), ('pair-width', b'unsupported exclusive pair element width'),
                             ('pair-null', b'invalid exclusive pair output')]:
        result = subprocess.run([str(binary), argument], capture_output=True)
        (out / (argument + '.stdout')).write_bytes(result.stdout)
        (out / (argument + '.stderr')).write_bytes(result.stderr)
        assert aborted(result.returncode) and reason in result.stderr, (result.returncode, result.stderr)
        negatives[argument] = dict(returncode=result.returncode, reason=reason.decode())
    diagnostic_cases = {
        'unresolved-zero': (0, 0x1234567876543210, 0x2345678987654321, 0x3456789a98765432),
        'unresolved-nonzero': (0x456789ab89abcdef, 0x56789abc9abcdef0, 0x6789abcdaabcdef1, 0x789abcdebbcdef12),
    }
    diagnostics = {}
    for argument, (target, pc, lr, sp) in diagnostic_cases.items():
        result = subprocess.run([str(binary), argument], capture_output=True)
        (out / (argument + '.stdout')).write_bytes(result.stdout)
        (out / (argument + '.stderr')).write_bytes(result.stderr)
        # C %#llx prints zero as "0", unlike Python's %#x.
        number = lambda value: hex(value) if value else '0'
        context = ('recomp: unresolved indirect context target=%s StatePC=%s LR=%s SP=%s' %
                   tuple(number(value) for value in (target, pc, lr, sp)))
        previous = 'recomp: unresolved indirect target at ' + number(target)
        lines = result.stderr.decode().splitlines()
        assert aborted(result.returncode), result.returncode
        assert lines.count(context) == lines.count(previous) == 1 and lines.index(context) < lines.index(previous), lines
        diagnostics[argument] = dict(returncode=result.returncode, target=target, StatePC=pc, LR=lr, SP=sp,
                                    context=context, unchanged_fatal_line=previous)
    for path, digest in sources.items():
        assert sha(path) == digest, path
    receipt = dict(passed=True, platform='windows' if args.windows else 'linux',
                   sources=sources, strict_source=True, executable_sha256=sha(binary),
                   positive_returncode=positive.returncode, positive_stdout=positive.stdout.decode(),
                   legacy_negatives=negatives, diagnostics=diagnostics,
                   evidence={str(path): sha(path) for path in out.iterdir() if path.is_file()},
                   limits='Native Runtime dispatch/error diagnostics only; Windows process returncode is WSL interoperability status, not a full native DWORD witness. No guest ISA, GPU, collector or game execution.')
    (out / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Exclusive alignment/unsupported-width rejection checks passed.')
    print('Unresolved zero/nonzero full64 State diagnostics passed.')


if __name__ == '__main__':
    main()
