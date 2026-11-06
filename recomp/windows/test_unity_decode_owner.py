"""Actual selected92B inner/Bionic normal paths and two-level lifetime owner gate."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,traceback
HERE=Path(__file__).resolve().parent;W=Path('/mnt/c/GitRepos/bunker/recomp/work')
OWN=['unity_decode_ref.c','unity_decode_owner_test.cpp','test_unity_decode_owner.py']
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(Path(p).resolve())],text=True).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source-packet',type=Path,required=True);ap.add_argument('--source-sha',required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);source=out/'source';commands=[];held={}
 def pin(p):held[str(Path(p).resolve())]=sha(p)
 def run(argv,label,timeout=120):
  argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print('STAGE',label,flush=True);r=subprocess.run(argv,capture_output=True,timeout=timeout);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  if r.returncode:raise RuntimeError(label+' exit='+str(r.returncode)+'\n'+r.stdout.decode(errors='replace')[-1500:]+'\n'+r.stderr.decode(errors='replace')[-5000:])
  return r
 try:
  assert sha(a.source_packet)==a.source_sha;pin(a.source_packet);packet=json.loads(a.source_packet.read_text());reviewed=packet['production_sources'];root=HERE.parent
  pending=['windows/'+n for n in OWN]+['windows/nonlocal_jmp.cpp','windows/font_cmap_owner_test.cpp','whole/runtime.cpp','whole/cooperative_poll.cpp'];seen=set()
  while pending:
   name=pending.pop();p=(root/name).resolve();name=str(p.relative_to(root))
   if name in seen:continue
   seen.add(name);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);pin(p)
   for inc in re.findall(r'^\s*#include\s*"([^"]+)"',p.read_text(errors='replace'),re.M):
    q=(p.parent/inc).resolve()
    if q.is_file()and q.is_relative_to(root):pending.append(str(q.relative_to(root)))
  for n,h in reviewed.items():assert sha(root/n)==h;pin(root/n)
  assert sha(source/'windows/game_bootstrap_detail.h')==reviewed['windows/game_bootstrap_detail.h']
  static=W/'runtime20-setjmp-frontier1/acceptance.json';assert sha(static)=='55cba8a89f120d39edd09b611b66ee9e9755776ed9f7bbc4584e2ec459fd5fee';pin(static);proof=json.loads(static.read_text());inner=next(x for x in proof['primary_FDEs']if x['name']=='inner')['original_bytes'];assert sha(inner['path'])==inner['sha256'];pin(inner['path']);blob=Path(inner['path']).read_bytes();assert len(blob)==92
  (source/'windows/unity_decode_native_bytes.h').write_text('static const unsigned char decode_inner_bytes[]={'+','.join(map(str,blob))+'};\n')
  selected=proof['current_selected_sources'][1]['current_object'];assert sha(selected['path'])==selected['sha256'];pin(selected['path'])
  undefined=run(['llvm-nm-18','--undefined-only',selected['path']],'selected-undefined').stdout.decode();names=re.findall(r'\bU (sub_[0-9a-f]+)',undefined);stubs=[n for n in names if n not in ['sub_700b92b0','sub_70a82428']]
  generated=source/'windows/unity_decode_unexpected.cpp';generated.write_text('#include "../whole/runtime.h"\n#include <cstdio>\n#include <cstdlib>\n'+''.join('extern "C" Memory* '+n+'(State&,addr_t,Memory*){std::fputs("unexpected guest '+n+'\\n",stderr);std::abort();}\n'for n in stubs))
  ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');cxx=Path('/mnt/c/mingw64/bin/g++.exe')
  for p in [ndk,qemu,cxx]:pin(p)
  reference=out/'original-inner-Bionic';run([ndk,'-static','-O1','-fno-emulated-tls','-Wall','-Wextra','-Werror',source/'windows/unity_decode_ref.c','-o',reference],'compile-Bionic');arm=run([qemu,reference],'actual-Bionic',30).stdout.decode();records=[l for l in arm.splitlines()if l.startswith('DECODE-REF ')];assert len(records)==6 and 'UNITY-DECODE-BIONIC-PASS'in arm
  flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-ffunction-sections','-fdata-sections','-isystem',wp(W/'remill-src/include')];objects=[]
  for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','windows/nonlocal_jmp.cpp','windows/unity_decode_owner_test.cpp','windows/unity_decode_unexpected.cpp']:
   obj=out/(Path(name).stem+'.o');run([cxx,*flags,'-Wall','-Wextra',*(['-Werror']if name.endswith('_test.cpp')else[]),'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);objects.append(obj)
  exe=out/'unity-decode-owner.exe';run([cxx,*map(wp,objects),wp(selected['path']),'-Wl,--wrap=sub_70a8aa64','-Wl,--wrap=__bunker_guest_call','-static','-pthread','-latomic','-lbcrypt','-Wl,--gc-sections','-o',wp(exe)],'link');windows=run([exe],'actual-Windows',30).stdout.decode();assert [l for l in windows.splitlines()if l.startswith('DECODE-REF ')]==records;match=re.search(r'UNITY-DECODE-OWNER-PASS checks=(\d+) negatives=(\d+) actual_inner=92 outer_test_harness=1 State=1200 Memory64=8',windows);assert match,windows
  old=W/'font-cmap-owner-qualification5';font_objects=[old/'original-303.o',old/'original-304.o']
  for p in font_objects:pin(p)
  font_obj=out/'font-regression.o';run([cxx,*flags,'-Wall','-Wextra','-Werror','-c',wp(source/'windows/font_cmap_owner_test.cpp'),'-o',wp(font_obj)],'compile-font-regression');font=out/'font-regression.exe';run([cxx,wp(font_obj),*map(wp,objects[:3]+font_objects),'-static','-pthread','-latomic','-lbcrypt','-Wl,--gc-sections','-o',wp(font)],'link-font-regression');font_stdout=run([font],'actual-font-regression',30).stdout.decode();assert 'FONT-CMAP-PASS checks=267 original_calls=6 saves=2 negatives=18 State=1200 Memory64=8'in font_stdout,font_stdout
  for p,h in held.items():assert sha(p)==h,p
  result=dict(passed=True,reviewed_production_sources=reviewed,production_source_packet=desc(a.source_packet),original_static_proof=desc(static),actual_selected_object=selected,actual_selected_object_linked_byte_exact=True,actual_selected_inner_executed=True,original_inner_bytes=92,original_outer_bytes=1080,actual_original_outer_executed=False,outer_invocation_test_harness=True,Bionic_matched_cases=6,checks=int(match[1]),negative_checks=int(match[2]),normal_repeated_inner_while_outer_live=True,fresh_generation_each_inner_invocation=True,expired_inner_while_outer_live_rejected=True,same_outer_live_inner_reentry_rejected=True,nested_outer_inner_lifetimes_checked=True,wrong_owner_thread_generation_geometry_and_return_rejected=True,State1200=True,Memory64=True,guest_longjmp_enabled=False,old_font_owner_regression=dict(passed=True,checks=267,negative_checks=18,stdout=desc(out/'actual-font-regression.stdout'),executable=desc(font)),records=records,source_snapshot={str(p.relative_to(source)):desc(p)for p in source.rglob('*')if p.is_file()},owned_sources={n:sha(source/'windows'/n)for n in OWN},actual_Bionic_stdout=desc(out/'actual-Bionic.stdout'),actual_Windows_stdout=desc(out/'actual-Windows.stdout'),reference=desc(reference),executable=desc(exe),commands=commands,held_inputs=held,limits='Actual unmodified92B ARM inner executes with real native Bionic setjmp; Windows links byteexact actual selected shard377 and executes its original inner. Decoder/cleanup are explicit TEST callback boundaries; no full decoder semantics claimed. Outer1080B only statically proved; TEST harness simulates exact original outer object geometry and callsite, never claimed original outer execution. Owner guards test repeated/nested/expired/recycled invocations and native unwind; no arbitrary stack admission, guest longjmp, original game, visible frame or full-bootstrap functional execution claim.')
  (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('UNITY-DECODE-QUALIFIED',sha(out/'acceptance.json'),flush=True)
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps(dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands,held_inputs=held),indent=2)+'\n');raise
if __name__=='__main__':main()
