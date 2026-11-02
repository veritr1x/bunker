"""Verify the original Managed copy and preserved baseline after its native run."""
import argparse,hashlib,json
from pathlib import Path
from unity_managed_copy_prepare import batch
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);a=p.parse_args()
 m=json.loads((a.build/'managed_inputs.json').read_text());r=json.loads((a.build/'managed_build_record.json').read_text());text=(a.build/'managed-run.log').read_text(errors='replace')
 assert r['status']=='native link passed' and r['run_exit_code']==0
 assert sha(a.build/'managed_inputs.json')==r['inputs_sha256'] and sha(a.build/'bunker-unity-managed-copy.exe')==r['executable_sha256']
 for token in ['MANAGED copied actual APK tree24 files24570231 bytes','MANAGED copied metadata real fd/read/mmap after fd-close SHA256/CRC d1b42bda/version24 exact; mapping retired','live=0 renameCalls=','original once acquire=2 release=1','MANAGED actual component teardown421934/4151dc/2390bc passed','ORIGINAL MANAGED COPY bounded gate passed:']:
  assert token in text,token
 assert text.count('Unity constructor ')==417 and text.count('IL2CPP constructor ')==9
 assert text.count('Unity finalizer ')==2 and text.count('IL2CPP finalizer ')==2
 actual=batch(m['previous_artifacts_sha256'],a.build)
 for path,value in m['previous_artifacts_sha256'].items():assert actual[str(Path(path).absolute())]==value,path
 sources={str(f.relative_to(a.build/'sources')):sha(f) for f in(a.build/'sources').rglob('*') if f.is_file()}
 assert sources==m['source_hashes']
 for name in ['unity_managed_copy.cpp','unity_managed_copy_prepare.py','unity_managed_copy_build.ps1','unity_managed_copy_hashes.ps1','test_unity_managed_copy.py','unity_managed_copy.md']:
  assert sha(Path(__file__).parent/name)==m['source_hashes']['windows/'+name],name
 proof=dict(status='original Managed-copy component passed',host_commit=m['host_commit'],executable_sha256=r['executable_sha256'],input_sha256=r['inputs_sha256'],run_log_sha256=sha(a.build/'managed-run.log'),inherited_objects_unchanged=sum('replaces'not in x for x in m['objects']),accepted_guest_replacements=sum('replaces'in x for x in m['objects']),expected_files=24,expected_bytes=24570231,source_sha256={n:sha(Path(__file__).parent/n) for n in ['unity_managed_copy.cpp','unity_managed_copy_prepare.py','unity_managed_copy_build.ps1','unity_managed_copy_hashes.ps1','test_unity_managed_copy.py','unity_managed_copy.md']},scope=m['gate'])
 (a.build/'managed-final-audit.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
