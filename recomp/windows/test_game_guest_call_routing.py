"""Freeze and run only the host Windows CallGuest routing/linker qualification."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
OWN=('game_guest_call_routing.h','game_guest_call_routing_test.cpp','test_game_guest_call_routing.py')
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pin(path):return dict(path=str(path),sha256=sha(path))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source-proof',type=Path,required=True);ap.add_argument('--source-proof-sha256',required=True);a=ap.parse_args()
 assert sha(a.source_proof)==a.source_proof_sha256
 out=a.out.resolve();assert not out.exists();out.mkdir();source=out/'sources';(source/'windows').mkdir(parents=True);(source/'whole').mkdir()
 owned={'windows/'+name:sha(HERE/name)for name in OWN}
 for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
 support=['windows/pthread_host.h','windows/android_types.h','windows/nonlocal_jmp.h','windows/nonlocal_jmp.cpp','windows/game_bootstrap_detail.h','whole/runtime.h','whole/runtime.cpp','whole/cooperative_poll.h','whole/cooperative_poll.cpp','whole/bridge.h','whole/guest_memory.h']
 for name in support:shutil.copyfile(a.repo/name,source/name)
 assert sha(source/'whole/runtime.h')=='7a3ee02b9ffbe0213f0ef514ae54a02d5bfd131271d4dd39b714a3d03e87ec54'
 assert sha(source/'whole/runtime.cpp')=='052411ac09dd05a6dd229d17f1f991a93ee984ae1f447416cefdf610629f1c56'
 proof=json.loads(a.source_proof.read_text());assert proof['owned_sources']==owned
 assert sha(source/'windows/game_bootstrap_detail.h')==proof['unchanged_save_helper_header']['sha256']
 incoming=proof['original_direct_incoming_audit'];assert sha(incoming['path'])==incoming['sha256']
 work=a.repo/'work';shutil.copytree(work/'remill-src/include',out/'remill-include')
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 cxx='/mnt/c/mingw64/bin/g++.exe';flags=['-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-attributes','-ffunction-sections','-fdata-sections','-DADDRESS_SIZE_BITS=64','-isystem',wp(out/'remill-include'),'-I'+wp(source/'windows')]
 commands=[]
 def run(argv,label):
  with(out/(label+'.log')).open('w')as log:r=subprocess.run(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT)
  commands.append(dict(label=label,argv=list(map(str,argv)),exit_code=r.returncode));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,(label,r.returncode)
 common=[]
 for name in ['whole/runtime.cpp','whole/cooperative_poll.cpp','windows/nonlocal_jmp.cpp']:
  obj=out/(Path(name).stem+'.o');run([cxx,*flags,'-c',wp(source/name),'-o',wp(obj)],'compile-'+obj.stem);common.append(obj)
 fixture=source/'windows/game_guest_call_routing_test.cpp';objects=[]
 for name,define in [('same','ROUTING_SAME_OBJECT'),('cross','ROUTING_CROSS_OBJECT')]:
  obj=out/(name+'.o');run([cxx,*flags,'-D'+define,'-c',wp(fixture),'-o',wp(obj)],'compile-'+name);objects.append(obj)
 # Actual COFF definition/reference roles are checked before either link.
 nm='/usr/lib/llvm-18/bin/llvm-nm';symbol_text={}
 for name in ['same','cross']:
  t=subprocess.check_output([nm,'--extern-only','--format=posix',str(out/(name+'.o'))],text=True);(out/(name+'-symbols.txt')).write_text(t);symbol_text[name]=t
 assert re.search(r'^sub_825b0544 T(?: |$)',symbol_text['same'],re.M)
 assert re.search(r'^sub_825b0544 U(?: |$)',symbol_text['cross'],re.M)
 assert all(re.search(r'^__bunker_guest_call U(?: |$)',t,re.M)for t in symbol_text.values())
 results={}
 for mode in ['legacy','adapter']:
  obj=out/(mode+'.o');run([cxx,*flags,*(['-DROUTING_LEGACY']if mode=='legacy'else[]),'-c',wp(fixture),'-o',wp(obj)],'compile-'+mode)
  exe=out/(mode+'.exe');argv=[cxx,wp(obj),*[wp(x)for x in objects+common],'-static','-pthread','-Wl,--gc-sections','-Wl,--wrap=sub_825b0544',*(['-Wl,--wrap=__bunker_guest_call']if mode=='adapter'else[]),'-latomic','-lbcrypt','-o',wp(exe)];run(argv,'link-'+mode)
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30);(out/(mode+'.stdout')).write_text(r.stdout);(out/(mode+'.stderr')).write_text(r.stderr);assert r.returncode==0,(mode,r.returncode,r.stderr)
  m=re.search(r'GUEST-CALL-ROUTING-PASS checks=(\d+) original_calls=(\d+) owned_calls=(\d+) legacy_wrap_calls=(\d+) forward_calls=(\d+) mode='+mode,r.stdout);assert m,(mode,r.stdout)
  counts=dict(zip(['checks','original_calls','owned_calls','legacy_wrap_calls','forward_calls'],map(int,m.groups())));assert counts['original_calls']==3
  assert(counts['owned_calls'],counts['legacy_wrap_calls'],counts['forward_calls'])==((2,1,0)if mode=='legacy'else(3,0,5))
  results[mode]=dict(exit_code=r.returncode,**counts,binary=pin(exe),stdout=pin(out/(mode+'.stdout')),stderr=pin(out/(mode+'.stderr')));print(mode,counts,flush=True)
 result=dict(passed=True,scope='Host Windows COFF/linker route plus actual qualified Runtime and unchanged GameOriginalSaveHelper around explicitly TEST original callbacks; no ARM/game execution claim',owned_sources=owned,source_proof=pin(a.source_proof),original_direct_incoming_audit=incoming,support_sources={name:sha(source/name)for name in support},results=dict(windows=results),controls=dict(same_object_definition_and_cross_object_undefined_COFF_verified=True,legacy_wrap_sub_misses_same_object=True,new_wrap_CallGuest_routes_same_and_cross=True,dynamic_null_retains_selected_table_Dispatch=True,ordinary_direct_and_dynamic_unchanged=True,all_six_inputs_and_actual_State_forwarded=True,opaque64_input_and_output_tokens_unchanged=True,exact_original_Memory_result=True,all1200_State_changes_only_TEST_original=True,errno_FENV_LastError_before_and_after_original_preserved=True,unchanged_GameOriginalSaveHelper_body_compiled=True,actual_nonlocal_save_registration_and_Forget_exercised=True),commands=commands,evidence={name:pin(out/name)for name in ['same.o','cross.o','same-symbols.txt','cross-symbols.txt','commands.json']},limits='Synthetic native caller/helper COFFs test link interception and unchanged existing owner machinery. No newly lifted guest, original save-helper ISA execution, general Runtime dispatch policy change, full collector qualification or original frame claim.')
 (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('ACCEPTANCE',sha(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
