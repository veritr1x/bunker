"""Prepare NEW three-original-API preinit variant after accepted7a32580."""
import argparse,copy,hashlib,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_EXE='f56febe53244ac87e519345e94f237667befc9a1380076e142d4a93497ec72b0'
BASE_INPUTS='2f21c9289334ded5c01eb03a519f569100acc75577b1cfeb7d1d0ce1384e04ec'
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise RuntimeError('New preinit variant requires a fresh workdir; never overwrite prior artifacts')
 old=json.loads((a.base_build/'icall_inputs.json').read_text());audit=json.loads((a.base_build/'icall-final-audit.json').read_text())
 if sha(a.base_build/'icall_inputs.json')!=BASE_INPUTS or sha(a.base_build/'bunker-unity-icalls.exe')!=BASE_EXE or audit['executable_sha256']!=BASE_EXE or audit['inputs_sha256']!=BASE_INPUTS:raise RuntimeError('Not the accepted7a32580 registration-only cohort')
 if old['host_commit']!='1942e24f1864ad686fb5b3d0ab0155d718e95d66'or old['union_trace_count']!=453342 or len(old['objects'])!=3548 or old['missing_direct_guest_targets']:raise RuntimeError('Frozen original source/trace/object ownership differs')
 for name,h in old['source_hashes'].items():
  if sha(a.base_build/'sources'/name)!=h:raise RuntimeError('Prior frozen source changed:'+name)
 for name,h in old['registration_preparation_hashes'].items():
  if sha(a.base_build/'sources/windows'/name)!=h:raise RuntimeError('Prior registration source changed:'+name)
 roots=[0x8254ddb4,0x825bb290,0x8254db80,0x82588f34,0x8254d16c,0x825baac8,0x825baac4,0x825bdb08,0x70371778,0x70371784,0x70419c74,0x70425524]
 entries={int(v,16)for v in re.findall(r'\{0x([0-9a-f]+),sub_',(a.base_build/'combined_traces.h').read_text())}
 if not set(roots)<=entries:raise RuntimeError('Actual API/getter/lifetime root unavailable')
 a.out.mkdir(parents=True)
 for name in ['sources','remill-include','zlib-include','audit']:shutil.copytree(a.base_build/name,a.out/name)
 for source in a.base_build.glob('*.h'):shutil.copyfile(source,a.out/source.name)
 for name in ['object-symbols.txt','cross-state-layout.old.txt','cross-state-layout.new.txt','il2cpp_module_exports_proof.json']:shutil.copyfile(a.base_build/name,a.out/name)
 meta=copy.deepcopy(old);meta['preinit_base_gate']=dict(commit='7a32580',directory=str(a.base_build),inputs_sha256=BASE_INPUTS,executable_sha256=BASE_EXE)
 (a.out/'native').mkdir()
 for module in meta['modules']:
  source=a.base_build/'native'/('lib'+module['name']+'.so');target=a.out/'native'/source.name
  if sha(source)!=module['sha256']:raise RuntimeError('Original image bytes differ')
  shutil.copyfile(source,target);module['data']=str(target.absolute())
 meta['preinit_preparation_hashes']={}
 for name in ['unity_preinit.cpp','unity_preinit_prepare.py','unity_preinit_build.ps1','test_unity_preinit.ps1','unity_preinit.md']:
  target=a.out/'sources/windows'/name;shutil.copyfile(HERE/name,target);meta['preinit_preparation_hashes'][name]=sha(target)
 meta['source_hashes']['windows/unity_preinit.cpp']=sha(HERE/'unity_preinit.cpp')
 for name in ['combined_traces.h','combined_metadata.h','unity_bootstrap_data.h','il2cpp_data.h','il2cpp_module_exports.h','icall_inventory.h']:
  target=a.out/name;meta['input_hashes'][str(target.absolute())]=sha(target)
 meta['preinit_profile']=dict(apis=[dict(name='il2cpp_register_log_callback',entry=0x8254ddb4),dict(name='il2cpp_runtime_unhandled_exception_policy_set',entry=0x8254db80),dict(name='il2cpp_set_commandline_arguments',entry=0x8254d16c)],required_roots=roots,argv=dict(getters=[0x70371778,0x70371784],owner=0x712bee00,array=0x712bee18,count=0x712bf618,guard=0x712bf620,maximum=256,never_invent=True),consumer_destructor=dict(entry=0x825baac4,object=0x879a7608,dso=0x8740c790,registration_lr=0x820cd264),input_destructor=dict(entry=0x70419c74,object=0x712bee00,dso=0x7123eac0,registration_lr=0x70419b5c),prohibited=['paths/config-dir/data-dir','debugger builder/API','lazy Unity manager','3bd0d8','Managed copy success claim','il2cpp_init/init_utf16','GC','managed code','stored native targets'])
 (a.out/'preinit_inputs.json').write_text(json.dumps(meta,indent=2)+'\n')
 print('New three-API preinit variant frozen;live argv required,no synthetic inputs or init/copy execution.')
if __name__=='__main__':main()
