"""Freeze an isolated original IL2CPP stack-helper gate; never rewrite old artifacts."""
import argparse,hashlib,io,json,os,pathlib,re,shutil,subprocess,tarfile,uuid
HERE=pathlib.Path(__file__).resolve().parent
_hash_cache={}
def absolute(path):return pathlib.Path(os.path.abspath(path))
def digest(path):
 path=absolute(path)
 if path not in _hash_cache:_hash_cache[path]=hashlib.sha256(path.read_bytes()).hexdigest()
 return _hash_cache[path]
def hashes(paths):
 # Inputs already have an explicitly resolved root. Avoid thousands of cross-
 # WSL ancestor stat calls; each exact file is still hashed by native Windows.
 paths=list(dict.fromkeys(absolute(x)for x in paths))
 if os.name=='posix'and all(re.match(r'^/mnt/[a-z]/',str(x))for x in paths):
  def wp(x):
   text=str(x);return text[5].upper()+':/'+text[7:]
  work=HERE.parent/'work/il2cpp-stack-hashes';work.mkdir(exist_ok=True);batch=work/(uuid.uuid4().hex+'.json')
  batch.write_text(json.dumps([{'key':str(x),'path':wp(x)}for x in paths]))
  result=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-File',wp(HERE/'il2cpp_stack_hashes.ps1'),'-InputFile',wp(batch)])
  values=json.loads(result.decode('utf-8-sig'));assert len(values)==len(paths)
  _hash_cache.update((x,values[str(x)])for x in paths)
 else:_hash_cache.update((x,hashlib.sha256(x.read_bytes()).hexdigest())for x in paths)
 return {str(x):_hash_cache[x]for x in paths}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--remill',type=pathlib.Path,required=True);p.add_argument('--zlib',type=pathlib.Path,required=True);p.add_argument('--host-commit',default='6d097e1');a=p.parse_args();repo=HERE.parent.parent
 if a.out.exists():raise ValueError('Use a new output directory; earlier artifacts must remain immutable')
 baseline=a.baseline.resolve();link=json.loads((baseline/'il2cpp_link.json').read_text());overlay_path=baseline/'overlay-01066/overlay.json';overlay=json.loads(overlay_path.read_text());old_record=json.loads((baseline/'il2cpp_overlay_build_record.json').read_text())
 assert link['complete']and link['base']==0x80000000 and link['trace_count']==393781 and len(link['objects'])==3079 and len(link['constructors'])==9 and len(link['finalizers'])==2
 assert overlay['status']=='validated'and overlay['original_manifest_sha256']==link['original_manifest_sha256']and overlay['state_layout']['equal']
 assert not any(overlay[x]for x in ['new_definitions','deleted_definitions','missing_direct_targets','duplicate_outside_definitions'])and len(overlay['original_definitions'])==128 and not overlay['unsupported_traces']
 state=a.remill/'include/remill/Arch/AArch64/Runtime/State.h'
 objects=[dict(x)for x in link['objects']];replaced=[x for x in objects if x['path']==overlay['replaces']];assert len(replaced)==1 and replaced[0]['sha256']==overlay['original_object_sha256'];objects=[x for x in objects if x['path']!=overlay['replaces']]+[overlay['object']]
 remaining=set(link['unsupported_traces'])-set(overlay['original_definitions']);remaining.update(overlay['unsupported_traces']);assert len(remaining)==189 and 0x825b1974 not in remaining
 hashes([baseline/item['path']for item in link['objects']+objects]+[baseline/'native/libil2cpp.so',state])
 assert digest(state)==old_record['runtime_state_sha256']
 for item in link['objects']+objects:assert digest(baseline/item['path'])==item['sha256'],item['path']
 assert digest(baseline/'native/libil2cpp.so')==link['sha256']
 a.out.mkdir(parents=True);commit=subprocess.check_output(['git','rev-parse',a.host_commit],cwd=repo,text=True).strip();archive=subprocess.check_output(['git','archive',commit,'recomp/windows','recomp/whole','recomp/fastaes'],cwd=repo)
 (a.out/'committed-host.tar').write_bytes(archive);sources=a.out/'sources';sources.mkdir()
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(sources,filter='data')
 shutil.copy2(HERE/'il2cpp_stack.cpp',sources/'recomp/windows/il2cpp_stack.cpp')
 for name in ['il2cpp_data.h','il2cpp_traces.h']:shutil.copy2(baseline/name,a.out/name)
 shutil.copytree(a.remill/'include',a.out/'remill-include');(a.out/'zlib').mkdir()
 for name in ['zlib.h','zconf.h']:shutil.copy2(a.zlib/'zlib-1.3.2'/name,a.out/'zlib'/name)
 shutil.copy2(a.zlib/'libz-inflate.a',a.out/'zlib/libz-inflate.a')
 # The source is committed, so live setvbuf/provider edits cannot enter this gate.
 assert '"setvbuf"'not in(sources/'recomp/windows/filesystem.cpp').read_text()
 header=(a.out/'il2cpp_traces.h').read_text();assert '0x825b1974'in header.lower()
 prior_paths=[x for x in baseline.iterdir()if x.is_file()and(x.suffix in ['.exe','.json','.h']or x.name.endswith('link.rsp'))]
 for directory in ['sources','overlay-sources','module-exports-sources']:
  for x in(baseline/directory).rglob('*'):
   if x.is_file():prior_paths.append(x)
 source_paths=[x for x in sources.rglob('*')if x.is_file()];support_paths=[x for folder in ['remill-include','zlib']for x in(a.out/folder).rglob('*')if x.is_file()]
 hashes(prior_paths+source_paths+support_paths+[a.out/'il2cpp_data.h',a.out/'il2cpp_traces.h'])
 old_artifacts={str(x):digest(x)for x in prior_paths}
 source_hashes={str(x.relative_to(sources)):digest(x)for x in sources.rglob('*')if x.is_file()}
 frozen_hashes={str(x.relative_to(a.out)):digest(x)for folder in ['remill-include','zlib']for x in(a.out/folder).rglob('*')if x.is_file()}
 metadata={'status':'prepared','host_commit':commit,'host_archive_sha256':hashlib.sha256(archive).hexdigest(),'baseline':str(baseline),'original_ELF':str(baseline/'native/libil2cpp.so'),'ELF_sha256':link['sha256'],'APK_sha256':link['apk_sha256'],'trace_count':393781,'remaining_unsupported':189,'constructors':link['constructors'],'finalizers':link['finalizers'],'original_manifest_sha256':link['original_manifest_sha256'],'objects':objects,'original_objects':link['objects'],'overlay_metadata_sha256':digest(overlay_path),'overlay_validation':overlay,'source_sha256':source_hashes,'frozen_support_sha256':frozen_hashes,'prior_artifacts_sha256':old_artifacts,'headers_sha256':{x:digest(a.out/x)for x in ['il2cpp_data.h','il2cpp_traces.h']},'input_state_sha256':digest(state),'new_harness_sha256':digest(HERE/'il2cpp_stack.cpp'),'gate':'actual parameterless825b1974 only; no init/GC/metadata/suspension/savecallback'}
 (a.out/'il2cpp_stack_inputs.json').write_text(json.dumps(metadata,indent=2)+'\n');print('Prepared isolated stack gate:',len(objects),'original/overlay objects; committed host',commit)
if __name__=='__main__':main()
