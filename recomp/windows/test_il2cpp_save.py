"""One fresh original save-helper process; all accepted artifacts stay immutable."""
import argparse,hashlib,json,pathlib,re,subprocess
from il2cpp_stack_prepare import hashes,absolute
HERE=pathlib.Path(__file__).resolve().parent
OWN=['il2cpp_save.cpp','il2cpp_save_audit.h','il2cpp_save_guest.S','il2cpp_save_guest.c','il2cpp_save_prepare.py','il2cpp_save_build.ps1','test_il2cpp_save.py','il2cpp_save.md']
def sha(path):
 with pathlib.Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--apk',type=pathlib.Path,required=True);a=p.parse_args();build=a.build.resolve()
 m=json.loads((build/'il2cpp_save_inputs.json').read_text());record=json.loads((build/'il2cpp_save_build.json').read_text())
 expected={**m['prior_artifacts_sha256'],**{str(pathlib.Path(m['baseline'])/x['path']):x['sha256']for x in m['original_objects']+m['objects']},**{str(build/'sources'/k):v for k,v in m['source_sha256'].items()},**{str(build/k):v for field in ['frozen_support_sha256','headers_sha256']for k,v in m[field].items()},**{x['path']:x['sha256']for x in m['fixture']['objects']}}
 expected.update({str(build/'il2cpp_save_inputs.json'):record['inputs_sha256'],str(build/'il2cpp-save.exe'):record['executable_sha256'],str(a.apk):m['APK_sha256'],m['fixture']['library']:m['fixture']['sha256'],str(build/'guest/manifest.json'):m['fixture']['manifest_sha256']})
 def verify():
  actual=hashes([pathlib.Path(x)for x in expected]);assert all(actual[str(absolute(k))]==v for k,v in expected.items()),'frozen or prior artifact changed'
 verify()
 def wp(path):return subprocess.check_output(['wslpath','-m',str(pathlib.Path(path).resolve())],text=True).strip()
 storage=build/'data-save-only';storage.mkdir(exist_ok=True)
 command=[str(build/'il2cpp-save.exe'),wp(m['original_ELF']),wp(a.apk),wp(storage),wp(m['fixture']['library'])]
 run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120);text=run.stdout.decode(errors='replace');log=build/'il2cpp-save-run.log';log.write_text(text);print(text,end='');verify()
 assert run.returncode==0 and all(s in text for s in ['IL2CPP actual save helper passed: entry=0x825b0544','registration revoked before outer caller resumes','IL2CPP save-only gate passed:','9 actual constructors,2 reverse finalizers,current-thread cleanup'])
 observed=re.search(r'actual env=(0x[0-9a-f]+) frameSP=(0x[0-9a-f]+) callbackSP=(0x[0-9a-f]+) generation=(\d+) mask=(0x[0-9a-f]+)',text);assert observed and int(observed[1],16)==int(observed[2],16)+8 and int(observed[3],16)<=int(observed[2],16)
 count=re.search(r'IL2CPP save-only gate passed: (\d+) checks',text);assert count
 bad=build/'invalid-probe.so';bad.write_bytes(b'not the approved strict NDK fixture')
 negative=subprocess.run(command[:-1]+[wp(bad)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20);negative_text=negative.stdout.decode(errors='replace');(build/'invalid-probe.log').write_text(negative_text)
 assert negative.returncode==1 and 'strict NDK fixture hash differs'in negative_text and 'IL2CPP stack constructor 'not in negative_text
 verify()
 final=dict(status='actual original save-only helper passed',checks=int(count[1]),exit_code=run.returncode,host_commit=m['host_commit'],base_gate=m['base_gate'],executable_sha256=record['executable_sha256'],inputs_sha256=record['inputs_sha256'],run_log_sha256=sha(log),original_helper='0x825b0544',actual_environment=observed[1],actual_saved_sp=observed[2],actual_callback_sp=observed[3],environment_generation=int(observed[4]),actual_mask=observed[5],environment_revoked_before_outer_caller_resumed=True,all_prior_objects_and_frozen_inputs_reverified=True,negative_fixture_hash_rejection=True,fixture=m['fixture'],limits=m['gate'],source_sha256={name:sha(HERE/name)for name in OWN})
 (build/'il2cpp_save_final_audit.json').write_text(json.dumps(final,indent=2)+'\n')
if __name__=='__main__':main()
