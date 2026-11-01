"""Build NDK ClassLoader.findLibrary callers and execute on each native host."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--remill',type=Path,required=True);p.add_argument('--windows',action='store_true')
    a=p.parse_args();out=HERE.parent/('work/java-native-libraries-windows'if a.windows else'work/java-native-libraries-linux');out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'caller.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector',str(HERE/'java_native_libraries_guest.c'),'-o',str(library)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),
                    '--lift',str(a.lift),'--cxx','clang++-18','--base','0x5d000000','--target',
                    'x86_64-w64-windows-gnu'if a.windows else'x86_64-linux-gnu'],check=True)
    m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
    def hp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()if a.windows else str(p)
    cc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else'clang++-18'
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    exe=out/('test.exe'if a.windows else'test');sources=['java_native_libraries_test.cpp','java_native_libraries.cpp','jni_host.cpp']
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(out/"guest")}',
      f'-DJAVA_LIBRARIES_IMAGE="{hp(library)}"',*[hp(HERE/n)for n in sources],hp(HERE.parent/'whole/runtime.cpp'),hp(loader),
      *[hp(Path(o))for o in m['objects']],'-pthread','-latomic','-o',hp(exe)]
    if a.windows:command.insert(1,'-static')
    shared=[HERE/'jni_host.cpp',HERE/'jni_host.h',HERE.parent/'whole/runtime.cpp',HERE.parent/'whole/runtime.h']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    shared_hashes={str(p):digest(p)for p in shared}
    subprocess.run(command,check=True)
    assert shared_hashes=={str(p):digest(p)for p in shared},'Shared native sources changed during compile'
    result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=30);print(result.stdout,end='',flush=True)
    fatal=[]
    for arg in ['--fatal-detached','--fatal-thread-env']:
        r=subprocess.run([str(exe),arg],capture_output=True,text=True,timeout=15)
        assert r.returncode and 'JNIEnv belongs to a different or detached thread'in r.stderr,(arg,r.returncode,r.stderr)
        fatal.append(dict(argument=arg,exit_code=r.returncode,diagnostic=r.stderr))
    record=dict(output=result.stdout,fatal_gates=fatal,source_sha256={n:digest(HERE/n)for n in sources+['java_native_libraries.h','java_native_libraries_guest.c','test_java_native_libraries.py']},
                shared_source_sha256=shared_hashes,executable_sha256=digest(exe),guest_manifest_sha256=digest(out/'guest/manifest.json'),native_module_loading=False)
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Detached/foreign JNIEnv caller gates fail explicitly; no native loading was attempted.',flush=True)
if __name__=='__main__':main()
