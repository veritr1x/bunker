"""Focused actual NDK/native-Windows window and weak-HWND reader lifetime gate."""
import argparse,hashlib,io,json,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('native_window.h','native_window.cpp','native_window_test.cpp','test_native_window.py')
BASE='5525d90ef65ab7576a9f11ce43ceb1fab9514659'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--support-commit',default=BASE)
 p.add_argument('--ndk',type=Path,required=True);p.add_argument('--lift',type=Path,required=True)
 p.add_argument('--semantics-dir',type=Path,required=True);p.add_argument('--cxx',default='clang++-18')
 a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);commands=[]
 def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with (O/(name+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  if r.returncode:raise RuntimeError(name+' exit '+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-5000:])
  return (O/(name+'.log')).read_text()
 commit=subprocess.check_output(['git.exe','-C',hp(HERE.parent.parent),'rev-parse',a.support_commit],text=True).strip();assert commit==BASE
 archive=subprocess.check_output(['git.exe','-C',hp(HERE.parent.parent),'archive',commit,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp';base_sources={n:sha(S/'windows'/n) for n in OWN}
 live={str(HERE/n):sha(HERE/n) for n in OWN}
 for n in OWN:shutil.copy2(HERE/n,S/'windows'/n)
 protected={n:sha(S/n) for n in ('windows/jni_host.h','windows/jni_host.cpp','whole/runtime.h','whole/runtime.cpp','whole/bridge.h')}
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');gcc=Path('/mnt/c/mingw64/bin/gcc.exe')
 assert sha(a.lift)=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e'
 assert sha(a.semantics_dir/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 sources={str(f):sha(f) for f in S.rglob('*') if f.is_file()}
 inputs={str(f):sha(f) for f in (cc.resolve(),a.lift,a.semantics_dir/'aarch64.bc',cxx,gcc,Path(shutil.which(a.cxx)).resolve())}
 for f in (a.semantics_dir/'include').rglob('*'):
  if f.is_file():inputs[str(f)]=sha(f)
 (O/'source-pin.json').write_text(json.dumps(dict(commit=commit,archive_sha256=sha(O/'support.tar'),sources=sources,inputs=inputs,live=live,base_sources=base_sources,protected_sources=protected),indent=2)+'\n')
 library=O/'window.so'
 run([cc,'-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',S/'windows/native_window_guest.c','-o',library],'strict-ndk')
 G=O/'guest';run([sys.executable,S/'whole/compile.py',library,'--out',G,'--lift',a.lift,'--semantics-dir',a.semantics_dir,'--cxx',a.cxx,'--base','0x5e000000','--target','x86_64-w64-windows-gnu'],'translate')
 m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces'] and not m['unresolved_direct_targets']
 loader=O/'elfload.o';run([gcc,'-O2','-c',hp(S/'fastaes/elfload.c'),'-o',hp(loader)],'loader')
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',hp(a.semantics_dir/'include'),'-I'+hp(G),f'-DNATIVE_WINDOW_LIBRARY="{hp(library)}"'];objects=[]
 for rel in ('windows/native_window_test.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
  obj=O/(Path(rel).stem+'.o');strict=['-Wall','-Wextra','-Werror'] if Path(rel).stem.startswith('native_window') else []
  run([cxx,*flags,*strict,'-c',hp(S/rel),'-o',hp(obj)],Path(rel).stem);objects.append(obj)
 binary=O/'test.exe';run([cxx,'-static',*map(hp,objects),hp(loader),*map(hp,m['objects']),'-pthread','-latomic','-luser32','-o',hp(binary)],'link')
 stdout=run([binary],'actual-windows')
 for group in (sources,inputs,live):
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 import re
 match=re.search(r'Native Windows window provider: (\d+) checks',stdout);assert match
 result=dict(passed=True,commit=commit,owned_sources={n:sha(S/'windows'/n) for n in OWN},base_sources=base_sources,protected_sources=protected,source_pin_sha256=sha(O/'source-pin.json'),windows=dict(stdout=stdout,checks=int(match[1]),heads=len(m['traces']),objects=len(m['objects']),binary_sha256=sha(binary)),scope='Actual NDK native-window controls and hidden owned Win32 HWND weak-reader lifetime tests; no game, OS settings, focus mutation or Linux port claim.',evidence={str(f):sha(f) for f in O.rglob('*') if f.is_file() and 'source' not in f.relative_to(O).parts})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('NATIVE-WINDOW-READER-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
