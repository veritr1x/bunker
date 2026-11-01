"""Translate a real NDK native-window caller; run against hidden actual Win32 windows."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--cxx',default='clang++-18')
    a=p.parse_args();out=HERE.parent/'work/native-window';out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'window.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(HERE/'native_window_guest.c'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(a.lift),
                    '--cxx',a.cxx,'--base','0x5e000000','--target','x86_64-w64-windows-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
    loader=out/'elfload.o';subprocess.run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/'test.exe'
    base=['/mnt/c/mingw64/bin/g++.exe','-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',
          '-isystem',hp(a.remill/'include'),f'-I{hp(out/"guest")}',f'-DNATIVE_WINDOW_LIBRARY="{hp(library)}"']
    objects=[]
    for source in [HERE/'native_window_test.cpp',HERE/'native_window.cpp',HERE/'jni_host.cpp',HERE.parent/'whole/runtime.cpp']:
        obj=out/(source.stem+'.o');strict=['-Wall','-Wextra','-Werror']if source.stem.startswith('native_window')else[]
        subprocess.run([*base,*strict,'-c',hp(source),'-o',hp(obj)],check=True);objects.append(obj)
    subprocess.run([base[0],'-static',*map(hp,objects),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic','-luser32','-o',hp(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=35)


if __name__=='__main__':main()
