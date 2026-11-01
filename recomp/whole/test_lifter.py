"""Regression checks for binary input, recursive callees and multi-entry lifting."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lift', type=Path, required=True)
    args = parser.parse_args()
    checks = 0
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        raw = root / 'input.bin'
        # entry: save LR; call helper; restore LR; ret. helper: add x0,#1; ret.
        code = bytes.fromhex('fd7bbfa903000094fd7bc1a8c0035fd600040091c0035fd6')
        raw.write_bytes(code + bytes(200000))  # Above Linux's per-argument limit.
        ir, trace_list = root / 'out.ll', root / 'traces.txt'
        common = [str(args.lift), '--arch', 'aarch64', '--os', 'linux', '--address', '268435456']
        def run(extra, expected=True):
            nonlocal checks
            result = subprocess.run(common + extra, capture_output=True, text=True)
            if (result.returncode == 0) != expected:
                raise RuntimeError(f'Unexpected lifter result {result.returncode}: {result.stderr}')
            checks += 1
            return result
        def definitions():
            return set(re.findall(r'^define[^\n]*@sub_([0-9a-f]+)\(', ir.read_text(), re.M))
        run(['--bytes_file', str(raw), '--ir_out', str(ir)])
        assert definitions() == {'10000000'}
        assert '@sub_10000010(' in ir.read_text()
        run(['--bytes_file', str(raw), '--lift_calls', '--ir_out', str(ir)])
        assert definitions() == {'10000000', '10000010'}
        seeds = root / 'entries.txt'
        seeds.write_text('0x10000000\n268435472\n0x10000000\n')
        run(['--bytes_file', str(raw), '--entry_addresses_file', str(seeds),
             '--ir_out', str(ir), '--trace_list_out', str(trace_list)])
        assert definitions() == {'10000000', '10000010'}
        assert trace_list.read_text().splitlines() == ['0x10000000', '0x10000010']
        seeds.write_text('0268435456\n')  # Decimal with a leading zero, not octal.
        run(['--bytes_file', str(raw), '--entry_addresses_file', str(seeds), '--ir_out', str(ir)])
        assert definitions() == {'10000000'}
        run(['--bytes', code.hex(), '--lift_calls', '--ir_out', str(ir)])
        assert definitions() == {'10000000', '10000010'}
        run([], False)
        run(['--bytes', 'abc'], False)
        run(['--bytes', 'zz'], False)
        run(['--bytes', '-1'], False)
        run(['--bytes', '+1'], False)
        run(['--bytes', ' a'], False)
        run(['--bytes_file', str(raw), '--bytes', code.hex()], False)
        run(['--bytes_file', str(root / 'missing.bin')], False)
        empty = root / 'empty.bin'
        empty.touch()
        run(['--bytes_file', str(empty)], False)
        for invalid in ('', '-1', '0x10000000junk', '18446744073709551616', '0x20000000'):
            seeds.write_text(invalid)
            run(['--bytes_file', str(raw), '--entry_addresses_file', str(seeds)], False)
        run(['--bytes_file', str(raw), '--address', '18446744073709551612'], False)
        run(['--bytes_file', str(raw), '--trace_list_out', str(root)], False)
        run(['--bytes_file', str(raw), '--semantics_dir', str(root)], False)
        tail = root / 'tail.bin'
        tail.write_bytes(bytes.fromhex('040000141f2003d51f2003d51f2003d500040091c0035fd6'))
        run(['--bytes_file', str(tail), '--ir_out', str(ir)])
        assert definitions() == {'10000000'} and '@sub_10000010(' not in ir.read_text()
        heads = root / 'heads.txt'
        heads.write_text('0x10000010\n')
        run(['--bytes_file', str(tail), '--trace_heads_file', str(heads), '--ir_out', str(ir)])
        assert definitions() == {'10000000'} and 'declare' in ir.read_text() and '@sub_10000010(' in ir.read_text()
    print(f'{checks} lifter regression checks passed.')


if __name__ == '__main__':
    main()
