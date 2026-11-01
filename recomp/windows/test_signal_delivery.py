"""Compile optimized worker+NDK signal handlers and exercise real frame delivery."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
WHOLE=HERE.parent/'whole'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--windows',action='store_true')
    parser.add_argument('--cc',default='clang-18')
    parser.add_argument('--cxx',default='clang++-18')
    args=parser.parse_args()
    out=HERE.parent/('work/signal-delivery-windows'if args.windows else'work/signal-delivery-linux');out.mkdir(parents=True,exist_ok=True)
    instrument=out/'poll-instrument'
    subprocess.run([sys.executable,str(WHOLE/'build_poll_instrument.py'),'--out',str(instrument),'--cxx',args.cxx],check=True)
    ndkcc=args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'delivery.so'
    subprocess.run([str(ndkcc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin','-fno-vectorize','-fno-slp-vectorize',
                    str(HERE/'signal_delivery_guest.c'),str(HERE/'signal_delivery_loop.S'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(WHOLE/'compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(args.lift),
                    '--cxx',args.cxx,'--base','0x5c000000','--target','x86_64-w64-windows-gnu'if args.windows else'x86_64-linux-gnu',
                    '--poll-instrument',str(instrument)],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text())
    assert manifest['cooperative_polls'] and not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if args.windows else str(path)
    cc='/mnt/c/mingw64/bin/gcc.exe'if args.windows else args.cc;cxx='/mnt/c/mingw64/bin/g++.exe'if args.windows else args.cxx
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/('test.exe'if args.windows else'test')
    sources=[HERE/'signal_delivery_test.cpp',HERE/'signal_delivery.cpp',HERE/'signal_host.cpp',HERE/'semaphore_host.cpp',
             WHOLE/'signal_frame.cpp',WHOLE/'cooperative_poll.cpp',WHOLE/'runtime.cpp']
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(args.remill/"include")}',f'-I{hp(out/"guest")}',
             f'-DSIGNAL_DELIVERY_LIBRARY="{hp(library)}"',*map(hp,sources),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic','-o',hp(binary)]
    if args.windows:command.insert(1,'-static')
    subprocess.run(command,check=True);subprocess.run([str(binary)],check=True,timeout=45)


if __name__=='__main__':main()
