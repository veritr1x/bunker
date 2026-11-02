"""Fresh, frozen ARM64 NDK alternate-stack and physical mapping lease gate (run in WSL)."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
FILES=['signal_host.h','signal_host.cpp','signal_delivery.h','signal_delivery.cpp',
       'signal_altstack_fixture.h','signal_altstack_guest.c','signal_altstack_mapping.h',
       'signal_altstack_reference.c','signal_altstack_test.cpp','test_signal_altstack.py']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(command,log,**kw):
    with log.open('w') as f:
        result=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,**kw)
    if result.returncode:raise RuntimeError(f'{log}: exit {result.returncode}\n{log.read_text(errors="replace")[-8000:]}')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--host',default='714daef')
    p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
    p.add_argument('--lift',type=Path,default=HERE.parent/'work/fp-fmul-indexed-linux/lifted/.toolchain/78e33b4cc37e8b2d-098d2e4b3214af9b/remill-lift')
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--reference-root',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root'))
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    host=subprocess.check_output(['git','rev-parse',a.host],cwd=ROOT,text=True).strip()
    archive=subprocess.check_output(['git','archive',host,'recomp'],cwd=ROOT)
    frozen=out/'host';frozen.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(frozen)
    windows=frozen/'recomp/windows';whole=frozen/'recomp/whole';hashes={}
    for name in FILES:
        src=HERE/name;hashes[name]=sha(src);shutil.copy2(src,windows/name)
    (out/'source-pin.json').write_text(json.dumps({'host':host,'overlay':hashes},indent=2)+'\n')
    print(f'Frozen {host} + {len(hashes)} exact overlay files',flush=True)
    reference=out/'reference';sysroot=a.reference_root/'usr/aarch64-linux-gnu';gcc=a.reference_root/'usr/lib/gcc-cross/aarch64-linux-gnu/13'
    run(['clang-18','--target=aarch64-linux-gnu',f'--sysroot={sysroot}',f'-B{gcc}',f'-L{gcc}','-fuse-ld=lld','-static','-O2',windows/'signal_altstack_reference.c','-o',reference],out/'reference-build.log')
    run([a.reference_root/'usr/bin/qemu-aarch64-static','-cpu','cortex-a53',reference],out/'reference.log',timeout=30)
    print((out/'reference.log').read_text(),flush=True)
    text=(out/'reference.log').read_text()
    expected=['layout size=24 align=8 flags=8 length=16',
        'initial result=0 errno=71 kind=0 flags=2 size=0 pad=00000000 untouched=0 guards=1',
        'install_a result=0 errno=71 kind=0 flags=2 size=0 pad=00000000 untouched=0 guards=1',
        'query_a result=0 errno=71 kind=1 flags=0 size=262144 pad=00000000 untouched=0 guards=1',
        'alias_b result=0 errno=71 kind=1 flags=0 size=262144 pad=00000000 untouched=0 guards=1',
        'query_b result=0 errno=71 kind=2 flags=0 size=262144 pad=00000000 untouched=0 guards=1',
        'small result=0 errno=71 kind=2 flags=0 size=262144 pad=00000000 untouched=0 guards=1',
        'invalid result=-1 errno=22 kind=9 flags=2779096485 size=11936128518282651045 pad=a5a5a5a5 untouched=1 guards=1',
        'restore_a result=0 errno=71 kind=1 flags=0 size=5119 pad=00000000 untouched=0 guards=1',
        'disable result=0 errno=71 kind=1 flags=0 size=262144 pad=00000000 untouched=0 guards=1',
        'query_disabled result=0 errno=71 kind=0 flags=2 size=0 pad=00000000 untouched=0 guards=1',
        'unity_restore_zero result=-1 errno=12 kind=9 flags=2779096485 size=11936128518282651045 pad=a5a5a5a5 untouched=1 guards=1',
        'bad_old result=-1 errno=14 committed=0',
        'delivery alt=1 nested_below=1 normal_saved=1 nested_saved=1 raw=0/1 query=1/1 onstack=-1/1',
        'normal_change normal=1 observed_b=1 restored_a=1 raw=0 query=0']
    assert text.splitlines()==expected,text
    # QEMU8.2.2 differs from pinned Android13-5.15+ARM64 NDK: minimum2048,
    # prevalidated old output, computed nested uc_stack.flags. Runtime below
    # intentionally follows Android's minimum5120, commit-before-copyout, raw flags.
    ndkcc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'altstack.so'
    run([ndkcc,'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin','-fno-vectorize','-fno-slp-vectorize',windows/'signal_altstack_guest.c','-o',library],out/'ndk-build.log')
    results={}
    for platform in ['linux','windows']:
        work=out/platform;work.mkdir();guest=work/'guest'
        run([sys.executable,whole/'compile.py',library,'--out',guest,'--lift',a.lift,'--semantics-dir',a.lift.parent,'--cxx','clang++-18','--base','0x76000000','--target','x86_64-w64-windows-gnu'if platform=='windows'else'x86_64-linux-gnu'],work/'lift.log')
        manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        win=platform=='windows'
        def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if win else str(path)
        cc='/mnt/c/mingw64/bin/gcc.exe'if win else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if win else'clang++-18'
        loader=work/'elfload.o';run([cc,'-O2','-c',hp(frozen/'recomp/fastaes/elfload.c'),'-o',hp(loader)],work/'loader-build.log')
        binary=work/('test.exe'if win else'test')
        sources=[windows/'signal_altstack_test.cpp',windows/'signal_host.cpp',windows/'signal_delivery.cpp',whole/'signal_frame.cpp',whole/'runtime.cpp']
        if win:sources.extend([windows/'filesystem.cpp',whole/'format.cpp'])
        command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(guest)}',f'-DALT_LIBRARY="{hp(library)}"',*map(hp,sources),hp(loader),*map(hp,manifest['objects']),'-pthread','-latomic','-o',hp(binary)]
        if win:command[1:1]=['-static'];command+=['-ladvapi32','-lbcrypt']
        run(command,work/'host-build.log');print(f'{platform}: built {len(manifest["objects"])} real fixture objects',flush=True)
        run([binary],work/'positive.log',timeout=45);positive=(work/'positive.log').read_text();assert 'checks passed' in positive
        print(f'{platform}: {positive.strip()}',flush=True)
        negatives={}
        for mode,needle in [('autodisarm','SS_AUTODISARM'),('onstack-input','SS_ONSTACK'),('unowned','owned writable'),('partial-output','partial')]:
            log=work/f'{mode}.log'
            with log.open('w') as f:r=subprocess.run([str(binary),f'--{mode}'],stdout=f,stderr=subprocess.STDOUT,timeout=20)
            assert r.returncode and needle in log.read_text(errors='replace'),(mode,r.returncode,log.read_text(errors='replace'))
            negatives[mode]=r.returncode
        results[platform]={'exe':sha(binary),'manifest':sha(guest/'manifest.json'),'positive':positive.strip(),'negatives':negatives,'traces':len(manifest['traces']) if 'traces'in manifest else manifest.get('trace_count')}
    for name,value in hashes.items():assert sha(HERE/name)==value and sha(windows/name)==value
    artifacts={str(p.relative_to(out)):sha(p)for p in out.rglob('*')if p.is_file()and ('host'not in p.relative_to(out).parts)and p.name!='acceptance.json'}
    (out/'acceptance.json').write_text(json.dumps({'host':host,'overlay':hashes,'results':results,'artifacts':artifacts,'production_polling':False,'production_signal_delivery':False},indent=2)+'\n')
    print(f'PASS {out}/acceptance.json',flush=True)

if __name__=='__main__':main()
