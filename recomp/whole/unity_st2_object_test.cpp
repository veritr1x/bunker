#include "runtime.h"
#include "unity_st2_object_fixture.h"
extern "C" Memory*sub_707bb458(State&,addr_t,Memory*);
static State expected_state;
static unsigned long polls;
static int polled;
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto r=__real___bunker_guest_poll_requested();if(r)die("unexpected request");return r;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
int main(int argc,char**argv){if(argc!=4)die("host arguments");polled=atoi(argv[1]);FILE*f=fopen(argv[2],"rb");uint64_t global=0;if(!f||fread(&global,1,8,f)!=8)die("original opaque global input");fclose(f);setup((unsigned)strtoul(argv[3],0,10),OBJECT_CAPTURE,global);
 State s{};for(size_t i=0;i<sizeof(s);++i)((uint8_t*)&s)[i]=(uint8_t)(i*13+case_id*17);for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=OBJECT_HEAD;s.sr.tpidr_el0.qword=UINT64_C(0x71e693b420c8d5a1);memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];unsigned nzcv=flag_id*5;s.sr.n=nzcv>>3&1;s.sr.z=nzcv>>2&1;s.sr.c=nzcv>>1&1;s.sr.v=nzcv&1;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=flag_id&1;port_saved_x18=port_seeds[18];port_saved_tls=s.sr.tpidr_el0.qword;
 expected_state=s;for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&expected_state.gpr.x0+i*16,&expected_gpr[i],8);memcpy(&expected_state.simd,expected_vectors,512);expected_state.gpr.pc.qword=OBJECT_CAPTURE;expected_state.sr.n=0;expected_state.sr.z=1;expected_state.sr.c=1;expected_state.sr.v=0;
 recomp::Runtime rt;const recomp::Trace trace{OBJECT_HEAD,sub_707bb458};rt.AddTraces(&trace,1);Memory*m=reinterpret_cast<Memory*>(UINT64_C(0x1234567887654320));if(rt.Run(s,OBJECT_HEAD,m)!=m)die("original memory token");if(memcmp(&s,&expected_state,sizeof(s))){for(size_t i=0;i<sizeof(s);++i)if(((uint8_t*)&s)[i]!=((uint8_t*)&expected_state)[i]){fprintf(stderr,"Statebyte%zu got%02x expected%02x\n",i,((uint8_t*)&s)[i],((uint8_t*)&expected_state)[i]);break;}die("independent full1200 State effects");}
 alignas(16)uint8_t snapshot[800]{};for(unsigned i=0;i<32;++i)put64(snapshot+i*8,gpr(s,i));memcpy(snapshot+256,&s.simd,512);put64(snapshot+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));put64(snapshot+776,s.fpsr.flat);put64(snapshot+784,s.fpcr.flat);put64(snapshot+792,s.sr.tpidr_el0.qword);emit(snapshot,0,polls,polled);
}
