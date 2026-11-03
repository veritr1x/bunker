"""Immutable static gates for the optional game collector profile; no game run."""
import argparse,ast,hashlib,json,subprocess,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('game_bootstrap.cpp','game_bootstrap_detail.h','game_collector_delivery.h','game_collector_mask.h','game_bootstrap_build.ps1','test_game_bootstrap.py','game_collector_profile.md','test_game_collector_source.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--build-support',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);support=a.build_support.resolve();root=HERE.parent.parent
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 owned={n:sha(HERE/n)for n in OWN};prerequisites={}
 priority_path=HERE.parent/'work/thread-priority-held1.json';priority=json.loads(priority_path.read_text());prerequisites[str(priority_path)]=sha(priority_path)
 focused=Path(priority['acceptance_path']);assert priority['passed']and sha(focused)==priority['acceptance_sha256'];qualified=json.loads(focused.read_text());assert qualified['passed'];prerequisites[str(focused)]=sha(focused)
 peer_path=HERE.parent/'work/priority-source-peer3/peer.json';assert sha(peer_path)=='0191336d24dd436573335a9d45fba278b4c4945df9893044d5da9a61eb31dd47';peer=json.loads(peer_path.read_text());assert peer['passed']and peer['source_files']==priority['core_sources'];prerequisites[str(peer_path)]=sha(peer_path)
 assert peer['old_jni_header_exact_after_only_reviewed_additions']and peer['old_jni_cpp_exact_after_only_reviewed_additions']
 assert peer['security_exception_catalog_delta_exact']and peer['security_exception_superclass']=='java/lang/RuntimeException'
 lease_path=Path(next(k for k in peer['evidence']if k.endswith('priority-source-peer1/peer.json')));assert sha(lease_path)==peer['evidence'][str(lease_path)];lease=json.loads(lease_path.read_text());assert lease['passed']and lease['pthread_old_cpp_body_exact_after_only_additions']and lease['pthread_old_header_exact_after_only_additions'];prerequisites[str(lease_path)]=sha(lease_path)
 for name,digest in priority['core_sources'].items():
  path=HERE.parent/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for name,digest in priority['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 base_archive=Path(priority['base_archive_path']);assert sha(base_archive)==priority['base_archive_sha256']==peer['base_archive_sha256'];prerequisites[str(base_archive)]=sha(base_archive)
 with tarfile.open(base_archive)as archive:
  old_pthreads={n:hashlib.sha256(archive.extractfile('recomp/windows/'+n).read()).hexdigest()for n in('pthread_host.h','pthread_host.cpp')}
 # Accepted component manifests pin the actual production inputs used here.
 for manifest,field,names in [('worker-signal-lifecycle-held4.json','seven_live_hashes',('worker_signal_lifecycle.h','worker_signal_lifecycle.cpp')),('pthread-wait-held.json','live_sources',('pthread_host.h','pthread_host.cpp')),('signal-sleep-held5.json','core_sources',('signal_host.h','signal_host.cpp','signal_sleep.h','signal_sleep.cpp'))]:
  path=HERE.parent/'work'/manifest;record=json.loads(path.read_text());prerequisites[str(path)]=sha(path)
  for name in names:
   if manifest=='pthread-wait-held.json':
    assert old_pthreads[name]==record[field][name],name
    assert sha(HERE/name)==lease['sources'][name]==priority['core_sources']['windows/'+name],name
   else:assert sha(HERE/name)==record[field][name],name
   prerequisites[str(HERE/name)]=sha(HERE/name)
  if manifest=='signal-sleep-held5.json':
   focused=Path(record['acceptance_path']);assert record['passed']and sha(focused)==record['acceptance_sha256'];prerequisites[str(focused)]=record['acceptance_sha256'];qualified=json.loads(focused.read_text())
   assert qualified['passed']and qualified['core']==record['core_sources']and qualified['arm64_records']==16
   for platform in ('linux','windows'):
    observed=qualified['platforms'][platform];assert'USLEEP-HOST-SUCCESS records=16'in observed['stdout']and'SIGNAL-DISPATCH-ALLOWED-SUCCESS'in observed['legacy_allowed_stdout']and'159 checks; NDK'in observed['legacy_default_stdout']
 futex_path=HERE.parent/'work/signal-futex-held1.json';futex=json.loads(futex_path.read_text());prerequisites[str(futex_path)]=sha(futex_path)
 focused=Path(futex['acceptance_path']);assert futex['passed']and sha(focused)==futex['acceptance_sha256'];prerequisites[str(focused)]=futex['acceptance_sha256'];qualified=json.loads(focused.read_text())
 assert qualified['passed']and qualified['core_sources']==futex['core_sources']and len(qualified['canonical_records'])==qualified['arm64_records']==23
 for name,digest in futex['core_sources'].items():
  path=HERE.parent/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for name,digest in futex['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for platform in ('linux','windows'):
  observed=qualified['platforms'][platform];assert'FUTEX-HOST-SUCCESS records=23'in observed['stdout']and observed['canonical_records']==qualified['canonical_records']
 audit=HERE.parent/'work/game20-first-gc-profile-audit/evidence.json';assert sha(audit)=='b4cf7340df35ab38d3e31b8dec70f5164356cd941590f70bd38f4893425052ca';data=json.loads(audit.read_text());original={str(audit):sha(audit)}
 for path,digest in data['files'].items():
  if '/work/' in path:assert sha(path)==digest,path;original[path]=digest
 library=support/'native/libil2cpp.so';assert sha(library)=='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522';original[str(library)]=sha(library)
 with library.open('rb')as f:
  elf=ELFFile(f);v=0x25aada0;segment=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=v<s['p_vaddr']+s['p_filesz']);assert segment.data()[v-segment['p_vaddr']:v-segment['p_vaddr']+4]==bytes.fromhex('c0035fd6')
 assert '{0x825aada0,' in (support/'game_traces.h').read_text(),'original return head absent'
 for n in ('test_game_bootstrap.py','test_game_collector_source.py'):ast.parse((HERE/n).read_text())
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(support/'remill-include'),'-I'+wp(support),'-I'+wp(support/'zlib-include'),'-I'+wp(support/'angle-include'),'-fsyntax-only',wp(HERE/'game_bootstrap.cpp')]
 results={}
 for name,macros,success in [('default',[],True),('enabled',['-DBUNKER_GAME_COLLECTOR_DELIVERY=1','-DBUNKER_GAME_COOPERATIVE_POLLS=1'],True),('missing-cohort',['-DBUNKER_GAME_COLLECTOR_DELIVERY=1'],False)]:
  with(out/(name+'.log')).open('w')as log:result=subprocess.run([str(cxx),*macros,*flags],stdout=log,stderr=subprocess.STDOUT)
  assert(result.returncode==0)==success,(name,result.returncode)
  if not success:assert 'Original collector delivery requires the qualified cooperative cohort'in(out/(name+'.log')).read_text()
  results[name]=result.returncode
 # Real Game19 was built without this capability. Verify refusal before any
 # runner hashing/launch/storage mutation; --verify-only cannot enable it.
 build=json.loads((support/'game_build.json').read_text());assert not build.get('collector_delivery_profile')
 result=subprocess.run([__import__('sys').executable,str(HERE/'test_game_bootstrap.py'),'--build',str(support),'--profile','frame-muted-gc','--verify-only'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/'unavailable-runner.log').write_text(result.stdout);assert result.returncode and'Original collector profile is unavailable'in result.stdout
 script=out/'parse.ps1';script.write_text('param([string]$Source)\n$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$t,[ref]$e)|Out-Null;if($e){$e|Out-String|Write-Output;exit 1}\n')
 with(out/'powershell-parse.log').open('w')as log:subprocess.run(['powershell.exe','-NoProfile','-File',wp(script),'-Source',wp(HERE/'game_bootstrap_build.ps1')],stdout=log,stderr=subprocess.STDOUT,check=True)
 for name,digest in owned.items():assert sha(HERE/name)==digest,name
 for path,digest in{**prerequisites,**original}.items():assert sha(path)==digest,path
 receipt={'passed':True,'scope':'static/source/CLI-capability gates only; no native game or guest code executed','owned_sources':owned,'component_inputs':prerequisites,'original_audit_inputs':original,'compiler':str(cxx),'compiler_sha256':sha(cxx),'syntax_exit_codes':results,'unavailable_runner_exit_code':result.returncode,'build_support':str(support),'evidence':{f.name:sha(f)for f in out.iterdir()if f.is_file()}};(out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('GAME-COLLECTOR-STATIC-PASS '+str(out/'acceptance.json'))
if __name__=='__main__':main()
