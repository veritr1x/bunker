"""Isolated Android signal/semaphore policy with real NDK callers and QEMU."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'whole'))
from test_fastaes import build_reference


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--cc',default='clang-18')
    p.add_argument('--cxx',default='clang++-18')
    a=p.parse_args();out=HERE.parent/('work/signal-host-windows'if a.windows else'work/signal-host-linux');out.mkdir(parents=True,exist_ok=True)
    reference=out/'reference'
    build_reference(a.cc,a.reference_root,[HERE/'signal_host_ref.c',HERE/'signal_host_guest.c'],reference)
    raw=subprocess.check_output([str(a.reference_root/'usr/bin/qemu-aarch64-static'),str(reference)],timeout=20)
    (out/'reference.bin').write_bytes(raw)
    count=struct.unpack_from('<I',raw)[0]
    facts=list(struct.iter_unpack('<6q',raw[4+count*8:]))
    expected=[(timed,restart,0 if restart and not timed else -1,0 if restart and not timed else 4,1,0 if restart and not timed else 1)
              for timed in range(2)for restart in range(2)]
    assert facts==expected,(facts,expected)
    print('ARM64 QEMU: untimed SA_RESTART retries; timed/nonrestart semaphore waits return EINTR.',flush=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'policy.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',
                    '-fno-vectorize','-fno-slp-vectorize',str(HERE/'signal_host_guest.c'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(a.lift),
                    '--cxx',a.cxx,'--base','0x5a000000','--target','x86_64-w64-windows-gnu'if a.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if a.windows else str(path)
    hostcc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else a.cc;hostcxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else a.cxx
    loader=out/'elfload.o';subprocess.run([hostcc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/('test.exe'if a.windows else'test')
    command=[hostcxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(out/"guest")}',
             f'-DSIGNAL_HOST_LIBRARY="{hp(library)}"',f'-DSIGNAL_HOST_REFERENCE="{hp(out/"reference.bin")}"',
             hp(HERE/'signal_host_test.cpp'),hp(HERE/'signal_host.cpp'),hp(HERE/'semaphore_host.cpp'),
             hp(HERE.parent/'whole/runtime.cpp'),hp(loader),*[hp(obj)for obj in manifest['objects']],'-pthread','-latomic','-o',hp(binary)]
    if a.windows:command.insert(1,'-static')
    subprocess.run(command,check=True);subprocess.run([str(binary)],check=True,timeout=45)


if __name__=='__main__':main()
