"""Test the isolated profile method against frozen1942 Host and existing NDK callers."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--windows',action='store_true');a=p.parse_args()
    m=json.loads((a.build/'combined_inputs.json').read_text());assert m['host_commit'].startswith('1942e24')
    source=a.build/'sources';out=a.build/('class-windows'if a.windows else'class-linux');out.mkdir(exist_ok=True)
    for n in ['combined_java_class.h','combined_java_class_test.cpp']:shutil.copyfile(HERE/n,source/'windows'/n)
    shared=['windows/jni_host.cpp','windows/jni_host.h','whole/runtime.cpp','whole/runtime.h']
    for n in shared:assert sha(source/n)==m['source_hashes'][n],n
    caller=HERE.parent/('work/java-native-libraries-windows'if a.windows else'work/java-native-libraries-linux')
    manifest=json.loads((caller/'guest/manifest.json').read_text())
    assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
    def hp(x):return subprocess.check_output(['wslpath','-m',str(x)],text=True).strip()if a.windows else str(x)
    cxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else'clang++-18'
    cc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else'clang-18'
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    exe=out/('class-test.exe'if a.windows else'class-test')
    inputs=[source/n for n in shared]+[source/'windows'/n for n in ['combined_java_class.h','combined_java_class_test.cpp']]
    before={str(n):sha(n)for n in inputs}
    command=[cxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-I'+hp(a.build/'remill-include'),'-I'+hp(caller/'guest'),
       '-DGETCLASS_CALLER="'+hp(caller/'caller.so')+'"',hp(source/'windows/combined_java_class_test.cpp'),hp(source/'windows/jni_host.cpp'),hp(source/'whole/runtime.cpp'),
       hp(loader),*[hp(Path(o))for o in manifest['objects']],'-pthread','-latomic','-o',hp(exe)]
    if a.windows:command.insert(1,'-static')
    subprocess.run(command,check=True);assert before=={str(n):sha(n)for n in inputs}
    r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30,check=True);print(r.stdout,end='')
    assert '42 runtime-class adapter checks +256 concurrent actual NDK calls passed'in r.stdout
    record=dict(status='passed',output=r.stdout,executable_sha256=sha(exe),sources=before,host_commit=m['host_commit'],
                ndk_caller_sha256=sha(caller/'caller.so'),guest_manifest_sha256=sha(caller/'guest/manifest.json'),
                fixture_reuse='NDK direct/V/A/stack-V caller; zero-argument descriptor ignores its spare argument')
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
