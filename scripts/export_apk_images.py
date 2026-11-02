#!/usr/bin/env python3
"""Statically export Unity sprites and selected text from a preserved APK.

The APK is never installed or executed. Requires UnityPy and Pillow.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--python-deps', type=Path)
    args = parser.parse_args()
    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve()))
    import UnityPy
    from PIL import Image

    apk = args.apk.resolve(strict=True)
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_hash = digest(apk)
    with zipfile.ZipFile(apk) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError('APK ZIP checksum failed: ' + bad)
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.startswith('assets/bin/Data/'):
                continue
            target = (scratch / entry.filename).resolve()
            if not target.is_relative_to(scratch):
                raise ValueError('Unsafe APK entry: ' + entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))

    environment = UnityPy.load(str(scratch / 'assets/bin/Data'))
    images, texts, errors = [], [], []
    for obj in environment.objects:
        kind = obj.type.name
        if kind not in ('Sprite', 'TextAsset'):
            continue
        asset_file = obj.assets_file.name
        identity = hashlib.sha256(asset_file.encode()).hexdigest()[:12] + '-' + str(obj.path_id)
        try:
            data = obj.read()
            name = data.m_Name
            stem = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)[:100] or 'unnamed'
            if kind == 'TextAsset':
                if name not in ('ui', 'nt', 'titleflow', 'README'):
                    continue
                raw = data.m_Script
                if isinstance(raw, str):
                    raw = raw.encode('utf-8', errors='surrogateescape')
                relative = 'text/' + stem + '-' + identity + '.txt'
                target = output / relative
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(raw)
                texts.append(dict(name=name, file=relative, bytes=len(raw),
                                  sha256=digest(target), asset_file=asset_file, object_id=obj.path_id))
                continue
            relative = 'images/' + stem + '-' + identity + '.png'
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            picture = data.image
            picture.save(target)
            with Image.open(target) as checked:
                checked.load()
                if checked.size != picture.size:
                    raise ValueError('PNG dimensions changed')
            images.append(dict(name=name, file=relative, width=picture.width, height=picture.height,
                               sha256=digest(target), asset_file=asset_file, object_id=obj.path_id))
        except Exception as error:
            errors.append(dict(type=kind, asset_file=asset_file, object_id=obj.path_id,
                               error=type(error).__name__ + ': ' + str(error)))
    manifest = dict(apk=str(apk), apk_sha256=source_hash, images=images, texts=texts, errors=errors,
                    note='Native built-in APK sprites. No claim of matching original notice website images.')
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    cards = ''.join('<figure><a href="{0}"><img loading="lazy" src="{0}"></a><figcaption>{1}<br>{2} × {3}</figcaption></figure>'.format(
        html.escape(x['file'], quote=True), html.escape(x['name']), x['width'], x['height']) for x in images)
    page = '''<!doctype html><meta charset="utf-8"><title>Historical APK sprites</title>
<style>body{font:16px system-ui;background:#202127;color:#eee;margin:24px}input{padding:10px;width:320px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px}figure{margin:0;padding:12px;background:#33343b;overflow-wrap:anywhere}img{width:100%;height:150px;object-fit:contain}figcaption{font-size:13px}</style>
<h1>Historical APK sprites</h1><p>Native sprites extracted from ''' + html.escape(apk.name) + '''. Click an image for its PNG.</p>
<input placeholder="Search sprite names" aria-label="Search sprite names"><p>''' + str(len(images)) + ''' images</p><main>''' + cards + '''</main>
<script>document.querySelector('input').oninput=e=>{const q=e.target.value.toLowerCase();for(const f of document.querySelectorAll('figure'))f.hidden=!f.textContent.toLowerCase().includes(q)}</script>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps(dict(apk=apk.name, images=len(images), texts=len(texts), errors=len(errors), output=str(output))), flush=True)
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
