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
from inventory import Dex

HERE=Path(__file__).resolve().parent
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
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
    sdk=int(re.search(r"^targetSdkVersion:'(\d+)'",badging,re.M).group(1))
    activity=re.search(r"^launchable-activity: name='([^']+)'",badging,re.M).group(1).replace('.','/')
    classes={}
    with zipfile.ZipFile(a.apk) as apk:
        for name in apk.namelist():
            if re.fullmatch(r'classes\d*\.dex',name):classes.update(Dex(apk.read(name)).unity_classes())
    if not classes:raise RuntimeError('Actual APK does not declare Unity JNI classes')
    with a.library.open('rb') as f:
        elf=ELFFile(f);syms=elf.get_section_by_name('.dynsym')
        imports={s.name:s['st_info']['type']=='STT_OBJECT' for s in syms.iter_symbols() if s['st_shndx']=='SHN_UNDEF' and s.name}
    if set(imports)!=set(m['imports']):raise RuntimeError('Original ELF and translation import catalogs differ')
    apk_hash=digest(a.apk)
    unsupported=len(m.get('unsupported_traces',[]))
    lines=['// Generated from original APK/ELF and verified translation, not desktop guesses.',
        f'static constexpr addr_t kUnityBase={m["base"]:#x};',f'static constexpr size_t kUnityImageSpan={m["image_span"]};',
        f'static constexpr size_t kExpectedConstructors={len(m["initializers"])};',f'static constexpr const char *kUnitySha256="{m["sha256"]}";',
        f'static constexpr const char *kApkSha256="{apk_hash}";',f'static constexpr bool kExploratory={str(a.exploratory).lower()};',
        f'static constexpr size_t kUnsupportedTraces={unsupported};',
        f'static constexpr const char16_t *kPackageName=u{json.dumps(package)};',f'static constexpr int32_t kTargetSdk={sdk};',
        f'static constexpr const char *kLaunchActivity={json.dumps(activity)};',
        'struct UnityImport {const char *name;bool is_object;};','static const UnityImport kUnityImports[]={']
    lines += [f'  {{{json.dumps(name)},{str(obj).lower()}}},' for name,obj in sorted(imports.items())]
    lines += ['};','struct UnityExport {const char *name;addr_t address;};','static const UnityExport kUnityExports[]={']
    lines += [f'  {{{json.dumps(name)},{entry:#x}}},' for name,entry in sorted(m['exports'].items())]
    lines += ['};','static const addr_t kUnityFinalizers[]={']+[f'  {entry:#x},' for entry in m['finalizers']]+['};']
    lines += ['static const char *const kUnityJavaClasses[]={']+[f'  {json.dumps(name)},' for name in sorted(classes)]+['};']
    lines += ['static void DefineUnityJavaCatalog(bunker::jni::Host &host){',
              '  // APK declarations support lookup/registration; Java bytecode is not executed.',
              '  // Framework services and complete Android inheritance remain explicit host work.']
    for name,info in sorted(classes.items()):
        lines.append(f'  host.DefineClass({json.dumps(name)},{{')
        lines += [f'    {{{json.dumps(method["name"])},{json.dumps(method["signature"])},{str(method["static"]).lower()},{str(method["native"]).lower()}}},' for method in info['methods']]
        lines.append('  });')
    lines += ['}']
    (out/'unity_bootstrap_data.h').write_text('\n'.join(lines)+'\n')
    if complete:
        shutil.copyfile(a.translation/'traces.h',out/'unity_traces.h')
        objects=out/'objects';objects.mkdir(exist_ok=True)
        for source in m['objects']:
            source=Path(source);destination=objects/source.name
            if not destination.is_file() or digest(source)!=digest(destination):shutil.copyfile(source,destination)
        native=out/'native';native.mkdir(exist_ok=True)
        shutil.copyfile(a.library,native/'libunity.so')
        (out/'unity_bootstrap_link.json').write_text(json.dumps({'complete':True,'unity_sha256':m['sha256'],'apk_sha256':apk_hash,
            'exploratory':a.exploratory,'unsupported_traces':unsupported,'base':m['base'],'constructors':len(m['initializers']),'objects':[f'objects/{Path(o).name}' for o in m['objects']]},indent=2)+'\n')
    else:
        # Syntax compilation only; no runtime binary or completed link manifest.
        entries=m['seed_entries']
        h=['// INCOMPLETE declaration catalog for compile-only validation.']
        h += [f'extern "C" Memory *sub_{entry:x}(State &,addr_t,Memory *);' for entry in entries]
        h += ['static const recomp::Trace kTraces[]={']+[f'  {{{entry:#x},sub_{entry:x}}},' for entry in entries]+['};']
        h += ['static const addr_t kInitializers[]={']+[f'  {entry:#x},' for entry in m['initializers']]+['};']
        (out/'unity_traces.h').write_text('\n'.join(h)+'\n')
        (out/'unity_bootstrap_link.json').unlink(missing_ok=True)
    print(f'Original Unity: {len(m["initializers"])} constructors, {len(imports)} imports, {len(classes)} APK Unity classes; '+('complete link inputs ready' if complete else 'compile-only metadata; full translation still required'))
if __name__=='__main__':main()
