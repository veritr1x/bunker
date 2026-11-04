"""Bounded actual NDK void binding and audited UI/UnityMain soft-input FIFO gate."""
import argparse
import concurrent.futures
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
W=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='3ef041dc3e4c858aaa8602e101fcafcfab5f0a31'
OWN=('unity_soft_input.h','unity_soft_input_guest.c','unity_soft_input_test.cpp','test_unity_soft_input.py')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def wp(path):
    return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()


def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    commands=[];pins={};lock=threading.Lock()
    def pin(path,expected=None):
        path=Path(path).resolve();digest=sha(path)
        assert expected is None or digest==expected,str(path)
        pins[str(path)]=digest
        return digest
    def run(label,command):
        command=list(map(str,command))
        with lock:
            commands.append({'label':label,'argv':command});save(out/'commands.json',commands)
        print('STAGE '+label,flush=True)
        with (out/(label+'.log')).open('x') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        text=(out/(label+'.log')).read_text(errors='replace')
        if result.returncode:
            raise RuntimeError(label+' exit='+str(result.returncode)+'\n'+text[-6000:])
        return {'exit_code':result.returncode,'stdout':text}
    try:
        proofpath=W/'jni-bind-void-source-preparation1/source-proof.json'
        proofsha=pin(proofpath,'23dfaea67c82301c4934069200cd60ae123752239f482e4d1c1968309ef0ce40')
        proof=json.loads(proofpath.read_text());assert proof['passed'] is True
        audit=W/'image-uniform1-hide-soft-input-boundary1/summary.json'
        auditsha=pin(audit,'daa5f2b7d713298ca742cabc2dd8f62e7a45e366bdf30cd0cd30db3d82c63cd3')
        assert json.loads(audit.read_text())['passed'] is True
        frame=W/'soft-input-frame-fifo1/acceptance.json'
        framesha=pin(frame,'0586a292d675fd4bd05a05082792d34e3e2ac4673cd84ada73b88f0cf930716e')
        assert json.loads(frame.read_text())['checks']==279
        archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes'])
        (out/'support.tar').write_bytes(archive)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            assert bundle.pax_headers['comment']==BASE
            bundle.extractall(out/'source',filter='data')
        source=out/'source/recomp';win=source/'windows'
        # The guest/provider are frozen before their compilation. The independent
        # harness writer can finish while translation/common compilation runs;
        # its source is frozen once, before its own strict compile/link.
        for name in (*[n for n in OWN if n!='unity_soft_input_test.cpp'],'jni_host.h','jni_host.cpp'):
            shutil.copyfile(HERE/name,win/name)
        jni_sources={'windows/'+n:sha(win/n) for n in ('jni_host.h','jni_host.cpp')}
        assert jni_sources==proof['core_sources']
        tool=W/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4'
        ndkroot=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64')
        ndk=ndkroot/'bin/aarch64-linux-android24-clang'
        cxx='/mnt/c/mingw64/bin/g++.exe';cc='/mnt/c/mingw64/bin/gcc.exe'
        for path in (ndk.resolve(),ndkroot/'sysroot/usr/include/jni.h',tool/'remill-lift',tool/'aarch64.bc',Path(cxx),Path(cc),Path(shutil.which('clang++-18')).resolve()):
            pin(path)
        for path in (tool/'include').rglob('*'):
            if path.is_file():pin(path)
        library=out/'soft-input.so'
        run('NDK-strict-build',[ndk,'-Wall','-Wextra','-Werror','-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',win/'unity_soft_input_guest.c','-o',library])
        pin(library)
        guest=out/'guest';flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include')]
        objects=[out/'elfload.o',out/'jni_host.o',out/'runtime.o']
        jobs=[('elfload',[cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(objects[0])]),
              ('jni-host',[cxx,*flags,'-c',wp(win/'jni_host.cpp'),'-o',wp(objects[1])]),
              ('runtime',[cxx,*flags,'-c',wp(source/'whole/runtime.cpp'),'-o',wp(objects[2])]),
              ('translate',[sys.executable,source/'whole/compile.py',library,'--out',guest,'--base','0x73000000','--lift',tool/'remill-lift','--semantics-dir',tool,'--target','x86_64-w64-windows-gnu','--cxx','clang++-18'])]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(run,label,command) for label,command in jobs]
            for future in futures:future.result()
        manifest=json.loads((guest/'manifest.json').read_text())
        assert not manifest['unsupported_traces'] and not manifest['unresolved_direct_targets']
        deadline=time.monotonic()+180
        while not (HERE/'unity_soft_input_test.cpp').exists():
            if time.monotonic()>deadline:raise RuntimeError('independent harness source was not ready')
            time.sleep(1)
        shutil.copyfile(HERE/'unity_soft_input_test.cpp',win/'unity_soft_input_test.cpp')
        owned={'windows/'+n:sha(win/n) for n in OWN}
        for n in OWN:assert b'\r' not in (win/n).read_bytes(),n
        source_hashes={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
        save(out/'source-hashes.json',source_hashes)
        executable=out/'unity-soft-input.exe'
        resultflags=[*flags,'-I'+wp(guest),'-DSOFT_INPUT_IMAGE="'+wp(library)+'"','-DSOFT_IMAGE="'+wp(library)+'"']
        run('strict-link',[cxx,*resultflags,'-Wall','-Wextra','-Werror',wp(win/'unity_soft_input_test.cpp'),*map(wp,objects),*map(wp,manifest['objects']),'-static','-pthread','-latomic','-o',wp(executable)])
        result=run('functional',[executable])
        assert 'SOFT-INPUT' in result['stdout'] and 'PASS' in result['stdout'],result['stdout']
        count=re.search(r'checks=(\d+)',result['stdout'])
        assert count,result['stdout']
        result.update(checks=int(count[1]),binary_sha256=sha(executable))
        for name,digest in source_hashes.items():assert sha(source/name)==digest,name
        for name,digest in owned.items():assert sha(HERE.parent/name)==digest,name
        for name,digest in jni_sources.items():assert sha(HERE.parent/name)==digest,name
        for path,digest in pins.items():assert sha(path)==digest,path
        receipt={'passed':True,'scope':'Focused Windows actual NDK JNI caller and host queue tests; native report bodies are fixture callbacks, not original game execution.',
                 'base_commit':BASE,'owned_sources':owned,'jni_sources':jni_sources,'source_proof':{'path':str(proofpath),'sha256':proofsha},
                 'DEX_audit':{'path':str(audit),'sha256':auditsha},'frame_fifo_regression':{'path':str(frame),'sha256':framesha,'reused_without_replay':True},
                 'results':{'windows':result},'manifest':{'path':str(guest/'manifest.json'),'sha256':sha(guest/'manifest.json'),'traces':len(manifest['traces']),'unsupported':0,'unresolved':0},
                 'binder_controls':['checked_existing_declaration_missing_static_native_wrong_result_null_duplicate','NDK_direct_V_A_reference_and_jint_owned_callback_frame_cleanup','pending_exception_preservation'],
                 'queue_controls':['always_deferred_UI_post','ordered_area_zero_then_visibility_false','native_loaded_enqueue_gate','sticky_finishing_enqueue_and_execution_gates','actual_attached_UnityMain_FIFOs_and_identity','unsupported_nonnull_dialog_not_silently_dropped'],
                 'inputs':pins,'support_sources':source_hashes,
                 'limits':'Initial null dialog and explicit resolved native-loaded/finishing states only. No general Handler, dialog dismissal, keyboard platform, original native body, game frame or rendering claim.'}
        receipt['evidence']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='acceptance.json'}
        save(out/'acceptance.json',receipt)
        print('UNITY-SOFT-INPUT-QUALIFIED '+sha(out/'acceptance.json'),flush=True)
    except BaseException as error:
        save(out/'failure.json',{'passed':False,'error':str(error),'traceback':traceback.format_exc()})
        raise


if __name__=='__main__':main()
