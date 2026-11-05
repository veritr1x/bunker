"""Literal NEG.2S kernel: actual static NDK ARM, raw and exact-polled Windows."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,traceback
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('vector_neg_2s_cases.h','vector_neg_2s_kernel.S','vector_neg_2s_ref.S','vector_neg_2s_ref.c','vector_neg_2s_test.cpp','test_vector_neg_2s.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(Path(p).resolve()),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def rows(p):return [x for x in Path(p).read_text().splitlines()if x.startswith('REC ')]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reference-only',action='store_true');ap.add_argument('--reference',type=Path);ap.add_argument('--toolchain',type=Path);ap.add_argument('--poll-instrument',type=Path,default=Path('/home/user/bunker-recomp/recomp/work/guest-eh-rebuild-preparation1/.toolchain/poll-instrument'));a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';source.mkdir();commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True)
  with(out/(label+'.log')).open('w')as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
 try:
  for name in OWN:shutil.copyfile(HERE/name,source/name);pin(HERE/name)
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');unity=W/'windows-first-frame-guest-transfer1/native/libunity.so'
  for p in(ndk,qemu,unity):pin(p)
  assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  with unity.open('rb')as f:
   elf=ELFFile(f);rva=0x161a78;seg=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=rva<rva+4<=s['p_vaddr']+s['p_filesz']);assert seg.data()[rva-seg['p_vaddr']:rva-seg['p_vaddr']+4]==bytes.fromhex('00b8a02e')
  if a.reference:
   reference=json.loads(a.reference.read_text());assert reference['passed']and reference['actual_static_Bionic']
   for name in OWN[:4]:assert reference['reference_sources'][name]==sha(source/name)
   for name in('NDK_object','reference','stdout','NDK_compiler','qemu'):item=reference[name];assert sha(item['path'])==item['sha256'];pin(item['path'])
   pin(a.reference);core=Path(reference['NDK_object']['path']);expected=rows(reference['stdout']['path'])
  else:
   core=out/'ndk-neg2s.o';run([ndk,'-c',source/'vector_neg_2s_kernel.S','-o',core],'compile-NDK-kernels');ref=out/'original-ARM';run([ndk,'-static','-O1','-fno-emulated-tls',source/'vector_neg_2s_ref.c',source/'vector_neg_2s_ref.S',core,'-o',ref],'compile-static-Bionic')
   with ref.open('rb')as f:
    elf=ELFFile(f);segments=list(elf.iter_segments());assert not any(s['p_type']=='PT_INTERP'for s in segments);tls=[s for s in segments if s['p_type']=='PT_TLS'];assert len(tls)==1 and tls[0]['p_align']>=64
   run([qemu,ref],'actual-original-ARM');assert 'NEG2S-ORIGINAL-PASS records=4352 TLS=17'in(out/'actual-original-ARM.log').read_text();expected=rows(out/'actual-original-ARM.log');reference=dict(passed=True,actual_static_Bionic=True,reference_sources={name:sha(source/name)for name in OWN[:4]},NDK_object=desc(core),reference=desc(ref),stdout=desc(out/'actual-original-ARM.log'),NDK_compiler=desc(ndk),qemu=desc(qemu),original_Unity_word=0x2ea0b800,original_Unity_PC='0x70161a78',original_ELF=desc(unity),records=4352,no_PT_INTERP=True,PT_TLS_alignment=tls[0]['p_align'],scope='Only actual NEG.2S word plus distinct register shape in NDK kernel, full buffers and independent unsigned modulo32 model; not entire4456byte Unity function.')
  assert len(expected)==4352;(out/'reference.json').write_text(json.dumps(reference,indent=2)+'\n')
  if a.reference_only:
   (out/'acceptance.json').write_text(json.dumps(reference,indent=2)+'\n');print('NEG2S-REFERENCE-PASS',sha(out/'acceptance.json'),flush=True);return
  assert a.toolchain;tool=a.toolchain.resolve();pin(tool/'remill-lift');pin(tool/'aarch64.bc');pin(a.poll_instrument);cxx=Path('/mnt/c/mingw64/bin/g++.exe');cc=Path('/mnt/c/mingw64/bin/gcc.exe');pin(cxx);pin(cc)
  parent=W/'windows-first-frame-gl-mapping-batch1/sources/recomp'
  for folder in('whole','fastaes'):
   target=source/folder;target.mkdir()
   for p in(parent/folder).iterdir():
    if p.is_file()and(p.suffix in('.h','.inc','.py')or p.name in('runtime.cpp','cooperative_poll.cpp','elfload.c')):shutil.copyfile(p,target/p.name);pin(p)
  guest=out/'neg2s.so';run([ndk,'-shared','-nostdlib',core,'-o',guest],'link-NDK-kernels');translated=out/'guest';run([sys.executable,source/'whole/compile.py',guest,'--out',translated,'--base','0x3b000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'],'lift-kernels');m=json.loads((translated/'manifest.json').read_text());assert not m['unsupported_traces']and not m['unresolved_direct_targets']
  inc=tool/'include'if(tool/'include').exists()else W/'remill-src/include';flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',wp(inc),'-I'+wp(source/'whole'),'-I'+wp(source/'fastaes'),'-I'+wp(source),'-I'+wp(translated),'-DNEG2S_LIBRARY="'+wp(guest)+'"'];common=[]
  for name in('runtime','cooperative_poll'):
   obj=out/(name+'.o');run([cxx,*flags,'-c',wp(source/'whole'/(name+'.cpp')),'-o',wp(obj)],'compile-'+name);common.append(obj)
  loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-loader');common.append(loader);hosts={}
  for label in('raw','polled'):
   objects=list(map(Path,m['objects']))
   if label=='polled':
    objects=[]
    for index,ir in enumerate(sorted(translated.glob('shard-*.ll'))):
     polled=out/(str(index)+'.polled.ll');obj=out/(str(index)+'.polled.o');run([a.poll_instrument,ir,polled],'poll-'+str(index));run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',polled,'-o',obj],'compile-polled-'+str(index));objects.append(obj)
   exe=out/(label+'.exe');run([cxx,*flags,'-Wall','-Wextra','-Werror',wp(source/'vector_neg_2s_test.cpp'),*map(wp,common),*map(wp,objects),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);run([exe],'actual-Windows-'+label);actual=rows(out/('actual-Windows-'+label+'.log'));assert actual==expected,next((f'{i}: {x[:100]} != {y[:100]}'for i,(x,y)in enumerate(zip(expected,actual))if x!=y),'record count mismatch');assert 'NEG2S-WINDOWS-PASS records=4352'in(out/('actual-Windows-'+label+'.log')).read_text();hosts[label]=dict(executable=desc(exe),stdout=desc(out/('actual-Windows-'+label+'.log')),objects=[desc(p)for p in objects])
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,scope='Kernel-only actual NEG V0.2S,V0.2S and distinct V3.2S,V5.2S, original literalword and same NDK object across ARM and Windows. No full4456byte Unity function execution claimed.',toolchain={name:desc(tool/name)for name in('remill-lift','aarch64.bc')},reference=desc(out/'reference.json'),NDK_object=desc(core),guest=desc(guest),manifest=desc(translated/'manifest.json'),records_each=4352,records_sha256=hashlib.sha256(('\n'.join(expected)+'\n').encode()).hexdigest(),records_exact=True,integer_lane_model='two unsigned32 zero-minus-lane modulo2^32; upper64ofVd zero',input_pairs=272,register_shapes=['actualV0=V0','distinctV3=V5'],memory_alias_shapes=2,architecture_status_seeds=4,State1200_fullbytes_checked=True,Memory64=True,whole_Unity_function_claim=False,hosts=hosts,owned_sources={n:sha(source/n)for n in OWN},held_inputs=held,commands=commands,limits='Only2S vector arrangement. No newFP semantics, saturatingNEG, otherarrangements or fullUnity/helper behavior; selectedfunction lowering/static127neighbor proof separate. No game/fullbuild/system changes.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('NEG2S-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands),indent=2)+'\n');raise
if __name__=='__main__':main()
