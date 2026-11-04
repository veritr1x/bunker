#include "runtime.h"
#include <array>
#include <utility>
#include <vector>
#include "unwind_cases_fixture.h"
#include "unwind_cases_traces.h"
static unsigned long polls;static int polled;
static std::array<unsigned,27>hits{};
static State original_state;static uint8_t*opaque_token;
template<size_t I>Memory*Observed(State&s,addr_t pc,Memory*m){++hits[I];return kUnwindNewTraces[I].entry(s,pc,m);}
template<size_t...I>constexpr auto ObservedTraces(std::index_sequence<I...>){return std::array<recomp::Trace,sizeof...(I)>{{{kUnwindNewTraces[I].address,Observed<I>}...}};}
extern "C" uint32_t __real___bunker_guest_poll_requested();
extern "C" uint32_t __wrap___bunker_guest_poll_requested(){++polls;auto value=__real___bunker_guest_poll_requested();if(value)die("unexpected poll request");return value;}
extern "C" void __wrap___bunker_guest_poll_slow(State*,uint64_t,uint64_t,uint64_t){die("unexpected slow poll");}
static uint64_t gpr(const State&s,unsigned i){uint64_t v;memcpy(&v,(const uint8_t*)&s.gpr.x0+i*16,8);return v;}
static void snapshot(const State&s,uint8_t*out){for(unsigned i=0;i<32;++i)put64(out+i*8,gpr(s,i));memcpy(out+256,&s.simd,512);put64(out+768,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));put64(out+776,s.fpsr.flat);put64(out+784,s.fpcr.flat);put64(out+792,s.sr.tpidr_el0.qword);}
static void finish(const State&s,int aborted){for(unsigned i=0;i<64;++i)if(opaque_token[i]!=0x6d)die("opaque token bytes");for(unsigned i=0;i<32;++i)if(memcmp((const uint8_t*)&s.gpr.x0+i*16+8,(const uint8_t*)&original_state.gpr.x0+i*16+8,8))die("high-cell preservation");alignas(16)uint8_t arch[800]{};snapshot(s,arch);printf("FULLSTATE case=%u bytes=1200 value=",case_id);hex(reinterpret_cast<const uint8_t*>(&s),sizeof(s));puts(" token64=unchanged highcells=preserved");printf("HITS case=%u mask=",case_id);for(auto h:hits)printf("%u",h!=0);puts("");emit(arch,0,polls,polled,aborted);}
extern "C" Memory*sub_820cb8d0(State&s,addr_t,Memory*m){
 const auto sp=s.gpr.sp.qword;uint64_t saved[]={gpr(s,3),gpr(s,4),gpr(s,5),gpr(s,6),gpr(s,7),gpr(s,8),(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28)};
 recomp::WriteGuestMemory(sp-64,saved,sizeof(saved));std::vector<uint8_t>bytes(s.gpr.x2.qword);recomp::ReadGuestMemory(bytes.data(),s.gpr.x1.qword,bytes.size());recomp::WriteGuestMemory(s.gpr.x0.qword,bytes.data(),bytes.size());s.gpr.pc.qword=s.gpr.x30.qword;return m;
}
extern "C" Memory*sub_820cbb10(State&s,addr_t,Memory*m){if(m!=reinterpret_cast<Memory*>(opaque_token))die("abort prefix token identity");finish(s,1);std::abort();}
int main(int argc,char**argv){
 static_assert(sizeof(State)==1200);if(argc!=5)die("host arguments");polled=atoi(argv[1]);setup((unsigned)strtoul(argv[4],0,10),argv[2],argv[3]);
 recomp::Runtime runtime;runtime.AddTraces(kUnwindTraces,std::size(kUnwindTraces));
 constexpr auto observed=ObservedTraces(std::make_index_sequence<27>{});runtime.AddTraces(observed.data(),observed.size());
 alignas(16)uint8_t token[64];memset(token,0x6d,sizeof(token));opaque_token=token;Memory*m=reinterpret_cast<Memory*>(token);
 State init{};init.gpr.sp.qword=entry_sp;init.gpr.x30.qword=FIXTURE_RETURN;runtime.Run(init,0x82624b2c,m);polls=0;
 if(*(const uint8_t*)(uintptr_t)UINT64_C(0x879a8fa0)!=8)die("genuine retained size initializer");
 State s{};for(size_t i=0;i<sizeof(s);++i)reinterpret_cast<uint8_t*>(&s)[i]=(uint8_t)(i*13+case_id*17);for(unsigned i=0;i<31;++i)memcpy((uint8_t*)&s.gpr.x0+i*16,&port_seeds[i],8);
 s.gpr.sp.qword=entry_sp;s.gpr.pc.qword=entry_pc;s.sr.tpidr_el0.qword=port_controls[3];memcpy(&s.simd,port_qseeds,512);s.nzcv.flat=port_controls[2];s.fpcr.flat=port_controls[0];s.fpsr.flat=port_controls[1];s.sr.n=case_id>>3&1;s.sr.z=case_id>>2&1;s.sr.c=case_id>>1&1;s.sr.v=case_id&1;s.sr.ioc=s.sr.dzc=s.sr.ofc=s.sr.ufc=s.sr.ixc=s.sr.idc=case_id&1;
 original_state=s;if(runtime.Run(s,entry_pc,m)!=m||s.gpr.pc.qword!=FIXTURE_RETURN)die("original RET PC/token");finish(s,0);
}
