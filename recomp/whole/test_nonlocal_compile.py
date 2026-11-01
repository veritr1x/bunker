"""Compiler defaults, opt-out, rebasing, manifest and fail-closed root guards."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
from unittest.mock import patch
from elftools.elf.elffile import ELFFile
import nonlocal_roots
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk',type=Path,required=True)
    a=p.parse_args();out=HERE.parent/'work/nonlocal-compile';out.mkdir(parents=True,exist_ok=True)
    cc=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    library=out/'fixture.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-Wl,--no-relax,--strip-all',
                    str(HERE/'nonlocal_roots_fixture.S'),'-o',str(library)],check=True)
    spec=importlib.util.spec_from_file_location('nonlocal_compiler_guards',HERE/'compile.py')
    compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
    checks=0
    def check(condition,why):
        nonlocal checks
        if not condition:raise AssertionError(why)
        checks+=1
    base=0x5c000000
    _,_,enabled,manifest=compiler.inspect(library,base)
    roots=manifest['nonlocal_roots'];relative=set(roots['entries']);rebased={base+e for e in relative}
    check(roots['enabled']and len(relative)==3,'default recovery evidence')
    check(rebased<=set(enabled),'entries rebased once into compiler seeds')
    _,_,disabled,without=compiler.inspect(library,base,recover_nonlocals=False)
    check(without['nonlocal_roots']==dict(enabled=False,entries=[],continuations=[],unresolved=[]),'disabled evidence explicit and empty')
    check(set(enabled)-set(disabled)==rebased and rebased.isdisjoint(disabled),'only continuation entries differ')
    _,_,zero,zero_manifest=compiler.inspect(library,0)
    check(relative<=set(zero)and zero_manifest['nonlocal_roots']['entries']==roots['entries'],'manifest proofs stay ELF-relative')
    with patch.object(nonlocal_roots,'recover',side_effect=AssertionError('disabled recovery executed')):
        _,_,_,skip=compiler.inspect(library,base,recover_nonlocals=False)
        check(not skip['nonlocal_roots']['enabled'],'disabled option never invokes analyzer')
    def bad_entry(path,address,why):
        report=dict(entries=[address],continuations=[],unresolved=[])
        with patch.object(nonlocal_roots,'recover',return_value=report):
            try:compiler.inspect(path,base)
            except ValueError as error:check('Nonlocal recovery returned'in str(error),why)
            else:raise AssertionError(why)
    bad_entry(library,min(relative)+1,'unaligned recovered entry rejected')
    bad_entry(library,0,'nonexecutable recovered entry rejected')
    raw=bytearray(library.read_bytes());elf=ELFFile(io.BytesIO(raw))
    text=elf.get_section_by_name('.text');end=text['sh_addr']+text['sh_size']
    section_index=elf.get_section_index('.text')
    struct.pack_into('<Q',raw,elf['e_shoff']+section_index*elf['e_shentsize']+32,text['sh_size']-2)
    truncated=out/'truncated-section.so';truncated.write_bytes(raw)
    bad_entry(truncated,end-4,'aligned but incomplete executable instruction rejected')
    for target in ('x86_64-linux-gnu','x86_64-w64-windows-gnu'):
        for callbacks in (True,False):
            for nonlocals in (True,False):
                destination=out/f'{target}-{int(callbacks)}-{int(nonlocals)}'
                command=[sys.executable,str(HERE/'compile.py'),str(library),'--out',str(destination),
                         '--lift',str(out/'unused-missing-lifter'),'--target',target,'--base',hex(base),'--plan-only']
                if not callbacks:command.append('--no-callback-recovery')
                if not nonlocals:command.append('--no-nonlocal-roots')
                subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
                plan=json.loads((destination/'plan.json').read_text())
                check(plan['nonlocal_roots']['enabled']==nonlocals,'CLI root flag retained in plan')
                check(plan['callback_roots']['enabled']==callbacks,'existing callback flag independent')
                check(plan['nonlocal_roots']['entries']==(roots['entries']if nonlocals else[]),'CLI proof entries retained')
                check((rebased<=set(plan['seed_entries']))if nonlocals else rebased.isdisjoint(plan['seed_entries']),'CLI rebased seeds match mode')
                check(not(destination/'.toolchain').exists(),'plan-only does not require or copy a lifter')
    indirect=out/'indirect.so'
    subprocess.run([str(cc),'-shared','-nostdlib','-fPIC','-Wl,--no-relax,--strip-all','-DNONLOCAL_INDIRECT',
                    str(HERE/'nonlocal_roots_fixture.S'),'-o',str(indirect)],check=True)
    _,_,_,indirect_manifest=compiler.inspect(indirect,base)
    rejected=indirect_manifest['nonlocal_roots']
    check(not rejected['entries']and len(rejected['unresolved'])==1,'unresolved indirect calls retained in manifest')
    check(rejected['unresolved'][0]['api']is None,'unknown indirect calls are not labeled setjmp')
    directory=out/'indirect-plan'
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(indirect),'--out',str(directory),
                    '--lift',str(out/'unused-missing-lifter'),'--base',hex(base),'--target',
                    'x86_64-w64-windows-gnu','--plan-only'],check=True,stdout=subprocess.DEVNULL)
    indirect_plan=json.loads((directory/'plan.json').read_text())
    check(indirect_plan['nonlocal_roots']['unresolved']==rejected['unresolved'],'JSON plan preserves unresolved evidence')
    (out/'result.json').write_text(json.dumps(dict(checks=checks,roots=roots,
      flags=['--no-callback-recovery','--no-nonlocal-roots'],native_transfer_implemented=False),indent=2)+'\n')
    print(f'Nonlocal compiler integration: {checks} plan/manifest/rebasing/guard/CLI checks pass.')


if __name__=='__main__':main()
