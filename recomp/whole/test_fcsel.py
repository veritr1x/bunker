"""Opaque-bit FCSEL reference matrix and exact old float-bits dereference regression."""
import argparse, hashlib, importlib.util, io, json, shutil, struct, subprocess, sys, tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('test_fcsel.py','test_fcsel_decode.py','fcsel_test.cpp','fcsel_ref.c','fcsel_native_wrapper.S','fcsel.md')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

RECORDS=r'''
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct{const char*name;unsigned width,rd,rn,rm,cond,original;} FCSELCase;
static const FCSELCase cases[]={
#define CASE(name,w,d,n,m,c,o) {#name,w,d,n,m,c,o},
#include "fcsel_cases.h"
#undef CASE
};
#define CASE_COUNT ((unsigned)(sizeof(cases)/sizeof(cases[0])))
static uint64_t get64(const uint8_t*p){uint64_t v;memcpy(&v,p,8);return v;}
static void put64(uint8_t*p,uint64_t v){memcpy(p,&v,8);}
static uint64_t scalar(const uint8_t*p,unsigned width){return width==32?(uint32_t)get64(p):get64(p);}
static int condition(unsigned c,uint64_t flags){unsigned n=flags>>31&1,z=flags>>30&1,carry=flags>>29&1,v=flags>>28&1;int result=1;if(c>=14)return 1;switch(c>>1){case 0:result=z;break;case 1:result=carry;break;case 2:result=n;break;case 3:result=v;break;case 4:result=carry&&!z;break;case 5:result=n==v;break;case 6:result=!z&&n==v;break;}return(c&1)?!result:result;}
static int run_fcsel_records(void(*call)(unsigned,uint8_t*,const uint8_t*)){
 static const uint64_t f32[]={0,0x80000000,1,0x00800000,0x007fffff,0x3f800000,0xbf800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc12345,0xffc54321,0x7f812345,0xff854321,0x00000002,0x3f000000};
 static const uint64_t f64[]={0,UINT64_C(0x8000000000000000),1,UINT64_C(0x0010000000000000),UINT64_C(0x000fffffffffffff),UINT64_C(0x3ff0000000000000),UINT64_C(0xbff0000000000000),UINT64_C(0x7fefffffffffffff),UINT64_C(0x7ff0000000000000),UINT64_C(0xfff0000000000000),UINT64_C(0x7ff8123456789abc),UINT64_C(0xfff8abcdef123456),UINT64_C(0x7ff0123456789abc),UINT64_C(0xfff0123456789abc),UINT64_C(0x000000003f800000),UINT64_C(0x3fe0000000000000)};
 unsigned count=0;
 for(unsigned test=0;test<CASE_COUNT;++test)for(unsigned seed=0;seed<256;++seed){
  const FCSELCase*c=&cases[test];unsigned pattern=seed&15,flags=seed>>4;
  uint8_t input[768] __attribute__((aligned(16))),output_space[1664] __attribute__((aligned(16))),expected[800],original[768];uint8_t*out=output_space+32;
  memset(input,0x73,sizeof(input));memset(output_space,0xab,sizeof(output_space));uint64_t random=UINT64_C(0x9e3779b97f4a7c15)^seed;
  for(unsigned n=0;n<92;++n){random^=random<<13;random^=random>>7;random^=random<<17;put64(input+n*8,random);}
  const uint64_t*edge=c->width==32?f32:f64;uint64_t a=edge[pattern],b=edge[(pattern+7)&15];
  if(c->width==32){memcpy(input+224+c->rn*16,&a,4);memcpy(input+224+c->rm*16,&b,4);}else{put64(input+224+c->rn*16,a);put64(input+224+c->rm*16,b);}
  if(c->original==1)put64(input+144,pattern&1);
  put64(input+736,(uint64_t)flags<<28);put64(input+744,(pattern&1)?UINT64_C(0x0800001f):0);put64(input+752,((uint64_t)(pattern&3)<<22)|((uint64_t)(pattern&12)<<22));
  memcpy(original,input,sizeof(input));call(test,out,input);
  if(memcmp(original,input,sizeof(input)))return 20;
  for(unsigned n=0;n<sizeof(output_space);++n)if((n<32||n>=1632)&&output_space[n]!=0xab)return 21;
  if(get64(out)!=(uintptr_t)out||get64(out+8)!=(uintptr_t)input||!get64(out+240)||get64(out+248)%16)return 22;
  for(unsigned reg=2;reg<30;++reg)if(reg!=18&&get64(out+reg*8)!=get64(input+(reg-2)*8))return 23;
  if(memcmp(out+256,input+224,512)||get64(out+768)!=get64(input+736)||get64(out+776)!=get64(input+744)||get64(out+784)!=get64(input+752))return 24;
  memcpy(expected,out,800);uint64_t selected;
  if(c->original==1){unsigned bit=(unsigned)get64(out+160)&1;selected=bit?0:0x3f800000;memset(expected+256+16,0,16);put64(expected+768,bit?0:0x40000000);}
  else selected=scalar(out+256+(c->original==2?c->rn:condition(c->cond,get64(out+768))?c->rn:c->rm)*16,c->width);
  memset(expected+256+c->rd*16,0,16);put64(expected+256+c->rd*16,selected);
  if(memcmp(expected,out+800,800)){fprintf(stderr,"FCSEL bit/state mismatch case=%s seed=%u\n",c->name,seed);return 25;}
  put64(expected,0);put64(expected+8,0);put64(expected+18*8,0);put64(expected+30*8,0);put64(expected+31*8,0);
  uint64_t hash=UINT64_C(1469598103934665603);for(unsigned n=0;n<800;++n){hash^=expected[n];hash*=UINT64_C(1099511628211);}
  printf("RECORD %s %u %016llx %016llx\n",c->name,seed,(unsigned long long)selected,(unsigned long long)hash);++count;
 }
 printf("FCSEL-RECORDS-SUCCESS %u\n",count);return 0;
}
'''

def generate(out,baseline):
 cases=[]
 if not baseline:
  for width in(32,64):
   for cond in range(16):
    for rd,rn,rm in((0,1,2),(1,1,2),(2,1,2),(7,7,7),(31,16,31),(8,15,8),(15,8,15)):
     word=(0x1e200c00 if width==32 else 0x1e600c00)|(rm<<16)|(cond<<12)|(rn<<5)|rd
     cases.append((f'fcsel_{width}_{cond}_{rd}_{rn}_{rm}',width,rd,rn,rm,cond,0,[word]))
 cases.append(('original_sequence',32,0,1,0,1,1,[0x7200029f,0x1e2e1000,0x1e2703e1,0x1e201c20]))
 if not baseline:
  cases.extend([('unchanged_fmov_s',32,0,1,0,14,2,[0x1e204020]),('unchanged_fmov_d',64,0,1,0,14,2,[0x1e604020])])
 lines=['.text']
 def function(name,body):lines.extend([f'.global {name}',f'.type {name},%function',f'{name}:','.cfi_startproc',*['  '+x for x in body],'.cfi_endproc',f'.size {name},.-{name}'])
 def snapshot(offset):
  b=[f'str x{r},[x0,#{offset+r*8}]'for r in range(31)]+[f'str q{r},[x0,#{offset+256+r*16}]'for r in range(32)]
  b+=['mov x2,sp',f'str x2,[x0,#{offset+248}]','cset x2,mi','lsl x2,x2,#31','cset x3,eq','orr x2,x2,x3,lsl#30','cset x3,cs','orr x2,x2,x3,lsl#29','cset x3,vs','orr x2,x2,x3,lsl#28',f'str x2,[x0,#{offset+768}]']
  for register,pos in(('fpsr',776),('fpcr',784)):b+=[f'mrs x2,{register}',f'str x2,[x0,#{offset+pos}]']
  return b+[f'ldr x2,[x0,#{offset+16}]',f'ldr x3,[x0,#{offset+24}]']
 for name,w,d,n,m,c,kind,words in cases:
  body=['sub sp,sp,#240']+[f'stp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['str x30,[sp,#96]']+[f'str q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]
  for register,pos in(('fpsr',744),('fpcr',752)):body+=[f'ldr x2,[x1,#{pos}]',f'msr {register},x2']
  body +=[f'ldr q{r},[x1,#{224+r*16}]'for r in range(32)]+[f'ldr x{r},[x1,#{(r-2)*8}]'for r in range(2,30)if r!=18]
  body+=snapshot(0)+[f'.inst 0x{x:08x}'for x in words]+snapshot(800)
  body+=[f'ldr q{r},[sp,#{112+(r-8)*16}]'for r in range(8,16)]+[f'ldp x{r},x{r+1},[sp,#{(r-18)*8}]'for r in range(18,30,2)]+['ldr x30,[sp,#96]','add sp,sp,#240','ret']
  function(name,body);function('raw_'+name,[*[f'.inst 0x{x:08x}'for x in words],'ret'])
 function('fcsel_control_copy',['ldr s0,[x0]','str s0,[x1]','ret'])
 (out/'fcsel.S').write_text('\n'.join(lines)+'\n');(out/'fcsel_cases.h').write_text(''.join(f'CASE({n},{w},{d},{rn},{rm},{c},{o})\n'for n,w,d,rn,rm,c,o,_ in cases));(out/'fcsel_records.h').write_text(RECORDS);(out/'case-oracle.json').write_text(json.dumps(cases,indent=2)+'\n');return cases

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in('out','toolchain','reference-root'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--support-commit',default='HEAD');p.add_argument('--ndk',type=Path,default=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018'))
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);root=HERE.parent.parent
 commit=subprocess.check_output(['git','rev-parse',a.support_commit],cwd=root,text=True).strip();archive=subprocess.check_output(['git','archive',commit,'recomp/whole','recomp/fastaes'],cwd=root);(out/'support.tar').write_bytes(archive)
 with tarfile.open(fileobj=io.BytesIO(archive))as tar:tar.extractall(out/'host',filter='data')
 source=out/'host/recomp';overlays={}
 for name in OWN:overlays[name]=sha(HERE/name);shutil.copy2(HERE/name,source/'whole'/name)
 pins={str(f):sha(f)for f in source.rglob('*')if f.is_file()};tools={str(f):sha(f)for f in a.toolchain.rglob('*')if f.is_file()}
 result={'passed':False,'qualification':'positive functional matrix','support_commit':commit,'overlays':overlays,'support_archive_sha256':sha(out/'support.tar'),'sources':pins,'tools':tools};(out/'source-pin.json').write_text(json.dumps(result,indent=2)+'\n')
 def run(cmd,name,negative=False,timeout=300):
  with(out/name).open('w')as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  if(bool(r.returncode)==negative):return r.returncode
  raise RuntimeError(f'{name}: exit{r.returncode}\n{(out/name).read_text(errors="replace")[-4000:]}')
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 ndk=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang';qemu=a.reference_root/'usr/bin/qemu-aarch64-static'
 external={str(f.resolve()):sha(f.resolve())for f in(ndk,qemu,Path('/usr/bin/clang-18'),Path('/usr/bin/clang++-18'),Path('/mnt/c/mingw64/bin/g++.exe'),Path('/mnt/c/mingw64/bin/gcc.exe'))}
 generated=out/'generated';generated.mkdir();cases=generate(generated,False);obj=out/'ndk-fcsel.o';run([ndk,'-c','-Wall','-Wextra','-Werror',generated/'fcsel.S','-o',obj],'ndk-build.log');library=out/'fcsel.so';run(['clang-18','--target=aarch64-linux-gnu','-fuse-ld=lld','-shared','-nostdlib',obj,'-o',library],'guest-link.log')
 unity=HERE.parent/'work/windows-game16/native/libunity.so';assert sha(unity)=='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
 with unity.open('rb')as stream:
  elf=ELFFile(stream);seg=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=0x43a780<s['p_vaddr']+s['p_filesz']);original=seg.data()[0x43a780-seg['p_vaddr']:0x43a790-seg['p_vaddr']]
 assert original==bytes.fromhex('9f02007200102e1ee103271e201c201e');external[str(unity)]=sha(unity)
 with obj.open('rb')as stream:
  elf=ELFFile(stream);sym=elf.get_section_by_name('.symtab').get_symbol_by_name('raw_original_sequence')[0];data=elf.get_section(sym['st_shndx']).data();assert data[sym['st_value']:sym['st_value']+16]==original
 expected=None
 run([sys.executable,source/'whole/test_fcsel_decode.py','--toolchain',a.toolchain,'--out',out/'decode'],'decode-controller.log')
 wrapper=out/'wrapper.o';run([ndk,'-c',source/'whole/fcsel_native_wrapper.S','-o',wrapper],'wrapper-build.log')
 spec=importlib.util.spec_from_file_location('frozen_reference',source/'whole/test_fastaes.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);reference=out/'reference';helper.build_reference('clang-18',a.reference_root,[source/'whole/fcsel_ref.c',obj,wrapper],reference,[generated]);run([qemu,reference],'arm64-records.log')
 text=(out/'arm64-records.log').read_text();expected=[x for x in text.splitlines()if x.startswith('RECORD ')];assert len(expected)==len(cases)*256 and f'FCSEL-RECORDS-SUCCESS {len(expected)}'in text and 'FCSEL-REFERENCE-SUCCESS'in text;result['reference_sha256']=sha(reference)
 hosts={}
 for windows in(False,True):
  label='windows'if windows else'linux';build=out/label;path=wp if windows else str;run([sys.executable,source/'whole/compile.py',library,'--out',build,'--base','0x38000000','--lift',a.toolchain/'remill-lift','--semantics-dir',a.toolchain,'--target','x86_64-w64-windows-gnu'if windows else'x86_64-linux-gnu','--cxx','clang++-18','--jobs','4'],label+'-compile.log',timeout=900)
  manifest=json.loads((build/'manifest.json').read_text());assert not manifest['unsupported_traces']and not manifest['unresolved_direct_targets'];cc='/mnt/c/mingw64/bin/gcc.exe'if windows else'clang-18';cxx='/mnt/c/mingw64/bin/g++.exe'if windows else'clang++-18';flags=['-O2','-std=c++17','-DADDRESS_SIZE_BITS=64','-isystem',path(a.toolchain/'include'),'-I'+path(source/'whole'),'-I'+path(source/'fastaes'),'-I'+path(generated),'-I'+path(build),f'-DFCSEL_LIB="{path(library)}"'];loader=build/'elfload.o';run([cc,'-O2','-c',path(source/'fastaes/elfload.c'),'-o',path(loader)],label+'-loader.log');objects=[]
  for filename,new in(('whole/runtime.cpp',False),('whole/fcsel_test.cpp',True)):
   target=build/(Path(filename).stem+'.o');run([cxx,*flags,*(['-Wall','-Wextra','-Werror']if new else[]),'-c',path(source/filename),'-o',path(target)],label+'-'+Path(filename).stem+'-build.log');objects.append(target)
  binary=build/('fcsel.exe'if windows else'fcsel');run([cxx,*map(path,objects),path(loader),*map(path,manifest['objects']),'-latomic','-pthread',*(['-static']if windows else[]),'-o',path(binary)],label+'-link.log')
  run([binary],label+'-records.log');text=(out/(label+'-records.log')).read_text();assert[x for x in text.splitlines()if x.startswith('RECORD ')]==expected;assert'FCSEL-HOST-SUCCESS'in text and'FCSEL-ORIGINAL-SEQUENCE-SUCCESS W20=0,1'in text;hosts[label]={'binary_sha256':sha(binary),'records':len(expected),'traces':len(manifest['traces']),'objects':len(manifest['objects'])};print(label+' FCSEL '+str(len(expected))+' actual-bit records PASS',flush=True)
 for name,pin in overlays.items():assert sha(HERE/name)==pin and sha(source/'whole'/name)==pin
 for name,pin in{**pins,**tools,**external}.items():assert sha(name)==pin
 result.update({'passed':True,'hosts':hosts,'cases':len(cases),'records_each':0 if expected is None else len(expected),'ndk_core_sha256':sha(obj),'fixture_sha256':sha(library),'external_inputs':external,'original_sequence_hex':original.hex()});result['evidence']={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and'host'not in f.relative_to(out).parts and f.name!='acceptance.json'};(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('FCSEL-GATE-SUCCESS '+str(out/'acceptance.json'),flush=True)
if __name__=='__main__':main()
