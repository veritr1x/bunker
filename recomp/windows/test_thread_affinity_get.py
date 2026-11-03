"""Focused public128 affinity NDK/Bionic + real owned Windows operations."""
import argparse,hashlib,io,json,re,shutil,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWN=('affinity_get_fixture.h','affinity_get_guest.c','affinity_get_ref.c','affinity_get_test.cpp','test_thread_affinity_get.py')
CORE=('windows/thread_affinity.h','windows/thread_affinity.cpp')
BASE='51046016c712835c3f6fdebec6a14e7be59639fc'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--source-proof',type=Path,required=True);p.add_argument('--source-proof-sha256',required=True);a=p.parse_args();O=a.out.resolve();O.mkdir(exist_ok=False);W=HERE.parent/'work';commands=[]
 assert sha(a.source_proof)==a.source_proof_sha256;proof=json.loads(a.source_proof.read_text());assert proof['passed']
 def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
 def run(cmd,name,timeout=240):
  cmd=list(map(str,cmd));commands.append(cmd);print('STAGE',name,flush=True)
  with (O/(name+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  if r.returncode:raise RuntimeError(name+' exit '+str(r.returncode)+'\n'+(O/(name+'.log')).read_text(errors='replace')[-5000:])
  return (O/(name+'.log')).read_text()
 archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(O/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(O/'source',filter='data')
 S=O/'source/recomp'
 for n in CORE:shutil.copy2(HERE.parent/n,S/n)
 for n in OWN:shutil.copy2(HERE/n,S/'windows'/n)
 core={n:sha(S/n) for n in CORE};assert core==proof['core_sources']
 protected={n:sha(S/n) for n in ('windows/pthread_host.h','windows/pthread_host.cpp','windows/signal_host.h','windows/signal_host.cpp','windows/signal_sleep.h','windows/signal_sleep.cpp','windows/signal_futex.h','windows/signal_futex.cpp','whole/runtime.h','whole/runtime.cpp','whole/bridge.h')}
 for n,h in protected.items():assert sha(HERE.parent/n)==h,n
 sources={str(f):sha(f) for f in S.rglob('*') if f.is_file()};live={str(HERE/n):sha(HERE/n) for n in OWN}|{str(HERE.parent/n):sha(HERE.parent/n) for n in CORE}
 T=W/'ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa';NDK=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018');cc=NDK/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe');gcc=Path('/mnt/c/mingw64/bin/gcc.exe');P=W/'affinity-get-preparation1'
 assert sha(T/'remill-lift')=='2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e' and sha(T/'aarch64.bc')=='06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a'
 external={str(f):sha(f) for f in (cc.resolve(),qemu,T/'remill-lift',T/'aarch64.bc',cxx,gcc,Path(shutil.which('clang++-18')).resolve(),Path('/mnt/c/Windows/System32/ntdll.dll'),a.source_proof,W/'affinity-public-source-peer1/peer.json',W/'thread-affinity-held1.json',W/'affinity-fixture1/qualification2/acceptance.json')}
 for directory in (T/'include',W/'window-manager-sched-getaffinity-boundary1',P):
  for f in directory.rglob('*'):
   if f.is_file():external[str(f)]=sha(f)
 OLD=W/'affinity-fixture1/qualification1';oldm=json.loads((OLD/'focused-guest/manifest.json').read_text())
 for f in [OLD/'affinity.so',OLD/'acceptance.json',OLD/'focused-guest/traces.h',*(Path(n) for n in oldm['objects'])]:external[str(f)]=sha(f)
 (O/'source-pin.json').write_text(json.dumps(dict(commit=BASE,archive_sha256=sha(O/'support.tar'),sources=sources,external=external,live=live,core_sources=core,protected_sources=protected),indent=2)+'\n')
 flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(S/'windows')]
 guest=O/'affinity-get.so';run([cc,*flags,'-shared','-nostdlib',S/'windows/affinity_get_guest.c','-o',guest],'strict-ndk')
 ref=O/'reference';run([cc,*flags,'-static',S/'windows/affinity_get_ref.c',S/'windows/affinity_get_guest.c','-pthread','-o',ref],'reference-build')
 from elftools.elf.elffile import ELFFile
 with ref.open('rb') as f:assert all(segment['p_align']>=64 for segment in ELFFile(f).iter_segments() if segment['p_type']=='PT_TLS')
 arm=run([qemu,ref],'arm64-bionic',60)
 assert 'GET-AFFINITY-ARM64-PASS records=26' in arm
 G=O/'guest';run([sys.executable,S/'whole/compile.py',guest,'--out',G,'--base','0x5c100000','--lift',T/'remill-lift','--semantics-dir',T,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'translate');m=json.loads((G/'manifest.json').read_text());assert not m['unsupported_traces'] and not m['unresolved_direct_targets']
 opts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(S/'windows'),'-I'+wp(G),f'-DAFFINITY_GET_LIBRARY="{wp(guest)}"']
 loader=O/'loader.o';run([gcc,'-O2','-c',wp(S/'fastaes/elfload.c'),'-o',wp(loader)],'loader');objects=[]
 for n in ('whole/runtime.cpp','windows/pthread_host.cpp','windows/thread_affinity.cpp'):
  obj=O/(Path(n).stem+'.o');strict=['-Wall','-Wextra','-Werror'] if n.endswith('thread_affinity.cpp') else [];run([cxx,*opts,*strict,'-c',wp(S/n),'-o',wp(obj)],Path(n).stem);objects.append(obj)
 binary=O/'affinity-get.exe';run([cxx,*opts,'-Wall','-Wextra','-Werror',wp(S/'windows/affinity_get_test.cpp'),*map(wp,objects),wp(loader),*map(wp,m['objects']),'-static','-pthread','-latomic','-o',wp(binary)],'strict-windows-link');win=run([binary],'actual-windows',60);match=re.search(r'GET-AFFINITY-WINDOWS-PASS checks=(\d+) records=(\d+)',win);assert match
 def canonical(text):return [(kind,int(case),int(form),int(rc),int(error)) for kind,case,form,rc,error in re.findall(r'(GET|SET)-AFFINITY (\d+) form=(\d+) rc=(-?\d+) errno=(\d+)',text) if kind=='SET' or int(case)<8]
 assert canonical(arm)==canonical(win) and len(canonical(arm))==26
 # Existing Windows setter controls once, against the newly compiled provider;
 # retain the exact historical NDK library/traces/COFF and nine old fixtures.
 oldopts=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(T/'include'),'-I'+wp(S/'windows'),'-I'+wp(OLD/'focused-guest'),f'-DAFFINITY_LIBRARY="{wp(OLD/"affinity.so")}"']
 oldexe=O/'old-setter.exe';run([cxx,*oldopts,'-Wall','-Wextra','-Werror',wp(S/'windows/affinity_test.cpp'),*map(wp,objects),wp(loader),*map(wp,oldm['objects']),'-static','-pthread','-latomic','-o',wp(oldexe)],'old-setter-link');legacy=run([oldexe],'old-setter-windows',60);assert re.search(r'AFFINITY-WINDOWS-SUCCESS checks=\d+ records=32 canonical=22',legacy)
 for group in (sources,external,live):
  for n,h in group.items():assert sha(n)==h,n
 (O/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=dict(passed=True,commit=BASE,core_sources=core,base_core_sources=proof['base_core_sources'],fixture_sources={n:sha(S/'windows'/n) for n in OWN},protected_sources=protected,source_proof_path=str(a.source_proof),source_proof_sha256=a.source_proof_sha256,source_pin_sha256=sha(O/'source-pin.json'),canonical_records=canonical(arm),arm64=dict(stdout=arm,records=26,reference_sha256=sha(ref)),windows=dict(stdout=win,checks=int(match[1]),records=int(match[2]),heads=len(m['traces']),objects=len(m['objects']),binary_sha256=sha(binary)),legacy_windows_setter_stdout=legacy,scope='Public128B Get/Set, explicit single-group64bit kernel-mask profile; real owned native affinity with full public getter zero-tail. Actual Bionic canonical return/errno checks; masks compared to separate native oracle per platform, not cross-platform CPU identity. Partial-copy and tail-unread are explicitly Windows software-profile controls; no inference of real Android device kernel mask size. Tail-only libc fault is fatal boundary, not ordinary EFAULT. No game or foreign/process-affinity mutation.',evidence={str(f):sha(f) for f in O.rglob('*') if f.is_file() and 'source' not in f.relative_to(O).parts})
 (O/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('PUBLIC-AFFINITY-PASS',sha(O/'acceptance.json'),flush=True)
if __name__=='__main__':main()
