"""Verify/copy the actual existing IL2CPP COFF snapshot; never translate it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
HERE=Path(__file__).resolve().parent
UNITY_SHA256='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'


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


def unity_requests(unity,library,manifest):
    """Extract only the independently audited, hash-pinned Unity API resolver."""
    if digest(unity)!=UNITY_SHA256:raise RuntimeError('Unity export proof supports only the audited original Unity hash')
    if digest(library)!=manifest['sha256']:raise RuntimeError('IL2CPP export proof source hash differs from manifest')
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    sys.path.insert(0,str(HERE.parent/'whole'))
    from callback_roots import _constant_step,_control,_reg
    decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);decoder.detail=True
    with unity.open('rb')as stream:
        elf=ELFFile(stream)
        sections=[(s,s.data())for s in elf.iter_sections()if s['sh_flags']&2 and s['sh_type']!='SHT_NOBITS']
        def bytes_at(address,size,code=False):
            for s,raw in sections:
                offset=address-s['sh_addr']
                if offset>=0 and size<=len(raw)-offset and(not code or s['sh_flags']&4):return raw[offset:offset+size]
            raise RuntimeError('Unity proof address is outside its required ELF section')
        def string_at(address):
            for s,raw in sections:
                offset=address-s['sh_addr']
                if 0<=offset<len(raw):
                    value=raw[offset:offset+160].split(b'\0',1)
                    if len(value)!=2:break
                    return value[0].decode('ascii')
            raise RuntimeError('Unity API name has no bounded ELF string')
        stub=list(decoder.disasm(bytes_at(0xb8b50,16,True),0xb8b50))
        if [i.mnemonic for i in stub]!=['adrp','ldr','add','br']:raise RuntimeError('Actual dlsym PLT sequence differs')
        if (stub[0].reg_name(stub[0].operands[0].reg)!='x16' or
            stub[1].reg_name(stub[1].operands[0].reg)!='x17' or
            stub[1].reg_name(stub[1].operands[1].mem.base)!='x16' or
            stub[3].reg_name(stub[3].operands[0].reg)!='x17'):raise RuntimeError('Actual dlsym register ownership differs')
        got=stub[0].operands[1].imm+stub[1].operands[1].mem.disp
        relocations=[]
        for s in elf.iter_sections():
            if isinstance(s,RelocationSection):
                syms=elf.get_section(s['sh_link'])
                for r in s.iter_relocations():
                    if r['r_offset']==got:
                        symbol=syms.get_symbol(r['r_info_sym'])
                        relocations.append(dict(got=got,type=r['r_info_type'],addend=r.entry.get('r_addend',0),
                                                name=symbol.name,undefined=symbol['st_shndx']=='SHN_UNDEF'))
        if relocations!=[dict(got=got,type=1026,addend=0,name='dlsym',undefined=True)]:raise RuntimeError('Actual dlsym GOT relocation differs')
        wrapper=list(decoder.disasm(bytes_at(0x384800,0xf0,True),0x384800))
        if sum(i.mnemonic=='bl'and i.operands[0].imm==0xb8b50 for i in wrapper)!=1:raise RuntimeError('Unity API wrapper does not call proved dlsym')
        instructions=list(decoder.disasm(bytes_at(0x3b7650,0x3ba044-0x3b7650,True),0x3b7650))
        requests=[]
        for index,ins in enumerate(instructions):
            if ins.mnemonic!='bl'or ins.operands[0].imm!=0x384800:continue
            begin=index
            while begin and not _control(instructions[begin-1]):begin-=1
            values={}
            for before in instructions[begin:index]:_constant_step(before,values)
            name=values.get('1')
            if not name or name[2]!=1:raise RuntimeError('Unity lookup lacks a proved image-relative name')
            values={};slot=None
            for after in instructions[index+1:index+5]:
                ops=after.operands
                if (after.mnemonic=='str'and ops[0].type==ARM64_OP_REG and _reg(after,ops[0].reg)[0]=='0'and
                    ops[1].type==ARM64_OP_MEM and not ops[1].mem.index):
                    base=values.get(_reg(after,ops[1].mem.base)[0])
                    if base and base[2]==1:slot=base[0]+ops[1].mem.disp
                    break
                if _control(after):break
                _constant_step(after,values)
            if slot!=0x12bbfd0+len(requests)*8:raise RuntimeError('Unity API result table is not the audited contiguous layout')
            spelling=string_at(name[0])
            if not spelling.startswith('il2cpp_'):raise RuntimeError('Unexpected Unity API lookup spelling')
            requests.append(dict(site=ins.address,name=spelling,literal=name[0],slot=slot))
    if len(requests)!=222 or len({r['name']for r in requests})!=222:raise RuntimeError('Unity must request exactly222 distinct APIs')
    with library.open('rb')as stream:
        elf=ELFFile(stream);symbols={s.name:s for s in elf.get_section_by_name('.dynsym').iter_symbols()if s.name}
        code=[(s['sh_addr'],s['sh_addr']+s['sh_size'])for s in elf.iter_sections()if s['sh_flags']&6==6]
        traces=set(manifest['traces']);unsupported=set(manifest['unsupported_traces'])
        for request in requests:
            symbol=symbols.get(request['name'])
            if symbol is None or symbol['st_shndx']=='SHN_UNDEF'or symbol['st_info']['type']!='STT_FUNC':
                raise RuntimeError('Unity-requested IL2CPP export is not a defined function: '+request['name'])
            relative=symbol['st_value'];address=manifest['base']+relative
            if relative%4 or not any(lo<=relative and relative+4<=hi for lo,hi in code):raise RuntimeError('IL2CPP export is not complete executable code')
            if manifest['exports'].get(request['name'])!=address or address not in traces or address in unsupported:
                raise RuntimeError('Unity-requested export is not a verified supported translated entry: '+request['name'])
            request.update(entry=address,elf_value=relative)
    return dict(status='proved',unity_sha256=UNITY_SHA256,il2cpp_sha256=manifest['sha256'],
                manifest_content_sha256=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
                resolver=[0x3b7650,0x3ba044],wrapper=0x384800,dlsym_plt=0xb8b50,dlsym_relocation=relocations[0],
                request_count=222,requests=requests)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--translation',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE.parent/'work/windows-il2cpp-bootstrap')
    p.add_argument('--exploratory',action='store_true')
    p.add_argument('--audit-only',action='store_true',help='Verify inputs/lifecycle/header without recopying shards')
    p.add_argument('--unity-library',type=Path,help='Original Unity ELF for its exact API lookup proof')
    p.add_argument('--module-exports-only',action='store_true',help='Emit new export-proof sidecars only; preserve original prepared artifacts')
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
    audit_name='il2cpp_module_exports_input_audit.json'if a.module_exports_only else'il2cpp_input_audit.json'
    (a.out/audit_name).write_text(json.dumps({'source_sha256':m['sha256'],'manifest_sha256':digest(manifest),
        'trace_header_sha256':digest(trace_header),'actual_initializers':actual_init,'actual_finalizers':actual_fini,
        'needed':needed,'imports':len(imports)},indent=2)+'\n')
    if a.module_exports_only:
        if a.audit_only or not a.unity_library:p.error('--module-exports-only requires --unity-library and excludes --audit-only')
        proof=unity_requests(a.unity_library,a.library,m)
        with zipfile.ZipFile(a.apk)as apk:
            for name,expected in [('lib/arm64-v8a/libunity.so',UNITY_SHA256),('lib/arm64-v8a/libil2cpp.so',m['sha256'])]:
                with apk.open(name)as source:
                    actual=hashlib.file_digest(source,'sha256').hexdigest()
                if actual!=expected:raise RuntimeError('Original APK member differs from proved native input: '+name)
        proof.update(apk_sha256=digest(a.apk),original_manifest_sha256=digest(manifest),extractor_sha256=digest(Path(__file__)))
        header=['#pragma once',f'static constexpr const char *kUnityApiProofSha256="{UNITY_SHA256}";',
                f'static constexpr const char *kUnityApiProofApkSha256="{proof["apk_sha256"]}";',
                'static const Il2cppExport kUnityRequestedExports[]={']
        header += [f'  {{{json.dumps(r["name"])},{r["entry"]:#x}}},'for r in proof['requests']]
        header += ['};']
        (a.out/'il2cpp_module_exports.h').write_text('\n'.join(header)+'\n')
        proof['header_sha256']=digest(a.out/'il2cpp_module_exports.h')
        (a.out/'il2cpp_module_exports_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        print('Proved222 actual Unity lookups against original APK/ELF/translated IL2CPP; original objects/headers/manifests untouched.')
        return
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
