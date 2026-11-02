"""Export the strict web-builder notice ZIP, keeping audit files separately."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path

NAME=re.compile(r'notices\.json|img/[A-Za-z0-9_-]+\.webp|web/(?:[A-Za-z0-9_@~-][A-Za-z0-9_.@~-]*/)*[A-Za-z0-9_@~-][A-Za-z0-9_.@~-]*')
AUDIT=('reconstruction/','generated/','templates/')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('inputs/bunker-notices-template-based.zip'))
    p.add_argument('--output',type=Path,default=Path('inputs/bunker-notices-template-runtime.zip'))
    p.add_argument('--report',type=Path,default=Path('.build/web-builder-notice-pack-run/runtime-pack.json'))
    a=p.parse_args();assert a.source.resolve()!=a.output.resolve()
    removed=[];kept=[]
    with zipfile.ZipFile(a.source) as src,zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED) as out:
        assert 'notices.json' in src.namelist()
        for name in src.namelist():
            if name.endswith('/'):continue
            if not NAME.fullmatch(name):
                assert name.startswith(AUDIT),f'Unrecognized file must not be dropped silently: {name}'
                removed.append(name);continue
            info=zipfile.ZipInfo(name,(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            out.writestr(info,src.read(name));kept.append(name)
    with zipfile.ZipFile(a.source) as src,zipfile.ZipFile(a.output) as out:
        assert out.testzip() is None
        assert all(src.read(n)==out.read(n) for n in kept)
        index=json.loads(out.read('notices.json'))
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    report={'source':str(a.source.resolve()),'source_sha256':sha(a.source),'runtime':str(a.output.resolve()),
            'runtime_sha256':sha(a.output),'bytes':a.output.stat().st_size,'notices':len(index['notices']),
            'gacha_keys':len(index['gacha']),'runtime_members_preserved_byte_for_byte':len(kept),'audit_members_omitted':removed}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
