"""Compile actual NDK mixed reference/jint JNI direct, V and A callers."""
import argparse,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ndk',type=pathlib.Path,required=True);p.add_argument('--lift',type=pathlib.Path,required=True);p.add_argument('--semantics-dir',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,default=HERE.parent/'work/windows-package-manager');p.add_argument('--target',default='x86_64-w64-windows-gnu');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';guest=a.out/'package.so'
    subprocess.run([str(cc),'-shared','-fPIC','-nostdlib','-O1','-fno-stack-protector','-ffreestanding',str(HERE/'package_guest_fixture.c'),'-o',str(guest)],check=True)
    command=[sys.executable,str(HERE.parent/'whole/compile.py'),str(guest),'--out',str(a.out/'guest'),'--lift',str(a.lift),'--base','0x74000000','--target',a.target]
    if a.semantics_dir:command.extend(['--semantics-dir',str(a.semantics_dir)])
    subprocess.run(command,check=True)
if __name__=='__main__':main()
