"""Check actual NDK Bionic clock/sysconf callers against native process/system data."""
import argparse,json,pathlib,subprocess,sys,hashlib
HERE=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ndk',type=pathlib.Path,required=True);p.add_argument('--lift',type=pathlib.Path,required=True);p.add_argument('--semantics-dir',type=pathlib.Path);p.add_argument('--remill',type=pathlib.Path,required=True);p.add_argument('--windows',action='store_true');p.add_argument('--mingw',type=pathlib.Path,default=pathlib.Path('/mnt/c/mingw64/bin'));a=p.parse_args()
 out=HERE.parent/('work/libc-process-windows'if a.windows else 'work/libc-process-linux');out.mkdir(parents=True,exist_ok=True)
 def run(command,**kw):return subprocess.run([str(x)for x in command],check=True,**kw)
 def hp(path):return subprocess.check_output(['wslpath','-m',str(pathlib.Path(path).resolve())],text=True).strip()if a.windows else str(path)
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';library=out/'process.so'
 run([cc,'-shared','-fPIC','-nostdlib','-O1','-fno-stack-protector','-fno-builtin','-funwind-tables',HERE/'libc_process_guest.c','-o',library])
 cmd=[sys.executable,HERE.parent/'whole/compile.py',library,'--out',out/'guest','--base','0x6c000000','--lift',a.lift,'--target','x86_64-w64-windows-gnu'if a.windows else 'x86_64-linux-gnu']
 if a.semantics_dir:cmd+=['--semantics-dir',a.semantics_dir]
 run(cmd);manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
 hostcc=a.mingw/'gcc.exe'if a.windows else 'clang-18';hostcxx=a.mingw/'g++.exe'if a.windows else 'clang++-18';loader=out/'elfload.o'
 run([hostcc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)])
 exe=out/('process.exe'if a.windows else 'process');cmd=[hostcxx,'-std=c++17','-O2','-Wall','-Wextra','-Wno-unknown-pragmas','-DADDRESS_SIZE_BITS=64','-I'+hp(a.remill/'include'),'-I'+hp(out/'guest'),'-DPROCESS_LIBRARY="'+hp(library)+'"',hp(HERE/'libc_process_test.cpp'),hp(HERE/'libc.cpp'),hp(HERE.parent/'whole/runtime.cpp'),hp(loader),*[hp(x)for x in manifest['objects']],'-latomic','-pthread','-o',hp(exe)]
 if a.windows:cmd.insert(1,'-static')
 run(cmd);run([exe]);failure=subprocess.run([str(exe),'known-unsupported'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if failure.returncode==0 or b'unsupported Android sysconf name: 6'not in failure.stderr or b'import sysconf failed'not in failure.stderr:raise RuntimeError('known valid unsupported sysconf did not terminate explicitly')
 print('Known valid unsupported sysconf terminates with exact name diagnostic.')
 names=['libc.h','libc.cpp','libc_process_detail.h','libc_sysconf_names.inc','libc_process_guest.c','libc_process_test.cpp','test_libc_process.py']
 (out/'result.json').write_text(json.dumps({'status':'passed','platform':'windows'if a.windows else 'linux','traces':len(manifest['traces']),'unsupported':0,'unresolved_direct':0,'source_sha256':{x:hashlib.sha256((HERE/x).read_bytes()).hexdigest()for x in names},'fixture_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'toolchain':manifest['toolchain']},indent=2)+'\n')
if __name__=='__main__':main()
