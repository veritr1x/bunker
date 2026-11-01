"""Build the opt-in LLVM18 cooperative poll instrumenter."""
import argparse
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cxx', default='clang++-18')
    parser.add_argument('--llvm-config', default='llvm-config-18')
    args = parser.parse_args()
    version = subprocess.check_output([args.llvm_config, '--version'], text=True).strip()
    if version.split('.')[0] != '18':
        raise SystemExit('This instrumenter requires LLVM18')
    flags = shlex.split(subprocess.check_output([args.llvm_config, '--cxxflags', '--ldflags', '--system-libs',
                                                '--libs', 'core', 'irreader'], text=True))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.cxx, str(Path(__file__).with_name('poll_instrument.cpp')), *flags,
                    '-std=c++17', '-O2', '-o', str(args.out)], check=True)


if __name__ == '__main__':
    main()
