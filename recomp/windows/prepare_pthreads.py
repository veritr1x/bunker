"""Verify actual NDK pthread wire layouts and translate Android ARM64 callers."""
import argparse
import json
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile

HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--lift',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE.parent/'work/windows-pthreads')
    p.add_argument('--cxx',default='clang++-18')
    p.add_argument('--lib-dir',type=Path,help='Record and verify actual game pthread import coverage')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    labels=['mutex_size','cond_size','attr_size','mutexattr_size','condattr_size','thread_size','key_size','once_size','rw_size',
            'attr_stack_base','attr_stack_size','attr_guard','attr_sched_policy','normal','recursive','errorcheck','stack_min','keys_max','destructor_rounds','monotonic','detached','boottime']
    source=out/'ndk_pthread_layout.c'
    source.write_text('#include <pthread.h>\n#include <limits.h>\n#include <stdint.h>\n#include <stddef.h>\n'
        'const uint64_t ndk_layout[]={sizeof(pthread_mutex_t),sizeof(pthread_cond_t),sizeof(pthread_attr_t),sizeof(pthread_mutexattr_t),sizeof(pthread_condattr_t),sizeof(pthread_t),sizeof(pthread_key_t),sizeof(pthread_once_t),sizeof(pthread_rwlock_t),'
        'offsetof(pthread_attr_t,stack_base),offsetof(pthread_attr_t,stack_size),offsetof(pthread_attr_t,guard_size),offsetof(pthread_attr_t,sched_policy),'
        'PTHREAD_MUTEX_NORMAL,PTHREAD_MUTEX_RECURSIVE,PTHREAD_MUTEX_ERRORCHECK,PTHREAD_STACK_MIN,PTHREAD_KEYS_MAX,PTHREAD_DESTRUCTOR_ITERATIONS,CLOCK_MONOTONIC,PTHREAD_CREATE_DETACHED,CLOCK_BOOTTIME};\n'
        'const pthread_mutex_t recursive_initializer=PTHREAD_RECURSIVE_MUTEX_INITIALIZER_NP;\n'
        'const pthread_mutex_t errorcheck_initializer=PTHREAD_ERRORCHECK_MUTEX_INITIALIZER_NP;\n'
        'const pthread_cond_t monotonic_initializer=PTHREAD_COND_INITIALIZER_MONOTONIC_NP;\n')
    obj=out/'ndk_pthread_layout.o';subprocess.run([str(cc),'-c',str(source),'-o',str(obj)],check=True)
    with obj.open('rb') as f:
        elf=ELFFile(f)
        def value(name):
            s=elf.get_section_by_name('.symtab').get_symbol_by_name(name)[0]
            return elf.get_section(s['st_shndx']).data()[s['st_value']:s['st_value']+s['st_size']]
        values=struct.unpack('<'+'Q'*len(labels),value('ndk_layout'))
        layout=dict(zip(labels,values))
        for name,expected in [('recursive_initializer',0x4000),('errorcheck_initializer',0x8000),('monotonic_initializer',2)]:
            word=struct.unpack_from('<I',value(name))[0];layout[name]=word
            if word!=expected:raise RuntimeError(f'Unexpected NDK initializer {name}={word}')
    expected=[40,48,56,8,8,8,4,4,56,8,16,24,32,0,1,2,16384,128,4,1,1,7]
    if list(values)!=expected:raise RuntimeError(f'NDK pthread layout mismatch: {layout}')
    (out/'ndk_pthread_layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    if a.lib_dir:
        imported={}
        for path in sorted(a.lib_dir.glob('*.so')):
            with path.open('rb') as f:
                elf=ELFFile(f);syms=elf.get_section_by_name('.dynsym')
                imported[path.name]=sorted({s.name for s in syms.iter_symbols() if s['st_shndx']=='SHN_UNDEF' and s.name.startswith('pthread_')}) if syms else []
        supported=set(re.findall(r'"(pthread_[a-z_]+)"',(HERE/'pthread_host.cpp').read_text()))
        missing=sorted(set().union(*map(set,imported.values()))-supported)
        if missing:raise RuntimeError(f'Unaccounted real pthread imports: {missing}')
        (out/'game_pthread_imports.json').write_text(json.dumps(imported,indent=2)+'\n')
        print(f'All {len(set().union(*map(set,imported.values())))} distinct game pthread imports are implemented or explicitly unsupported.')
    guest=out/'pthread-guest.so'
    subprocess.run([str(cc),'-shared','-fPIC','-nostdlib','-O1','-fno-stack-protector','-D_FORTIFY_SOURCE=0',str(HERE/'pthread_guest_fixture.c'),'-o',str(guest)],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'whole/compile.py'),str(guest),'--out',str(out/'guest'),'--lift',str(a.lift),'--base','0x70000000','--target','x86_64-w64-windows-gnu','--cxx',a.cxx],check=True)
    shutil.copyfile(out/'guest/traces.h',out/'pthread_traces.h')
    print('Verified NDK ARM64 layouts, static initializers, limits; translated actual pthread callers.')
if __name__=='__main__':main()
