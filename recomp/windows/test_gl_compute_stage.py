"""Real ANGLE compute shader objects through NDK callers, plus typed draw regression."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
WORK=Path('/mnt/c/GitRepos/bunker/recomp/work')
BASE='ebeef029afc8e128bae67a3b9e47de457b5c8bb9'
OWN=('gl_host.cpp','gl_draw_guest.c','gl_draw_test.cpp','test_gl_compute_stage.py')

def sha(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()

def command_names(source):
    cpp=(source/'windows/gl_host.cpp').read_text()
    draw=re.search(r'#define GL_DRAW_API\(X\)(.*?)\n// Types',cpp,re.S);assert draw
    draw_names=re.findall(r'X\((gl\w+),',draw[1]);names=['glGetString','glGetStringi','glGetIntegerv','glGetFloatv','glGetBooleanv','glGetError']
    block=cpp[cpp.index('const char *const names[]='):cpp.index('std::string Hex(')]
    for token in re.finditer(r'#include "([^"]+)"|GL_DRAW_API\(DRAW_NAME\)',block):
        if not token[1]:names+=draw_names
        else:
            text=(source/'windows'/token[1]).read_text();entries=re.findall(r'GL_[A-Z0-9_]+\((gl\w+),',text);assert entries,token[1];names+=entries
    assert len(names)==len(set(names))and'glIsVertexArray'in names
    return names

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    archive=subprocess.check_output(['git.exe','-C',wp(HERE.parent.parent),'archive',BASE,'recomp/windows','recomp/whole','recomp/fastaes']);(out/'support.tar').write_bytes(archive)
    source=out/'source';source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive))as bundle:
        assert bundle.pax_headers['comment']==BASE;bundle.extractall(source,filter='data')
    source=source/'recomp';old=(source/'windows/gl_host.cpp').read_bytes();old_names=command_names(source)
    for name in OWN:shutil.copyfile(HERE/name,source/'windows'/name)
    new=(source/'windows/gl_host.cpp').read_bytes();proof_path=WORK/'compute-stage-preparation1/source-proof.json';assert sha(proof_path)=='3797f746c98f7e80ce2e61ba69e66cf0dc2bf5676c7ba2287bcbe03215b7d4ff'
    proof=json.loads(proof_path.read_text());assert proof['passed']is True and proof['base_commit']==BASE
    before=bytes.fromhex(proof['old_line_hex']);after=bytes.fromhex(proof['new_line_hex'])
    assert hashlib.sha256(old).hexdigest()==proof['old_sha256']and hashlib.sha256(new).hexdigest()==proof['new_sha256']
    assert old.count(before)==new.count(after)==1 and new.replace(after,before,1)==old and command_names(source)==old_names
    (out/'gl_draw_old_commands.h').write_text('#pragma once\nstatic const char*const kOldDrawCommands[]={'+','.join(map(json.dumps,old_names))+'};\nstatic constexpr size_t kOldObjectIndex='+str(old_names.index('glIsVertexArray'))+';\n')
    owned={'windows/'+name:sha(source/'windows'/name)for name in OWN};sources={str(path.relative_to(source)):sha(path)for path in source.rglob('*')if path.is_file()}
    parent=json.loads((WORK/'windows-first-frame-nanosleep1/game_inputs.json').read_text());protected=parent['collector_delivery_qualification']['protected_implementation_source_sha256'];assert len(protected)==27
    for name,h in protected.items():assert sources[name]==sha(HERE.parent/name)==h,name
    tool=WORK/'faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');angle=WORK/'angle-native';dlls=angle/'bundle/bin'
    inputs={str(path):sha(path)for path in(proof_path,ndk.resolve(),tool/'remill-lift',tool/'aarch64.bc',Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'),Path(shutil.which('clang++-18')).resolve())}
    for folder in(tool/'include',angle/'src/include',dlls):
        for path in folder.rglob('*'):
            if path.is_file():inputs[str(path)]=sha(path)
    commands=[]
    def run(command,label):
        command=list(map(str,command));commands.append(command);print('STAGE '+label,flush=True)
        with(out/(label+'.log')).open('w')as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        text=(out/(label+'.log')).read_text(errors='replace')
        if result.returncode:
            (out/'failure.json').write_text(json.dumps({'passed':False,'stage':label,'exit_code':result.returncode},indent=2)+'\n');raise RuntimeError(label+'\n'+text[-5000:])
        return text
    library=out/'draw.so';run([ndk,'-Wall','-Wextra','-Werror','-shared','-nostdlib','-fPIC','-O1','-fno-stack-protector','-fno-builtin',source/'windows/gl_draw_guest.c','-o',library],'NDK-build')
    guest=out/'guest';run([sys.executable,source/'whole/compile.py',library,'--out',guest,'--lift',tool/'remill-lift','--semantics-dir',tool,'--cxx','clang++-18','--base','0x5b000000','--target','x86_64-w64-windows-gnu'],'NDK-translate')
    manifest=json.loads((guest/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets']
    cc='/mnt/c/mingw64/bin/gcc.exe';cxx='/mnt/c/mingw64/bin/g++.exe';loader=out/'elfload.o';run([cc,'-O2','-c',wp(source/'fastaes/elfload.c'),'-o',wp(loader)],'loader')
    flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(tool/'include'),'-I'+wp(guest),'-I'+wp(out),'-I'+wp(angle/'src/include'),f'-DGL_DRAW_LIBRARY="{wp(library)}"',f'-DGL_DRAW_DLL_DIRECTORY=L"{wp(dlls)}"'];objects=[loader]
    for rel in('windows/gl_draw_test.cpp','windows/gl_host.cpp','windows/egl_host.cpp','windows/native_window.cpp','windows/jni_host.cpp','whole/runtime.cpp'):
        obj=out/(Path(rel).stem+'.o');strict=['-Wall','-Wextra','-Werror']if Path(rel).stem in('gl_draw_test','gl_host')else[]
        run([cxx,*flags,*strict,'-c',wp(source/rel),'-o',wp(obj)],Path(rel).stem);objects.append(obj)
    binary=out/'test.exe';run([cxx,'-static',*map(wp,objects),*map(wp,manifest['objects']),'-pthread','-latomic','-luser32','-lgdi32','-lole32','-luuid','-o',wp(binary)],'link')
    stdout=run([binary],'real-ANGLE-test');assert'GL compute stage: 3 NDK create paths and compile/link/query;'in stdout and'GL typed draw:'in stdout and'checks passed'in stdout
    for name,h in sources.items():assert sha(source/name)==h,name
    for name,h in owned.items():assert sha(HERE.parent/name)==h,name
    for path,h in inputs.items():assert sha(path)==h,path
    for name,h in protected.items():assert sha(HERE.parent/name)==h,name
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    receipt={'passed':True,'scope':'Actual Windows ANGLE/Vulkan ES3.1+ shader creation/compile/link/query and existing typed vertex/fragment triangle fixture; no compute dispatch or original game execution','commit':BASE,'owned_sources':owned,'source_sha256':sources,'protected_27_source_sha256':protected,'source_proof':{'path':str(proof_path),'sha256':sha(proof_path)},'inputs':inputs,'binary_sha256':sha(binary),'stdout':stdout,'checks':int(re.search(r'GL typed draw: (\d+) checks passed',stdout)[1]),'NDK':{'library_sha256':sha(library),'manifest_sha256':sha(guest/'manifest.json'),'heads':len(manifest['traces']),'objects':len(manifest['objects']),'unsupported':manifest['unsupported_traces'],'unresolved':manifest['unresolved_direct_targets']},'real_ANGLE_ES31_compute_stage_objects':True,'actual_NDK_direct_pointer_procedure_GLuint32_GLenum32':True,'source_compile_attach_link_use_type_status_and_workgroup_query':True,'invalid_stage_delegates_real_backend_error':True,'existing_vertex_fragment_triangle_and_shader_error_regressions':True,'complete_parent_command_namespace_and_markers_unchanged':True,'production_one_binding_change_only':True,'compute_dispatch_or_execution_implemented':False,'original_game_executed':False,'limits':'Backend shader objects/program pipeline only. No compute workload or memory/image/storage dispatch semantics. Existing host readback and capture behavior unchanged.'}
    receipt['evidence']={str(path.relative_to(out)):sha(path)for path in out.rglob('*')if path.is_file()and path.name!='acceptance.json'}
    (out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('GL-COMPUTE-STAGE-QUALIFIED '+sha(out/'acceptance.json'),flush=True)

if __name__=='__main__':main()
