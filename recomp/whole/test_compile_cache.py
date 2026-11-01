"""Verify that long library builds resume safely and repair invalid shards."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--lift', type=Path, required=True)
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--poll-instrument', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory)
        command = [sys.executable, str(HERE / 'compile.py'), str(args.library), '--out', str(out),
                   '--lift', str(args.lift), '--cxx', args.cxx, '--shard-size', '2', '--jobs', '2', '--resume']
        if args.poll_instrument:
            command.extend(['--poll-instrument', str(args.poll_instrument)])
        def run():
            return subprocess.check_output(command, text=True)
        run()
        objects = sorted(out.glob('shard-*.o'))
        assert len(objects) > 1
        initial = {p.name: p.stat().st_mtime_ns for p in objects}
        cached = run()
        assert cached.count('(cached)') == len(objects)
        assert initial == {p.name: p.stat().st_mtime_ns for p in objects}
        damaged = objects[-1]
        original_hash = hashlib.sha256(damaged.read_bytes()).hexdigest()
        damaged.write_bytes(damaged.read_bytes() + b'broken-object')
        repaired = run()
        assert repaired.count('(cached)') == len(objects) - 1
        assert hashlib.sha256(damaged.read_bytes()).hexdigest() == original_hash
        for obj in objects[:-1]:
            assert obj.stat().st_mtime_ns == initial[obj.name]
        damaged.with_suffix('.cache.json').write_text('{partial')
        repaired = run()
        assert repaired.count('(cached)') == len(objects) - 1
        manifest = json.loads((out / 'manifest.json').read_text())
        assert len(manifest['toolchain']['lifter']) == len(manifest['toolchain']['semantics']) == 64
        assert len(list((out / '.toolchain').glob('*/remill-lift'))) == 1
        if args.poll_instrument:
            assert manifest['cooperative_polls'] and manifest['toolchain']['poll_instrument'] == hashlib.sha256(args.poll_instrument.read_bytes()).hexdigest()
            del command[-2:]
            assert '(cached)' not in run(), 'Instrumented objects reused by an uninstrumented build'
            plain = json.loads((out / 'manifest.json').read_text())
            assert not plain['cooperative_polls'] and 'poll_instrument' not in plain['toolchain']
            command.extend(['--poll-instrument', str(args.poll_instrument)])
            assert '(cached)' not in run(), 'Uninstrumented objects reused by an instrumented build'
            assert run().count('(cached)') == len(objects)
    print('Compiler resume checks pass: frozen toolchain, unchanged shards, corrupt object repair, partial-cache recovery.')


if __name__ == '__main__':
    main()
