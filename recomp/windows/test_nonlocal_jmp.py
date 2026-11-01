"""Android 13 Bionic setjmp wire context: original-assembly QEMU and NDK gates."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import urllib.request
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'whole'))
from test_fastaes import build_reference
SOURCE='https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/arch-arm64/bionic/setjmp.S?format=TEXT'
SHA='cd0eacde5d3332c6726a0a07ccc0c37f8ac3eb4a5e90f6e3078e9c40875e0309'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--remill',type=Path,required=True)
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--reference-only',action='store_true')
    a=p.parse_args();out=HERE.parent/('work/nonlocal-windows'if a.windows else'work/nonlocal-linux');out.mkdir(parents=True,exist_ok=True)
    source=out/'android13-setjmp.S'
    if not source.exists():source.write_bytes(base64.b64decode(urllib.request.urlopen(SOURCE).read()))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SHA
    private=out/'reference-include/private';private.mkdir(parents=True,exist_ok=True)
    (private/'bionic_asm.h').write_text(
        '#define ENTRY(n) .global n; .type n,%function; n:; .cfi_startproc\n'
        '#define END(n) .cfi_endproc; .size n,.-n\n'
        '#define ALIAS_SYMBOL(a,b) .global a; .set a,b\n'
        '#define __BIONIC_WEAK_ASM_FOR_NATIVE_BRIDGE(n)\n'
        '#define NOTE_GNU_PROPERTY()\n')
    (private/'bionic_constants.h').write_text('#define SCS_SIZE 8192\n')
    names=['setjmp','_setjmp','sigsetjmp','longjmp','_longjmp','siglongjmp']
    defines=[name+'=reference_'+name for name in names]+['sigprocmask=reference_mask','NONLOCAL_REFERENCE_JUMP']
    reference=out/'reference'
    build_reference('clang-18',a.reference_root,[HERE/'nonlocal_jmp_ref.c',HERE/'nonlocal_jmp_guest.S',source],reference,
                    [out/'reference-include'],defines)
    raw=subprocess.check_output([str(a.reference_root/'usr/bin/qemu-aarch64-static'),'-cpu','cortex-a53',str(reference)],timeout=20)
    assert len(raw)==512*8 and not any(struct.unpack('<512Q',raw))
    (out/'reference.bin').write_bytes(raw)
    (out/'reference-lineage.json').write_text(json.dumps({'source':SOURCE,'sha256':SHA,
      'profile':'cortex-a53 PAC-disabled; original assembler body; minimal ENTRY/END and SCS_SIZE scaffolding',
      'cookie':'deterministic reference cookie; controlled fixture mask helper',
      'save_records':512,'actual_nonlocal_restore_records':64},indent=2)+'\n')
    print('ARM64 QEMU: 512 original Android13 save contexts and 64 actual nonlocal restores passed.',flush=True)
    if a.reference_only:return
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'caller.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC',str(HERE/'nonlocal_jmp_guest.S'),'-o',str(library)],check=True)
    # Independently check the public NDK declarations, not host setjmp types.
    declarations=out/'sizes.c';declarations.write_text('#include <setjmp.h>\n_Static_assert(sizeof(jmp_buf)==256,"jmp");\n_Static_assert(sizeof(sigjmp_buf)==264,"sigjmp");\n')
    subprocess.run([str(cc),'-c',str(declarations),'-o',str(out/'sizes.o')],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(library),'--out',str(out/'guest'),
                    '--lift',str(a.lift),'--cxx','clang++-18','--base','0x5b000000',
                    '--target','x86_64-w64-windows-gnu'if a.windows else'x86_64-linux-gnu'],check=True)
    manifest=json.loads((out/'guest/manifest.json').read_text());assert not manifest['unsupported_traces']
    def hp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()if a.windows else str(path)
    hostcc='/mnt/c/mingw64/bin/gcc.exe'if a.windows else'clang-18'
    hostcxx='/mnt/c/mingw64/bin/g++.exe'if a.windows else'clang++-18'
    loader=out/'elfload.o';subprocess.run([hostcc,'-O2','-c',hp(HERE.parent/'fastaes/elfload.c'),'-o',hp(loader)],check=True)
    binary=out/('test.exe'if a.windows else'test')
    command=[hostcxx,'-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',f'-I{hp(a.remill/"include")}',f'-I{hp(out/"guest")}',
      f'-DNONLOCAL_LIBRARY="{hp(library)}"',hp(HERE/'nonlocal_jmp_test.cpp'),hp(HERE/'nonlocal_jmp.cpp'),
      hp(HERE.parent/'whole/runtime.cpp'),hp(loader),*[hp(obj)for obj in manifest['objects']],'-pthread','-latomic',
      '-o',hp(binary)]
    if a.windows:command[1:1]=['-static'];command+=['-lbcrypt']
    subprocess.run(command,check=True)
    run=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=20)
    print(run.stdout,end='',flush=True)
    if run.stderr:print(run.stderr,file=sys.stderr,end='')
    failures=[]
    for arg,message in [('--fatal-longjmp',b'controlled nonlocal transfer is unimplemented'),
                        ('--fatal-corrupt',b'checksum mismatch'),('--fatal-flag',b'unexpected signal flag bits')]:
        result=subprocess.run([str(binary),arg],capture_output=True,timeout=10)
        assert result.returncode==3 and message in result.stderr,(result.returncode,result.stderr)
        failures.append({'argument':arg,'exit_code':result.returncode,'diagnostic':result.stderr.decode()})
    sources=['nonlocal_jmp.h','nonlocal_jmp.cpp','nonlocal_jmp_checks.h','nonlocal_jmp_guest.S',
             'nonlocal_jmp_ref.c','nonlocal_jmp_test.cpp','test_nonlocal_jmp.py']
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps({
      'platform':'native Windows x86_64'if a.windows else'Linux x86_64',
      'native_output':run.stdout,'fatal_gates':failures,
      'source_sha256':{name:digest(HERE/name)for name in sources},
      'reference_source_sha256':SHA,'qemu_save_records':512,'qemu_nonlocal_restore_records':64,
      'ndk_manifest_sha256':digest(out/'guest/manifest.json'),'native_executable_sha256':digest(binary),
      'longjmp_control_transfer_implemented':False},indent=2)+'\n')
    print('Fatal-path gates: unsupported transfer, checksum corruption and invalid sigflag all exit3.',flush=True)

if __name__=='__main__':main()
