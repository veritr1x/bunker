"""Real reached Android gettimeofday callers against native Windows UTC."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True);p.add_argument('--semantics-dir',type=Path,required=True);p.add_argument('--support-source',type=Path,required=True);a=p.parse_args()
 out=HERE.parent/'work/libc-wall-time';out.mkdir(exist_ok=True,parents=True);source=out/'source'
 for directory in('windows','whole','fastaes'):
  target=source/directory;target.mkdir(exist_ok=True,parents=True)
  for f in(a.support_source/directory).iterdir():
   if f.is_file() and f.suffix in('.h','.cpp','.c','.inc'):shutil.copyfile(f,target/f.name)
 for name in('libc.h','libc.cpp','libc_wall_time_detail.h','libc_wall_time_guest.c','libc_wall_time_test.cpp'):shutil.copyfile(HERE/name,source/'windows'/name)
 def run(command,**kw):return subprocess.run(list(map(str,command)),check=True,**kw)
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 guest=out/'wall.so';run([a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang','-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin',source/'windows/libc_wall_time_guest.c','-o',guest])
 run([sys.executable,HERE.parent/'whole/compile.py',guest,'--out',out/'guest','--base','0x58000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18','--resume'])
 m=json.loads((out/'guest/manifest.json').read_text());assert not m['unsupported_traces'] and not m['unresolved_direct_targets']
 gxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o';run(['/mnt/c/mingw64/bin/gcc.exe','-O2','-c',hp(source/'fastaes/elfload.c'),'-o',hp(loader)])
 base=[gxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(HERE.parent/'work/remill-src/include'),'-I'+hp(out/'guest'),f'-DWALL_LIBRARY="{hp(guest)}"'];objects=[]
 for rel in('windows/libc_wall_time_test.cpp','windows/libc.cpp','whole/runtime.cpp'):
  obj=out/(Path(rel).stem+'.o');run([*base,*(['-Wall','-Wextra','-Werror']if rel.endswith('_test.cpp')else[]),'-c',hp(source/rel),'-o',hp(obj)]);objects.append(obj)
 exe=out/'test.exe';run([gxx,'-static',*map(hp,objects),hp(loader),*map(hp,m['objects']),'-latomic','-pthread','-o',hp(exe)])
 result=run([exe],capture_output=True,text=True,timeout=90);print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
 previous=HERE.parent/'work/libc-process-windows';prior=json.loads((previous/'guest/manifest.json').read_text());assert not prior['unsupported_traces'] and not prior['unresolved_direct_targets']
 regression=out/'process-regression.exe';run([gxx,'-std=c++17','-O2','-static','-DADDRESS_SIZE_BITS=64','-isystem',hp(HERE.parent/'work/remill-src/include'),'-I'+hp(previous/'guest'),f'-DPROCESS_LIBRARY="{hp(previous/"process.so")}"',hp(source/'windows/libc_process_test.cpp'),*map(hp,objects[1:]),hp(loader),*map(hp,prior['objects']),'-latomic','-pthread','-o',hp(regression)])
 old=run([regression],capture_output=True,text=True,timeout=90);print(old.stdout,end='');print(old.stderr,end='',file=sys.stderr)
 digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 (out/'acceptance.json').write_text(json.dumps(dict(passed=True,stdout=result.stdout,stderr=result.stderr,traces=len(m['traces']),unsupported=m['unsupported_traces'],unresolved=m['unresolved_direct_targets'],fixture_sha256=digest(guest),binary_sha256=digest(exe),toolchain=m['toolchain'],regression=dict(stdout=old.stdout,binary_sha256=digest(regression)),source_sha256={str(f.relative_to(source)):digest(f)for f in source.rglob('*')if f.is_file()},runner_sha256=digest(Path(__file__))),indent=2)+'\n')
if __name__=='__main__':main()
