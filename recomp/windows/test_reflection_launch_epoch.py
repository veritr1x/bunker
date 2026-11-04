"""Qualified endUnityLaunch epoch side effect through actual NDK direct/V/A callers."""
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORK=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='ab351e2314be540c52ea7c5dea5dbd7261393d50'
OWN=('reflection_launch_epoch.h','reflection_launch_epoch_guest.c','reflection_launch_epoch_test.cpp','test_reflection_launch_epoch.py')

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    audit=WORK/'launch-url1-end-launch-boundary1/summary.json';assert sha(audit)=='a0c98e621c0850b54c505e640864bbe1d27e7af4c9758201d6b7a8cc359af22a'
    assert json.loads(audit.read_text())['passed']is True
    code=WORK/'launch-url1-end-launch-boundary1/exact-code-items.json';record=json.loads(code.read_text());assert record['passed']is True
    dex=WORK/'launch-url1-end-launch-boundary1/classes2.dex';assert sha(dex)==record['dex_sha256']=='21db9654baeaf0fcdbba642f89ed4f34db1839bd64b1a18ce63d3515012738a4'
    raw=dex.read_bytes();end=record['items']['endUnityLaunch'];offset=int(end['code_item'],16)+16
    assert raw[offset:offset+end['code_units']*2].hex()==end['code_hex']=='6100d0a016020100bb206800d0a00e00'
    archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
    source=out/'source';source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive))as bundle:bundle.extractall(source,filter='data')
    source=source/'recomp'
    for name in OWN:shutil.copy2(HERE/name,source/'windows'/name)
    owned={'windows/'+name:sha(source/'windows'/name)for name in OWN}
    support={str(path.relative_to(source)):sha(path)for path in source.rglob('*')if path.is_file()}
    assert support['windows/jni_host.h']=='606a188ec507bf8c49acbb611ac4f8d769dde3b01dc3b77a3109471930d86f30'
    assert support['windows/jni_host.cpp']=='0fad8c9cdc4fb66b4074a4d3ef248ee7ff8d4855e237f0a1adc4b16d4796e8a6'
    tool=WORK/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4'
    ndkroot=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64')
    ndk=ndkroot/'bin/aarch64-linux-android24-clang';jni=ndkroot/'sysroot/usr/include/jni.h'
    inputs={str(path):sha(path)for path in(audit,code,dex,ndk.resolve(),jni,tool/'remill-lift',tool/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve(),Path(shutil.which('clang-18')).resolve())}
    for path in(tool/'include').rglob('*'):
        if path.is_file():inputs[str(path)]=sha(path)
    commands=[]
    def run(command,label):
        command=list(map(str,command));commands.append(command);print('STAGE '+label,flush=True)
        with(out/(label+'.log')).open('w')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        text=(out/(label+'.log')).read_text(errors='replace')
        if result.returncode:
            (out/'failure.json').write_text(json.dumps({'passed':False,'stage':label,'exit_code':result.returncode},indent=2)+'\n');raise RuntimeError(label+'\n'+text[-4000:])
        return {'exit_code':result.returncode,'stdout':text}
    library=out/'reflection-launch-epoch.so';win=source/'windows'
    run([ndk,'-shared','-nostdlib','-O1','-fPIC','-fno-stack-protector','-fno-builtin','-Wall','-Wextra','-Werror',win/'reflection_launch_epoch_guest.c','-o',library],'NDK-build')
    inputs[str(library)]=sha(library);platforms={};manifests={}
    for windows in(True,False):
        platform='windows'if windows else'linux';build=out/platform;build.mkdir();convert=wp if windows else str
        cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
        flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',convert(tool/'include')]
        loader=build/'elfload.o';run([cc,'-O2','-c',convert(source/'fastaes/elfload.c'),'-o',convert(loader)],platform+'-loader');objects=[loader]
        for name in('windows/jni_host.cpp','whole/runtime.cpp'):
            obj=build/(Path(name).stem+'.o');run([cxx,*flags,'-c',convert(source/name),'-o',convert(obj)],platform+'-'+obj.stem);objects.append(obj)
        guest=build/'guest';run([sys.executable,source/'whole/compile.py',library,'--out',guest,'--base','0x73000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],platform+'-translate')
        manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
        manifests[platform]={'path':str(guest/'manifest.json'),'sha256':sha(guest/'manifest.json'),'traces':len(manifest['traces']),'objects':len(manifest['objects'])}
        executable=build/('reflection-launch-epoch.exe'if windows else'reflection-launch-epoch')
        run([cxx,*flags,'-I'+convert(guest),f'-DREFLECTION_EPOCH_IMAGE="{convert(library)}"','-Wall','-Wextra','-Werror',convert(win/'reflection_launch_epoch_test.cpp'),*map(convert,objects),*map(convert,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',convert(executable)],platform+'-link')
        result=run([executable],platform+'-test');assert'REFLECTION-LAUNCH-EPOCH-PASS'in result['stdout'];result['checks']=int(re.search(r'checks=(\d+)',result['stdout'])[1]);result['binary_sha256']=sha(executable);platforms[platform]=result
    for name,digest in support.items():assert sha(source/name)==digest,name
    for name,digest in owned.items():assert sha(HERE.parent/name)==digest,name
    for path,digest in inputs.items():assert sha(path)==digest,path
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    receipt={'passed':True,'commit':BASE,'owned_sources':owned,'support_sources':support,'inputs':inputs,'DEX_audit':{'path':str(audit),'sha256':sha(audit)},'platforms':platforms,'manifests':manifests,'actual_NDK_static_void_direct_V_A':True,'zero_initialized_per_Host_retained_epoch':True,'unsigned_modulo_wrap_helper_qualified':True,'separate_relaxed_load_store_not_atomic_RMW':True,'no_JNI_core_or_existing_proxy_changes':True,'no_class_initialization_or_unbacked_static_field_claim':True,'limits':'Only ReflectionHelper.endUnityLaunch side effect is supplied. Host-owned epoch is not yet exposed through Java b:J or accessor; ReflectionHelper proxy factory/dispatch remain unsupported and must share this owner when ported. Existing bitter/JNIBridge is independent. No original game execution.'}
    receipt['evidence']={str(path.relative_to(out)):sha(path)for path in out.rglob('*')if path.is_file()and path.name!='acceptance.json'}
    (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('REFLECTION-LAUNCH-EPOCH-QUALIFIED '+sha(out/'acceptance.json'),flush=True)

if __name__=='__main__':main()
