#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include "unity_117d_cases.h"
#include "component_entries.h"
extern "C" Memory*sub_70117c5c(State&,addr_t,Memory*);
extern "C" Memory*sub_701172fc(State&,addr_t,Memory*);
extern "C" Memory*sub_70117d1c(State&,addr_t,Memory*);
extern "C" Memory*sub_70117d24(State&,addr_t,Memory*);
extern "C" Memory*sub_70117d34(State&,addr_t,Memory*);
extern "C" Memory*sub_70117d3c(State&,addr_t,Memory*);
static u17_case*active;static unsigned checks;
static void check(bool ok,const char*why){++checks;if(!ok)throw std::runtime_error(why);}
static void put(State&s,unsigned n,uint64_t v){std::memcpy(reinterpret_cast<unsigned char*>(&s.gpr)+n*16+8,&v,8);}
static uint64_t get(const State&s,unsigned n){uint64_t v;std::memcpy(&v,reinterpret_cast<const unsigned char*>(&s.gpr)+n*16+8,8);return v;}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Memory*)==8);check(argc==3,"original tables/corpus arguments");check(VirtualAlloc(reinterpret_cast<void*>(U17_BASE),U17_ARENA,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(U17_BASE),"fixture data/stack arena");check(VirtualAlloc(reinterpret_cast<void*>(0x70e70000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(0x70e70000),"original table page reservation");
 FILE*tables=std::fopen(argv[1],"rb");check(tables&&std::fread(reinterpret_cast<void*>(0x70e7a000),1,4096,tables)==4096,"byte-exact original table page");check(std::fgetc(tables)==EOF,"original table size");std::fclose(tables);FILE*corpus=std::fopen(argv[2],"wb");check(corpus!=nullptr,"owned Windows corpus");
 recomp::Runtime runtime;const recomp::Trace retained[]={{0x70117c5c,sub_70117c5c},{0x701172fc,sub_701172fc},{0x70117d1c,sub_70117d1c},{0x70117d24,sub_70117d24},{0x70117d34,sub_70117d34},{0x70117d3c,sub_70117d3c}};runtime.AddTraces(retained,std::size(retained));runtime.AddTraces(bunker::unity_70117d_switch_entries::kAddedTraces,std::size(bunker::unity_70117d_switch_entries::kAddedTraces));
 runtime.AddImport(U17_CALLBACK,[](State&s){++active->calls;active->shape+=s.gpr.x0.qword==U17_OBJECT;s.gpr.x0.qword=active->ready;});
 std::array<unsigned char,U17_DATA>before{};
 for(unsigned id=0;id<88;id++){
  u17_case sample;u17_setup(&sample,id);active=&sample;std::memcpy(before.data(),reinterpret_cast<void*>(U17_BASE),U17_DATA);State state;std::memset(&state,0x5a,sizeof(state));std::memset(&state.sr,0,sizeof(state.sr));state.nzcv.flat=0;state.fpcr.flat=0;state.fpsr.flat=0;for(unsigned n=0;n<31;n++)put(state,n,UINT64_C(0x1234567800000000)+n);for(unsigned n=0;n<11;n++)put(state,n+19,sample.before.gpr[n]);for(unsigned n=0;n<32;n++){uint64_t vector[2]={UINT64_C(0x0123456789abcdef)^n,UINT64_C(0xfedcba9876543210)^n};std::memcpy(&state.simd.v[n],vector,16);}for(unsigned n=0;n<8;n++)std::memcpy(&state.simd.v[n+8],&sample.before.d[n],8);
  state.gpr.x0.qword=U17_OBJECT;state.gpr.x1.qword=sample.index;state.gpr.x2.qword=sample.type;state.gpr.x3.qword=U17_OUT;state.gpr.x30.qword=U17_RETURN;state.gpr.sp.qword=U17_BASE+0xfff0;state.gpr.pc.qword=0x70117c5c;state.sr.tpidr_el0.qword=U17_BASE+0xa000;State original;std::memcpy(&original,&state,sizeof(state));std::array<uint64_t,8>token{};std::memcpy(token.data(),reinterpret_cast<void*>(U17_BASE+0xb000),64);auto*memory=reinterpret_cast<Memory*>(U17_BASE+0xb000);
  check(runtime.Run(state,0x70117c5c,memory)==memory,"unchanged oldCOFF plus actual new8 preserve Memory64");check(!std::memcmp(token.data(),reinterpret_cast<void*>(U17_BASE+0xb000),64),"opaque Memory64 contents preserved");check(state.gpr.pc.qword==U17_RETURN&&state.gpr.x30.qword==U17_RETURN&&state.gpr.sp.qword==original.gpr.sp.qword,"genuine outer48B epilogue restores SP/LR/PC");
  for(unsigned n=0;n<11;n++)check(get(state,n+19)==sample.before.gpr[n],"original outer/helper restore all11 callee-save GPR");for(unsigned n=0;n<8;n++){uint64_t d;std::memcpy(&d,&state.simd.v[n+8],8);check(d==sample.before.d[n],"original outer/helper preserve all8 callee-save d registers");}
  check(state.gpr.x0.qword==sample.expected&&sample.calls==(sample.ready?2u:1u)&&sample.shape==sample.calls,"real original helper boolean vtable path and result");check(u17_check_memory(before.data(),&sample),"all49152 data bytes/output oracle/guards");
  bool stack_guards=true;for(unsigned n=0;n<4096;n++)stack_guards&=*(reinterpret_cast<unsigned char*>(U17_BASE+0xc000)+n)==(unsigned char)(0xadu^((0xc000+n)*13u+sample.seed*29u));for(unsigned n=0;n<16;n++)stack_guards&=*(reinterpret_cast<unsigned char*>(U17_BASE+0xfff0)+n)==(unsigned char)(0xadu^((0xfff0+n)*13u+sample.seed*29u));check(stack_guards,"lower4KB and upper16B guest-stack guards");
  State permitted=original;for(unsigned n=0;n<32;n++)put(permitted,n,get(state,n));permitted.gpr.pc.qword=state.gpr.pc.qword;std::memcpy(&permitted.simd.v[0],&state.simd.v[0],16);permitted.sr.n=state.sr.n;permitted.sr.z=state.sr.z;permitted.sr.c=state.sr.c;permitted.sr.v=state.sr.v;check(!std::memcmp(&permitted,&state,sizeof(state)),"all unrelatedState bytes/padding, FP flags, TLS and SIMD preserved");
  std::memcpy(sample.after.v0,&state.simd.v[0],16);uint32_t flags=uint32_t(state.sr.n)<<31|uint32_t(state.sr.z)<<30|uint32_t(state.sr.c)<<29|uint32_t(state.sr.v)<<28;u17_print(&sample,state.gpr.x0.qword,flags);check(std::fwrite(reinterpret_cast<void*>(U17_BASE),1,U17_DATA,corpus)==U17_DATA,"Windows corpus write");
 }
 check(!std::fclose(corpus),"Windows corpus close");std::printf("UNITY-117D-WINDOWS-PASS checks=%u cases=88 success=64 failure=24 State=1200 Memory64=8 oldAndNewCOFF=1\n",checks);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"Unity117d Windows case%u: %s\n",active?active->id:999,e.what());return 91;}}
