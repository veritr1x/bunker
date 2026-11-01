"""Prepare verified original Unity metadata/COFF objects for the Windows gate.

Run in WSL. Translation is produced separately by whole/compile.py; this never
builds Remill or silently accepts incomplete/unsupported translated output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from inventory import Dex
from application_metadata import read_application_metadata

HERE=Path(__file__).resolve().parent
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def u16(value):
    raw=value.encode('utf-16-le','surrogatepass')
    units=[int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
    return 'std::u16string({'+','.join(f'char16_t({n:#x})' for n in units)+'})'

def executable_ranges(manifest):
    """Use the compiler's actual executable sections, including interior PCs."""
    ranges=manifest.get('executable_ranges',[])
    if not ranges:raise RuntimeError('Translation is missing executable section ranges')
    previous=manifest['base']
    for pair in ranges:
        if not isinstance(pair,list) or len(pair)!=2 or any(type(n) is not int for n in pair):raise RuntimeError('Invalid executable range metadata')
        low,high=pair
        if low<previous or low>=high or high>manifest['base']+manifest['image_span'] or low%4 or high%4:raise RuntimeError('Executable range is overlapping, unaligned or outside the image')
        previous=high
    return ranges

def registration_tables(library):
    """Read actual JNI_OnLoad's FindClass/RegisterNatives wrappers, not guesses."""
    with library.open('rb') as f:
        elf=ELFFile(f);loads=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD'];relocations={}
        def read(address,size):
            for s in loads:
                if s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']:
                    f.seek(s['p_offset']+address-s['p_vaddr']);return f.read(size)
            raise RuntimeError(f'JNI metadata address {address:#x} is outside file data')
        for section in elf.iter_sections():
            if not isinstance(section,RelocationSection):continue
            symbols=elf.get_section(section['sh_link'])
            for r in section.iter_relocations():
                value=r.entry.get('r_addend',0)
                if r['r_info_sym']:
                    symbol=symbols.get_symbol(r['r_info_sym'])
                    if symbol['st_shndx']=='SHN_UNDEF':continue
                    value+=symbol['st_value']
                relocations[r['r_offset']]=value
        def pointer(at):return relocations.get(at,int.from_bytes(read(at,8),'little'))
        def string(at):return read(at,1024).split(b'\0',1)[0].decode('utf-8')
        onload=elf.get_section_by_name('.dynsym').get_symbol_by_name('JNI_OnLoad')[0]
        dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);dis.detail=True
        calls=[i.operands[0].imm for i in dis.disasm(read(onload['st_value'],onload['st_size']),onload['st_value']) if i.mnemonic=='bl']
        groups=[]
        for helper in calls:
            first=next(dis.disasm(read(helper,4),helper));body=first.operands[0].imm if first.mnemonic=='b' else helper
            code=list(dis.disasm(read(body,112),body))
            # Exact evidenced wrapper shape. Pre-Attach time-baseline setup does
            # not match and therefore cannot introduce guessed Java classes.
            if len(code)!=28 or code[3].mnemonic!='adrp' or code[4].mnemonic!='ldr' or code[10].mnemonic!='adrp':continue
            if code[6].mnemonic!='ldr' or code[6].operands[1].mem.disp!=6*8:continue
            if code[13].mnemonic!='ldr' or code[13].operands[1].mem.disp!=215*8:continue
            class_slot=code[3].operands[1].imm+code[4].operands[1].mem.disp
            table=code[10].operands[1].imm+code[12].operands[2].imm
            count=code[14].operands[-1].imm
            if not 0<count<=256:raise RuntimeError('Invalid actual JNI native table length')
            methods=[{'name':string(pointer(table+i*24)),'signature':string(pointer(table+i*24+8)),
                      'entry_rva':pointer(table+i*24+16)} for i in range(count)]
            groups.append({'helper_rva':helper,'class':string(pointer(class_slot)),'class_pointer_rva':class_slot,'table_rva':table,'count':count,'methods':methods})
        if len(groups)!=9 or sum(g['count'] for g in groups)!=42:raise RuntimeError('Actual JNI_OnLoad registration shape changed; inspect it before extending the catalog')
        return groups
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--translation',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--aapt',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE.parent/'work/windows-unity-bootstrap')
    p.add_argument('--metadata-only',action='store_true',help='Prepare declarations for compile-only checks while translation runs; cannot link/run')
    p.add_argument('--exploratory',action='store_true',help='Allow explicitly incomplete instruction coverage for diagnostic constructor execution only')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    complete=(a.translation/'manifest.json').is_file()
    if not complete and not a.metadata_only:raise RuntimeError('Unity translation manifest is not complete yet; do not skip constructors or link partial shards')
    m=json.loads((a.translation/('manifest.json' if complete else 'plan.json')).read_text())
    if m['sha256']!=digest(a.library):raise RuntimeError('Original Unity ELF SHA256 does not match translated image')
    if m['target']!='x86_64-w64-windows-gnu' or m['base']!=0x70000000:raise RuntimeError('Expected real Unity COFF translation at guest base0x70000000')
    if len(m['initializers'])!=417:raise RuntimeError('Real Unity constructor inventory changed; inspect the input rather than skipping entries')
    if complete and m['unresolved_direct_targets']:raise RuntimeError('Unity translation contains unresolved direct targets; these cannot link safely')
    if complete and m['unsupported_traces'] and not a.exploratory:raise RuntimeError('Unity translation contains unsupported traces; strict gate refused (explicit --exploratory is diagnostic-only)')
    if complete:
        for entry in m['initializers']+[m['exports']['JNI_OnLoad']]:
            if entry not in m['traces']:raise RuntimeError(f'Required actual Unity entry {entry:#x} is not translated')
    badging=subprocess.check_output([str(a.aapt),'dump','badging',str(a.apk)],text=True)
    package=re.search(r"^package: name='([^']+)'",badging,re.M).group(1)
    version_name=re.search(r"^package: .* versionName='([^']*)'",badging,re.M).group(1)
    version_code=int(re.search(r"^package: .* versionCode='(\d+)'",badging,re.M).group(1))
    if not 0<=version_code<1<<31:raise RuntimeError('Unsupported APK versionCode width')
    metadata=read_application_metadata(a.apk,a.aapt)
    sdk=int(re.search(r"^targetSdkVersion:'(\d+)'",badging,re.M).group(1))
    activity=re.search(r"^launchable-activity: name='([^']+)'",badging,re.M).group(1).replace('.','/')
    groups=registration_tables(a.library)
    # Actual initJni helper0xab6eb4 resolves this class and registers its two
    # natives. Include only its real APK declarations, never Java method bodies.
    bridge='bitter/jnibridge/JNIBridge'
    required={g['class'] for g in groups}|{bridge};classes={}
    with zipfile.ZipFile(a.apk) as apk:
        for name in apk.namelist():
            if re.fullmatch(r'classes\d*\.dex',name):classes.update(Dex(apk.read(name)).unity_classes(required))
    if not classes:raise RuntimeError('Actual APK does not declare Unity JNI classes')
    if bridge not in classes:raise RuntimeError('Evidenced initJni bridge class is absent from actual APK')
    for name,signature in [('delete','(J)V'),('invoke','(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;')]:
        found=[m for m in classes[bridge]['methods'] if m['name']==name and m['signature']==signature]
        if len(found)!=1 or not found[0]['native'] or not found[0]['static']:raise RuntimeError('Actual initJni bridge native/DEX mismatch: '+name)
    for group in groups:
        if group['class'] not in classes:raise RuntimeError('Actual registration class absent from APK: '+group['class'])
        for method in group['methods']:
            declared=[m for m in classes[group['class']]['methods'] if m['name']==method['name'] and m['signature']==method['signature']]
            if len(declared)!=1 or not declared[0]['native']:raise RuntimeError('Native/DEX method mismatch: '+group['class']+'.'+method['name'])
            method['static']=declared[0]['static']
    (out/'jni_onload_catalog.json').write_text(json.dumps(groups,indent=2)+'\n')
    (out/'application_metadata.json').write_text(json.dumps({'apk_sha256':digest(a.apk),'version_name':version_name,'version_code':version_code,'scope':'direct application children only','metadata':metadata},indent=2)+'\n')
    with a.library.open('rb') as f:
        elf=ELFFile(f);syms=elf.get_section_by_name('.dynsym')
        imports={s.name:s['st_info']['type']=='STT_OBJECT' for s in syms.iter_symbols() if s['st_shndx']=='SHN_UNDEF' and s.name}
    if set(imports)!=set(m['imports']):raise RuntimeError('Original ELF and translation import catalogs differ')
    apk_hash=digest(a.apk)
    unsupported=len(m.get('unsupported_traces',[]))
    code_ranges=executable_ranges(m)
    lines=['// Generated from original APK/ELF and verified translation, not desktop guesses.',
        f'static constexpr addr_t kUnityBase={m["base"]:#x};',f'static constexpr size_t kUnityImageSpan={m["image_span"]};',
        f'static constexpr size_t kExpectedConstructors={len(m["initializers"])};',f'static constexpr const char *kUnitySha256="{m["sha256"]}";',
        f'static constexpr const char *kApkSha256="{apk_hash}";',f'static constexpr bool kExploratory={str(a.exploratory).lower()};',
        f'static constexpr size_t kUnsupportedTraces={unsupported};',
        f'static constexpr const char16_t *kPackageName=u{json.dumps(package)};',f'static constexpr int32_t kTargetSdk={sdk};',
        f'static constexpr const char *kLaunchActivity={json.dumps(activity)};',
        'struct UnityImport {const char *name;bool is_object;};','static const UnityImport kUnityImports[]={']
    lines += [f'  {{{json.dumps(name)},{str(obj).lower()}}},' for name,obj in sorted(imports.items())]
    lines += ['};','struct UnityCodeRange {addr_t low,high;};','static constexpr UnityCodeRange kUnityExecutableRanges[]={']
    lines += [f'  {{{low:#x},{high:#x}}},' for low,high in code_ranges]
    lines += ['};','struct UnityExport {const char *name;addr_t address;};','static const UnityExport kUnityExports[]={']
    lines += [f'  {{{json.dumps(name)},{entry:#x}}},' for name,entry in sorted(m['exports'].items())]
    lines += ['};','static const addr_t kUnityFinalizers[]={']+[f'  {entry:#x},' for entry in m['finalizers']]+['};']
    lines += ['struct UnityRegistration {const char *class_name,*name,*signature;addr_t entry;};','static const UnityRegistration kUnityRegistrations[]={']
    lines += [f'  {{{json.dumps(g["class"])},{json.dumps(method["name"])},{json.dumps(method["signature"])},{m["base"]+method["entry_rva"]:#x}}},' for g in groups for method in g['methods']]
    lines += ['};']
    lines += ['static const char *const kUnityJavaClasses[]={']+[f'  {json.dumps(name)},' for name in sorted(classes)]+['};']
    lines += ['static void DefineUnityJavaCatalog(bunker::jni::Host &host){',
              '  // APK declarations support lookup/registration; Java bytecode is not executed.',
              '  // Framework services and complete Android inheritance remain explicit host work.']
    for name,info in sorted(classes.items()):
        lines.append(f'  host.DefineClass({json.dumps(name)},{{')
        lines += [f'    {{{json.dumps(method["name"])},{json.dumps(method["signature"])},{str(method["static"]).lower()},{str(method["native"]).lower()}}},' for method in info['methods']]
        lines.append('  });')
    lines += ['}','static void ApplyUnityPackageMetadata(bunker::windows::AndroidContextConfig &config){',f'  config.version=bunker::windows::AndroidContextConfig::PackageVersion{{{u16(version_name)},{version_code}}};','  config.application_metadata={']
    for name,value in sorted(metadata.items()):
        kind,data=value['type'],value['value']
        factory='String('+u16(data)+')' if kind=='string' else 'Integer('+str(data)+')' if kind=='int' else 'Boolean('+str(data).lower()+')'
        lines.append('    {'+u16(name)+',bunker::windows::LaunchExtra::'+factory+'},')
    lines += ['  };','}']
    (out/'unity_bootstrap_data.h').write_text('\n'.join(lines)+'\n')
    if complete and not a.metadata_only:
        shutil.copyfile(a.translation/'traces.h',out/'unity_traces.h')
        objects=out/'objects';objects.mkdir(exist_ok=True)
        for source in m['objects']:
            source=Path(source);destination=objects/source.name
            if not destination.is_file() or digest(source)!=digest(destination):shutil.copyfile(source,destination)
        native=out/'native';native.mkdir(exist_ok=True)
        shutil.copyfile(a.library,native/'libunity.so')
        (out/'unity_bootstrap_link.json').write_text(json.dumps({'complete':True,'unity_sha256':m['sha256'],'apk_sha256':apk_hash,
            'exploratory':a.exploratory,'unsupported_traces':unsupported,'base':m['base'],'executable_ranges':code_ranges,'constructors':len(m['initializers']),'objects':[f'objects/{Path(o).name}' for o in m['objects']]},indent=2)+'\n')
    elif complete:
        shutil.copyfile(a.translation/'traces.h',out/'unity_traces.h')
        (out/'unity_bootstrap_link.json').unlink(missing_ok=True)
    else:
        # Syntax compilation only; no runtime binary or completed link manifest.
        entries=m['seed_entries']
        h=['// INCOMPLETE declaration catalog for compile-only validation.']
        h += [f'extern "C" Memory *sub_{entry:x}(State &,addr_t,Memory *);' for entry in entries]
        h += ['static const recomp::Trace kTraces[]={']+[f'  {{{entry:#x},sub_{entry:x}}},' for entry in entries]+['};']
        h += ['static const addr_t kInitializers[]={']+[f'  {entry:#x},' for entry in m['initializers']]+['};']
        (out/'unity_traces.h').write_text('\n'.join(h)+'\n')
        (out/'unity_bootstrap_link.json').unlink(missing_ok=True)
    print(f'Original Unity: {len(m["initializers"])} constructors, {len(imports)} imports, {len(classes)} evidenced APK classes; nine JNI tables/42 native signatures validated; '+('complete link inputs ready' if complete and not a.metadata_only else 'compile-only metadata; full translation/link inputs still required'))
if __name__=='__main__':main()
