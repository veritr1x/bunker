"""Actual four frame-pacing heads: finite helper-free early exits only."""
from pathlib import Path
import hashlib,json,re,subprocess,traceback
import argparse
A=argparse.ArgumentParser();A.add_argument('--candidate',type=Path,required=True);A.add_argument('--out',type=Path,required=True);args=A.parse_args()
W=Path('/mnt/c/GitRepos/bunker/recomp/work');P=Path(__file__).resolve().parent;O=args.out.resolve()

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def wp(p):return subprocess.check_output(['wslpath','-m',str(p)],text=True).strip()
def save(p,v):assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n')
qpath=args.candidate.resolve();assert sha(qpath)=='731257daf2ac8343b59ef27f62ca11821af3097c1bfe66f09edd992fa169da63';q=json.loads(qpath.read_bytes());r=q['results'][0];assert r['heads']==['0x7022c0d8','0x7022c0ec','0x7022c104','0x7022c158'];O.mkdir(exist_ok=False);commands=[];held={}
def pin(p):held[str(p)]=sha(p)
def run(argv,label):
 argv=list(map(str,argv));commands.append(dict(stage=label,argv=argv));save(O/(label+'-command.json'),commands[-1]);print('STAGE',label,flush=True)
 with(O/(label+'.log')).open('w')as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
 return(O/(label+'.log')).read_text()
common='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const uintptr_t H=0x50000000;
static uint64_t digest(){uint64_t h=1469598103934665603ULL;for(unsigned i=0;i<0x440;i++)h=(h^((unsigned char*)H)[i])*1099511628211ULL;return h;}
static const uintptr_t heads[]={0x7022c0d8,0x7022c0d8,0x7022c0d8,0x7022c0d8,0x7022c0d8,0x7022c0ec,0x7022c0ec,0x7022c0ec,0x7022c0ec,0x7022c0ec,0x7022c104,0x7022c104,0x7022c104,0x7022c104,0x7022c158,0x7022c158,0x7022c158,0x7022c158};
static const unsigned active[]={0,1,2,3,4294967295,0,1,2,3,4294967295,2,3,4,4294967295,0,1,4,4294967295};static const unsigned selectors[]={0,0,0,0,0,2,2,2,2,2,1,1,1,1,3,3,3,3};
static void seed(unsigned p,unsigned a){for(unsigned i=0;i<0x440;i++)((unsigned char*)H)[i]=(unsigned char)(i*37+p*17+11);((unsigned char*)H)[0xc0]=(unsigned char)a;}
static void record(unsigned p,unsigned i,unsigned status){printf("EARLY %u %llx %u %u %016llx\\n",p,(unsigned long long)heads[i],active[i],status,(unsigned long long)digest());}
''';(O/'common.h').write_text(common)
asm='''.text
.global original_case
.type original_case,%function
original_case:
stp x19,x20,[sp,#-16]!
stp x29,x30,[sp,#-16]!
mov x29,sp
sub sp,sp,#0x20
mov x9,#0x2020
str x9,[sp]
mov x9,#0xa5a5
str x9,[sp,#8]
mov x9,#0x1919
str x9,[sp,#0x10]
adr x9,1f
str x9,[sp,#0x18]
mov x19,x0
mov w20,w2
mov w0,w3
br x1
1:
mov x10,#0x1919
cmp x19,x10
cset w9,eq
mov x10,#0x2020
cmp x20,x10
cset w10,eq
and w9,w9,w10
mov x10,sp
cmp x10,x29
cset w10,eq
and w9,w9,w10
ldr x10,[sp,#-0x18]
mov x11,#0xa5a5
cmp x10,x11
cset w10,eq
and w9,w9,w10
adrp x10,abi_ok
str w9,[x10,:lo12:abi_ok]
ldp x29,x30,[sp],#16
ldp x19,x20,[sp],#16
ret
''';(O/'trampoline.S').write_text(asm)
arm='''#include <sys/mman.h>
#include <elf.h>
#include "common.h"
_Thread_local unsigned tls __attribute__((aligned(64)));
volatile unsigned abi_ok;
extern unsigned original_case(uintptr_t,uintptr_t,unsigned,unsigned);
int main(int argc,char**argv){tls=17;if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 3;Elf64_Ehdr h;if(fread(&h,1,sizeof(h),f)!=sizeof(h))return 4;Elf64_Phdr p[32];if(h.e_phnum>32)return 5;fseek(f,h.e_phoff,SEEK_SET);if(fread(p,sizeof(*p),h.e_phnum,f)!=h.e_phnum)return 6;if(mmap((void*)0x70000000,0x3000000,7,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)0x70000000)return 7;for(unsigned i=0;i<h.e_phnum;i++)if(p[i].p_type==PT_LOAD){fseek(f,p[i].p_offset,SEEK_SET);if(fread((void*)(0x70000000+p[i].p_vaddr),1,p[i].p_filesz,f)!=p[i].p_filesz)return 8;}fclose(f);__builtin___clear_cache((char*)0x70000000,(char*)0x73000000);if(mmap((void*)H,0x20000,3,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=(void*)H)return 9;for(unsigned profile=0;profile<2;profile++)for(unsigned i=0;i<18;i++){seed(profile,active[i]);uint64_t before=digest();unsigned result=original_case(H,heads[i],active[i],selectors[i]);if(result!=selectors[i]||!abi_ok||digest()!=before)return 10;record(profile,i,result);}puts("ORIGINAL-EARLY-PASS executions=36 TLS=17");return tls!=17;}
''';(O/'reference.c').write_text(arm)
stub=''.join('extern "C" Memory*sub_'+x[2:]+'(State&,addr_t,Memory*){fputs("UNEXECUTED-ORIGINAL-CALLOUT-SENTINEL\\n",stderr);abort();}\n'for x in r['native_references']);(O/'unexecuted-sentinels.inc').write_text(stub)
entries=''.join('ENTRY('+x[2:]+')\n'for x in r['heads']);(O/'entries.inc').write_text(entries)
native='''#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "common.h"
#define ENTRY(h) extern "C" Memory*sub_##h(State&,addr_t,Memory*);
#include "entries.inc"
#undef ENTRY
#include "unexecuted-sentinels.inc"
static recomp::Trace traces[]={
#define ENTRY(h) {0x##h,sub_##h},
#include "entries.inc"
#undef ENTRY
};static recomp::Trace current;
static Memory*enter(State&s,addr_t,Memory*m){s.gpr.sp.qword-=0x20;return current.entry(s,current.address,m);}
int main(){static_assert(sizeof(State)==1200&&alignof(State)==16,"State");if(VirtualAlloc((void*)H,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)!=(void*)H)return 2;recomp::Runtime r;r.AddTraces(traces,sizeof(traces)/sizeof(*traces));recomp::Trace wrapper{0x60000010,enter};r.AddTraces(&wrapper,1);for(unsigned p=0;p<2;p++)for(unsigned i=0;i<18;i++){seed(p,active[i]);uint64_t before=digest();uintptr_t sp=H+0x10000;memset((void*)sp,0xa5,0x40);uint64_t saved[]={0x2020,0xa5a5,0x1919,0x60000000};memcpy((void*)sp,saved,sizeof(saved));State s{};s.gpr.sp.qword=sp+0x20;s.gpr.x0.qword=selectors[i];s.gpr.x19.qword=H;s.gpr.x20.qword=active[i];s.gpr.x21.qword=0x2121;s.gpr.x22.qword=0x2222;s.gpr.x30.qword=0x60000000;for(auto&t:traces)if(t.address==heads[i])current=t;uint64_t opaque_bytes[8],before_bytes[8];memset(opaque_bytes,0xa7,sizeof(opaque_bytes));memcpy(before_bytes,opaque_bytes,sizeof(opaque_bytes));auto*opaque=reinterpret_cast<Memory*>(opaque_bytes);auto*returned=r.Run(s,0x60000010,opaque);if(returned!=opaque||memcmp(opaque_bytes,before_bytes,sizeof(opaque_bytes))||memcmp((void*)sp,saved,sizeof(saved))||s.gpr.x0.qword!=selectors[i]||s.gpr.pc.qword!=0x60000000||s.gpr.sp.qword!=sp+0x20||s.gpr.x19.qword!=0x1919||s.gpr.x20.qword!=0x2020||s.gpr.x21.qword!=0x2121||s.gpr.x22.qword!=0x2222||digest()!=before)return 3;record(p,i,unsigned(s.gpr.x0.qword));}puts("WINDOWS-EARLY-PASS executions=36 State=1200 Memory64=1 noCalloutsExecuted=1");}
''';(O/'native.cpp').write_text(native)
try:
 elf=W/'windows-first-frame-guest-transfer1/native/libunity.so';ndk=Path('/home/user/bunker-tools/android-sdk/ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang');qemu=Path('/home/user/bunker-recomp/recomp/work/reference-tools/root/usr/bin/qemu-aarch64-static');support=W/'socket-wait-collector-qualification2';cxx=Path('/mnt/c/mingw64/bin/g++.exe')
 for p in [qpath,Path(__file__),elf,ndk,qemu,cxx,support/'runtime.o',support/'cooperative_poll.o',Path(r['object']['path']),Path(r['raw_ir']['path']),*O.glob('*.h'),*O.glob('*.c'),*O.glob('*.cpp'),*O.glob('*.inc'),O/'trampoline.S']:pin(p)
 run([ndk,'-static','-O2','-fno-emulated-tls',O/'reference.c',O/'trampoline.S','-o',O/'Bionic-original'],'compile-original-ARM');original=run([qemu,O/'Bionic-original',elf],'actual-original-ARM');assert 'executions=36'in original
 flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(W/'remill-src/include'),'-I'+wp(support/'source/whole')]
 for label,obj in [('polled',Path(r['object']['path'])),('raw',O/'raw.o')]:
  if label=='raw':run(['clang++-18','-target','x86_64-w64-windows-gnu','-O2','-Wno-override-module','-c',r['raw_ir']['path'],'-o',obj],'compile-raw')
  exe=O/(label+'.exe');run([cxx,*flags,wp(O/'native.cpp'),wp(obj),wp(support/'runtime.o'),wp(support/'cooperative_poll.o'),'-static','-pthread','-latomic','-o',wp(exe)],'link-'+label);text=run([exe],'actual-Windows-'+label);assert 'executions=36'in text
  assert [x for x in original.splitlines()if x.startswith('EARLY ')]==[x for x in text.splitlines()if x.startswith('EARLY ')]
 assert all(sha(p)==value for p,value in held.items())
 result=dict(passed=True,scope='Four original frame-pacing case early exits only: admitted events0/1/2/3/4/UINT32_MAX, two whole object patterns,36 executions per platform.',candidate=desc(qpath),original_ELF=desc(elf),polled_object=desc(Path(r['object']['path'])),platforms=['actual_original_ARM_staticBionic','raw_Windows','exact_polled_Windows'],executions_per_platform=36,records_exact=True,State1200=True,Memory64=True,unexecuted_callouts=dict(abort_only_link_sentinels=len(r['native_references']),executed=0,production_helper_behavior_claim=False),ABI='Actual32byteframe; savedX20/X19/LR, padding, selectorX0, nativeX21/X22, SP/PC and opaqueMemory64 canaries, whole0x440object unchanged.',held_inputs=held,logs={name:desc(O/(name+'.log'))for name in ['actual-original-ARM','actual-Windows-raw','actual-Windows-polled']},commands=commands,limits='Active timing/state-mutating branches unexecuted. No substitute timing/helper callbacks. Runtimeevent/state unlogged; no actual profile inferred. No AndroidART/fullhost/game/process control.')
 save(O/'acceptance.json',result);print('EARLY-QUALIFIED',sha(O/'acceptance.json'))
except BaseException as e:
 save(O/'failure.json',dict(passed=False,error=str(e),traceback=traceback.format_exc(),commands=commands));raise
