"""Focused cross-thread reservation/ABA gates for actual LibC and Zlib providers."""
import argparse
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--cxx',default='clang++-18')
    a=p.parse_args()
    backend=HERE.parent/('work/zlib-native' if a.windows else 'work/zlib-linux/backend')
    out=HERE.parent/('work/provider-memory-windows' if a.windows else 'work/provider-memory-linux');out.mkdir(parents=True,exist_ok=True)
    def hp(path):
        if a.windows:return subprocess.check_output(['wslpath','-m',str(path.resolve())],text=True).strip()
        return str(path)
    cxx='/mnt/c/mingw64/bin/g++.exe' if a.windows else a.cxx
    binary=out/('test.exe' if a.windows else 'test')
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(backend/"zlib-1.3.2")}',
             hp(HERE/'libc_zlib_memory_test.cpp'),hp(HERE/'libc.cpp'),hp(HERE/'zlib_host.cpp'),hp(HERE.parent/'whole/runtime.cpp'),hp(backend/'libz-inflate.a'),'-latomic','-pthread','-o',hp(binary)]
    if a.windows:command.insert(1,'-static')
    subprocess.run(command,check=True);subprocess.run([str(binary)],check=True,timeout=90)


if __name__=='__main__':main()
