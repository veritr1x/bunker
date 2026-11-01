"""Verify/copy the actual existing IL2CPP COFF snapshot; never translate it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
HERE=Path(__file__).resolve().parent


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def lifecycle(elf,base):
    arrays={}
    for name in ('.init_array','.fini_array'):
        section=elf.get_section_by_name(name)
        if section:arrays[name]=(section,[int.from_bytes(section.data()[i:i+8],'little')for i in range(0,section['sh_size'],8)])
    for section in elf.iter_sections():
        if not isinstance(section,RelocationSection):continue
        symbols=elf.get_section(section['sh_link'])
        for relocation in section.iter_relocations():
            for array,values in arrays.values():
                if array['sh_addr']<=relocation['r_offset']<array['sh_addr']+array['sh_size']:
                    value=relocation.entry.get('r_addend',0)
                    if relocation['r_info_sym']:
                        symbol=symbols.get_symbol(relocation['r_info_sym'])
                        if symbol['st_shndx']=='SHN_UNDEF':raise RuntimeError('Unexpected imported lifecycle target')
                        value+=symbol['st_value']
                    values[(relocation['r_offset']-array['sh_addr'])//8]=value
    init=list(arrays.get('.init_array',(None,[]))[1]);fini=list(arrays.get('.fini_array',(None,[]))[1])
    for tag in elf.get_section_by_name('.dynamic').iter_tags():
        if tag.entry.d_tag=='DT_INIT':init.insert(0,tag['d_ptr'])
        elif tag.entry.d_tag=='DT_FINI':fini.insert(0,tag['d_ptr'])
    return [base+x for x in init if x],[base+x for x in fini if x]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--translation',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE.parent/'work/windows-il2cpp-bootstrap')
    p.add_argument('--exploratory',action='store_true')
    p.add_argument('--audit-only',action='store_true',help='Verify inputs/lifecycle/header without recopying shards')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    manifest=a.translation/'manifest.json';m=json.loads(manifest.read_text())
    if m['target']!='x86_64-w64-windows-gnu'or m['base']!=0x80000000:raise RuntimeError('Expected existing Windows IL2CPP snapshot at0x80000000')
    if digest(a.library)!=m['sha256']:raise RuntimeError('Actual IL2CPP hash differs from translated input')
    if len(m['initializers'])!=9 or len(m['finalizers'])!=2:raise RuntimeError('Actual IL2CPP lifecycle inventory changed')
    if m['unresolved_direct_targets']:raise RuntimeError('Snapshot has unresolved direct targets')
    if m['unsupported_traces']and not a.exploratory:raise RuntimeError('Explicit --exploratory required for incomplete instruction coverage')
    if any(entry not in m['traces']for entry in m['initializers']+m['finalizers']):raise RuntimeError('Actual lifecycle entry absent from translation')
    if any(entry in m['unsupported_traces']for entry in m['initializers']):raise RuntimeError('An actual constructor is itself unsupported')
    with a.library.open('rb')as stream:
        elf=ELFFile(stream);symbols=elf.get_section_by_name('.dynsym')
        imports=sorted((s.name,s['st_info']['type']=='STT_OBJECT',s['st_info']['bind']=='STB_WEAK')
                       for s in symbols.iter_symbols()if s.name and s['st_shndx']=='SHN_UNDEF')
        needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags()if t.entry.d_tag=='DT_NEEDED']
        actual_init,actual_fini=lifecycle(elf,m['base'])
        if actual_init!=m['initializers']or actual_fini!=m['finalizers']:raise RuntimeError('Actual ELF lifecycle order differs from original manifest')
    if {name for name,_,_ in imports}!=set(m['imports']):raise RuntimeError('Actual dynamic import inventory differs from snapshot')
    trace_header=a.translation/'traces.h';text=trace_header.read_text()
    entries=[int(x,16)for x in re.findall(r'\{0x([0-9a-f]+), sub_',text)]
    if entries!=m['traces']:raise RuntimeError('Original trace table differs from complete manifest')
    header_init=re.search(r'kInitializers\[\]\s*=\s*\{([^}]+)\}',text,re.S)
    if not header_init or [int(x,16)for x in re.findall(r'0x([0-9a-f]+)',header_init.group(1))]!=actual_init:
        raise RuntimeError('Generated constructor order differs from independently read ELF lifecycle')
    (a.out/'il2cpp_input_audit.json').write_text(json.dumps({'source_sha256':m['sha256'],'manifest_sha256':digest(manifest),
        'trace_header_sha256':digest(trace_header),'actual_initializers':actual_init,'actual_finalizers':actual_fini,
        'needed':needed,'imports':len(imports)},indent=2)+'\n')
    if a.audit_only:
        print('Actual ELF relocations/dynamic lifecycle, manifest and generated constructor table agree.')
        return
    (a.out/'native').mkdir(exist_ok=True);(a.out/'objects').mkdir(exist_ok=True)
    library=a.out/'native/libil2cpp.so'
    if not library.exists()or digest(library)!=m['sha256']:shutil.copyfile(a.library,library)
    if digest(library)!=m['sha256']:raise RuntimeError('Copied ELF hash differs')
    shutil.copyfile(trace_header,a.out/'il2cpp_traces.h')
    objects=[]
    for index,name in enumerate(m['objects']):
        source=Path(name);destination=a.out/'objects'/source.name
        expected=digest(source)
        if not destination.exists()or digest(destination)!=expected:shutil.copyfile(source,destination)
        if digest(destination)!=expected:raise RuntimeError('Copied COFF shard hash differs: '+name)
        objects.append({'path':'objects/'+source.name,'sha256':expected,'size':source.stat().st_size})
        if index%256==0:print(f'Verified/copied {index+1}/{len(m["objects"])} actual IL2CPP shards',flush=True)
    header=['#pragma once',f'static constexpr addr_t kIl2cppBase={m["base"]:#x};',
            f'static constexpr size_t kIl2cppSpan={m["image_span"]};',f'static constexpr size_t kExpectedConstructors=9;',
            f'static constexpr const char *kIl2cppSha256="{m["sha256"]}";',
            f'static constexpr const char *kApkSha256="{digest(a.apk)}";',
            f'static constexpr size_t kUnsupportedTraces={len(m["unsupported_traces"])};',
            'struct Il2cppImport {const char *name;bool object,weak;};','static const Il2cppImport kImports[]={']
    header += [f'  {{{json.dumps(name)},{str(obj).lower()},{str(weak).lower()}}},'for name,obj,weak in imports]
    header += ['};','struct Il2cppExport {const char *name;addr_t address;};','static const Il2cppExport kExports[]={']
    header += [f'  {{{json.dumps(name)},{value:#x}}},'for name,value in sorted(m['exports'].items())]
    header += ['};','static const addr_t kFinalizers[]={']+[f'  {value:#x},'for value in m['finalizers']]+['};']
    (a.out/'il2cpp_data.h').write_text('\n'.join(header)+'\n')
    report={'complete':True,'exploratory':a.exploratory,'sha256':m['sha256'],'apk_sha256':digest(a.apk),
            'base':m['base'],'image_span':m['image_span'],'constructors':m['initializers'],'finalizers':m['finalizers'],
            'trace_count':len(m['traces']),'unsupported_traces':m['unsupported_traces'],'needed':needed,
            'gc_signal_init':m['base']+0x25b3020,'gc_signal_init_translated':m['base']+0x25b3020 in m['traces'],
            'original_manifest_sha256':digest(manifest),'original_trace_header_sha256':digest(trace_header),
            'toolchain':m['toolchain'],'imports':[dict(name=n,object=o,weak=w)for n,o,w in imports],'objects':objects}
    (a.out/'il2cpp_link.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Prepared actual IL2CPP: {len(m["traces"]):,} traces/{len(objects):,} objects/9 constructors/{len(imports)} imports; {len(m["unsupported_traces"])} unsupported traces remain.',flush=True)


if __name__=='__main__':main()
