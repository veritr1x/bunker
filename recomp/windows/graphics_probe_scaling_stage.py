"""Stage a separate diagnostic scaling bundle after a successful variant build."""
from pathlib import Path
import hashlib
import json
import shutil
WORK=Path(__file__).resolve().parent.parent/'work'


def main():
    root=WORK/'angle-scaling';base=WORK/'angle-native/bundle';bundle=root/'bundle'
    assert root.resolve()!=base.parent.resolve()
    build=json.loads((root/'build-success.json').read_text(encoding='utf-8-sig'))
    patch=json.loads((root/'scaling-patch.json').read_text())
    if build['source_patch']['patch_sha256']!=patch['patch_sha256']:raise RuntimeError('Scaling source changed after build')
    for file in build['files']:
        if hashlib.sha256(Path(file['path']).read_bytes()).hexdigest()!=file['sha256']:raise RuntimeError('Built scaling DLL hash mismatch')
    for name,digest in patch['files_sha256'].items():
        if hashlib.sha256((root/'src'/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Scaling source differs from built pin')
    shutil.copytree(base,bundle,dirs_exist_ok=True)
    output=root/'src/out/BunkerVulkanScaling'
    for name in ['libEGL.dll','libGLESv2.dll','libthird_party_zlib.dll']:shutil.copy2(output/name,bundle/'bin'/name)
    files={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file() and p.name!='provenance.json'}
    record={'diagnostic_only':True,'redistribution_review_complete':False,'accepted':False,'base_bundle_provenance_sha256':hashlib.sha256((base/'provenance.json').read_bytes()).hexdigest(),
            'source_provenance':json.loads((root/'prepare-provenance.json').read_text()),'variant_patch':patch,'build':build,'files_sha256':files,
            'purpose':'Isolated native Vulkan fixed-buffer prototype; base accepted bundle remains unchanged'}
    (bundle/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Separate diagnostic scaling bundle staged:'+str(bundle/'bin'))


if __name__=='__main__':main()
