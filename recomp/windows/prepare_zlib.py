"""Fetch verified official zlib sources and build the static inflate backend.

Pinned upstream release/hash: https://www.zlib.net/ (2026-02-17 release).
Downloaded sources and archives remain in ignored recomp/work, with the
upstream license retained. No MinGW zlib DLL is needed by the resulting EXE.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

VERSION = '1.3.2'
URL = f'https://zlib.net/fossils/zlib-{VERSION}.tar.gz'
SHA256 = 'bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16'
SOURCES = ['adler32.c', 'crc32.c', 'inffast.c', 'inflate.c', 'inftrees.c', 'zutil.c']
HERE = Path(__file__).resolve().parent


def prepare(out, cc, ar, host_path=str):
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f'zlib-{VERSION}.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as source:
            archive.write_bytes(source.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('Official zlib archive SHA256 mismatch')
    source = out / f'zlib-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(out, filter='data')
    objects = []
    for name in SOURCES:
        obj = out / (name[:-2] + '.o')
        subprocess.run([str(cc), '-O2', '-c', host_path(source / name), f'-I{host_path(source)}', '-o', host_path(obj)], check=True)
        objects.append(obj)
    library = out / 'libz-inflate.a'
    subprocess.run([str(ar), 'rcs', host_path(library), *map(host_path, objects)], check=True)
    evidence = {'version': VERSION, 'url': URL, 'sha256': SHA256, 'sources': SOURCES,
                'compiler': str(cc), 'archive': str(library), 'license': str(source / 'LICENSE')}
    (out / 'backend.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return source, library


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=HERE.parent / 'work/zlib-native')
    p.add_argument('--cc', default='C:/mingw64/bin/gcc.exe')
    p.add_argument('--ar', default='C:/mingw64/bin/ar.exe')
    a = p.parse_args()
    source, library = prepare(a.out, a.cc, a.ar)
    print(f'Verified official zlib {VERSION}: {SHA256}; static backend {library}')


if __name__ == '__main__':
    main()
