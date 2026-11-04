#include "runtime.h"
#include "unity_st3_block_fixture.h"
extern "C" Memory*sub_704fd850(State&,addr_t,Memory*);
struct PrefixCaptured{};
static State captured,initial;
static Memory*captured_token;
static unsigned long polls;
static int polled;
extern "C" Memory*sub_704fedc8(State&s,addr_t pc,Memory*m){if(pc!=BLOCK_STOP)die("actual helper entry PC");captured=s;captured_token=m;throw PrefixCaptured{};}
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r)die("unexpected poll request");return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
int main(int argc,char**argv){if(argc!=4)die("host arguments");polled=atoi(argv[1]);setup((unsigned)strtoul(argv[3],0,10),argv[2]);State s{};for(size_t i=0;i<sizeof(s);++i)((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=BLOCK_HEAD;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];unsigned flags=(case_id&3)*5;s.sr.n=flags>>3&1;s.sr.z=flags>>2&1;s.sr.c=flags>>1&1;s.sr.v=flags&1;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=(case_id>>2)&1;port_saved_x18=port_seeds[18];port_saved_tls=s.sr.tpidr_el0.qword;initial=s;
 recomp::Runtime rt;const recomp::Trace trace{BLOCK_HEAD,sub_704fd850};rt.AddTraces(&trace,1);Memory*m=reinterpret_cast<Memory*>(UINT64_C(0x1234567887654320));bool stopped=false;try{rt.Run(s,BLOCK_HEAD,m);}catch(const PrefixCaptured&){stopped=true;}if(!stopped||captured_token!=m||captured.gpr.pc.qword!=BLOCK_STOP)die("exact real-helper capture and token");s=captured;
 // Full architectural800 bytes are compared with native ARM. Padding/high GPR
 // cells and TLS backing outside those architectural fields must stay exact.
 for(unsigned i=0;i<32;++i)if(memcmp((const uint8_t*)&s.gpr.x0+i*16+8,(const uint8_t*)&initial.gpr.x0+i*16+8,8))die("GPR high-cell preservation");
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i)put64(snapshot+i*8,gpr(s,i));memcpy(snapshot+256,&s.simd,512);put64(snapshot+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));auto fpsr=s.fpsr;fpsr.ixc=s.sr.ixc;fpsr.ofc=s.sr.ofc;fpsr.ufc=s.sr.ufc;fpsr.idc=s.sr.idc;fpsr.ioc=s.sr.ioc;fpsr.dzc=s.sr.dzc;put64(snapshot+776,fpsr.flat);put64(snapshot+784,s.fpcr.flat);put64(snapshot+792,s.sr.tpidr_el0.qword);emit(snapshot,0,polls,polled);}
