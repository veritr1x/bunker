#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include "frinta_function_cases.h"
extern "C" Memory*sub_70828b78(State&,addr_t,Memory*);
static recomp::Runtime*active_runtime;static unsigned calls,shape,checks,case_id;static FFModfRecord record;
static void check(bool ok,const char*why){checks++;if(!ok)throw std::runtime_error(why);}
extern "C" Memory*FRINTAFunctionImport(State&s,addr_t pc,Memory*m){return active_runtime->Dispatch(s,pc,m);}
static void put(State&s,unsigned reg,uint64_t value){std::memcpy(reinterpret_cast<unsigned char*>(&s.gpr)+reg*16+8,&value,8);}
static uint64_t get(const State&s,unsigned reg){uint64_t value;std::memcpy(&value,reinterpret_cast<const unsigned char*>(&s.gpr)+reg*16+8,8);return value;}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,3);try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Memory*)==8);check(argc==2,"owned Windows corpus argument");check(VirtualAlloc(reinterpret_cast<void*>(FF_BASE),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==reinterpret_cast<void*>(FF_BASE),"owned fixture outputs");FILE*corpus=std::fopen(argv[1],"wb");check(corpus!=nullptr,"owned Windows corpus");recomp::Runtime runtime;active_runtime=&runtime;const recomp::Trace trace[]={{0x70828b78,sub_70828b78}};runtime.AddTraces(trace,std::size(trace));runtime.AddImport(0x700b8f40,[](State&s){calls++;shape+=s.gpr.x0.qword==FF_INTEGRAL;float input,fraction,integral;std::memcpy(&input,&s.simd.v[0],4);std::memcpy(&record.input,&input,4);recomp::ReadGuestMemory(&record.before,s.gpr.x0.qword,4);fraction=std::modf(input,&integral);std::memcpy(&record.fraction,&fraction,4);std::memcpy(&record.integral,&integral,4);recomp::WriteGuestMemory(s.gpr.x0.qword,&integral,4);std::memset(&s.simd.v[0],0,16);std::memcpy(&s.simd.v[0],&fraction,4);});
 alignas(16)std::array<unsigned char,65536>stack{};
 for(case_id=0;case_id<384;case_id++){
  FFCase sample;ff_setup(&sample,case_id);unsigned char before[64];std::memcpy(before,reinterpret_cast<void*>(FF_BASE),64);calls=shape=0;std::memset(&record,0,sizeof(record));State state;std::memset(&state,0x5a,sizeof(state));std::memset(&state.sr,0,sizeof(state.sr));state.nzcv.flat=0;state.fpcr.flat=0;state.fpsr.flat=0;for(unsigned n=0;n<31;n++)put(state,n,UINT64_C(0xabcdef0000000000)+n);for(unsigned n=0;n<11;n++)put(state,n+19,sample.before.gpr[n]);for(unsigned n=0;n<32;n++){uint64_t vector[2]={UINT64_C(0x123456789abcdef0)^n,UINT64_C(0xfedcba9876543210)^n};std::memcpy(&state.simd.v[n],vector,16);}for(unsigned n=0;n<8;n++)std::memcpy(&state.simd.v[n+8],&sample.before.d[n],8);for(unsigned n=0;n<6;n++){std::memset(&state.simd.v[n],0,16);std::memcpy(&state.simd.v[n],&sample.s[n],4);}state.gpr.x0.qword=sample.flags0;state.gpr.x1.qword=FF_LEFT;state.gpr.x2.qword=FF_INTEGRAL;state.gpr.x3.qword=sample.flags3;state.gpr.x30.qword=0x6f00fffc;state.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());state.gpr.pc.qword=0x70828b78;State initial;std::memcpy(&initial,&state,sizeof(state));std::array<uint64_t,8>memory={1,3,7,15,31,63,127,255};auto saved=memory;auto*token=reinterpret_cast<Memory*>(memory.data());
  check(runtime.Run(state,0x70828b78,token)==token&&memory==saved,"actual selected object preserves nonnull Memory64 identity/content");check(calls==1&&shape==1,"one real-shape tracked float modff bridge");check(state.gpr.sp.qword==initial.gpr.sp.qword&&state.gpr.x30.qword==0x6f00fffc&&state.gpr.pc.qword==0x6f00fffc,"original112B frame normal SP/LR/PC return");for(unsigned n=0;n<11;n++)check(get(state,n+19)==sample.before.gpr[n],"all11 original callee-save GPR restored");for(unsigned n=0;n<8;n++){uint64_t d;std::memcpy(&d,&state.simd.v[n+8],8);check(d==sample.before.d[n],"all8 original callee-save D preserved");}
  auto fpsr=state.fpsr;fpsr.ioc=state.sr.ioc;fpsr.dzc=state.sr.dzc;fpsr.ofc=state.sr.ofc;fpsr.ufc=state.sr.ufc;fpsr.ixc=state.sr.ixc;fpsr.idc=state.sr.idc;sample.after.fpsr=uint32_t(fpsr.flat);sample.after.nzcv=uint64_t(state.sr.n)<<31|uint64_t(state.sr.z)<<30|uint64_t(state.sr.c)<<29|uint64_t(state.sr.v)<<28;std::memcpy(&sample.after.result,&state.simd.v[0],4);check(sample.after.fpsr==0&&state.fpcr.flat==0,"whole binary-exact function has no new exceptions/IXC");check(ff_guards(before),"only original two output floats changed");
  State permitted=initial;for(unsigned n=0;n<33;n++)put(permitted,n,get(state,n));for(unsigned n=0;n<15;n++)std::memcpy(&permitted.simd.v[n],&state.simd.v[n],16);permitted.sr.n=state.sr.n;permitted.sr.z=state.sr.z;permitted.sr.c=state.sr.c;permitted.sr.v=state.sr.v;check(!std::memcmp(&permitted,&state,sizeof(state)),"unrelatedState, padding, higherSIMD and FP controls preserved");check(std::fwrite(reinterpret_cast<void*>(FF_BASE),1,64,corpus)==64,"Windows data corpus write");ff_print(&sample,calls,shape,&record);
 }
 check(!std::fclose(corpus),"Windows corpus close");std::printf("FRINTA-FUNCTION-WINDOWS-PASS checks=%u cases=384 State=1200 Memory64=8\n",checks);return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FRINTA original Windows case%u: %s\n",case_id,e.what());return 91;}}
