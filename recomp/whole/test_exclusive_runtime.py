"""Check persistent reservations and synchronized host/guest memory access."""
import argparse
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', action='store_true')
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--mingw', type=Path, default=Path('/mnt/c/mingw64/bin'))
    args = parser.parse_args()
    out = HERE.parent / 'work/exclusive-runtime'
    out.mkdir(parents=True, exist_ok=True)
    def host(path):
        return subprocess.check_output(['wslpath', '-m', str(Path(path).resolve())], text=True).strip() if args.windows else str(path)
    binary = out / ('exclusive.exe' if args.windows else 'exclusive')
    cxx = args.mingw / 'g++.exe' if args.windows else args.cxx
    command = [str(cxx), '-O2', '-std=c++17', '-pthread', '-DADDRESS_SIZE_BITS=64',
               f'-I{host(HERE.parent / "work/remill-src/include")}', f'-I{host(HERE)}',
               host(HERE / 'exclusive_runtime_test.cpp'), host(HERE / 'runtime.cpp'),
               '-latomic', '-o', host(binary)]
    if args.windows:
        command.insert(1, '-static')
    subprocess.run(command, check=True)
    subprocess.run([str(binary)], check=True)
    for argument, reason in [('alignment', b'unaligned exclusive access'), ('width', b'unsupported exclusive access width'),
                             ('pair-align', b'unaligned exclusive access'), ('pair-width', b'unsupported exclusive pair element width'),
                             ('pair-null', b'invalid exclusive pair output')]:
        result = subprocess.run([str(binary), argument], capture_output=True)
        assert result.returncode and reason in result.stderr, (result.returncode, result.stderr)
    print('Exclusive alignment/unsupported-width rejection checks passed.')


if __name__ == '__main__':
    main()
