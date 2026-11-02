"""Prepare a NEW immutable dual-engine natural native-frame diagnostic."""
import argparse,hashlib,importlib.util,io,json,re,shutil,struct,subprocess,tarfile
from collections import Counter
from pathlib import Path
from elftools.elf.elffile import ELFFile
from il2cpp_stack_prepare import hashes,absolute
HERE=Path(__file__).resolve().parent
LAYOUT='ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d'
OWN=['game_bootstrap.cpp','game_bootstrap_detail.h','game_bootstrap_prepare.py','game_bootstrap_build.ps1','test_game_bootstrap.py','game_bootstrap.md']
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['unity-build','il2cpp-build','unity-overlay','apk','out']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--host-commit');p.add_argument('--plan-only',action='store_true');p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src');p.add_argument('--zlib',type=Path,default=HERE.parent/'work/zlib-native');p.add_argument('--angle',type=Path,default=HERE.parent/'work/angle-native');p.add_argument('--angle-dlls',type=Path,default=HERE.parent/'work/angle-scaling/bundle/bin')
 a=p.parse_args();repo=HERE.parent.parent
 if a.out.exists():raise RuntimeError('Preserve every prior variant; provide a NEW output directory')
 if not a.plan_only and not a.host_commit:p.error('A committed accepted Java/PID host checkpoint is required for final preparation')
 u=json.loads((a.unity_build/'unity_bootstrap_link.json').read_text());up=json.loads((a.unity_build.parent/'prepare-proof.json').read_text());ua=json.loads((a.unity_build.parent/'acceptance.json').read_text())
 il=json.loads((a.il2cpp_build/'il2cpp_link.json').read_text());ia=json.loads((a.il2cpp_build.parent/'parity-acceptance.json').read_text());ib=json.loads((a.il2cpp_build/'il2cpp_build_record.json').read_text());overlay=json.loads(a.unity_overlay.read_text())
 assert u['complete']and il['complete']and ua['static_checks_passed']and ia['gates']['default']['exit_code']==0 and ia['gates']['signal']['exit_code']==0
 assert u['base']==0x70000000 and il['base']==0x80000000 and u['trace_count']==59626 and il['trace_count']==397058
 assert u['object_count']==470 and len(il['objects'])==3105 and il['original_manifest_sha256']==ia['input_manifest_sha256']=='afbbd86190c72dfac7f5fba7959c7b40f5c0ab339a46063b56c465e74d3451f6'
 assert overlay['original_manifest_sha256']=='b0588939bd6cd549766e97991625eb7b56720cd1e3d61e3efdfd79b55d1a9df1'and overlay['state_layout']['equal']and overlay['state_layout']['sha256']==LAYOUT
 assert len(overlay['original_definitions'])==128 and overlay['original_definitions']==overlay['replacement_definitions']and not any(overlay[k]for k in ['new_definitions','deleted_definitions','missing_direct_targets','duplicate_outside_definitions','unsupported_traces'])
 assert overlay['remaining_unsupported_count']==1342 and len(u['additive_overlay']['new_heads'])==16 and u['additive_overlay']['old_objects_unchanged']and u['additive_overlay']['State_layout_sha256']==LAYOUT
 expected={};objects=[];input_paths=[a.unity_build/'unity_bootstrap_link.json',a.unity_build.parent/'prepare-proof.json',a.unity_build.parent/'acceptance.json',a.unity_build.parent/'pre-run-proof.json',a.il2cpp_build/'il2cpp_link.json',a.il2cpp_build/'il2cpp_build_record.json',a.il2cpp_build.parent/'parity-acceptance.json',a.unity_overlay]
 assert ia['state_layout_sha256']==LAYOUT and sha(a.remill/'include/remill/Arch/AArch64/Runtime/State.h')==ib['runtime_state_sha256']
 for relative in u['objects']:
  path=a.unity_build/relative;want=u['additive_overlay']['object_sha256']if path.name=='hash-tail-additive.o'else up['original_objects'][path.name]
  expected[str(path)]=want
  if relative==overlay['replaces']:
   assert want==overlay['original_object_sha256'];selected=Path(overlay['object']['path']);expected[str(selected)]=overlay['object']['sha256'];objects.append(dict(module='Unity',role='accepted USHLL replacement',path=str(selected),sha256=overlay['object']['sha256']))
  else:objects.append(dict(module='Unity',role='accepted base/additive',path=str(path),sha256=want))
 for item in il['objects']:
  path=a.il2cpp_build/item['path'];expected[str(path)]=item['sha256'];objects.append(dict(module='IL2CPP',role='accepted current full cohort',path=str(path),sha256=item['sha256']))
 for base,metadata in [(a.unity_build,u),(a.il2cpp_build,il)]:
  path=base/'native'/('libunity.so'if base==a.unity_build else'libil2cpp.so');expected[str(path)]=metadata.get('unity_sha256',metadata.get('sha256'))
 expected[str(a.apk)]=u['apk_sha256'];assert u['apk_sha256']==il['apk_sha256']==ia.get('apk_sha256',il['apk_sha256'])
 # Hash Windows-resident objects in one native batch; independently hash the
 # WSL-resident validated replacement through its actual filesystem.
 win=[Path(k)for k in expected if str(k).startswith('/mnt/')];native=[Path(k)for k in expected if not str(k).startswith('/mnt/')]
 actual=hashes(win);assert all(actual[str(absolute(k))]==expected[str(k)]for k in win)
 assert all(sha(k)==expected[str(k)]for k in native)
 for obj in objects:
  with Path(obj['path']).open('rb')as f:assert struct.unpack('<H',f.read(2))[0]==0x8664
 out=a.out.resolve();out.mkdir(parents=True)
 shutil.copyfile(Path(overlay['object']['path']),out/'unity-ushll-replacement.o')
 for obj in objects:
  if obj['role']=='accepted USHLL replacement':obj['path']=str(out/'unity-ushll-replacement.o')
 entries=set();modules=[];ranges=[]
 from il2cpp_prepare import lifecycle,unity_requests
 for name,build,meta,trace_header,data_header in [('unity',a.unity_build,u,'unity_traces.h','unity_bootstrap_data.h'),('il2cpp',a.il2cpp_build,il,'il2cpp_traces.h','il2cpp_data.h')]:
  header=(build/trace_header).read_text();heads=[int(x,16)for x in re.findall(r'\{(0x[0-9a-f]+),\s*sub_',header)]
  assert heads==sorted(set(heads))and len(heads)==meta['trace_count']and not entries.intersection(heads);entries.update(heads)
  native_path=build/'native'/('lib'+name+'.so')
  with native_path.open('rb')as f:
   elf=ELFFile(f);ctors,finis=lifecycle(elf,meta['base']);assert len(ctors)==(417 if name=='unity'else 9)and len(finis)==2 and not set(ctors)&set(finis)and set(ctors+finis)<=set(heads)
   imports=[dict(name=s.name,object=s['st_info']['type']=='STT_OBJECT',weak=s['st_info']['bind']=='STB_WEAK')for s in elf.get_section_by_name('.dynsym').iter_symbols()if s.name and s['st_shndx']=='SHN_UNDEF']
   code_ranges=[(meta['base']+s['sh_addr'],meta['base']+s['sh_addr']+s['sh_size'])for s in elf.iter_sections()if s['sh_flags']&4 and s['sh_size']and s['sh_type']!='SHT_NOBITS'];ranges+=code_ranges
   high=max(s['p_vaddr']+s['p_memsz']for s in elf.iter_segments()if s['p_type']=='PT_LOAD');span=(high+65535)&~65535
  modules.append(dict(name=name,base=meta['base'],span=span,constructors=ctors,finalizers=finis,imports=imports,sha256=expected[str(native_path)],original_data=str(native_path),unsupported=1342 if name=='unity'else 101))
  text=(build/data_header).read_text()
  if name=='unity':text=re.sub(r'(kUnsupportedTraces\s*=\s*)\d+',r'\g<1>1342',text)
  (out/data_header).write_text(text)
 assert len(entries)==456684 and len(objects)==3575 and 0x704fb338 in entries and 0x825b0580 in entries
 (out/'game_traces.h').write_text('// Exact approved Unity+IL2CPP union.\n'+''.join(f'extern "C" Memory *sub_{pc:x}(State &,addr_t,Memory *);\n'for pc in sorted(entries))+'static const recomp::Trace kTraces[]={\n'+''.join(f'{{0x{pc:x},sub_{pc:x}}},\n'for pc in sorted(entries))+'};\n')
 lines=['#pragma once','struct GameImport {const char *name;bool object,weak;};']
 for mod in modules:
  lines+=['namespace '+mod['name']+'_image {','#include "'+('unity_bootstrap_data.h'if mod['name']=='unity'else'il2cpp_data.h')+'"','static const addr_t kConstructors[]={'+','.join(hex(x)for x in mod['constructors'])+'};','static const GameImport kGameImports[]={']
  lines+=['{'+json.dumps(x['name'])+','+str(x['object']).lower()+','+str(x['weak']).lower()+'},'for x in mod['imports']];lines+=['};','}']
 lines+=['struct GameRange {addr_t low,high;};','static const GameRange kGameExecutableRanges[]={']+['{'+hex(lo)+','+hex(hi)+'},'for lo,hi in sorted(ranges)]+['};']
 (out/'game_metadata.h').write_text('\n'.join(lines)+'\n')
 manifest_path=Path('/home/user/bunker-recomp/recomp/work/whole-il2cpp-current/manifest.json');manifest=json.loads(manifest_path.read_text());assert sha(manifest_path)==il['original_manifest_sha256']
 proof=unity_requests(a.unity_build/'native/libunity.so',a.il2cpp_build/'native/libil2cpp.so',manifest);assert proof['request_count']==222;(out/'real-222-export-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
 # Validate the actually selected joint COFF set, including the one replacement.
 nm=out/'object-symbols.txt'
 with nm.open('w')as f:subprocess.run(['llvm-nm-18','--extern-only','-p',*[x['path']for x in objects]],stdout=f,check=True)
 definitions=Counter();direct=set();strong=Counter()
 for line in nm.open():
  match=re.match(r'^\s*U\s+sub_([0-9a-f]+)$',line)
  if match:direct.add(int(match[1],16));continue
  match=re.match(r'^[0-9a-fA-F]+\s+([A-Za-z])\s+(\S+)$',line.strip())
  if not match:continue
  kind,symbol=match.groups()
  if symbol.startswith('sub_'):definitions[int(symbol[4:],16)]+=1
  elif kind in ['T','D','B']:strong[symbol]+=1
 assert definitions==Counter(entries)and not direct-entries and all(n==1 for n in strong.values())
 metadata=dict(status='static plan passed; host not frozen',union_trace_count=len(entries),objects=objects,modules=modules,actual_direct_targets=len(direct),missing_direct_targets=[],canonical_state_sha256=LAYOUT,runtime_state_sha256=ib['runtime_state_sha256'],unity_overlay_sha256=sha(a.unity_overlay),apk=str(a.apk.resolve()),apk_sha256=u['apk_sha256'],input_hashes={str(path):sha(path)for path in input_paths},original_object_hashes=expected,real_export_proof_sha256=sha(out/'real-222-export-proof.json'))
 metadata['generated_header_sha256']={name:sha(out/name)for name in ['game_traces.h','game_metadata.h','unity_bootstrap_data.h','il2cpp_data.h']}
 if not a.plan_only:
  commit=subprocess.check_output(['git','rev-parse',a.host_commit],cwd=repo,text=True).strip();archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=repo);(out/'host-source.tar').write_bytes(archive)
  (out/'sources').mkdir()
  with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'sources',filter='data')
  host=out/'sources/recomp';assert 'BindUnityPlayer'in(host/'windows/android_context.h').read_text(),'accepted Java checkpoint with actual player binding is required'
  for name in OWN:shutil.copyfile(HERE/name,host/'windows'/name)
  shutil.copytree(a.remill/'include',out/'remill-include');(out/'zlib-include').mkdir()
  for name in ['zlib.h','zconf.h']:shutil.copyfile(a.zlib/'zlib-1.3.2'/name,out/'zlib-include'/name)
  shutil.copyfile(a.zlib/'libz-inflate.a',out/'libz-inflate.a');shutil.copytree(a.angle/'src/include',out/'angle-include')
  (out/'native').mkdir()
  for mod in modules:shutil.copyfile(mod['original_data'],out/'native'/('lib'+mod['name']+'.so'))
  metadata.update(status='prepared',host_commit=commit,host_archive_sha256=sha(out/'host-source.tar'),source_sha256={str(f.relative_to(out/'sources')):sha(f)for f in(out/'sources').rglob('*')if f.is_file()},frozen_support_sha256={str(f.relative_to(out)):sha(f)for folder in ['remill-include','zlib-include','angle-include']for f in(out/folder).rglob('*')if f.is_file()},zlib_sha256=sha(out/'libz-inflate.a'),angle_directory=str(a.angle_dlls.resolve()),angle_dll_sha256={f.name:sha(f)for f in a.angle_dlls.glob('*.dll')},preparation_source_sha256={name:sha(HERE/name)for name in OWN})
 (out/'game_inputs.json').write_text(json.dumps(metadata,indent=2)+'\n');print('Game inputs:',metadata['status'],len(entries),'heads/',len(objects),'objects; no guest execution')
if __name__=='__main__':main()
