"""Prepare a NEW frozen actual internal-call registration variant of574235f."""
import argparse,copy,hashlib,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_EXE='27aebf55092e792f548e714cab17faab193a39bfc38fdfc2e85eb2cfdbfb90ef'
BASE_INPUTS='487961c87aadb58ab0ad560a78685e835a71b85ce024f86e2c7594adf1bf53f3'
INVENTORY='9856925ca64f522503d10f132ba057e44f99559a1281a038a5d09653e781c61d'
def sha(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-build',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise RuntimeError('New variant requires a fresh directory; preserve every previous gate')
    old=json.loads((a.base_build/'api_loader_inputs.json').read_text());audit=json.loads((a.base_build/'api-loader-final-audit.json').read_text())
    if sha(a.base_build/'api_loader_inputs.json')!=BASE_INPUTS or sha(a.base_build/'bunker-unity-api-loader.exe')!=BASE_EXE:raise RuntimeError('Not the approved574235f original-loader input/executable')
    if audit['input_sha256']!=BASE_INPUTS or audit['executable_sha256']!=BASE_EXE or old['host_commit']!='1942e24f1864ad686fb5b3d0ab0155d718e95d66':raise RuntimeError('Frozen baseline lineage differs')
    if old['union_trace_count']!=453342 or len(old['objects'])!=3548 or old['missing_direct_guest_targets']:raise RuntimeError('Original union ownership/direct-target closure differs')
    for name,expected in old['source_hashes'].items():
        if sha(a.base_build/'sources'/name)!=expected:raise RuntimeError('Frozen source changed:'+name)
    inventory_path=a.audit/'icall-registration.json'
    if sha(inventory_path)!=INVENTORY:raise RuntimeError('Unapproved original registration inventory')
    inventory=json.loads(inventory_path.read_text());rows=inventory['resolved'];summary=json.loads((a.audit/'summary.json').read_text())
    if len(rows)!=1987 or inventory['unresolved']or len({r['name']for r in rows})!=1987 or len({r['native_rva']for r in rows})!=1987:raise RuntimeError('Registration inventory incomplete/ambiguous')
    if inventory['source_sha256']!='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f':raise RuntimeError('Original Unity bytes differ')
    if any(not all(r[k]for k in ['executable','aligned','native_root_present','wrapper_root_present'])for r in rows):raise RuntimeError('Native/wrapper root proof incomplete')
    entries={int(v,16)for v in re.findall(r'\{0x([0-9a-f]+),sub_', (a.base_build/'combined_traces.h').read_text())}
    roots={0x709dd61c,0x700dd318,0x703afe28,0x8254d19c,0x8254d1a0,0x8257cdc0,0x82590024,0x82602418,0x826024d8}
    for row in rows:roots|={row['native_guest'],0x70000000+row['wrapper']}
    if not roots<=entries:raise RuntimeError('Registration/cleanup original trace roots unavailable')
    if len([r for r in rows if r['native_entry_unsupported']])!=3:raise RuntimeError('Old unsupported native-body inventory differs')
    a.out.mkdir(parents=True);shutil.copytree(a.base_build/'sources',a.out/'sources');shutil.copytree(a.base_build/'remill-include',a.out/'remill-include');shutil.copytree(a.base_build/'zlib-include',a.out/'zlib-include')
    for source in a.base_build.glob('*.h'):shutil.copyfile(source,a.out/source.name)
    for name in ['object-symbols.txt','cross-state-layout.old.txt','cross-state-layout.new.txt','il2cpp_module_exports_proof.json']:shutil.copyfile(a.base_build/name,a.out/name)
    metadata=copy.deepcopy(old);metadata['registration_base_gate']=dict(commit='574235f',directory=str(a.base_build),inputs_sha256=BASE_INPUTS,executable_sha256=BASE_EXE)
    (a.out/'native').mkdir()
    for module in metadata['modules']:
        source=a.base_build/'native'/('lib'+module['name']+'.so');target=a.out/'native'/source.name
        if sha(source)!=module['sha256']:raise RuntimeError('Original data image changed')
        shutil.copyfile(source,target);module['data']=str(target.absolute())
    metadata['registration_preparation_hashes']={}
    for name in ['unity_icalls.cpp','unity_icalls_prepare.py','unity_icalls_build.ps1','test_unity_icalls.ps1','unity_icalls.md']:
        target=a.out/'sources/windows'/name;shutil.copyfile(HERE/name,target);metadata['registration_preparation_hashes'][name]=sha(target)
    metadata['source_hashes']['windows/unity_icalls.cpp']=sha(HERE/'unity_icalls.cpp')
    lines=['#pragma once','namespace icall_image {','struct Entry {const char*name;addr_t native,wrapper;bool unsupported;};','inline constexpr Entry kEntries[] = {']
    for r in rows:
        if not r['name'].isascii()or '\0'in r['name']:raise RuntimeError('Nonliteral C string in original inventory')
        lines.append('  {%s,0x%xULL,0x%xULL,%s},'%(json.dumps(r['name']),r['native_guest'],0x70000000+r['wrapper'],'true'if r['native_entry_unsupported']else'false'))
    lines+=['};','} // namespace icall_image',''];header=a.out/'icall_inventory.h';header.write_text('\n'.join(lines))
    metadata['input_hashes'][str(header.absolute())]=sha(header)
    (a.out/'audit').mkdir()
    for name in ['icall-registration.json','summary.json','icall-closure-summary.json','icall-symbol-ownership.json','icall-allocator-ownership.json','REPORT.md','proposal.json']:
        target=a.out/'audit'/name;shutil.copyfile(a.audit/name,target);metadata['input_hashes'][str(target.absolute())]=sha(target)
    metadata['icall_profile']=dict(dispatcher=0x709dd61c,expected_count=1987,inventory_sha256=INVENTORY,required_roots=sorted(roots),observers=[0x712ba2d0,0x712ba2d8,0x712ba2e0],map=0x879a5b70,init_counter=0x879a6190,add_api=0x8254d19c,lookup_api=0x8254d1a0,destructor=0x8257cdc0,dso=0x8740c790,registration_lr=0x820ccca0,old_unsupported_stored_targets=summary['icalls']['unsupported_native_entries'],prohibited=['3bd0d8','configuration APIs','il2cpp_init/init_utf16','GC','managed code','RegisterModules','stored native targets'])
    (a.out/'icall_inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('New registration-only variant prepared:1987 exact original pairs,all roots available,3 stored unsupported native bodies retained. No guest execution.')
if __name__=='__main__':main()
