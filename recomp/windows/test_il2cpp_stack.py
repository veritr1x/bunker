"""Run one fresh original stack-top-only process and reverify prior artifacts."""
import argparse,json,pathlib,subprocess,hashlib,re
from il2cpp_stack_prepare import hashes,absolute
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=pathlib.Path,required=True);p.add_argument('--apk',type=pathlib.Path,required=True);a=p.parse_args();m=json.loads((a.build/'il2cpp_stack_inputs.json').read_text());record=json.loads((a.build/'il2cpp_stack_build.json').read_text())
 first=hashes([a.build/'il2cpp_stack_inputs.json',a.build/'il2cpp-stack.exe',a.apk])
 assert first[str(absolute(a.build/'il2cpp_stack_inputs.json'))]==record['inputs_sha256']and first[str(absolute(a.build/'il2cpp-stack.exe'))]==record['executable_sha256']and first[str(absolute(a.apk))]==m['APK_sha256']
 def prior():
  files={**m['prior_artifacts_sha256'],**{str(pathlib.Path(m['baseline'])/item['path']):item['sha256']for item in m['original_objects']+m['objects']}}
  actual=hashes([pathlib.Path(x)for x in files])
  for name,want in files.items():assert actual[str(absolute(name))]==want,name
 prior()
 def wp(path):return subprocess.check_output(['wslpath','-m',str(path.resolve())],text=True).strip()
 storage=a.build/'data-stack-only';storage.mkdir(exist_ok=True)
 result=subprocess.run([str((a.build/'il2cpp-stack.exe').resolve()),wp(pathlib.Path(m['original_ELF'])),wp(a.apk),wp(storage)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 text=result.stdout.decode(errors='replace');(a.build/'il2cpp-stack-run.log').write_text(text);print(text,end='');prior()
 if result.returncode or not all(x in text for x in ['IL2CPP actual stack helper passed: entry=0x825b1974','IL2CPP stack gate passed:','9 actual constructors,2 reverse finalizers,current-thread cleanup']):raise RuntimeError('Actual original stack gate failed; preserved log')
 observed=re.search(r'guest=\[(0x[0-9a-f]+),(0x[0-9a-f]+)\) result=(0x[0-9a-f]+)',text);assert observed and observed[2]==observed[3]
 final={'status':'actual original parameterless stack helper passed','exit_code':result.returncode,'host_commit':m['host_commit'],'executable_sha256':record['executable_sha256'],'inputs_sha256':record['inputs_sha256'],'run_log_sha256':digest(a.build/'il2cpp-stack-run.log'),'actual_helper':'0x825b1974','actual_guest_base':observed[1],'actual_guest_top':observed[2],'result':observed[3],'prior_artifacts_and_all3079objects_unchanged':True,'limits':m['gate'],'source_sha256':{name:digest(pathlib.Path(__file__).parent/name)for name in ['il2cpp_stack.cpp','il2cpp_stack_prepare.py','il2cpp_stack_build.ps1','il2cpp_stack_hashes.ps1','test_il2cpp_stack.py','il2cpp_stack.md']}}
 (a.build/'il2cpp_stack_final_audit.json').write_text(json.dumps(final,indent=2)+'\n')
if __name__=='__main__':main()
