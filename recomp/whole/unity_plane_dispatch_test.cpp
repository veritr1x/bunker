#include "runtime.h"
#include "unity_plane_dispatch_fixture.h"
#include "plane_dispatch_traces.h"
static unsigned long polls;static int polled;
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r){die("unexpected poll request");}return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
int main(int argc,char**argv){if(argc!=4){die("host arguments");}polled=atoi(argv[1]);setup((unsigned)strtoul(argv[3],0,10),argv[2]);State s{};for(size_t i=0;i<sizeof(s);++i){((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);}for(unsigned i=0;i<31;++i){memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);}s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=DISPATCH_HEAD;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];s.sr.n=case_id>>3&1;s.sr.z=case_id>>2&1;s.sr.c=case_id>>1&1;s.sr.v=case_id&1;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=case_id&1;State initial=s;
 recomp::Runtime rt;rt.AddTraces(kPlaneDispatchTraces,sizeof(kPlaneDispatchTraces)/sizeof(kPlaneDispatchTraces[0]));alignas(16)uint8_t token[64];memset(token,0x6d,64);Memory*m=reinterpret_cast<Memory*>(token);if(rt.Run(s,DISPATCH_HEAD,m)!=m||s.gpr.pc.qword!=FIXTURE_RETURN){die("genuine return PC/token");}for(auto v:token){if(v!=0x6d){die("opaque token bytes");}}for(unsigned i=0;i<32;++i){if(memcmp((uint8_t*)&s.gpr.x0+i*16+8,(uint8_t*)&initial.gpr.x0+i*16+8,8)){die("GPR high-cell preservation");}}
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i){put64(snapshot+i*8,gpr(s,i));}memcpy(snapshot+256,&s.simd,512);put64(snapshot+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));put64(snapshot+784,s.fpcr.flat);emit(snapshot,0,polls,polled);}
