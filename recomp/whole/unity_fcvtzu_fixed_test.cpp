#include "runtime.h"
#include "unity_fcvtzu_fixed_fixture.h"
extern "C" Memory*sub_70362a2c(State&,addr_t,Memory*);
static unsigned long polls;
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r)die("unexpected request");return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow delivery");}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
static void flags(State&s,uint64_t n,uint64_t f){s.sr.n=n>>31&1;s.sr.z=n>>30&1;s.sr.c=n>>29&1;s.sr.v=n>>28&1;s.sr.ioc=f&1;s.sr.dzc=f>>1&1;s.sr.ofc=f>>2&1;s.sr.ufc=f>>3&1;s.sr.ixc=f>>4&1;s.sr.idc=f>>7&1;}
int main(int argc,char**argv){
 if(argc!=4){die("arguments:polled literal case");}int polled=atoi(argv[1]);uint8_t literal[4];load_file(literal,4,argv[2]);setup((unsigned)strtoul(argv[3],0,10),OBJECT_CAPTURE,literal);
 State s{};for(size_t i=0;i<sizeof(s);++i)((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=OBJECT_HEAD;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];flags(s,port_controls[2],port_controls[1]);port_saved_x18=port_seeds[18];port_saved_tls=s.sr.tpidr_el0.qword;
 State expected=s;for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&expected.gpr.x0+i*16,&expected_gpr[i],8);expected.gpr.pc.qword=OBJECT_CAPTURE;memcpy(&expected.simd,expected_vectors,512);flags(expected,expected_nzcv,expected_fpsr);
 recomp::Runtime rt;const recomp::Trace trace{OBJECT_HEAD,sub_70362a2c};rt.AddTraces(&trace,1);Memory*m=reinterpret_cast<Memory*>(UINT64_C(0x1234567887654320));if(rt.Run(s,OBJECT_HEAD,m)!=m)die("memory token");
 if(memcmp(&s,&expected,sizeof(s))){for(size_t i=0;i<sizeof(s);++i)if(((uint8_t*)&s)[i]!=((uint8_t*)&expected)[i]){fprintf(stderr,"Statebyte%zu got%02x want%02x\n",i,((uint8_t*)&s)[i],((uint8_t*)&expected)[i]);break;}die("independent host full1200 State oracle");}
 alignas(16)uint8_t snap[800]{};for(unsigned i=0;i<32;++i)put64(snap+i*8,gpr(s,i));memcpy(snap+256,&s.simd,512);put64(snap+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));
 uint64_t fpsr=(s.fpsr.flat&~UINT64_C(0x9f))|s.sr.ioc|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);put64(snap+776,fpsr);put64(snap+784,s.fpcr.flat);put64(snap+792,s.sr.tpidr_el0.qword);emit(snap,0,polls,polled);
}
