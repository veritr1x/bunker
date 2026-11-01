"""Check pure Android frame bytes with NDK handlers and QEMU signal frames."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
from test_fastaes import build_reference
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--cc',default='clang-18')
    p.add_argument('--cxx',default='clang++-18')
    a=p.parse_args();out=HERE.parent/('work/signal-frame-windows'if a.windows else'work/signal-frame-linux');out.mkdir(parents=True,exist_ok=True)
    reference=out/'reference'
    build_reference(a.cc,a.reference_root,[HERE/'signal_frame_probe.c',HERE/'signal_frame_entry.S'],reference)
    raw=subprocess.check_output([str(a.reference_root/'usr/bin/qemu-aarch64-static'),'-cpu','cortex-a53',str(reference)])
    expected=[1]*7+[0x46508001,528,0,0]+[1]*7+[128,4560,4384,24,16,40,176,8,256,264,272,288,528,16]
    facts=list(struct.iter_unpack('<'+('Q'*len(expected)),raw))
    assert len(facts)==2 and all(list(row)==expected for row in facts),facts
    (out/'qemu-frame-facts.json').write_text(json.dumps({'normal_stack':facts[0],'alternate_stack':facts[1]},indent=2))
    print('Actual ARM64 QEMU SA_SIGINFO frames: normal/alternate stack placement, FP chain, FPSIMD/terminator and wire offsets agree.',flush=True)
    ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'handler.so'
    subprocess.run([str(ndkcc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin','-fno-vectorize','-fno-slp-vectorize',
                    str(HERE/'signal_frame_guest.c'),str(HERE/'signal_frame_entry.S'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(library),'--out',str(out/'guest'),'--lift',str(a.lift),
                    '--cxx',a.cxx,'--base','0x58000000','--target','x86_64-w64-windows-gnu'if a.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['imports'] and not manifest['unsupported_traces']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if a.windows else str(path)
    cc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else a.cc;cxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else a.cxx
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/('test.exe'if a.windows else'test')
    command=[cxx,'-O2','-std=c++17','-DADDRESS_SIZE_BITS=64',f'-DSIGNAL_FRAME_LIBRARY="{hp(library)}"',
             f'-I{hp(a.remill/"include")}',f'-I{hp(out/"guest")}',hp(HERE/'signal_frame_test.cpp'),hp(HERE/'signal_frame.cpp'),
             hp(HERE/'runtime.cpp'),hp(loader),*[hp(obj)for obj in manifest['objects']],'-latomic','-o',hp(binary)]
    if a.windows:command.insert(1,'-static')
    subprocess.run(command,check=True);subprocess.run([str(binary)],check=True,timeout=30)


if __name__=='__main__':main()
