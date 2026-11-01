"""Run actual NDK format-only native-window changes against real Vulkan window configs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    parser.add_argument('--cxx',default='clang++-18')
    args=parser.parse_args();out=HERE.parent/'work/egl-format';out.mkdir(parents=True,exist_ok=True)
    cc=args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'formats.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(HERE/'egl_format_guest.c'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(args.lift),
                    '--cxx',args.cxx,'--base','0x5b000000','--target','x86_64-w64-windows-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
    loader=out/'elfload.o';subprocess.run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/'test.exe';dlls=HERE.parent/'work/angle-native/bundle/bin'
    base=['/mnt/c/mingw64/bin/g++.exe','-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(args.remill/'include'),f'-I{hp(out/"guest")}',
          f'-DEGL_HOST_LIBRARY="{hp(library)}"',f'-DEGL_HOST_DLL_DIRECTORY=L"{hp(dlls)}"']
    objects=[]
    for source in [HERE/'egl_format_test.cpp',HERE/'egl_host.cpp',HERE/'native_window.cpp',HERE/'jni_host.cpp',HERE.parent/'whole/runtime.cpp']:
        obj=out/(source.stem+'.o');strict=['-Wall','-Wextra','-Werror']if source.stem in ('egl_host','egl_format_test','native_window')else[]
        subprocess.run([*base,*strict,'-c',hp(source),'-o',hp(obj)],check=True);objects.append(obj)
    subprocess.run([base[0],'-static',*map(hp,objects),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic','-luser32','-o',hp(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=65)


if __name__=='__main__':main()
