#include "runtime.h"
#include "yield_fixture.h"
extern "C" Memory*sub_703835a0(State&,addr_t,Memory*);
struct Captured{};
static State captured,initial;static Memory*captured_token;static unsigned long polls;
extern "C" void yield_capture(State*s,addr_t pc,Memory*m){if(pc!=YIELD_STOP){die("original B continuation capture");}captured=*s;captured_token=m;throw Captured{};}
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r){die("unexpected poll request");}return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
int main(int argc,char**argv){
 if(argc!=3){die("host arguments");}const int polled=atoi(argv[1]);setup((unsigned)strtoul(argv[2],0,10));State s{};
 for(size_t i=0;i<sizeof(s);++i){((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);}
 for(unsigned i=0;i<31;++i){memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);}s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=YIELD_START;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);
 s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];s.sr.n=case_id>>3&1;s.sr.z=case_id>>2&1;s.sr.c=case_id>>1&1;s.sr.v=case_id&1;
 s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=(case_id>>2)&1;port_saved_x18=port_seeds[18];port_saved_tls=s.sr.tpidr_el0.qword;initial=s;
 recomp::Runtime rt;const recomp::Trace trace{YIELD_START,sub_703835a0};rt.AddTraces(&trace,1);alignas(16)uint8_t token[64];memset(token,0x6d,64);Memory*m=reinterpret_cast<Memory*>(token);
 bool stopped=false;try{rt.Run(s,YIELD_START,m);}catch(const Captured&){stopped=true;}if(!stopped||captured_token!=m||captured.gpr.pc.qword!=YIELD_STOP){die("actual original continuation/token");}
 for(auto c:token){if(c!=0x6d){die("opaque memory token preserved");}}State want=initial;want.gpr.pc.qword=YIELD_STOP;if(memcmp(&captured,&want,sizeof(want))){die("independent full1200 State preservation including hypercall and monitor fields");}s=captured;
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i){uint64_t v;memcpy(&v,(uint8_t*)&s.gpr.x0+i*16,8);put64(snapshot+i*8,v);}memcpy(snapshot+256,&s.simd,512);
 put64(snapshot+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));auto fpsr=s.fpsr;fpsr.ixc=s.sr.ixc;fpsr.ofc=s.sr.ofc;fpsr.ufc=s.sr.ufc;fpsr.idc=s.sr.idc;fpsr.ioc=s.sr.ioc;fpsr.dzc=s.sr.dzc;put64(snapshot+776,fpsr.flat);put64(snapshot+784,s.fpcr.flat);put64(snapshot+792,s.sr.tpidr_el0.qword);emit(snapshot,0,polls,polled);
}
