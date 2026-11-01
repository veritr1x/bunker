"""Prepare a separate frozen Unity+IL2CPP load-only gate; never translate code."""
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,struct,io
from collections import Counter
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
WINDOWS_SOURCES=['jni_host.cpp','android_context.cpp','android_assets.cpp','apk_assets.cpp','java_native_libraries.cpp',
 'filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp','signal_host.cpp','semaphore_host.cpp']
def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unity-build',type=Path,required=True);p.add_argument('--il2cpp-build',type=Path,required=True)
    p.add_argument('--host-source',type=Path,required=True);p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--remill',type=Path,required=True);p.add_argument('--zlib',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE.parent/'work/windows-combined-modules')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    commit=(a.host_source.parents[1]/'source-commit.txt').read_text().strip()
    if not commit.startswith('1942e24'):raise RuntimeError('Expected parent-approved frozen host cohort1942e24')
    u=json.loads((a.unity_build/'unity_bootstrap_link.json').read_text())
    il=json.loads((a.il2cpp_build/'il2cpp_link.json').read_text())
    overlay=json.loads((a.il2cpp_build/'overlay-01066/overlay.json').read_text())
    proof=json.loads((a.il2cpp_build/'il2cpp_module_exports_proof.json').read_text())
    if not u['complete']or not il['complete']or u['base']!=0x70000000 or il['base']!=0x80000000:raise RuntimeError('Wrong engine snapshot/base')
    if digest(a.apk)!=u['apk_sha256']or u['apk_sha256']!=il['apk_sha256']or proof['apk_sha256']!=u['apk_sha256']:raise RuntimeError('Original APK hashes differ')
    if overlay['status']!='validated'or not overlay['state_layout']['equal']or overlay['new_definitions']or overlay['deleted_definitions']or overlay['missing_direct_targets']or overlay['duplicate_outside_definitions']:raise RuntimeError('IL2CPP overlay validation incomplete')
    if overlay['original_manifest_sha256']!=il['original_manifest_sha256']:raise RuntimeError('IL2CPP overlay owner manifest differs')
    if proof['request_count']!=222 or proof['il2cpp_sha256']!=il['sha256']or proof['unity_sha256']!=u['unity_sha256']:raise RuntimeError('Export lookup proof belongs to another input')
    spec=importlib.util.spec_from_file_location('combined_frozen_prepare',a.host_source/'windows/il2cpp_prepare.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    modules=[];entries=set();all_objects=[];input_hashes={}
    for name,build,metadata,sha,trace_header,data_header in [
        ('unity',a.unity_build,u,u['unity_sha256'],'unity_traces.h','unity_bootstrap_data.h'),
        ('il2cpp',a.il2cpp_build,il,il['sha256'],'il2cpp_traces.h','il2cpp_data.h')]:
        original=build/('native/lib'+name+'.so')
        if digest(original)!=sha:raise RuntimeError('Original module ELF differs: '+name)
        text=(build/trace_header).read_text();traces=[int(x,16)for x in re.findall(r'\{0x([0-9a-f]+), sub_',text)]
        if traces!=sorted(set(traces))or entries.intersection(traces):raise RuntimeError('Trace tables are unordered or overlap')
        entries.update(traces)
        with io.BytesIO(original.read_bytes())as stream:
            elf=ELFFile(stream);ctors,finis=helper.lifecycle(elf,metadata['base'])
            high=max(s['p_vaddr']+s['p_memsz']for s in elf.iter_segments()if s['p_type']=='PT_LOAD')
            low=min(s['p_vaddr']for s in elf.iter_segments()if s['p_type']=='PT_LOAD')
            if low:raise RuntimeError('Expected zero-based ELF PT_LOAD image')
            span=(high+65535)&~65535
            imports=[dict(name=s.name,object=s['st_info']['type']=='STT_OBJECT',weak=s['st_info']['bind']=='STB_WEAK')
                     for s in elf.get_section_by_name('.dynsym').iter_symbols()if s.name and s['st_shndx']=='SHN_UNDEF']
        expected=417 if name=='unity'else 9
        if len(ctors)!=expected or len(finis)!=2 or not set(ctors+finis)<=set(traces):raise RuntimeError('Actual module lifecycle/entries differ')
        target=a.out/'native'/original.name;target.parent.mkdir(exist_ok=True)
        if not target.exists()or digest(target)!=sha:shutil.copyfile(original,target)
        if digest(target)!=sha:raise RuntimeError('Copied data image differs')
        objects=[dict(path=str((build/o).absolute()))for o in metadata['objects']]if name=='unity'else[
            dict(path=str((build/o['path']).absolute()),expected=o['sha256'])for o in metadata['objects']if o['path']!=overlay['replaces']]
        if name=='il2cpp':
            obj=overlay['object'];objects.append(dict(path=str((build/obj['path']).absolute()),expected=obj['sha256']))
        print(name+': checking '+str(len(objects))+' COFF hashes/machine headers',flush=True)
        for obj in objects:
            path=Path(obj['path']);actual=digest(path)
            with path.open('rb')as stream:
                if struct.unpack('<H',stream.read(2))[0]!=0x8664:raise RuntimeError('Non-x86_64 COFF object: '+str(path))
            if obj.get('expected',actual)!=actual:raise RuntimeError('Frozen object differs: '+str(path))
            if name=='unity':
                source=Path('/home/sattam/bunker-recomp/recomp/work/whole-unity')/path.name
                if digest(source)!=actual:raise RuntimeError('Accepted Unity COFF differs from immutable original WSL source: '+str(path))
                obj['original_source']=str(source)
            obj.update(sha256=actual,size=path.stat().st_size,module=name)
        all_objects.extend(objects)
        for file in [trace_header,data_header]:shutil.copyfile(build/file,a.out/file);input_hashes[str(build/file)]=digest(build/file)
        if name=='unity':
            manifest=Path('/home/sattam/bunker-recomp/recomp/work/whole-unity/manifest.json')
            original_manifest=json.loads(manifest.read_text())
            if traces!=original_manifest['traces']or original_manifest['sha256']!=sha or original_manifest['unresolved_direct_targets']:raise RuntimeError('Accepted Unity traces/closure differ from original manifest')
            input_hashes[str(manifest)]=digest(manifest)
        input_hashes[str(original)]=sha
        unsupported=metadata['unsupported_traces']
        if name=='il2cpp':
            remaining=set(unsupported)-set(overlay['original_definitions'])
            remaining.update(overlay['unsupported_traces']);unsupported=len(remaining)
        modules.append(dict(name=name,base=metadata['base'],span=span,
            sha256=sha,guest_path='/data/app/bunker/lib/arm64/'+original.name,aliases=[original.name,'/data/app/bunker/lib/arm64/'+original.name],
            data=str(target.resolve()),trace_count=len(traces),constructors=ctors,finalizers=finis,imports=imports,
            unsupported=unsupported))
    for address in [0x7041a214,0x700dff6c,0x700e0044]:
        if address not in entries:raise RuntimeError('Actual helper/string entry missing: '+hex(address))
    if modules[0]['base']+modules[0]['span']>modules[1]['base']:raise RuntimeError('Data images overlap')
    for f in ['il2cpp_module_exports.h','il2cpp_module_exports_proof.json']:
        shutil.copyfile(a.il2cpp_build/f,a.out/f);input_hashes[str(a.il2cpp_build/f)]=digest(a.il2cpp_build/f)
    if digest(a.out/'il2cpp_module_exports.h')!=proof['header_sha256']:raise RuntimeError('Lookup header differs from proof')
    # Check the frozen host tree against the actual approved Git blobs.
    repo=HERE.parents[1]
    tree=subprocess.check_output(['git','-c','safe.directory='+str(repo),'-C',str(repo),'ls-tree','-r',commit,
                                  '--','recomp/windows','recomp/whole','recomp/fastaes'],text=True)
    blobs={line.split('\t',1)[1]:line.split()[2]for line in tree.splitlines()}
    selected=[a.host_source/'windows'/n for n in WINDOWS_SOURCES]
    selected.append(a.host_source/'windows/il2cpp_prepare.py')
    selected+=list((a.host_source/'windows').glob('*.h'))+list((a.host_source/'whole').glob('*.h'))
    selected +=[a.host_source/'whole'/n for n in ['runtime.cpp','format.cpp']]
    selected +=[a.host_source/'fastaes'/n for n in ['elfload.c','elfload.h','elf64.h']]
    source_hashes={}
    for source in selected:
        rel=source.relative_to(a.host_source);raw=source.read_bytes()
        git_hash=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blobs.get('recomp/'+rel.as_posix())!=git_hash:raise RuntimeError('Frozen host file differs from approved commit: '+str(rel))
        target=a.out/'sources'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        source_hashes[rel.as_posix()]=hashlib.sha256(raw).hexdigest()
    for name in ['combined_modules.cpp','combined_java_class.h']:
        shutil.copyfile(HERE/name,a.out/'sources/windows'/name)
        source_hashes['windows/'+name]=digest(HERE/name)
    preparation_hashes={}
    for name in ['combined_modules_prepare.py','combined_modules_build.ps1']:
        source=HERE/name;target=a.out/'sources/windows'/name
        shutil.copyfile(source,target);preparation_hashes[name]=digest(source)
    headers={}
    for source in (a.remill/'include').rglob('*'):
        if not source.is_file():continue
        rel=source.relative_to(a.remill/'include');target=a.out/'remill-include'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        raw=source.read_bytes();target.write_bytes(raw);headers[rel.as_posix()]=hashlib.sha256(raw).hexdigest()
    for name in ['zlib.h','zconf.h']:
        target=a.out/'zlib-include'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(a.zlib/'zlib-1.3.2'/name,target)
    lines=['// Exact union of accepted frozen trace tables.']
    lines +=[f'extern "C" Memory *sub_{v:x}(State &,addr_t,Memory *);'for v in sorted(entries)]
    lines +=['static const recomp::Trace kTraces[]={']+[f'  {{{v:#x},sub_{v:x}}},'for v in sorted(entries)]+['};']
    (a.out/'combined_traces.h').write_text('\n'.join(lines)+'\n')
    lines=['#pragma once','struct CombinedImport {const char*name;bool object,weak;};']
    for mod in modules:
        name=mod['name'];lines.append('namespace '+name+'_image {')
        lines.append('#include "'+('unity_bootstrap_data.h'if name=='unity'else'il2cpp_data.h')+'"')
        if name=='il2cpp':lines.append('#include "il2cpp_module_exports.h"')
        for label,key in [('kConstructors','constructors'),('kFinalizersOwned','finalizers')]:
            lines+=['static const addr_t '+label+'[]={']+[f' {v:#x},'for v in mod[key]]+['};']
        lines+=['static const CombinedImport kCombinedImports[]={']+[
            '{'+json.dumps(i['name'])+','+str(i['object']).lower()+','+str(i['weak']).lower()+'},'for i in mod['imports']]+['};','}']
    (a.out/'combined_metadata.h').write_text('\n'.join(lines)+'\n')
    # Actual COFF guest definitions must exactly match the combined address table.
    nm=a.out/'object-symbols.txt'
    with nm.open('w')as output:subprocess.run(['llvm-nm-18','--extern-only','-p',*[o['path']for o in all_objects]],stdout=output,check=True)
    guest=[];other=Counter();direct_refs=set()
    for line in nm.open():
        undefined=re.match(r'^\s*U\s+sub_([0-9a-f]+)$',line)
        if undefined:direct_refs.add(int(undefined[1],16));continue
        match=re.match(r'^[0-9a-fA-F]+\s+([A-Za-z])\s+(\S+)$',line.strip())
        if not match:continue
        kind,symbol=match.groups()
        if symbol.startswith('sub_'):guest.append(int(symbol[4:],16))
        else:other[(kind,symbol)]+=1
    if Counter(guest)!=Counter(entries):raise RuntimeError('Actual COFF union guest ownership is missing/duplicated')
    if direct_refs-entries:raise RuntimeError('Actual COFF direct guest target closure incomplete: '+str(sorted(direct_refs-entries)))
    duplicate_other=[dict(kind=k,symbol=s,count=n)for(k,s),n in other.items()if n>1]
    if any(x['kind']in['T','D','B']for x in duplicate_other):raise RuntimeError('Strong non-guest COFF definitions collide')
    metadata=dict(status='prepared',host_commit=commit,host_source=str(a.host_source),apk=str(a.apk.resolve()),apk_sha256=digest(a.apk),
        modules=modules,objects=all_objects,union_trace_count=len(entries),non_guest_duplicate_symbols=duplicate_other,
        direct_guest_target_count=len(direct_refs),missing_direct_guest_targets=[],
        source_hashes=source_hashes,remill_header_hashes=headers,input_hashes=input_hashes,
        preparation_hashes=preparation_hashes,
        zlib_backend=str((a.zlib/'libz-inflate.a').resolve()),zlib_sha256=digest(a.zlib/'libz-inflate.a'),
        il2cpp_overlay=overlay,unity_lookup_proof=proof,
        native_string=dict(size=40,alignment=16,allocator_tag=0x49,tag_offset=32,length_offset=24,inline_offset=8,
            helper=0x7041a214,literal=0x70ed01b3,destructor=0x700e0044,
            arguments={'x0':'original UTF8 il2cpp literal','x1':'owned guarded40-byte output','x8':'not an sret argument; overwritten by LDRB W8 before use; fresh runner sets zero'},
            caller_rvas=[0x424ab8,0x424ac4,0x424aec,0x424af8],api_loader_not_called=0x703b7650),
        isolated_profile_addition=dict(method='java/lang/Object.getClass()Ljava/lang/Class;',implementation='checked GetObjectClass JNI slot31; IsSameObject-keyed Host-lifetime globals; temporary locals deleted; no destructor JNI'))
    (a.out/'combined_inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Prepared frozen combined gate: {len(entries)} traces/{len(all_objects)} verified COFF objects; host {commit}; no translation or guest execution.')
if __name__=='__main__':main()
