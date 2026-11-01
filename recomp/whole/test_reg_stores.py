"""Compare scalar SIMD STR register-offset forms against actual ARM64 execution.

Separate from the main semantic suite: generated all-register/mode matrix,
complete128-byte output buffers, outer guards, raw NaN/subnormal bit patterns,
source preservation and truthful aligned SP scratch frames.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import reg_store_cases
from test_fastaes import build_reference

HERE=Path(__file__).resolve().parent
RUNNER=r'''#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef void (*semantic_call)(const char*,uint8_t*,const uint8_t*,uint64_t);
static int run_semantic_cases(semantic_call call){
  static const uint64_t bits64[]={0,0x8000000000000000ULL,1,0x8000000000000001ULL,
    0x7ff0000000000000ULL,0xfff0000000000000ULL,0x7ff8123456789abcULL,0x7ff0000000000001ULL,
    0xfff0000000000001ULL,0x3ff0000000000000ULL,0x0123456789abcdefULL,0xfedcba9876543210ULL,
    0x0010000000000000ULL,0x000fffffffffffffULL,0x7fefffffffffffffULL,0xffffffffffffffffULL};
  static const uint32_t bits32[]={0,0x80000000U,1,0x80000001U,0x7f800000U,0xff800000U,
    0x7fc12345U,0x7f800001U,0xff800001U,0x3f800000U,0x89abcdefU,0xfedcba98U,
    0x00800000U,0x007fffffU,0x7f7fffffU,0xffffffffU};
  static const uint16_t bits16[]={0,0x8000,1,0x8001,0x7c00,0xfc00,0x7e55,0x7c01,
    0xfc01,0x3c00,0x0123,0xfedc,0x0400,0x03ff,0x7bff,0xffff};
  uint8_t input_space[160],output_space[160];
  for(unsigned test=0;test<sizeof(case_names)/sizeof(case_names[0]);++test){
    for(unsigned seed=0;seed<32;++seed){
      uint8_t *input=input_space+seed%16,*output=output_space+(seed*7)%16;
      for(unsigned i=0;i<128;++i)input[i]=(seed*37+i*19)&255;
      unsigned pattern=seed%16;
      if(strstr(case_names[test],"strreg_d_"))memcpy(input,bits64+pattern,8);
      else if(strstr(case_names[test],"strreg_s_"))memcpy(input,bits32+pattern,4);
      else if(strstr(case_names[test],"strreg_h_"))memcpy(input,bits16+pattern,2);
      memset(output_space,0xab,sizeof(output_space));
      call(case_names[test],output,input,seed);
      for(uint8_t *p=output_space;p<output;++p)if(*p!=0xab)return 1;
      for(uint8_t *p=output+128;p<output_space+sizeof(output_space);++p)if(*p!=0xab)return 2;
      printf("%s %u ",case_names[test],seed);
      for(unsigned i=0;i<128;++i)printf("%02x",output[i]);putchar('\n');
    }
  }return 0;
}
'''

def generate(out):
    cases=reg_store_cases.generate();lines=['.text']
    for name,code in cases.items():
        lines += [f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc']
        lines += ['  '+line for line in code]+['.cfi_endproc',f'.size {name},.-{name}']
    source=out/'reg-stores.S';source.write_text('\n'.join(lines)+'\n')
    (out/'generated_cases.h').write_text(''.join(f'CASE({name})\n' for name in cases))
    (out/'reg_store_runner.h').write_text(RUNNER)
    for source_name,target_name in [('semantic_ref.c','reg_store_ref.c'),('semantic_test.cpp','reg_store_test.cpp')]:
        (out/target_name).write_text((HERE/source_name).read_text().replace('"semantic_cases.h"','"reg_store_runner.h"'))
    return source,len(cases)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lift',type=Path)
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--remill',type=Path,default=HERE.parent/'work/remill-src')
    p.add_argument('--out',type=Path)
    p.add_argument('--cc',default='clang-18');p.add_argument('--cxx',default='clang++-18')
    p.add_argument('--windows',action='store_true');p.add_argument('--mingw',type=Path,default=Path('/mnt/c/mingw64/bin'))
    p.add_argument('--assemble-only',action='store_true')
    a=p.parse_args();out=a.out or HERE.parent/('work/windows-reg-stores' if a.windows else 'work/whole-reg-stores');out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    source,count=generate(out);library=out/'reg-stores.so'
    subprocess.run([a.cc,'--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',str(source),'-o',str(library)],check=True)
    print(f'{count} generated store/register variants assemble successfully.',flush=True)
    if a.assemble_only:return
    if not a.lift:p.error('--lift required unless --assemble-only')
    subprocess.run([sys.executable,str(HERE/'compile.py'),str(library),'--out',str(out),'--base','0x30000000','--lift',str(a.lift),'--cxx',a.cxx,
                    '--target','x86_64-w64-windows-gnu' if a.windows else 'x86_64-linux-gnu','--jobs','2'],check=True)
    m=json.loads((out/'manifest.json').read_text())
    def host(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip() if a.windows else str(path)
    cc=str(a.mingw/'gcc.exe') if a.windows else a.cc;cxx=str(a.mingw/'g++.exe') if a.windows else a.cxx
    loader=out/'elfload.o';subprocess.run([cc,'-O2','-c',host(HERE.parent/'fastaes/elfload.c'),'-o',host(loader)],check=True)
    binary=out/('recomp.exe' if a.windows else 'recomp')
    command=[cxx,'-O2','-std=c++17','-DADDRESS_SIZE_BITS=64',f'-DSEMANTIC_LIB="{host(library)}"',f'-I{host(a.remill/"include")}',
             f'-I{host(HERE)}',f'-I{host(HERE.parent/"fastaes")}',f'-I{host(out)}',host(out/'reg_store_test.cpp'),host(HERE/'runtime.cpp'),host(loader),
             *[host(o) for o in m['objects']],'-latomic','-o',host(binary)]
    if a.windows:command.insert(1,'-static')
    subprocess.run(command,check=True)
    reference=out/'reference';build_reference(a.cc,a.reference_root,[out/'reg_store_ref.c',source],reference,[HERE,out])
    with (out/'recomp.txt').open('w') as log:subprocess.run([str(binary)],stdout=log,check=True)
    with (out/'ref.txt').open('w') as log:subprocess.run([str(a.reference_root/'usr/bin/qemu-aarch64-static'),str(reference)],stdout=log,check=True)
    expected=(out/'ref.txt').read_text().splitlines();actual=(out/'recomp.txt').read_text().splitlines()
    if len(expected)!=count*32 or len(actual)!=len(expected):raise RuntimeError('Wrong reference/lifted case count')
    failures=[(x,y) for x,y in zip(expected,actual) if x!=y]
    if failures:
        for x,y in failures[:5]:print('ARM64:',x,'\nx86:  ',y)
        raise SystemExit(f'{len(failures)} register-offset store cases differ')
    print(f'{len(expected):,} register-offset scalar SIMD stores match ARM64 QEMU ({count} variants; {"native Windows" if a.windows else "Linux"}).')
if __name__=='__main__':main()
