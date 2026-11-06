#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include "numeric_minmax_cluster_cases.h"
extern "C" Memory*sub_841e55d0(State&,addr_t,Memory*);
static NMCRegisters observed;static unsigned checks,boundaries,case_id;
static void check(bool ok,const char*why){checks++;if(!ok)throw std::runtime_error(why);}
static void put(State&s,unsigned reg,uint64_t value){memcpy(reinterpret_cast<unsigned char*>(&s.gpr)+reg*16+8,&value,8);}
extern "C" Memory*sub_841e55f0(State&s,addr_t pc,Memory*m){
 check(pc==NMC_STOP&&s.gpr.pc.qword==NMC_STOP,"true original fallthrough reached beforeFMUL");check(++boundaries==1,"exactly one fixture boundary");memset(&observed,0,sizeof(observed));for(unsigned n=0;n<32;n++)memcpy(&observed.x[n],reinterpret_cast<const unsigned char*>(&s.gpr)+n*16+8,8);memcpy(observed.v,s.simd.v,512);observed.nzcv=uint64_t(s.sr.n)<<31|uint64_t(s.sr.z)<<30|uint64_t(s.sr.c)<<29|uint64_t(s.sr.v)<<28;auto fpsr=s.fpsr;fpsr.ioc=s.sr.ioc;fpsr.dzc=s.sr.dzc;fpsr.ofc=s.sr.ofc;fpsr.ufc=s.sr.ufc;fpsr.ixc=s.sr.ixc;fpsr.idc=s.sr.idc;observed.fpsr=fpsr.flat;observed.fpcr=s.fpcr.flat;observed.pc=pc;
 // Stop the isolated test fragment at its genuine fallthrough. No guest RET
 // instruction or full original function return is synthesized or claimed.
 s.gpr.pc.qword=NMC_RETURN;return m;
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Memory*)==8&&sizeof(NMCRegisters)==808);check(argc==2,"owned Windows snapshot filename");check(VirtualAlloc(reinterpret_cast<void*>(NMC_BASE),NMC_ARENA,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(NMC_BASE),"owned controlled input/stack/read arena");FILE*file=std::fopen(argv[1],"wb");check(file!=nullptr,"owned Windows snapshot corpus");recomp::Runtime runtime;const recomp::Trace trace[]={{NMC_ENTRY,sub_841e55d0}};runtime.AddTraces(trace,std::size(trace));static unsigned char before[NMC_ARENA];
 for(unsigned mode=0;mode<16;mode++)for(unsigned sticky=0;sticky<2;sticky++)for(unsigned pair=0;pair<32;pair++){
  case_id=(mode*2+sticky)*32+pair;NMCRegisters input;nmc_setup(&input,pair,mode,sticky);NMCRegisters expected=nmc_expected(&input);memcpy(before,reinterpret_cast<void*>(NMC_BASE),NMC_ARENA);State state;memset(&state,0x5a,sizeof(state));for(unsigned n=0;n<32;n++)put(state,n,input.x[n]);state.gpr.pc.qword=NMC_ENTRY;memcpy(state.simd.v,input.v,512);state.nzcv.flat=input.nzcv;state.fpcr.flat=input.fpcr;state.fpsr.flat=input.fpsr;state.sr.n=input.nzcv>>31&1;state.sr.z=input.nzcv>>30&1;state.sr.c=input.nzcv>>29&1;state.sr.v=input.nzcv>>28&1;state.sr.ioc=input.fpsr&1;state.sr.dzc=input.fpsr>>1&1;state.sr.ofc=input.fpsr>>2&1;state.sr.ufc=input.fpsr>>3&1;state.sr.ixc=input.fpsr>>4&1;state.sr.idc=input.fpsr>>7&1;state.sr.tpidr_el0.qword=0x123456789abcdef0;state.sr.tpidrro_el0.qword=0xfedcba9876543210;State initial;memcpy(&initial,&state,sizeof(state));boundaries=0;auto*memory=reinterpret_cast<Memory*>(NMC_BASE+0xa000);
  check(runtime.Run(state,NMC_ENTRY,memory)==memory,"original fragment preserves nonnull Memory64 identity");check(boundaries==1&&!memcmp(&observed,&expected,sizeof(expected)),"all808B real GPR/SIMD/FP snapshot equals oracle");check(nmc_guards(before),"all source/load/opaque-memory arena bytes outside fixture collector unchanged");check(state.gpr.pc.qword==NMC_RETURN,"fixture boundary stopped without executingFMUL");
  State permitted=initial;permitted.gpr.pc.qword=NMC_RETURN;for(unsigned n:{0u,1u,2u,3u,6u,7u})memcpy(&permitted.simd.v[n],&state.simd.v[n],16);permitted.sr.ioc=state.sr.ioc;permitted.sr.idc=state.sr.idc;check(!memcmp(&permitted,&state,sizeof(state)),"all unrelated1200State bytes/padding/NZCV/TLS/Memory preserved");check(std::fwrite(&observed,1,sizeof(observed),file)==sizeof(observed),"Windows complete snapshot write");nmc_print(pair,mode,sticky,&observed);
 }
 check(!std::fclose(file),"Windows corpus close");std::printf("NUMERIC-CLUSTER-WINDOWS-PASS checks=%u cases=1024 State=1200 Memory64=8 exact_fallthrough=841e55f0\n",checks);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"Numeric cluster Windows case%u: %s\n",case_id,e.what());return 91;}}
