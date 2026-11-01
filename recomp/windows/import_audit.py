"""Audit real ELF import inventories against compiled native provider Marker APIs.

Marker discovery proves that the current provider claims a symbol, not that all
argument/flag combinations are implemented. Configuration and checked failures
remain part of each provider's contract. Missing weak symbols are reported
separately; no missing strong symbol is silently treated as available.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROVIDERS = {
    'filesystem': ('filesystem.h', 'FileSystem provider;'),
    'logging': ('logging.h', 'Logging provider;'),
    'libc': ('libc.h', 'LibC provider;'),
    'modules': ('module_registry.h', 'ModuleRegistry provider([](addr_t){});'),
    'pthreads': ('pthread_host.h', 'recomp::Runtime runtime; Pthreads provider(runtime,[](addr_t){return false;});'),
    'zlib': ('zlib_host.h', 'Zlib provider;'),
}
LIMITATIONS = {
    'filesystem': 'Only explicitly mounted guest paths and supported Android flags/layouts; opaque guest FILE handles.',
    'logging': 'Sequential narrow printf formats; wide/long-double/positional/%n unsupported. FILE writer callback required.',
    'libc': 'C locale and explicitly configured virtual environment; host libm implementation; translated callback runner required for destructors.',
    'modules': 'Only explicitly registered translated modules; no native ARM64 execution or host DLL fallback.',
    'pthreads': 'Supported synchronization/thread/clock operations; some signal-related functions explicitly return ENOSYS/ENOTSUP.',
    'zlib': 'Exact imported inflate group; explicit Android wire stream and real static backend. Translated callback runner required for custom allocators.',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provider_hashes(extra=()):
    files = {HERE / header for header, _ in PROVIDERS.values()}
    files |= {path.with_suffix('.cpp') for path in files}
    files |= {HERE / name for name in ('provider_memory.h', 'android_types.h')}
    files |= {HERE.parent / 'whole' / name for name in ('bridge.h', 'guest_memory.h', 'format.h', 'format.cpp', 'runtime.h', 'runtime.cpp')}
    files |= set(extra)
    return {str(path): digest(path) for path in sorted(files)}


def build_probe(cxx, remill, out, zlib_source, zlib_archive):
    extra = (zlib_source / 'zlib.h', zlib_source / 'zconf.h', zlib_archive)
    hashes = provider_hashes(extra)
    declarations = []
    calls = []
    sources = []
    for name, (header, constructor) in PROVIDERS.items():
        source = out / f'probe-{name}.cpp'
        source.write_text(
            f'#include "{(HERE / header).as_posix()}"\nusing namespace bunker::windows;\n'
            f'extern "C" uint64_t audit_{name}(const char *name) {{\n'
            f'  static {constructor}\n'
            '  try { return provider.Marker(name); } catch (...) { return 0; }\n}\n')
        sources.append(source)
        declarations.append(f'extern "C" uint64_t audit_{name}(const char *);')
        calls.append(f'    if(auto value=audit_{name}(name.c_str())) std::cout << name << "\\t{name}\\t" << std::hex << value << "\\n";')
    main = out / 'probe-main.cpp'
    main.write_text('#include <cstdint>\n#include <iostream>\n#include <string>\n' + '\n'.join(declarations) +
                    '\nint main(){std::string name;while(std::getline(std::cin,name)){\n' + '\n'.join(calls) + '\n}}\n')
    binary = out / 'provider-probe.exe'
    subprocess.run([str(cxx), '-std=c++17', '-O2', '-static', '-DADDRESS_SIZE_BITS=64', f'-I{remill / "include"}', f'-I{zlib_source}',
                    str(main), *map(str, sources), *[str(HERE / name) for name in
                    ('filesystem.cpp', 'logging.cpp', 'libc.cpp', 'module_registry.cpp', 'pthread_host.cpp', 'zlib_host.cpp')],
                    str(HERE.parent / 'whole/format.cpp'), str(HERE.parent / 'whole/runtime.cpp'), str(zlib_archive), '-latomic', '-o', str(binary)], check=True)
    if hashes != provider_hashes(extra):
        raise RuntimeError('Provider sources changed during audit probe build; rerun for a consistent snapshot')
    binary.with_suffix('.sources.json').write_text(json.dumps(hashes, indent=2))
    return binary


def audit(inventory, manifests, bindings):
    exports = {}
    translated = []
    for path, manifest in manifests:
        source = Path(manifest['source']).name
        translated.append({'manifest': str(path), 'source': manifest['source'], 'sha256': manifest.get('sha256'),
                           'target': manifest.get('target'), 'traces': len(manifest.get('traces', [])),
                           'unsupported_traces': len(manifest.get('unsupported_traces', [])),
                           'unresolved_direct_targets': len(manifest.get('unresolved_direct_targets', [])),
                           'imports': manifest.get('imports', [])})
        for name in manifest.get('exports', {}):
            exports.setdefault(name, []).append(source)
    for item in translated:
        item['import_bindings'] = [
            {'symbol': name, 'providers': bindings.get(name, []), 'translated_modules': exports.get(name, []),
             'status': 'provider_marker' if bindings.get(name) else 'translated_export' if exports.get(name) else 'missing'}
            for name in item.pop('imports')]
        item['import_counts'] = dict(Counter(row['status'] for row in item['import_bindings']))
    libraries = {}
    for library, data in inventory['libraries'].items():
        rows = []
        for symbol, imported in sorted(data['imports'].items()):
            candidates = bindings.get(symbol, [])
            modules = exports.get(symbol, [])
            status = 'provider_marker' if candidates else 'translated_export' if modules else 'missing_weak' if imported['binding'] == 'STB_WEAK' else 'missing_strong'
            rows.append({'symbol': symbol, **imported, 'status': status, 'providers': candidates, 'translated_modules': modules})
        libraries[library] = {'sha256': data.get('sha256'), 'needed': data.get('needed', []),
                              'counts': dict(Counter(row['status'] for row in rows)),
                              'missing_by_category': dict(Counter(row['category'] for row in rows if row['status'] == 'missing_strong')),
                              'imports': rows}
    return {'discovery': 'Compiled native Windows providers; actual Marker(name) calls. This is import ownership, not blanket semantic coverage.',
            'limitations': LIMITATIONS, 'manifests': translated, 'libraries': libraries}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, default=HERE.parent / 'work/windows-jni/inventory.json')
    p.add_argument('--manifest', type=Path, action='append', default=[])
    p.add_argument('--out', type=Path, default=HERE.parent / 'work/import-audit')
    p.add_argument('--remill', type=Path, default=HERE.parent / 'work/remill-src')
    p.add_argument('--cxx', type=Path, default=Path('C:/mingw64/bin/g++.exe'))
    p.add_argument('--probe', type=Path, help='Use an already-built provider probe instead of compiling it')
    p.add_argument('--zlib-source', type=Path, default=HERE.parent / 'work/zlib-native/zlib-1.3.2')
    p.add_argument('--zlib-archive', type=Path, default=HERE.parent / 'work/zlib-native/libz-inflate.a')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(a.inventory.read_text())
    manifests = [(path, json.loads(path.read_text())) for path in a.manifest]
    names = sorted({name for data in inventory['libraries'].values() for name in data['imports']} |
                   {name for _, manifest in manifests for name in manifest.get('imports', [])})
    binary = a.probe or build_probe(a.cxx, a.remill, a.out, a.zlib_source, a.zlib_archive)
    stamp = binary.with_suffix('.sources.json')
    if not stamp.exists() or json.loads(stamp.read_text()) != provider_hashes((a.zlib_source / 'zlib.h', a.zlib_source / 'zconf.h', a.zlib_archive)):
        raise RuntimeError('Audit probe is unverified or stale; omit --probe to build against current sources')
    output = subprocess.check_output([str(binary.resolve())], input='\n'.join(names) + '\n', text=True)
    bindings = {}
    for line in output.splitlines():
        symbol, provider, address = line.split('\t')
        bindings.setdefault(symbol, []).append({'provider': provider, 'address': '0x' + address,
                                                'kind': 'data' if symbol in ('environ', '__sF') else 'function'})
    report = audit(inventory, manifests, bindings)
    report['inputs'] = {'inventory': str(a.inventory), 'inventory_sha256': digest(a.inventory),
                        'probe': str(binary), 'probe_sha256': digest(binary),
                        'providers': {name: digest((HERE / header).with_suffix('.cpp'))
                                      for name, (header, _) in PROVIDERS.items()}}
    (a.out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Native Windows import audit', '', report['discovery'], '']
    for library in ('libunity.so', 'libil2cpp.so'):
        if library not in report['libraries']:
            continue
        entry = report['libraries'][library]
        counts = entry['counts']
        text = f'{library}: ' + ', '.join(f'{n} {status}' for status, n in sorted(counts.items()))
        print(text)
        lines += [f'## {library}', '', text, '', 'Missing strong imports:', '']
        lines += ['- ' + row['symbol'] for row in entry['imports'] if row['status'] == 'missing_strong']
        lines += ['']
    (a.out / 'audit.md').write_text('\n'.join(lines))
    print(f'Wrote {a.out / "audit.json"}')


if __name__ == '__main__':
    main()
