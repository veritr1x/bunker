"""Focused Windows OS entropy / actual NDK and selected original RNG gate (WSL)."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, sys, traceback
HERE = Path(__file__).resolve().parent
W = Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN = ('urandom_guest.c', 'urandom_test.cpp', 'test_urandom.py')
WRAP = '_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
PRODUCTION = '4c012e2391dd9b7d122954f1148d7bb2670c6c1accc682caef8038fa278e5666'
def sha(p):
 with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def desc(p):
 p=Path(p).resolve(); return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p): return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); out=a.out.resolve(); out.mkdir(exist_ok=False); commands=[]; held={}
 def pin(p): held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=180):
  argv=list(map(str,argv)); commands.append(dict(stage=label,argv=argv)); (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n'); print('STAGE',label,flush=True)
  with (out/(label+'.log')).open('w') as log: subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  packet=W/'urandom-source-preparation1/production-sources1.json'; assert sha(packet)=='9ec4a5f01506a302a8debc392b1b09074c943c78930c6535a1d92f531925d80a'; pin(packet); production=json.loads(packet.read_text())['production_sources']; assert production=={'windows/filesystem.cpp':PRODUCTION}
  root=HERE.parent; source=out/'source'; required=['windows/filesystem.cpp','windows/growdown_memory.cpp','whole/format.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','fastaes/elfload.c',*('windows/'+n for n in OWN)]; pending=list(required)+[str(p.relative_to(root)) for p in (root/'whole').glob('*.py')]; copied=set()
  while pending:
   name=pending.pop(); p=(root/name).resolve(); name=str(p.relative_to(root));
   if name in copied: continue
   copied.add(name); target=source/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,target); pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file() and q.is_relative_to(root): pending.append(str(q.relative_to(root)))
  assert sha(source/'windows/filesystem.cpp')==PRODUCTION
  extraction=W/'entropy-original-rng-extract1/acceptance.json'; assert sha(extraction)=='964db7913702d576c74a36308e908339407af51602ad46357ba0d56b70dd22df'; pin(extraction); original=json.loads(extraction.read_text()); original_object=Path(original['object']['path']); assert sha(original_object)==original['object']['sha256']; pin(original_object)
  # Verify the TEST literal reproduces the actual original ELF bytes, not a substitute path.
  from elftools.elf.elffile import ELFFile
  elf=W/'windows-first-frame-guest-transfer1/native/libil2cpp.so'
  with elf.open('rb') as f:
   e=ELFFile(f); address=0x5af6edf; segment=next(s for s in e.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address<s['p_vaddr']+s['p_filesz']); f.seek(segment['p_offset']+address-segment['p_vaddr']); assert f.read(13)==b'/dev/urandom\0'
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'); tool=W/'integer-popcount8b-preparation1/toolchains/f967bf3b57f889d7-469903ec4d84cbd3'; cxx=Path('/mnt/c/mingw64/bin/g++.exe'); cc=Path('/mnt/c/mingw64/bin/gcc.exe')
  for p in (ndk,tool/'remill-lift',tool/'aarch64.bc',cxx,cc): pin(p)
  guest=out/'urandom.so'; run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-builtin','-fno-stack-protector','-Wall','-Wextra','-Werror',source/'windows/urandom_guest.c','-o',guest],'compile-NDK')
  translated=out/'guest'; run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x6b000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK'); m=json.loads((translated/'manifest.json').read_text()); assert not m['unsupported_traces'] and not m['unresolved_direct_targets']
  loader=out/'elfload.o'; run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader')
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(translated),'-DURANDOM_GUEST="'+wp(guest)+'"','-DDATA_DIRECTORY="'+wp(out/'ordinary-data')+'"']; objects=[]
  for name in required:
   if not name.endswith('.cpp'): continue
   obj=out/(Path(name).stem+'.o'); run([cxx,*flags,*(['-Wall','-Wextra','-Werror'] if name.endswith('urandom_test.cpp') else []),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem); objects.append(obj)
  exe=out/'urandom.exe'; run([cxx,*map(wp,objects),wp(loader),wp(original_object),*map(wp,m['objects']),'-Wl,--wrap='+WRAP,'-Wl,--wrap=__imp_GetProcAddress','-static','-pthread','-latomic','-ladvapi32','-o',wp(exe)],'link'); run([exe],'actual-Windows',60)
  text=(out/'actual-Windows.log').read_text(); match=re.search(r'URANDOM-PASS checks=(\d+) NDK_calls=(\d+) installed=(\d+) original_calls=(\d+) RNG_calls=(\d+) real_failures=(\d+) failure_NTSTATUS=(-?\d+) State=1200 Memory64=8',text); assert match,text; assert int(match[4])==3 and int(match[6])==2 and int(match[7])<0
  for p,h in held.items(): assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,production_source_manifest=desc(packet),source_snapshot={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},scope='Real Windows system-preferred BCrypt entropy through actual NDK direct/volatile pointer calls and two exact selected original RNG bodies; descriptor lifetime/publication and one ordinary-file regression.',focus=dict(checks=int(match[1]),actual_NDK_calls=int(match[2]),installed_callbacks=int(match[3]),original_calls=int(match[4]),real_native_calls=int(match[5]),real_native_failures=int(match[6]),failure_NTSTATUS=int(match[7]),State=1200,Memory64=8,traces=len(m['traces']),objects=len(m['objects']),ordinary_file_regression_passed=True),original_extraction=desc(extraction),original_object=desc(original_object),guest=desc(guest),guest_manifest=desc(translated/'manifest.json'),executable=desc(exe),stdout=desc(out/'actual-Windows.log'),held_inputs=held,commands=commands,limits='No RNG byte normalization or entropy-quality claim. TEST dynamic observer forwards every normal native call unchanged; two explicit faults invoke the real OS API with flags0/null provider and preserve its actual failing NTSTATUS. No guest output is published on failure. Environment assertions cover recognized entropy operations, not unrelated invalid descriptors. Original functions use TEST-owned literal/global/stack storage with actual open/read/errno provider callouts; no full DES, private key, whole game or first-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n'); print('URANDOM-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n'); raise
if __name__=='__main__': main()
