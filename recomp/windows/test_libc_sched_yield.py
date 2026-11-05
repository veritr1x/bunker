"""Actual NDK sched_yield ABI/Bionic reference and focused Windows provider gate."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('libc_sched_yield_guest.c','libc_sched_yield_ref.c','libc_sched_yield_test.cpp','libc_sched_yield.md','test_libc_sched_yield.py')
CPP='a615884813b3e138362330900978c7160a00529782ab608c4f6d1b004f65436f'
WRAP='_ZN6recomp7Runtime9AddImportEySt8functionIFvR5StateEE'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for k in('ndk','lift','semantics-dir','support-source','out'):ap.add_argument('--'+k,type=Path,required=True)
 ap.add_argument('--qemu',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static'))
 a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 try:
  assert sha(HERE/'libc.cpp')==CPP
  for folder in('windows','whole','fastaes'):
   target=source/folder;target.mkdir(parents=True)
   for f in(a.support_source/folder).iterdir():
    if f.is_file()and f.suffix in('.h','.cpp','.c','.inc','.py'):shutil.copyfile(f,target/f.name)
  for n in OWN:shutil.copyfile(HERE/n,source/'windows'/n);pin(HERE/n)
  production={'windows/libc.cpp':CPP};header=sha(HERE/'libc.h');pin(HERE/'libc.cpp');pin(HERE/'libc.h')
  baseline=a.support_source/'work/windows-first-frame-network-proxy1/sources/recomp/windows/libc.cpp';pin(baseline)
  binding=dict(passed=True,production_sources=production,unchanged_LibC_header_sha256=header,baseline=desc(baseline),candidate=desc(source/'windows/libc.cpp'),scope='Exact source binding; baseline is actual preceding original-game snapshot, not semantic-equivalence claim')
  (out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
  ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';pin(ndk);pin(a.qemu);pin(a.lift);pin(a.semantics_dir/'aarch64.bc');pin(a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include/sched.h')
  core=out/'ndk-yield.o';run([ndk,'-O1','-fPIC','-fno-stack-protector','-fno-builtin','-c',source/'windows/libc_sched_yield_guest.c','-o',core],'compile-NDK-caller')
  reference=out/'Bionic-reference';run([ndk,'-O1','-static','-fno-builtin','-fno-emulated-tls',source/'windows/libc_sched_yield_ref.c',core,'-o',reference],'compile-static-Bionic')
  with reference.open('rb')as f:
   elf=ELFFile(f);segments=list(elf.iter_segments());assert elf['e_machine']=='EM_AARCH64'and not any(s['p_type']=='PT_INTERP'for s in segments);tls=[s for s in segments if s['p_type']=='PT_TLS'];assert len(tls)==1 and tls[0]['p_align']>=64;tls_info=dict(alignment=tls[0]['p_align'],memory_bytes=tls[0]['p_memsz'])
  run([a.qemu,reference],'actual-static-Bionic');assert 'SCHED-YIELD-BIONIC-PASS calls=16 TLS=17'in(out/'actual-static-Bionic.log').read_text()
  bionic=dict(passed=True,actual_static_Bionic=True,actual_NDK_calls=16,NDK_object=desc(core),reference=desc(reference),stdout=desc(out/'actual-static-Bionic.log'),NDK_compiler=desc(ndk),qemu=desc(a.qemu),PT_TLS=tls_info,no_PT_INTERP=True,limits='Actual Linux scheduler under QEMU confirms Android calling/status/errno contract; no Windows scheduler equivalence or fairness claim')
  (out/'Bionic-reference.json').write_text(json.dumps(bionic,indent=2)+'\n')
  guest=out/'yield.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-caller');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x7a000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-NDK-Windows');manifest=json.loads((translated/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe');pin(cc);pin(cxx);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(a.support_source/'work/remill-src/include'),'-I'+wp(translated),'-DYIELD_LIBRARY="'+wp(guest)+'"'];objects=[]
  for relative in('windows/libc.cpp','whole/runtime.cpp','windows/libc_sched_yield_test.cpp'):
   obj=out/(Path(relative).stem+'.o');strict=['-Wall','-Wextra','-Werror']if relative.endswith('_test.cpp')else[];run([cxx,*flags,*strict,'-c',wp(source/relative),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'sched-yield.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-Wl,--wrap='+WRAP,'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');run([exe],'actual-Windows');text=(out/'actual-Windows.log').read_text();m=re.search(r'SCHED-YIELD-PASS checks=(\d+) NDK_calls=(\d+) workers=2 State=1200 Memory64=1',text);assert m and int(m[2])==48
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,production_sources=production,unchanged_LibC_header_sha256=header,owned_sources={'windows/'+n:sha(source/'windows'/n)for n in OWN},source_binding=desc(out/'source-binding.json'),Bionic_reference=desc(out/'Bionic-reference.json'),NDK_object=desc(core),platforms=dict(windows=dict(exit_code=0,checks=int(m[1]),actual_NDK_calls=int(m[2]),APIs=1,native_worker_threads=2,traces=len(manifest['traces']),objects=len(manifest['objects']),unsupported=[],unresolved=[],executable=desc(exe),stdout=desc(out/'actual-Windows.log'))),controls=['actual NDK direct and volatile function-pointer calls','actual static Bionic status and errno sentinel reference','main and two actual native workers repeated yields','success returns signed32 zero, preserves guesterrno, no failure sink','registered genuine callback native errno LastError nonzeroFENV preserved','State1200align16/SIMD128/highcells/saved64regs/PCSP/opaqueMemory64','old marker namespace prefix preserved, yield appended after difftime'],held_inputs=held,commands=commands,limits='Focused component only. Windows calls the real native SwitchToThread once; no scheduler fairness, timing, Linux policy equivalence, forced context switch, sleep fallback or failure injection claim. Static Bionic reference uses same NDK caller object. Test-only AddImport link wrapper measures callback native environment after Runtime scaffolding. No production edits, game/fullhost link, process control, scheduling priority changes or old gate replay.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('SCHED-YIELD-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
