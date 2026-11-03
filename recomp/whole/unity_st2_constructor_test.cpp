#include "runtime.h"
#include "bridge.h"
#include <string>
#include "provider_memory.h"
#include "unity_st2_constructor_fixture.h"
extern "C" Memory*sub_707520c4(State&,addr_t,Memory*);
static recomp::Runtime*active_runtime;
static unsigned long polls,memset_calls;
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r)die("unexpected request");return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
// Test import adaptation, with the identical production Fill/typed bridge memory effect.
// Exceptions terminate here; none may unwind through compiled guest LLVM.
extern "C" Memory*sub_700b8440(State&s,addr_t,Memory*m){
 try{if(s.gpr.x0.qword!=port_seeds[0]+8||s.gpr.x1.dword!=0||s.gpr.x2.qword!=0x68)die("actual memset argument tuple");++memset_calls;return active_runtime->Dispatch(s,0x7f020000,m);}catch(...){die("real memset import failed");}return nullptr;
}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
int main(int argc,char**argv){
 if(argc!=5){die("arguments: polled global literals case");}int polled=atoi(argv[1]);uint64_t global;uint8_t literals[24];load_file(&global,8,argv[2]);load_file(literals,24,argv[3]);setup((unsigned)strtoul(argv[4],0,10),OBJECT_CAPTURE,global,literals);protect(global_page,65536,0);
 State s{};for(size_t i=0;i<sizeof(s);++i)((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=OBJECT_HEAD;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];unsigned nzcv=flag_id*5;s.sr.n=nzcv>>3&1;s.sr.z=nzcv>>2&1;s.sr.c=nzcv>>1&1;s.sr.v=nzcv&1;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=flag_id&1;port_saved_x18=port_seeds[18];port_saved_tls=s.sr.tpidr_el0.qword;
 recomp::Runtime rt;active_runtime=&rt;const recomp::Trace trace{OBJECT_HEAD,sub_707520c4};rt.AddTraces(&trace,1);
 rt.AddImport(0x7f020000,recomp::MakeBridge<void*(void*,int32_t,uint64_t)>([](void*p,int32_t v,uint64_t n){return bunker::windows::provider_memory::Fill(p,v,n);}));
 Memory*m=reinterpret_cast<Memory*>(UINT64_C(0x1234567887654320));if(rt.Run(s,OBJECT_HEAD,m)!=m||memset_calls!=1||s.gpr.pc.qword!=OBJECT_CAPTURE)die("true return/memory token/one real memset");
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i)put64(snapshot+i*8,gpr(s,i));memcpy(snapshot+256,&s.simd,512);put64(snapshot+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));put64(snapshot+776,s.fpsr.flat);put64(snapshot+784,s.fpcr.flat);put64(snapshot+792,s.sr.tpidr_el0.qword);emit(snapshot,0,polls,polled);
}
