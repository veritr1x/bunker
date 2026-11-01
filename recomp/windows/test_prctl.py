"""Strict NDK variadic PR_SET_NAME callers against real Windows descriptions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--remill',type=Path,default=Path('/home/sattam/bunker-recomp/recomp/work/remill-src'))
    args=parser.parse_args();out=HERE.parent/'work/prctl';out.mkdir(exist_ok=True,parents=True)
    cc=args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    guest=out/'prctl.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(HERE/'prctl_guest.c'),'-o',str(guest)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(guest),'--out',str(out/'guest'),'--lift',str(args.lift),'--cxx','clang++-18','--base','0x5b000000','--target','x86_64-w64-windows-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
    loader=out/'elfload.o';subprocess.run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/'test.exe'
    command=['/mnt/c/mingw64/bin/g++.exe','-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(args.remill/'include'),'-I'+hp(out/'guest'),f'-DPRCTL_GUEST_IMAGE="{hp(guest)}"',hp(HERE/'prctl_test.cpp'),hp(HERE/'pthread_host.cpp'),hp(HERE.parent/'whole/runtime.cpp'),hp(loader),*map(hp,manifest['objects']),'-static','-pthread','-latomic','-o',hp(binary)]
    subprocess.run(command,check=True)
    run=subprocess.run([str(binary)],check=True,timeout=60,capture_output=True,text=True)
    print(run.stdout,end='');print(run.stderr,end='',file=sys.stderr)
    (out/'stdout.log').write_text(run.stdout)
    (out/'stderr.log').write_text(run.stderr)
    sources=[HERE/name for name in ('pthread_host.h','pthread_host.cpp','prctl_guest.c','prctl_test.cpp','test_prctl.py')]
    (out/'acceptance.json').write_text(json.dumps({
        'passed':True,'stdout':run.stdout,'stderr':run.stderr,'traces':len(manifest['traces']),
        'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets'],
        'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'build_command':command,
        'primary_semantics':[
            'https://raw.githubusercontent.com/torvalds/linux/master/kernel/sys.c',
            'https://raw.githubusercontent.com/aosp-mirror/platform_bionic/master/libc/include/sys/prctl.h'],
        'boundary':'PR_SET_NAME only; strict UTF8 after15-byte truncation; other options explicit ENOSYS; no Linux PID namespace or scheduling effects; invalid nonnull pointers remain outside the provider memory contract',
    },indent=2)+'\n')
    print(f'Strict PR_SET_NAME fixture: {len(manifest["traces"])} traces, zero unsupported/unresolved')


if __name__=='__main__':main()
