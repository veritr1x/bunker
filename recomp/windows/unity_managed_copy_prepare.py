"""Freeze a NEW original Unity Managed-copy component gate, preserving old gates."""
import argparse,copy,hashlib,io,json,re,shutil,struct,subprocess,tarfile
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
NAMES=['unity_managed_copy.cpp','unity_managed_copy_prepare.py','unity_managed_copy_build.ps1','unity_managed_copy_hashes.ps1','test_unity_managed_copy.py','unity_managed_copy.md']
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def win(p):
 s=str(Path(p).absolute())
 if not re.match(r'^/mnt/[a-z]/',s):raise ValueError('native hash batch requires explicit /mnt/drive inputs')
 return s[5].upper()+':/'+s[7:]
def batch(paths,out):
 paths=list(dict.fromkeys(Path(x).absolute() for x in paths));request=out/'native-hash-input.json'
 request.write_text(json.dumps([dict(key=str(x),path=win(x)) for x in paths]))
 result=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-File',win(HERE/'unity_managed_copy_hashes.ps1'),'-InputFile',win(request)])
 values=json.loads(result.decode('utf-8-sig'));assert len(values)==len(paths)
 return values
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--base',type=Path,required=True);p.add_argument('--unity',type=Path,required=True)
 p.add_argument('--component',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
 p.add_argument('--unity-overlay',type=Path,help='Explicit accepted unsigned-widening shard replacement proof')
 p.add_argument('--out',type=Path,required=True);p.add_argument('--host-commit',required=True);a=p.parse_args()
 if a.out.exists():raise RuntimeError('Use a NEW directory; preserve earlier runtime and failure artifacts')
 a.out.mkdir(parents=True)
 base=json.loads((a.base/'api_loader_inputs.json').read_text());old_audit=json.loads((a.base/'api-loader-final-audit.json').read_text())
 assert base['host_commit'].startswith('1942e24') and base['union_trace_count']==453342 and len(base['objects'])==3548
 assert sha(a.base/'api_loader_inputs.json')=='487961c87aadb58ab0ad560a78685e835a71b85ce024f86e2c7594adf1bf53f3'
 assert old_audit['executable_sha256']=='27aebf55092e792f548e714cab17faab193a39bfc38fdfc2e85eb2cfdbfb90ef'
 u=json.loads((a.unity/'unity_bootstrap_link.json').read_text())
 lineage_path=HERE.parent/'work/unity-indexed-fp-lineage/result.json';lineage=json.loads(lineage_path.read_text())
 parity_path=a.unity.parent/'parity-acceptance.json';parity=json.loads(parity_path.read_text())
 assert u['complete'] and u['unsupported_traces']==1343 and lineage['traces']==59610 and lineage['objects']==469 and parity['passed']
 assert u['unity_sha256']==lineage['source_sha256']=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 assert lineage['state_layout_sha256']=='ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d'
 component=json.loads((a.component/'static-proof.json').read_text())
 assert not component['runtime_executed'] and component['source']['source_bytes_sha256']=='94d65f645fa4283bdbcde773cb406a2ef7d36c40b6e55c1f2d30825065f46b10'
 assert sha(a.component/'component.o')==component['artifact_sha256']['component.o']
 expected={x['path']:x['sha256'] for x in base['objects']}
 expected.update({str(a.base/'sources'/name):value for name,value in base['source_hashes'].items()})
 expected[str(a.base/'bunker-unity-api-loader.exe')]=old_audit['executable_sha256']
 objects=[dict(x) for x in base['objects'] if x['module']=='il2cpp']
 assert len(objects)==3079
 for item in u['objects']:
  path=a.unity/item;expected[str(path.absolute())]=lineage['object_sha256'][path.name]
  objects.append(dict(path=str(path.absolute()),sha256=expected[str(path.absolute())],module='unity'))
 actual=batch(expected,a.out)
 for path,value in expected.items():assert actual[str(Path(path).absolute())]==value,path
 overlay=None
 if a.unity_overlay:
  assert sha(a.unity_overlay)=='9e86c5fc63f01968f349a7553c65dae59754b5ce47998f078eb92d7147effaf7'
  overlay=json.loads(a.unity_overlay.read_text())
  assert overlay['original_trace_count']==59610 and overlay['remaining_unsupported_count']==1342
  assert overlay['original_definitions']==overlay['replacement_definitions'] and len(overlay['replacement_definitions'])==128
  for field in ['new_definitions','deleted_definitions','missing_direct_targets','duplicate_outside_definitions','unsupported_traces']:assert not overlay[field],field
  assert overlay['removed_unsupported']==['0x70413e00'] and len(overlay['remaining_unsupported'])==1342
  assert overlay['state_layout']['equal'] and overlay['state_layout']['sha256']==lineage['state_layout_sha256']
  assert overlay['toolchain']==dict(lifter='fa80a8edb3f33d1815ad4b256d7eaa9d1625889adfd6ff59044be0b1cc6277ad',semantics='9524e65b09c51e5b62d1a2f2fae631da9cb6f8ddda5fa3af6401947986cae802')
  replacement=Path(overlay['object']['path']);assert sha(replacement)==overlay['object']['sha256']=='c451301af47e820e57ab76174d40bf7e6914d7ea12f749cef93d8775d2e1c9bb'
  old_path=str((a.unity/overlay['replaces']).absolute());matches=[i for i,x in enumerate(objects)if x['path']==old_path];assert len(matches)==1
  index=matches[0];assert objects[index]['sha256']==overlay['original_object_sha256']
  target=a.out/'unity-ushll-replacement.o';shutil.copyfile(replacement,target);assert sha(target)==overlay['object']['sha256']
  objects[index]=dict(path=str(target.absolute()),sha256=overlay['object']['sha256'],module='unity',replaces=old_path)
  shutil.copyfile(a.unity_overlay,a.out/'unity-overlay.json')
 commit=subprocess.check_output(['git','rev-parse',a.host_commit],cwd=HERE.parent.parent,text=True).strip()
 archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=HERE.parent.parent)
 (a.out/'host-source.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(a.out/'archive',filter='data')
 shutil.move(str(a.out/'archive/recomp'),str(a.out/'sources'))
 for name in NAMES:shutil.copyfile(HERE/name,a.out/'sources/windows'/name)
 assert '"unlink"' in(a.out/'sources/windows/filesystem.cpp').read_text()
 assert '"rename"' in(a.out/'sources/windows/filesystem.cpp').read_text(), 'freeze the accepted real rename provider'
 m=copy.deepcopy(base);m.update(host_commit=commit,host_source_archive_sha256=sha(a.out/'host-source.tar'),objects=objects,
  base_api_loader=dict(directory=str(a.base.absolute()),inputs_sha256=sha(a.base/'api_loader_inputs.json'),executable_sha256=old_audit['executable_sha256']),
  previous_artifacts_sha256=expected,component=component,unity_lineage_sha256=sha(lineage_path),unity_parity_sha256=sha(parity_path))
 if overlay:m['unity_overlay']=dict(proof_sha256=sha(a.unity_overlay),**overlay)
 for module in m['modules']:
  old=a.unity/'native/libunity.so' if module['name']=='unity' else a.base/'native/libil2cpp.so'
  target=a.out/'native'/old.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(old,target)
  assert sha(target)==module['sha256'];module['data']=str(target.absolute())
  if module['name']=='unity':module.update(trace_count=59610,unsupported=1342 if overlay else 1343)
 for name in ['combined_metadata.h','il2cpp_data.h','il2cpp_traces.h','il2cpp_module_exports.h']:
  shutil.copyfile(a.base/name,a.out/name)
 shutil.copyfile(a.unity/'unity_bootstrap_data.h',a.out/'unity_bootstrap_data.h')
 shutil.copyfile(a.unity/'unity_traces.h',a.out/'unity_traces.h')
 entries=set()
 for name in ('unity_traces.h','il2cpp_traces.h'):
  found=[int(x,16) for x in re.findall(r'\{0x([0-9a-f]+),\s*sub_', (a.out/name).read_text())]
  assert found==sorted(set(found)) and not entries.intersection(found);entries.update(found)
  if overlay and name=='unity_traces.h':assert found==overlay['full_original_heads']
 for entry in [0x7023907c,0x702390bc,0x704151cc,0x704151dc,0x70429c8c,0x702380b4,0x7041748c,0x70421934,0x702391a8,0x7023a378,0x702392cc,0x70371d90,0x7037053c,0x700ee64c,0x70e71d10,0x70e71dcc]:assert entry in entries,hex(entry)
 assert 0x704250b8 not in entries and 0x70424ad8 not in entries
 lines=['// Exact current Unity + preserved IL2CPP union.']
 lines +=[f'extern "C" Memory *sub_{x:x}(State &,addr_t,Memory *);' for x in sorted(entries)]
 lines+=['static const recomp::Trace kTraces[]={']+[f'{{0x{x:x},sub_{x:x}}},' for x in sorted(entries)]+['};']
 (a.out/'combined_traces.h').write_text('\n'.join(lines)+'\n')
 nm=a.out/'object-symbols.txt'
 with nm.open('w') as f:subprocess.run(['llvm-nm-18','--extern-only','-p',*[x['path'] for x in objects]],stdout=f,check=True)
 definitions=Counter();refs=set()
 for line in nm.open():
  found=re.match(r'^\s*U\s+sub_([0-9a-f]+)$',line)
  if found:refs.add(int(found[1],16));continue
  found=re.match(r'^[0-9a-fA-F]+\s+[A-Za-z]\s+sub_([0-9a-f]+)$',line.strip())
  if found:definitions[int(found[1],16)]+=1
 assert definitions==Counter(entries) and not refs-entries
 tool=HERE.parent/'work/unity-native2-lineage/state-layout'
 subprocess.run([str(tool),'/home/sattam/bunker-recomp/recomp/work/whole-unity-fmla-fmul-indexed/shard-00000.ll',str(a.component/'component.ll'),str(a.out/'once-state')],check=True)
 assert sha(a.out/'once-state.new.txt')==lineage['state_layout_sha256']
 subprocess.run([str(tool),'/home/sattam/bunker-recomp/recomp/work/whole-unity-fmla-fmul-indexed/shard-00000.ll','/home/sattam/bunker-recomp/recomp/work/whole-il2cpp/shard-00000.ll',str(a.out/'union-state')],check=True)
 assert sha(a.out/'union-state.new.txt')==lineage['state_layout_sha256']
 if overlay:
  ir=Path(overlay['object']['path']).parent/'replacement.ll';assert sha(ir)==overlay['replacement_ir_sha256']
  subprocess.run([str(tool),'/home/sattam/bunker-recomp/recomp/work/whole-unity-fmla-fmul-indexed/shard-00000.ll',str(ir),str(a.out/'overlay-state')],check=True)
  assert sha(a.out/'overlay-state.new.txt')==lineage['state_layout_sha256']
 shutil.copyfile(a.component/'component.o',a.out/'once-component.o')
 shutil.copytree(a.base/'remill-include',a.out/'remill-include');shutil.copytree(a.base/'zlib-include',a.out/'zlib-include')
 inventory=json.loads((a.audit/'managed-inventory.json').read_text());assert inventory['count']==24 and inventory['bytes']==24570231
 h=['#pragma once','struct ManagedExpected {const char *name;uint64_t size;const char *sha;uint32_t crc;};','static constexpr ManagedExpected kManagedExpected[]={']
 for row in inventory['members']:h.append('{%s,%s,%s,0x%s},'%(json.dumps(row['name'].removeprefix('assets/bin/Data/Managed/')),row['size'],json.dumps(row['sha256']),row['crc32']))
 h+=['};'];(a.out/'managed_expected.h').write_text('\n'.join(h)+'\n')
 m['input_hashes']={str(x.absolute()):sha(x) for x in a.out.glob('*.h')}
 m['input_hashes'][str((a.out/'once-component.o').absolute())]=sha(a.out/'once-component.o')
 if overlay:
  for name in ['unity-overlay.json','unity-ushll-replacement.o']:m['input_hashes'][str((a.out/name).absolute())]=sha(a.out/name)
 m['source_hashes']={str(x.relative_to(a.out/'sources')):sha(x) for x in(a.out/'sources').rglob('*') if x.is_file()}
 m['union_trace_count']=len(entries);m['direct_guest_target_count']=len(refs);m['missing_direct_guest_targets']=[]
 m['gate']=dict(kind='original Managed copy component',fresh_destination=True,normal_engine_init=False,IL2CPP_init=False,GC=False,expected_files=24,expected_bytes=24570231)
 (a.out/'managed_inputs.json').write_text(json.dumps(m,indent=2)+'\n')
 print(f'Prepared original Managed-copy gate: {len(entries)} union heads/{len(objects)} objects/{int(bool(overlay))} accepted replacements/current host{commit}; no guest execution.')
if __name__=='__main__':main()
