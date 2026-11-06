"""Same NDK core: genuine scalar FRINTA Bionic reference and Windows integer-bit/state gate."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,struct,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work');OWN=['frinta_cases.py','frinta_records.h','frinta_ref.c','frinta_native_wrapper.S','frinta_test.cpp','test_frinta.py'];OLD=['frint_cases.py','frint_ref.c','frint_native_wrapper.S','frint_test.cpp','test_frint.py','test_frint_decode.py','frint.md']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--lift',type=Path);ap.add_argument('--semantics-dir',type=Path);ap.add_argument('--reference-only',action='store_true');a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';held={};commands=[];old_pins={name:sha(HERE/name)for name in OLD}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stderr.decode(errors='replace')[-5000:])
  return r
 try:
  support=['runtime.cpp','runtime.h','cooperative_poll.cpp','cooperative_poll.h','guest_memory.h','compile.py','jump_tables.py','callback_roots.py','nonlocal_roots.py']
  (source/'whole').mkdir(parents=True);(source/'fastaes').mkdir()
  for name in OWN+support:shutil.copyfile(HERE/name,source/'whole'/name);pin(HERE/name)
  for name in ['elfload.c','elfload.h','elf64.h']:shutil.copyfile(HERE.parent/'fastaes'/name,source/'fastaes'/name);pin(HERE.parent/'fastaes'/name)
  include=out/'remill-include';shutil.copytree(W/'remill-src/include',include)
  for p in (W/'remill-src/include').rglob('*'):
   if p.is_file():pin(p)
  spec=importlib.util.spec_from_file_location('frozen_frinta_cases',source/'whole/frinta_cases.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);generated=out/'generated';generated.mkdir();cases=module.generate(generated);oracle=json.loads((generated/'case-oracle.json').read_text())
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cc=Path('/mnt/c/mingw64/bin/gcc.exe');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cc,cxx]:pin(p)
  obj=out/'ndk-frinta.o';run([ndk,'-c',generated/'frinta.S','-o',obj],'compile-NDK-core');wrapper=out/'native-wrapper.o';run([ndk,'-c',source/'whole/frinta_native_wrapper.S','-o',wrapper],'compile-native-wrapper')
  native=W/'windows-first-frame-guest-transfer1/native/libunity.so';assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f';pin(native)
  from elftools.elf.elffile import ELFFile
  with native.open('rb')as stream:
   elf=ELFFile(stream);segment=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=0x828c24<0x828c28<=s['p_vaddr']+s['p_filesz']);assert segment.data()[0x828c24-segment['p_vaddr']:0x828c28-segment['p_vaddr']]==bytes.fromhex('6340261e')
  with obj.open('rb')as stream:
   elf=ELFFile(stream);symbol=elf.get_section_by_name('.symtab').get_symbol_by_name('raw_actual_unity_70828c24_1e264063')[0];assert elf.get_section(symbol['st_shndx']).data()[symbol['st_value']:symbol['st_value']+4]==bytes.fromhex('6340261e')
  reference=out/'actual-Bionic';run([ndk,'-static','-O2','-fno-emulated-tls','-Wall','-Wextra','-Werror','-I'+str(generated),source/'whole/frinta_ref.c',obj,wrapper,'-o',reference],'link-Bionic');r=run([qemu,reference],'actual-Bionic',120);native_rows=[line for line in r.stdout.decode().splitlines()if line.startswith('RECORD ')];assert len(native_rows)==oracle['records']and f"FRINTA-RECORDS-SUCCESS {oracle['records']}"in r.stdout.decode()and'FRINTA-REFERENCE-SUCCESS actual_Bionic=1 memory_control=1'in r.stdout.decode()
  result=dict(passed=True,reference_only=a.reference_only,variants=len(cases),records_each=oracle['records'],edges_per_width={width:len(values)for width,values in oracle['edges'].items()},FPCR_profiles=16,initial_FPSR_profiles=2,random_patterns_per_profile=64,actual_Bionic_reference=True,reference=desc(reference),NDK_core_object=desc(obj),native_ELF=desc(native),original_word='1e264063',original_word_address='0x70828c24',native_output=desc(out/'actual-Bionic.stdout'))
  if not a.reference_only:
   assert a.lift is not None and a.semantics_dir is not None
   pin(a.lift);pin(a.semantics_dir/'aarch64.bc');library=out/'frinta.so';run([ndk,'-shared','-nostdlib',obj,'-o',library],'link-guest');build=out/'windows';run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x38000000','--lift',a.lift,'--semantics-dir',a.semantics_dir,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18','--jobs','1'],'lift-Windows',900);manifest=json.loads((build/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
   loader=build/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(include),'-I'+wp(source/'whole'),'-I'+wp(source/'fastaes'),'-I'+wp(generated),'-I'+wp(build),'-DFRINTA_LIB="'+wp(library)+'"'];objects=[]
   for name in ['runtime.cpp','cooperative_poll.cpp','frinta_test.cpp']:
    output=build/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name=='frinta_test.cpp'else[]),'-c',wp(source/'whole'/name),'-o',wp(output)],'compile-'+Path(name).stem);objects.append(output)
   exe=build/'frinta.exe';run([cxx,*map(wp,objects),wp(loader),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(exe)],'link-Windows');r=run([exe],'actual-Windows',120);text=r.stdout.decode();actual=[line for line in text.splitlines()if line.startswith('RECORD ')];assert actual==native_rows,'Native/Windows record disagreement';assert'FRINTA-HOST-SUCCESS memory_control=1 State1200=1 Memory64=1'in text
   result.update(Windows_output=desc(out/'actual-Windows.stdout'),executable=desc(exe),actual_lifter=desc(a.lift.resolve()),actual_semantics=desc((a.semantics_dir/'aarch64.bc').resolve()),compiled_manifest=desc(build/'manifest.json'),toolchain=manifest['toolchain'],State_size=1200,State_align=16,Memory64_identity_and_contents_preserved=True,all_unrelated_State_bytes_and_padding_preserved=True)
  for p,digest in held.items():assert sha(p)==digest,p
  for name,digest in old_pins.items():assert sha(HERE/name)==digest,name
  result.update(owned_sources={name:sha(source/'whole'/name)for name in OWN},source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},unchanged_old_FRINTP_M_fixture_sources=old_pins,case_corpus=desc(generated/'case-oracle.json'),commands=commands,held_inputs=held,limits='ScalarS/D baseline nonmerging only; no half/vector/AFP/traps. Literal reached original word plus alias/nonalias/high registers. Every exact half-tie exponent and adjacent encoding, signed zeros/extremes/NaN payloads/sNaNs/subnormals, all16 DN/FZ/RMode profiles and clear/preexisting FPSR tested against original ARM instructions and independent integer-bit oracle. exactFALSE adds noIXC; IOC/IDC cumulative. Input/output guards and800B pre/post architectural snapshots checked byteexactly; native/Windows normalized rows compared. No original game/fullfunction/first-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FRINTA-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as error:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
