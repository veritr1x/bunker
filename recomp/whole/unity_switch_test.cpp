#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include "unity_switch_cases.h"
#include "component_entries.h"
static unsigned current_head,current_seed,calls,checks;static us_registers observed;
static void check(bool ok,const char*why){++checks;if(!ok)throw std::runtime_error(why);}
static void getregs(const State&s,us_registers*r,addr_t pc){
 std::memset(r,0,sizeof(*r));for(unsigned n=0;n<32;n++)std::memcpy(&r->x[n],reinterpret_cast<const unsigned char*>(&s.gpr)+n*16+8,8);
 r->nzcv=uint64_t(s.sr.n)<<31|uint64_t(s.sr.z)<<30|uint64_t(s.sr.c)<<29|uint64_t(s.sr.v)<<28;std::memcpy(r->v,s.simd.v,512);r->pc=pc;
}
extern "C" Memory*UnitySwitchImport(State&s,addr_t pc,Memory*m){
 check(pc==us_observer(current_head)&&s.gpr.pc.qword==pc,"only the expected genuine outgoing call boundary is permitted");check(++calls==1,"exactly one fixture boundary");getregs(s,&observed,pc);
 // Explicit fixture-owned return to this Run's root; the normal guest-transfer
 // guards retire lifted frames. No production jump implementation is altered.
 s.gpr.pc.qword=US_RETURN;return m;
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Memory*)==8);void*p=VirtualAlloc(reinterpret_cast<void*>(US_BASE),US_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);check(p==reinterpret_cast<void*>(US_BASE),"fixed fixture memory");
 void*table_allocation=VirtualAlloc(reinterpret_cast<void*>(0x70e70000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);check(table_allocation==reinterpret_cast<void*>(0x70e70000),"original table fixture allocation");void*tables=reinterpret_cast<void*>(0x70e7a000);
 void*global=VirtualAlloc(reinterpret_cast<void*>(0x71230000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);check(global==reinterpret_cast<void*>(0x71230000),"controlled fixture global allocation");us_u32(0x7123eb40,0x12345678);
 // These are the authentic original read-only words, not reconstructed tables.
 check(argc==3,"original table and owned corpus arguments");FILE*f=std::fopen(argv[1],"rb");check(f!=nullptr,"original table input");check(std::fread(tables,1,4096,f)==4096,"full original table page");check(std::fgetc(f)==EOF,"table input exact size");std::fclose(f);FILE*corpus=std::fopen(argv[2],"wb");check(corpus!=nullptr,"create Windows byte-exact memory corpus");
 recomp::Runtime runtime;runtime.AddTraces(bunker::unity_701078_switch_entries::kAddedTraces,std::size(bunker::unity_701078_switch_entries::kAddedTraces));for(auto pc:us_heads)check(runtime.HasGuestTrace(pc),"all12 actual candidate targets selectable");
 for(current_head=0;current_head<12;current_head++)for(current_seed=0;current_seed<32;current_seed++){
  us_registers initial;us_setup(&initial,current_head,current_seed);calls=0;State state;std::memset(&state,0x5a,sizeof(state));std::memset(&state.sr,0,sizeof(state.sr));state.nzcv.flat=initial.nzcv;state.fpcr.flat=0;state.fpsr.flat=0;
  for(unsigned n=0;n<32;n++)std::memcpy(reinterpret_cast<unsigned char*>(&state.gpr)+n*16+8,&initial.x[n],8);
  state.gpr.pc.qword=us_heads[current_head];state.sr.n=(initial.nzcv>>31)&1;state.sr.z=(initial.nzcv>>30)&1;state.sr.c=(initial.nzcv>>29)&1;state.sr.v=(initial.nzcv>>28)&1;std::memcpy(state.simd.v,initial.v,512);State before;std::memcpy(&before,&state,sizeof(before));
  std::array<uint64_t,8>token;std::memcpy(token.data(),reinterpret_cast<void*>(US_BASE+0xa000),64);auto*memory=reinterpret_cast<Memory*>(US_BASE+0xa000);
  check(runtime.Run(state,us_heads[current_head],memory)==memory,"actual selected COFF preserves non-null Memory64 identity");check(!std::memcmp(token.data(),reinterpret_cast<void*>(US_BASE+0xa000),64),"opaque Memory64 content preserved");check(calls==1&&observed.pc==us_observer(current_head),"actual target reaches designated outgoing call");check(state.gpr.pc.qword==US_RETURN&&state.gpr.sp.qword==US_SP,"fixture root transfer propagated through original guards");
  check(observed.x[31]==initial.x[31],"interior SP at genuine call matches native boundary");check(!std::memcmp(observed.v,initial.v,sizeof(initial.v)),"all32 SIMD registers preserved by original interior block");
  State permitted=before;std::memcpy(&permitted.gpr,&state.gpr,sizeof(state.gpr));permitted.sr.n=state.sr.n;permitted.sr.z=state.sr.z;permitted.sr.c=state.sr.c;permitted.sr.v=state.sr.v;check(!std::memcmp(&permitted,&state,sizeof(state)),"all unrelated1200 State fields and padding preserved");
  check(us_dump_memory(corpus),"write Windows byte-exact memory corpus");us_print("UNITY-SWITCH",current_head,current_seed,&observed);
 }
 check(!std::fclose(corpus),"close Windows memory corpus");std::printf("UNITY-SWITCH-WINDOWS-PASS checks=%u cases=384 State=1200 Memory64=8 actualCOFF=1\n",checks);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"Unity switch fixture head=%llx seed=%u: %s\n",(unsigned long long)us_heads[current_head],current_seed,e.what());return 91;}}
