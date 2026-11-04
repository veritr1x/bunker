"""Build and exercise explicit guest call/return routing (no game required)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def native(path, platform):
    path = Path(path).resolve()
    if platform == 'windows' and os.name != 'nt':
        return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--remill-include', type=Path, required=True)
    parser.add_argument('--platform', choices=('linux', 'windows', 'both'),
                        default='windows' if os.name == 'nt' else 'linux')
    parser.add_argument('--linux-cxx', default='clang++-18')
    parser.add_argument('--windows-cxx', default='C:/mingw64/bin/g++.exe' if os.name == 'nt'
                        else '/mnt/c/mingw64/bin/g++.exe')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    here = Path(__file__).resolve().parent
    sources = [here/name for name in ('runtime.h', 'runtime.cpp', 'cooperative_poll.h',
                                      'cooperative_poll.cpp', 'guest_call_transfer_test.cpp')]
    pins = {str(path): sha(path) for path in sources+[Path(__file__)]}
    commands = []
    results = {}
    negatives = {
        'unknown': 'unselectable guest resume target',
        'no-owner': 'guest transfer has no owner in this Run',
        'cross-state': 'guest call outside its active Run/State',
        'same-state-escape': 'guest transfer has no owner in this Run',
        'stale-token': 'pending guest transfer State/token changed during propagation',
        'wrong-thread': 'guest call outside its active Run/State',
        'outside-run': 'guest call outside its active Run/State',
    }
    platforms = ('linux', 'windows') if args.platform == 'both' else (args.platform,)
    try:
        for platform in platforms:
            compiler = args.windows_cxx if platform == 'windows' else args.linux_cxx
            exe = out/('transfer-'+platform+('.exe' if platform == 'windows' else ''))
            convert = lambda path: native(path, platform)
            command = [compiler, '-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64',
                       '-isystem', convert(args.remill_include), '-I'+convert(here),
                       '-Wall', '-Wextra', '-Werror', '-Wno-attributes',
                       *(['-Wno-atomic-alignment'] if platform == 'linux' and 'clang' in compiler else []),
                       *[convert(here/name) for name in ('runtime.cpp', 'cooperative_poll.cpp',
                                                       'guest_call_transfer_test.cpp')],
                       '-pthread', '-latomic', *(['-static'] if platform == 'windows' else []),
                       '-o', convert(exe)]
            with (out/(platform+'-build.log')).open('x') as log:
                built = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            commands.append(dict(stage=platform+'-build', argv=command, exit_code=built.returncode))
            assert built.returncode == 0, platform+' build failed'
            tests = {}
            for case in ('positive', *negatives):
                command = [str(exe)] + ([] if case == 'positive' else [case])
                run = subprocess.run(command, capture_output=True, text=True)
                (out/(platform+'-'+case+'.stdout')).write_text(run.stdout)
                (out/(platform+'-'+case+'.stderr')).write_text(run.stderr)
                commands.append(dict(stage=platform+'-'+case, argv=command,
                                     exit_code=run.returncode))
                if case == 'positive':
                    assert run.returncode == 0, run.stderr
                    match = re.fullmatch(r'GUEST-CALL-TRANSFER-PASS cases=15 checks=220 '
                                         r'State_bytes=1200 token_bytes=64\s*', run.stdout)
                    assert match, run.stdout
                else:
                    assert run.returncode not in (0, 9) and negatives[case] in run.stderr, (
                        platform, case, run.returncode, run.stderr)
                tests[case] = dict(exit_code=run.returncode, expected_result_observed=True)
            results[platform] = dict(positive_cases=15, checks=220, negative_controls=7,
                                     tests=tests, executable_sha256=sha(exe))
        assert all(sha(path) == digest for path, digest in pins.items())
        record = dict(passed=True, scope='Runtime routing unit tests; no original EH or game claim',
                      owned_sources=pins, results=results, commands=commands)
        (out/'acceptance.json').write_text(json.dumps(record, indent=2)+'\n')
        print('GUEST-CALL-TRANSFER-TEST-PASS', sha(out/'acceptance.json'), flush=True)
    except BaseException as error:
        (out/'failure.json').write_text(json.dumps(dict(passed=False, error=str(error),
            commands=commands, owned_sources=pins), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
