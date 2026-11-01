"""Freeze a NEW original-API-loader variant; preserve the approved combined gate."""
import argparse,copy,hashlib,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise RuntimeError('New variant requires a fresh directory; never overwrite prior evidence')
    old=json.loads((a.base_build/'combined_inputs.json').read_text());audit=json.loads((a.base_build/'combined-final-audit.json').read_text())
    if audit['executable_sha256']!='5881a4910072ebaaab45f7537a85f53c7203c46425d197a31dbc66c9bf1449bd' or sha(a.base_build/'bunker-combined-modules.exe')!=audit['executable_sha256']:raise RuntimeError('Not the approved1756d78 combined executable')
    if sha(a.base_build/'combined_inputs.json')!=audit['inputs_sha256']or old['host_commit']!='1942e24f1864ad686fb5b3d0ab0155d718e95d66':raise RuntimeError('Approved frozen input lineage differs')
    if old['union_trace_count']!=453342 or len(old['objects'])!=3548 or old['missing_direct_guest_targets']:raise RuntimeError('Base trace ownership/closure incomplete')
    for name,expected in old['source_hashes'].items():
        if sha(a.base_build/'sources'/name)!=expected:raise RuntimeError('Frozen source changed:'+name)
    entries={int(v,16)for v in re.findall(r'\{0x([0-9a-f]+),sub_', (a.base_build/'combined_traces.h').read_text())}
    roots=[0x703b7650,0x70384764,0x70384aa0,0x70384c94,0x7043ab34,0x70ab72e8,0x7041a214,0x700e0044]
    if not set(roots)<=entries:raise RuntimeError('Actual loader/cleanup entry unavailable: '+str([hex(x)for x in set(roots)-entries]))
    a.out.mkdir(parents=True);shutil.copytree(a.base_build/'sources',a.out/'sources');shutil.copytree(a.base_build/'remill-include',a.out/'remill-include');shutil.copytree(a.base_build/'zlib-include',a.out/'zlib-include')
    for source in a.base_build.glob('*.h'):shutil.copyfile(source,a.out/source.name)
    for name in ['object-symbols.txt','cross-state-layout.old.txt','cross-state-layout.new.txt','il2cpp_module_exports_proof.json']:shutil.copyfile(a.base_build/name,a.out/name)
    metadata=copy.deepcopy(old);metadata['base_gate']=dict(commit='1756d78',directory=str(a.base_build),inputs_sha256=audit['inputs_sha256'],executable_sha256=audit['executable_sha256'])
    (a.out/'native').mkdir()
    for module in metadata['modules']:
        source=a.base_build/'native'/('lib'+module['name']+'.so');target=a.out/'native'/source.name
        if sha(source)!=module['sha256']:raise RuntimeError('Original data image changed')
        shutil.copyfile(source,target);module['data']=str(target.absolute())
    metadata['variant_preparation_hashes']={}
    for name in ['unity_api_loader.cpp','unity_api_loader_prepare.py','unity_api_loader_build.ps1']:
        target=a.out/'sources/windows'/name;shutil.copyfile(HERE/name,target);metadata['variant_preparation_hashes'][name]=sha(target)
    metadata['source_hashes']['windows/unity_api_loader.cpp']=sha(HERE/'unity_api_loader.cpp')
    metadata['api_loader_profile']=dict(entry=0x703b7650,argument='X0 points to live actual helper-produced guarded40-byte NativeString',return_value='W0 bit0 boolean',
      required_roots=roots,slots=0x712bbfd0,count=222,handle=0x712bc6c0,cache=0x712b97c0,
      queue=dict(base=0x7127ef90,count=0x7127fb90,active=0x7127fb98,dirty=0x7127fba0,require_empty=True),
      jni_cache=dict(head=0x7130da68,require_empty_cleanup_closure=True,unknown_callback='precondition failure before APIloader'),
      teardown=dict(onunload_before_close=True,guest_close=0x70384764,map_initializer_not_destructor=0x70384aa0,
        retained='persistent empty-map allocation and unchanged stale top slots/handle until process exit; no reuse/reset/reopen/API calls'),
      prohibited=['RegisterModules','il2cpp_init','GC','managed bodies','nonempty startup queue','UnityTLS setter'])
    (a.out/'api_loader_inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('New frozen APIloader variant prepared; all cleanup roots available; prior gate untouched. Runtime has not executed.')
if __name__=='__main__':main()
