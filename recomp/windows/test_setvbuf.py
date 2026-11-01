"""Exact reached Android setvbuf shape on real owned Windows CRT streams."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
HERE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--lift',type=Path,required=True)
    parser.add_argument('--support-source',type=Path,default=HERE.parent)
    parser.add_argument('--regression',action='store_true')
    parser.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    a=parser.parse_args();out=HERE.parent/'work/setvbuf';out.mkdir(parents=True,exist_ok=True);source=out/'source'
    for directory in ('windows','whole','fastaes'):
        target=source/directory;target.mkdir(parents=True,exist_ok=True)
        for file in(a.support_source/directory).iterdir():
            if file.is_file()and file.suffix in('.h','.cpp','.c','.inc'):shutil.copyfile(file,target/file.name)
    for name in('filesystem.cpp','filesystem.h','setvbuf_guest.c','setvbuf_test.cpp','filesystem_test.cpp'):
        shutil.copyfile(HERE/name,source/'windows'/name)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';guest=out/'setvbuf.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',str(source/'windows/setvbuf_guest.c'),'-o',str(guest)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(guest),'--out',str(out/'guest'),'--lift',str(a.lift),'--cxx','clang++-18','--base','0x5a000000','--target','x86_64-w64-windows-gnu','--resume'],check=True)
    m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
    def hp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
    loader=out/'elfload.o';subprocess.run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    base=['/mnt/c/mingw64/bin/g++.exe','-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.remill/'include'),'-I'+hp(out/'guest'),f'-DSETVBUF_IMAGE="{hp(guest)}"',f'-DSETVBUF_ROOT="{hp(out)}"']
    objects=[]
    for rel in('windows/setvbuf_test.cpp','windows/filesystem.cpp','whole/runtime.cpp'):
        obj=out/(Path(rel).stem+'.o');strict=['-Wall','-Wextra','-Werror']if rel.endswith('setvbuf_test.cpp')else[]
        subprocess.run([*base,*strict,'-c',hp(source/rel),'-o',hp(obj)],check=True);objects.append(obj)
    binary=out/'test.exe';command=[base[0],'-static',*map(hp,objects),hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-o',hp(binary)]
    subprocess.run(command,check=True);run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=90);print(run.stdout,end='');print(run.stderr,end='',file=sys.stderr);run.check_returncode()
    regression=None
    if a.regression:
        old=HERE.parent/'work/windows-files';prior=json.loads((old/'guest/manifest.json').read_text());assert not prior['unsupported_traces']and not prior['unresolved_direct_targets']
        rb=[base[0],'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.remill/'include'),'-I'+hp(old),f'-DFILES_ROOT="{hp(old)}"','-DHAVE_GUEST_FILE_FIXTURE',f'-DGUEST_FILES_IMAGE="{hp(old/"file-guest.so")}"','-I'+hp(HERE.parent/'work/zlib-native/zlib-1.3.2')]
        ro=[]
        for name in('filesystem_test','jni_host','android_context','android_assets','apk_assets'):
            obj=out/(name+'-regression.o');subprocess.run([*rb,'-c',hp(source/'windows'/(name+'.cpp')),'-o',hp(obj)],check=True);ro.append(obj)
        exe=out/'filesystem-regression.exe';subprocess.run([base[0],'-static',*map(hp,ro),*map(hp,objects[1:]),hp(loader),*map(hp,prior['objects']),hp(HERE.parent/'work/zlib-native/libz-inflate.a'),'-pthread','-latomic','-o',hp(exe)],check=True)
        result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90);print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr);result.check_returncode()
        regression=dict(stdout=result.stdout,stderr=result.stderr,binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'acceptance.json').write_text(json.dumps(dict(passed=True,stdout=run.stdout,stderr=run.stderr,traces=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],source_sha256={str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},binary_sha256=digest(binary),toolchain=m['toolchain'],regression=regression,command=command),indent=2)+'\n')

if __name__=='__main__':main()
