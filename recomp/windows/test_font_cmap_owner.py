"""Exact selected font bodies and original ARM/Bionic code; bounded owner profile."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=('font_cmap_cases.h','font_cmap_ref.c','font_cmap_owner_test.cpp','test_font_cmap_owner.py')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source-packet',type=Path,required=True);ap.add_argument('--source-sha',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120,allow_failure=False):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode and not allow_failure:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stderr.decode(errors='replace')[-5000:])
  return r
 try:
  assert sha(a.source_packet)==a.source_sha;pin(a.source_packet);packet=json.loads(a.source_packet.read_text());root=HERE.parent
  pending=['windows/'+n for n in OWN]+['windows/nonlocal_jmp.cpp','windows/nonlocal_jmp_test.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp','fastaes/elfload.c'];seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  reviewed={'windows/game_bootstrap.cpp':'cb127e9474a55f6da17f882453682f82eb6bc3fc0f98a6b9a52a89a49d0b5e29','windows/game_bootstrap_detail.h':'b0e4202e52bd1d06594373b5afa54cce3192176c232e1e682d0a438decbed210'}
  for name,digest in reviewed.items():assert sha(root/name)==digest;pin(root/name)
  assert sha(source/'windows/game_bootstrap_detail.h')==reviewed['windows/game_bootstrap_detail.h']
  native=W/'windows-first-frame-guest-transfer1/native/libunity.so';pin(native);assert sha(native)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
  from elftools.elf.elffile import ELFFile
  with native.open('rb')as f:
   elf=ELFFile(f);segments=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'];blobs={}
   for name,lo,n in [('outer',0x8d905c,588),('init',0x8e6e98,20)]:
    s=next(s for s in segments if s['p_vaddr']<=lo and lo+n<=s['p_vaddr']+s['p_filesz']);f.seek(s['p_offset']+lo-s['p_vaddr']);blobs[name]=f.read(n)
  generated=source/'windows/font_cmap_native_bytes.h';generated.write_text('\n'.join('static const unsigned char font_'+n+'_bytes[]={' + ','.join(map(str,b))+'};'for n,b in blobs.items())+'\n')
  selected=json.loads((W/'windows-first-frame-resize1/overlay.json').read_bytes());extractions=[];original_objects=[]
  for index,keep in [(303,{'sub_708d905c','sub_708d9240'}),(304,{'sub_708e6e98'})]:
   folder=Path('/home/user/bunker-recomp/recomp/work/guest-eh-candidate5')/('shard-'+str(index).zfill(5));row=selected['objects'][index];cache=folder/'fresh-cache.json';sealed=json.loads(cache.read_text());assert sealed['result']['built']is True and sealed['result']['module']=='unity';assert sha(row['path'])==sha(folder/'candidate.o')==row['sha256']==sealed['result']['object']['sha256'];assert sha(folder/'guarded.polled.ll')==sealed['result']['polled_ir']['sha256'];pin(cache);pin(row['path']);pin(folder/'candidate.o');pin(folder/'guarded.polled.ll');text=(folder/'guarded.polled.ll').read_text();retained={}
   def extract(m):
    body=m[0];name=re.search(r'@([^ (]+)\(',body)[1]
    if name in keep:retained[name]=hashlib.sha256(body.encode()).hexdigest();return body
    header=body.split('\n',1)[0].rstrip().removesuffix('{').rstrip();return re.sub(r'^define\s+(?:internal\s+|private\s+)?','declare ',header)
   isolated=re.sub(r'^define [^\n]+\{\n.*?^}',extract,text,flags=re.M|re.S);assert set(retained)==keep;ir=out/('original-'+str(index)+'.ll');ir.write_text(isolated);obj=out/('original-'+str(index)+'.o');run(['clang++-18','--target=x86_64-w64-windows-gnu','-O2','-x','ir','-c',ir,'-o',obj],'extract-'+str(index));original_objects.append(obj);extractions.append(dict(selected=row,selected_source_object=desc(folder/'candidate.o'),qualified_polled_IR=desc(folder/'guarded.polled.ll'),matching_producer_cache=desc(cache),function_body_sha256=retained,fixture_IR=desc(ir),fixture_object=desc(obj),scope='Fixture-only exact unchanged selected polled IR body extraction; new isolated codegen, not production object replacement or exact selected COFF byte-identity claim.'))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in(ndk,qemu,cxx):pin(p)
  reference=out/'original-font-Bionic';run([ndk,'-static','-O1','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'windows/font_cmap_ref.c','-o',reference],'compile-Bionic');r=run([qemu,reference],'actual-Bionic',30);arm=r.stdout.decode();records=[x for x in arm.splitlines()if x.startswith('FONT-REF ')];assert len(records)==6 and 'FONT-CMAP-BIONIC-PASS'in arm
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-ffunction-sections','-fdata-sections','-isystem',wp(W/'remill-src/include')];objects=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','windows/nonlocal_jmp.cpp','windows/font_cmap_owner_test.cpp']:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if name.endswith('_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'font-cmap-owner.exe';run([cxx,*map(wp,objects+original_objects),'-static','-pthread','-latomic','-lbcrypt','-Wl,--gc-sections','-o',wp(exe)],'link');r=run([exe],'actual-Windows',30);windows=r.stdout.decode();assert[x for x in windows.splitlines()if x.startswith('FONT-REF ')]==records;match=re.search(r'FONT-CMAP-PASS checks=(\d+) original_calls=(\d+) saves=(\d+) negatives=(\d+) State=1200 Memory64=8',windows);assert match,windows
  old=W/'nonlocal-windows';old_result=json.loads((old/'result.json').read_text());old_manifest=old/'guest/manifest.json';assert sha(old_manifest)==old_result['ndk_manifest_sha256'];old_guest=json.loads(old_manifest.read_text());assert not old_guest['unsupported_traces']and sha(old/'caller.so')==old_guest['sha256'];pin(old_manifest);pin(old/'result.json');pin(old/'caller.so');pin(old/'reference');pin(old/'android13-setjmp.S');assert sha(old/'android13-setjmp.S')=='cd0eacde5d3332c6726a0a07ccc0c37f8ac3eb4a5e90f6e3078e9c40875e0309'
  r=run([qemu,'-cpu','cortex-a53',old/'reference'],'existing-core-original-ARM',30);assert len(r.stdout)==4096 and not any(r.stdout)
  cc=Path('/mnt/c/mingw64/bin/gcc.exe');pin(cc);loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'compile-core-loader');core_obj=out/'core-test.o';run([cxx,*flags,'-I'+wp(old/'guest'),'-DNONLOCAL_LIBRARY="'+wp(old/'caller.so')+'"','-c',wp(source/'windows/nonlocal_jmp_test.cpp'),'-o',wp(core_obj)],'compile-existing-core');core=out/'existing-core.exe'
  for p in old_guest['objects']:pin(p)
  run([cxx,wp(core_obj),*map(wp,objects[:3]),wp(loader),*map(wp,old_guest['objects']),'-static','-pthread','-latomic','-lbcrypt','-Wl,--gc-sections','-o',wp(core)],'link-existing-core');r=run([core],'actual-existing-core',30);core_text=r.stdout.decode();assert 'Nonlocal context: 563 checks, 512 actual NDK caller records; longjmp transfer remains unsupported.'in core_text
  fatal={}
  for option,needle in [('--fatal-longjmp','controlled nonlocal transfer is unimplemented'),('--fatal-corrupt','checksum mismatch'),('--fatal-flag','unexpected signal flag bits')]:
   r=run([core,option],'existing-core-'+option[2:],30,True);assert r.returncode==3 and needle in r.stderr.decode();fatal[option]=dict(exit_code=r.returncode,stderr=desc(out/('existing-core-'+option[2:]+'.stderr')))
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,reviewed_production_sources=reviewed,production_source_packet=desc(a.source_packet),source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},owned_sources={n:sha(source/'windows'/n)for n in OWN},original_native_ELF=desc(native),original_ARM_bytes={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())for n,b in blobs.items()},original_extractions=extractions,reference=desc(reference),actual_Bionic_stdout=desc(out/'actual-Bionic.stdout'),actual_Windows_stdout=desc(out/'actual-Windows.stdout'),executable=desc(exe),focus=dict(checks=int(match[1]),actual_original_calls=int(match[2]),negative_checks=int(match[4]),Bionic_matched_cases=6,original_outer_bytes=588,original_init_bytes=20,real_Bionic_setjmp=True,actual_NonlocalJumps_Save_and_Inspect=True,State1200=True,Memory64=True),existing_core=dict(checks=563,actual_NDK_caller_records=512,original_Android13_save_records=512,original_reference_restore_records=64,reference_scope='Existing frozen original Android13 assembly with deterministic reference cookie/mask scaffolding, rerun under QEMU; separate six-case reference uses real native Bionic setjmp.',executable=desc(core),stdout=desc(out/'actual-existing-core.stdout'),fatal_children=fatal,source_result=desc(old/'result.json'),source_guest_manifest=desc(old_manifest)),records=records,commands=commands,held_inputs=held,limits='Test-owned cmap tables/class pointers and transparent callback fixtures. Original ARM outer588B/init20B execute at original addresses with native Bionic setjmp; Windows uses exact selected polled original IR bodies with current real Runtime/owner/NonlocalJumps. Validators and cmap constructors are explicit TEST callbacks, not claimed font-validation/allocation semantics. Synthetic owner-negative paths test lifetime and shape guards. No guest longjmp support, full original font pipeline, renderer/game execution or first-frame claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FONT-CMAP-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
