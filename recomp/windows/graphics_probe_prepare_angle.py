"""Prepare a workspace-only pinned MinGW ANGLE build; never installs software.

Uses the official MSYS2 portability recipe at a fixed commit. Source checkouts
are detached at exact upstream commits. Tools and package verification evidence
stay under recomp/work/angle-native. Existing graphics-probe reports are untouched.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'work/angle-native'
RECIPE = 'dd88a67c5372893318e3d223aa8bfb6f8fb3aff1'
SOURCES = {
    'src': ('https://github.com/google/angle.git', '890b5d8fa2988e3719e0d80421bf3e927db9cd5c'),
    'src/build': ('https://chromium.googlesource.com/chromium/src/build.git', '70c150bc0ae989d00c15ab1ed67464198e4890d0'),
    'src/third_party/zlib': ('https://chromium.googlesource.com/chromium/src/third_party/zlib.git', 'bf1e8de6cc305fdab82db1b65bed76b70bd96c8b'),
    'src/tools/clang': ('https://chromium.googlesource.com/chromium/src/tools/clang.git', 'd6072980974f9a4922d2eb27e4fd244ca3017031'),
    'src/third_party/spirv-headers/src': ('https://github.com/KhronosGroup/SPIRV-Headers.git', 'c8ad050fcb29e42a2f57d9f59e97488f465c436d'),
    'src/third_party/spirv-tools/src': ('https://github.com/KhronosGroup/SPIRV-Tools.git', '257a227fbadf8176ea386c7d8fb9b889cbf08640'),
    'src/third_party/vulkan-headers/src': ('https://github.com/KhronosGroup/Vulkan-Headers.git', '7cff847503174e2049b08253ee5f30428866fea3'),
    'src/third_party/vulkan-loader/src': ('https://github.com/KhronosGroup/Vulkan-Loader.git', '235d1d2cf617af03a2ecbf6e951287595138feda'),
    'src/third_party/vulkan_memory_allocator': ('https://chromium.googlesource.com/external/github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator.git', '56300b29fbfcc693ee6609ddad3fdd5b7a449a21'),
    'src/third_party/vulkan-tools/src': ('https://chromium.googlesource.com/external/github.com/KhronosGroup/Vulkan-Tools.git', '5968d14a1ef8a7eeacf342e1542099e1aff20f70'),
    'src/third_party/astc-encoder/src': ('https://chromium.googlesource.com/external/github.com/ARM-software/astc-encoder', '2319d9c4d4af53a7fc7c52985e264ce6e8a02a9b'),
    'src/third_party/jsoncpp': ('https://chromium.googlesource.com/chromium/src/third_party/jsoncpp', 'f62d44704b4da6014aa231cfc116e7fd29617d2a'),
    'src/third_party/jsoncpp/source': ('https://github.com/open-source-parsers/jsoncpp.git', '42e892d96e47b1f6e29844cc705e148ec4856448'),
    'src/third_party/rapidjson/src': ('https://github.com/Tencent/rapidjson.git', '781a4e667d84aeedbeb8184b7b62425ea66ec59f'),
    'tools/gn-src': ('https://gn.googlesource.com/gn','150a9d6ba0aa7f407aa4feeabc5f03ce9aa7e04b'),
}

def run(args, cwd=None):
    command=[x.as_posix() if isinstance(x,Path) else str(x) for x in args]
    try:
        return subprocess.check_output(command, cwd=cwd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f'Command failed: {command}\n{error.output}') from error

def checkout(item):
    relative, (url, commit) = item
    target = ROOT / relative
    target.mkdir(parents=True, exist_ok=True)
    if not (target/'.git').exists():
        run(['git','init','-q',target])
        run(['git','remote','add','origin',url], target)
    try:
        head = run(['git','rev-parse','HEAD'], target).strip()
    except RuntimeError:
        head = ''
    if head != commit:
        if head and run(['git','status','--porcelain'], target).strip():
            raise RuntimeError(f'Refusing to replace modified source {target}')
        print(f'Fetch {relative} {commit}', flush=True)
        try:
            run(['git','-c','core.autocrlf=false','fetch','--depth=1',url,commit], target)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f'{relative}: {error.output}') from error
        run(['git','-c','core.autocrlf=false','checkout','--detach','FETCH_HEAD'], target)
    assert run(['git','rev-parse','HEAD'], target).strip() == commit
    licenses = {}
    for path in target.iterdir():
        if path.is_file() and any(x in path.name.lower() for x in ('license','copying','copyright','notice')):
            licenses[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f'Ready {relative}', flush=True)
    return relative, {'url':url,'commit':commit,'licenses_sha256':licenses}

def fetch(url, target, expected=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        print(f'Download {target.name}',flush=True)
        raw=urllib.request.urlopen(url,timeout=120).read()
        target.write_bytes(raw)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f'SHA256 mismatch: {target}')
    return {'url':url,'sha256':digest,'bytes':target.stat().st_size}

def tools():
    target=ROOT/'tools';target.mkdir(parents=True,exist_ok=True)
    package='mingw-w64-x86_64-gn-0.2540.150a9d6b-1-any.pkg.tar.zst'
    base='https://repo.msys2.org/mingw/mingw64/'
    records={package:fetch(base+package,target/package,'3ae5b384b2c3b5e08acc4e3c47c0a27cdcd3fc1201debd5ef26813cdc78cebd5')}
    records[package+'.sig']=fetch(base+package+'.sig',target/(package+'.sig'))
    ring='https://raw.githubusercontent.com/msys2/MSYS2-keyring/5d249077a0cfeec9dbf51515e5e01da413d28859/msys2.gpg'
    records['msys2.gpg']=fetch(ring,target/'msys2.gpg')
    gpgv=Path('C:/Program Files/Git/usr/bin/gpgv.exe')
    home=target/'gnupg';home.mkdir(exist_ok=True)
    run(['C:/Program Files/Git/usr/bin/gpg.exe','--no-options','--homedir',home,'--batch','--yes','--dearmor','--output',target/'keyring.gpg',target/'msys2.gpg'])
    verification=run([gpgv,'--homedir',home,'--status-fd','1','--keyring',target/'keyring.gpg',target/(package+'.sig'),target/package])
    if '[GNUPG:] VALIDSIG ' not in verification:
        raise RuntimeError('GN package has no valid official keyring signature')
    (target/'gn-signature.txt').write_text(verification)
    # Validate every archive member before extraction; no absolute/traversal paths.
    members=run(['C:/Windows/System32/tar.exe','-tf',target/package]).splitlines()
    for member in members:
        path=Path(member)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Unsafe GN archive member '+member)
    run(['C:/Windows/System32/tar.exe','-xf',target/package,'-C',target])
    records['verification']=verification
    records['license_sha256']=hashlib.sha256((target/'mingw64/share/licenses/gn/LICENSE').read_bytes()).hexdigest()
    records['gn_exe_sha256']=hashlib.sha256((target/'mingw64/bin/gn.exe').read_bytes()).hexdigest()
    (target/'provenance.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Verified workspace GN binary, official MSYS2 signature and SHA256',flush=True)
    # Keep the official GN package and its exact private runtime together.
    # This prefix is never added to the compiler's PATH: ANGLE uses the existing
    # Winlibs UCRT GCC15 toolchain; GN uses its own MSYS2 GCC16 runtime.
    dependencies={
        'libstdc++-16.2.0-6':'924b47e8c3e20b6448e29d3333acc638a4f4783c1c45230e09673532f9c4f198',
        'libgcc-16.2.0-6':'e0815432c4225892b0eef57055fe507fa0b9a036436f046605f6629696bd1b88',
        'libwinpthread-14.0.0.r569.g34eeafb7d-1':'7774d48f1b2727f54c8148e5994a4a8e464dfa2dd5a177e630ebfd522dcbe2c0',
        'tzdata-2026f-1':'ee33831fd41045555220d250a816a2a3a57116f8b1fb7f574bf3db7079299da2',
    }
    for name,digest in dependencies.items():
        package='mingw-w64-x86_64-'+name+'-any.pkg.tar.zst'
        records[package]=fetch(base+package,target/package,digest)
        records[package+'.sig']=fetch(base+package+'.sig',target/(package+'.sig'))
        verification=run([gpgv,'--homedir',home,'--status-fd','1','--keyring',target/'keyring.gpg',target/(package+'.sig'),target/package])
        if '[GNUPG:] VALIDSIG ' not in verification:
            raise RuntimeError('Runtime package has no official signature: '+package)
        records[package]['signature_verification']=verification
        members=run(['C:/Windows/System32/tar.exe','-tf',target/package]).splitlines()
        for member in members:
            path=Path(member)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unsafe runtime archive member '+member)
        run(['C:/Windows/System32/tar.exe','-xf',target/package,'-C',target])
    executable=target/'mingw64/bin/gn.exe'
    records['version']=run([executable,'--version']).strip()
    records['private_runtime_licenses_sha256']={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (target/'mingw64/share/licenses').rglob('*') if p.is_file()}
    (target/'provenance.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Verified official GN and private runtime, with no system installation',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--tools-only',action='store_true')
    args=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    if args.tools_only:
        tools();return
    evidence_path=ROOT/'prepare-provenance.json'
    evidence=json.loads(evidence_path.read_text()) if evidence_path.exists() else {'sources':{},'downloads':{}}
    # Parent checkout must exist before nested dependency repositories are created.
    key,record=checkout(('src',SOURCES['src']))
    evidence['sources'][key]=record
    evidence_path.write_text(json.dumps(evidence,indent=2)+'\n')
    # jsoncpp's source repository must follow its enclosing Chromium GN files.
    for group in [lambda p:p not in ('src','src/third_party/jsoncpp/source'),lambda p:p=='src/third_party/jsoncpp/source']:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures={pool.submit(checkout,item):item[0] for item in SOURCES.items() if group(item[0])}
            failures=[]
            for future in concurrent.futures.as_completed(futures):
                try:
                    key,record=future.result();evidence['sources'][key]=record
                except Exception as error:
                    failures.append(str(error))
                evidence_path.write_text(json.dumps(evidence,indent=2)+'\n')
            if failures:raise RuntimeError('\n'.join(failures))
    recipe=ROOT/'recipe'
    for name in ['PKGBUILD','001-add-mingw-toolchain.patch','002-buildflags-fixes.patch','003-angle-src-fixes.patch','005-vulkan-memory-allocator-updates.patch','006-spirv-updates.patch','007-vulkan-loader-updates.patch']:
        url=f'https://raw.githubusercontent.com/msys2/MINGW-packages/{RECIPE}/mingw-w64-angleproject/{name}'
        evidence['downloads'][f'recipe/{name}']=fetch(url,recipe/name)
    evidence['recipe_commit']=RECIPE
    evidence_path.write_text(json.dumps(evidence,indent=2)+'\n')
    if not args.sources_only:tools()
    print('Source preparation complete; see prepare-provenance.json',flush=True)

if __name__=='__main__':
    main()
