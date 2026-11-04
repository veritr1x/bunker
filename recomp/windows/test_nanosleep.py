"""New nanosleep provider: frozen actual Bionic ARM reference and translated hosts."""
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
BASE='df179927722c32566e881497247ea853904849f4'
OWN=('signal_nanosleep.h','signal_nanosleep.cpp','nanosleep_guest.c','nanosleep_guest.S','nanosleep_ref.c','nanosleep_native_wrappers.c','nanosleep_test.cpp','test_nanosleep.py')
FIXTURES=('nanosleep_guest.c','nanosleep_guest.S','nanosleep_ref.c')

def sha(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()

def canonical(text,count=30):
    records=[line for line in text.splitlines()if line.startswith('record ')]
    assert len(records)==count,len(records)
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--host-only',action='store_true');p.add_argument('--reuse-host',action='store_true')
    for kind in('arm-reference','native-reference'):
        p.add_argument('--'+kind,type=Path);p.add_argument('--'+kind+'-sha')
    a=p.parse_args();out=a.out.resolve()
    if a.reuse_host:
        assert not a.host_only;seal(out,a);return
    out.mkdir(parents=True,exist_ok=False)
    root=HERE.parent.parent;archive=subprocess.check_output(['git.exe','-C',wp(root),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
    source=out/'source';source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive))as bundle:bundle.extractall(source,filter='data')
    source=source/'recomp'
    for name in OWN:shutil.copy2(HERE/name,source/'windows'/name)
    owned={'windows/'+name:sha(source/'windows'/name)for name in OWN};support={str(path.relative_to(source)):sha(path)for path in source.rglob('*')if path.is_file()}
    parent=json.loads((WORK/'windows-first-frame-continuation1/game_inputs.json').read_text());protected=parent['collector_delivery_qualification']['protected_implementation_source_sha256'];assert len(protected)==27
    for name,h in protected.items():assert support[name]==h and sha(HERE.parent/name)==h,name
    tool=WORK/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4';ndkroot=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64');ndk=ndkroot/'bin/aarch64-linux-android24-clang'
    inputs={str(path):sha(path)for path in(ndk.resolve(),tool/'remill-lift',tool/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve(),Path(shutil.which('clang-18')).resolve())}
    caller=WORK/'continuation1-nanosleep-boundary1/summary.json';assert sha(caller)=='0b1c099221db47559ca2a76728451c3954cf937be25f8708195feb13b0cda6cc';inputs[str(caller)]=sha(caller)
    for path in(tool/'include').rglob('*'):
        if path.is_file():inputs[str(path)]=sha(path)
    commands=[]
    def run(command,label):
        command=list(map(str,command));commands.append(command);print('STAGE '+label,flush=True)
        with(out/(label+'.log')).open('w')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        text=(out/(label+'.log')).read_text(errors='replace')
        if result.returncode:
            (out/'failure.json').write_text(json.dumps({'passed':False,'stage':label,'exit_code':result.returncode},indent=2)+'\n');raise RuntimeError(label+'\n'+text[-5000:])
        return {'exit_code':result.returncode,'stdout':text}
    win=source/'windows';objects=[];flags=['-O1','-fPIC','-fno-builtin','-fno-stack-protector','-fno-emulated-tls','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror']
    for suffix in('c','S'):
        obj=out/('guest-'+suffix+'.o');run([ndk,*flags,'-c',win/('nanosleep_guest.'+suffix),'-o',obj],'NDK-'+suffix);objects.append(obj)
    library=out/'nanosleep.so';run([ndk,'-shared','-nostdlib',*objects,'-o',library],'NDK-library');inputs[str(library)]=sha(library)
    platforms={};manifests={}
    for windows in(False,True):
        platform='windows'if windows else'linux';build=out/platform;build.mkdir();convert=wp if windows else str
        cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18'
        guest=build/'guest';run([sys.executable,source/'whole/compile.py',library,'--out',guest,'--base','0x5b000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18'],platform+'-translate')
        manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
        manifests[platform]={'manifest_sha256':sha(guest/'manifest.json'),'heads':len(manifest['traces']),'objects':len(manifest['objects'])}
        cpp=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',convert(tool/'include'),'-I'+convert(guest),f'-DNANOSLEEP_IMAGE="{convert(library)}"']
        run([cxx,*cpp,'-Wall','-Wextra','-Werror','-fsyntax-only',convert(win/'signal_nanosleep.cpp'),convert(win/'nanosleep_test.cpp')],platform+'-strict')
        loader=build/'loader.o';run([cc,'-O2','-c',convert(source/'fastaes/elfload.c'),'-o',convert(loader)],platform+'-loader');compiled=[loader]
        for rel in('windows/signal_host.cpp','windows/signal_nanosleep.cpp','windows/signal_delivery.cpp','whole/signal_frame.cpp','whole/runtime.cpp'):
            obj=build/(Path(rel).stem+'.o');run([cxx,*cpp,'-c',convert(source/rel),'-o',convert(obj)],platform+'-'+obj.stem);compiled.append(obj)
        exe=build/('nanosleep.exe'if windows else'nanosleep');run([cxx,*cpp,'-Wall','-Wextra','-Werror',convert(win/'nanosleep_test.cpp'),*map(convert,compiled),*map(convert,manifest['objects']),'-pthread','-latomic',*(['-static']if windows else[]),'-o',convert(exe)],platform+'-link')
        result=run([exe],platform+'-test');assert'NANOSLEEP-HOST-SUCCESS records=30'in result['stdout']
        result['checks']=int(re.search(r'checks=(\d+)',result['stdout'])[1]);result['binary_sha256']=sha(exe);result['canonical_records']=canonical(result['stdout'])
        negatives={}
        for mode in('excluded','throw'):
            failure=subprocess.run([str(exe),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
            assert failure.returncode!=0 and 'signal nanosleep:'in failure.stderr and ('outside admitted'in failure.stderr if mode=='excluded'else'unknown exception'in failure.stderr),(failure.returncode,failure.stderr)
            negatives[mode]={'exit_code':failure.returncode,'stdout':failure.stdout,'stderr':failure.stderr};(out/(platform+'-'+mode+'.json')).write_text(json.dumps(negatives[mode],indent=2)+'\n')
        result['negatives']=negatives;platforms[platform]=result;(out/'progress.json').write_text(json.dumps(platforms,indent=2)+'\n')
    for name,h in support.items():assert sha(source/name)==h,name
    for name,h in owned.items():assert sha(HERE.parent/name)==h,name
    for name,h in protected.items():assert sha(HERE.parent/name)==h,name
    for path,h in inputs.items():assert sha(path)==h,path
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    stage={'passed_host_tests':True,'commit':BASE,'owned_sources':owned,'support_sources':support,'protected_27_source_sha256':protected,'inputs':inputs,'platforms':platforms,'manifests':manifests,'original_caller_audit':{'path':str(caller),'sha256':sha(caller)},'scope':'Actual Windows/Linux host tests only; native reference comparison pending'}
    stage['evidence']={str(path.relative_to(out)):sha(path)for path in out.rglob('*')if path.is_file()and path.name not in('acceptance.json','progress.json','host-stage.json')}
    (out/'host-stage.json').write_text(json.dumps(stage,indent=2)+'\n')
    if a.host_only:print('NANOSLEEP-HOST-STAGE-PASS '+sha(out/'host-stage.json'),flush=True);return
    seal(out,a)


def seal(out,a):
    assert a.arm_reference and a.arm_reference_sha and a.native_reference and a.native_reference_sha
    arm_path=a.arm_reference.resolve();native_path=a.native_reference.resolve()
    assert sha(arm_path)==a.arm_reference_sha and sha(native_path)==a.native_reference_sha
    arm=json.loads(arm_path.read_text());native=json.loads(native_path.read_text());assert arm['passed']is native['passed']is True
    arm_records=canonical(arm['stdout'],24);native_records=canonical(native['stdout'],30)
    assert arm['canonical_records']==arm_records and native['canonical_records']==native_records
    for name in FIXTURES:assert sha(HERE/name)==arm['source_hashes'][name],name
    for name in('nanosleep_guest.c','nanosleep_ref.c','nanosleep_native_wrappers.c'):
        assert sha(HERE/name)==native['source_hashes'][name],name
    for reference in(arm,native):
        for path,h in reference['evidence'].items():assert sha(path)==h,path
    stage=json.loads((out/'host-stage.json').read_text());assert stage['passed_host_tests']is True and stage['commit']==BASE
    owned=stage['owned_sources'];support=stage['support_sources'];protected=stage['protected_27_source_sha256'];inputs=stage['inputs'];platforms=stage['platforms'];manifests=stage['manifests'];caller=Path(stage['original_caller_audit']['path'])
    for name,h in owned.items():assert sha(HERE.parent/name)==h,name
    for name,h in support.items():assert sha(out/'source/recomp'/name)==h,name
    for path,h in inputs.items():assert sha(path)==h,path
    for rel,h in stage['evidence'].items():assert sha(out/rel)==h,rel
    for platform,row in platforms.items():
        all_records=canonical(row['stdout']);assert all_records==native_records
        supported=[line for line in all_records if not line.startswith('record fault ')and not(line.startswith('record interrupt ')and'kind=3 'in line)]
        assert supported==arm_records and len(supported)==24
    inputs=inputs|{str(arm_path):a.arm_reference_sha,str(native_path):a.native_reference_sha}
    receipt={'passed':True,'commit':BASE,'owned_sources':owned,'support_sources':support,'protected_27_source_sha256':protected,'ARM_reference':{'path':str(arm_path),'sha256':a.arm_reference_sha,'records':24},'native_Linux_reference':{'path':str(native_path),'sha256':a.native_reference_sha,'records':30},'original_caller_audit':{'path':str(caller),'sha256':sha(caller)},'inputs':inputs,'platforms':platforms,'manifests':manifests,'actual_NDK_direct_indirect_Bionic_ARM24_and_native_Linux30_records_match':True,'fixed_active_monotonic_deadline_with_signed_ktime_saturation':True,'bounded_relative_wait_chunks_preserve_fixed_budget':True,'immutable_unaligned_timespec64_request_snapshot':True,'faultsafe_EFAULT_EINVAL_and_remainder_alias_controls':True,'remainder_copy_before_actual_handler_including_delay':True,'EINTR_despite_SA_RESTART_and_remainder_EFAULT_does_not_swallow_handler':True,'excluded_pending_and_siginfo_retained_before_consume':True,'no_old_usleep_signal_runtime_or_collector_core_changes':True,'limits':['New provider/component only; no original game execution or frame proof','QEMU8.2.2 ignores request/rem copy errors and mutates rem onEINVAL: ARM oracle excludes6 EFAULTcases and invalid-rem bytes; nativeLinux30 and translated hosts retain actual EFAULTcontrols','Production bootstrap admits zero signals here and no collector checkpoint','Fault-copy scope requires stable memory mapping/protection during each copy; concurrent native VirtualProtect/mprotect races and atomic partial-write equivalence are not qualified','Existing untagged lower48 address profile; tagged-address ABI is explicitly unsupported','TEST-only handler-delay import exists only in the fixture and is never installed in production']}
    receipt['host_stage_sha256']=sha(out/'host-stage.json')
    receipt['evidence']=stage['evidence']|{'host-stage.json':sha(out/'host-stage.json')}
    (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('NANOSLEEP-QUALIFIED '+sha(out/'acceptance.json'),flush=True)

if __name__=='__main__':main()
