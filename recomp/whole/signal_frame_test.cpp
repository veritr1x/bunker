#include "signal_frame.h"
#include "signal_frame_driver.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

using namespace recomp::signal_frame;
namespace {
unsigned checks;
void Check(bool okay,const char *why){++checks;if(!okay){std::fprintf(stderr,"signal frame check: %s\n",why);std::exit(1);}}
void Put(std::vector<uint8_t>&b,size_t at,uint64_t value,unsigned width=8){for(unsigned i=0;i<width;++i)b.at(at+i)=uint8_t(value>>(i*8));}
uint64_t Get(const std::vector<uint8_t>&b,size_t at,unsigned width=8){uint64_t v=0;for(unsigned i=0;i<width;++i)v|=uint64_t(b.at(at+i))<<(i*8);return v;}
uint64_t Gp(const State&s,unsigned i){uint64_t v;std::memcpy(&v,(const uint8_t*)&s.gpr+i*16+8,8);return v;}
void Gp(State&s,unsigned i,uint64_t v){std::memcpy((uint8_t*)&s.gpr+i*16+8,&v,8);}
template<class F>void Reject(F f,const char*why){bool rejected=false;try{f();}catch(const std::invalid_argument&){rejected=true;}Check(rejected,why);}
}
int main(){
  elf_image image{};Check(!elf_load(SIGNAL_FRAME_LIBRARY,0x58000000,nullptr,&image),"NDK image load");
  recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
  const addr_t handler=(addr_t)elf_symbol(&image,"frame_handler"),install=(addr_t)elf_symbol(&image,"frame_install");
  alignas(16)std::array<uint8_t,65536> stack{},alt{};
  alignas(16)std::array<uint64_t,8> roots{};
  Bounds ordinary{(addr_t)stack.data(),(addr_t)(stack.data()+stack.size())};
  Bounds alternate{(addr_t)alt.data(),(addr_t)(alt.data()+alt.size())};
  unsigned successes=0;
  for(unsigned mode=0;mode<32;++mode){
    State state{};
    for(unsigned i=0;i<31;++i)Gp(state,i,0x7000000000ULL+mode*0x100+i);
    state.gpr.x19.qword=(addr_t)roots.data();state.gpr.sp.qword=ordinary.high;state.gpr.pc.qword=0x80001000;
    state.sr.tpidr_el0.qword=0x12340000+mode;state.sr.tpidrro_el0.qword=0x56780000+mode;
    state.fpcr.flat=uint64_t(mode&15)<<22;state.fpsr.flat=(1u<<27)|0x9f;
    state.sr.n=(mode>>0)&1;state.sr.z=(mode>>1)&1;state.sr.c=(mode>>2)&1;state.sr.v=(mode>>3)&1;
    state.sr.ioc=(mode>>0)&1;state.sr.dzc=(mode>>1)&1;state.sr.ofc=(mode>>2)&1;state.sr.ufc=(mode>>3)&1;state.sr.ixc=(mode>>4)&1;state.sr.idc=(mode>>0)&1;
    for(unsigned i=0;i<32;++i){uint64_t q[]={0x7ff8000000000000ULL+mode*32+i,0xfff0000000000001ULL+i};std::memcpy(&state.simd.v[i],q,16);}
    uint64_t root_pair[]={(addr_t)roots.data(),(addr_t)roots.data()+8};std::memcpy(&state.simd.v[31],root_pair,16);
    Metadata m;m.pstate=0xa500000000000000ULL|0xf0000000|((mode&4)?1ULL<<25:0);m.mask=0x8000000000000100ULL+mode;m.fault_address=0xfeed0000+mode;
    m.altstack={alternate.low,0,uint64_t(alternate.high-alternate.low)};
    for(unsigned i=0;i<128;++i)m.siginfo[i]=uint8_t(i+mode);
    m.siginfo[0]=30;m.siginfo[1]=m.siginfo[2]=m.siginfo[3]=0;
    m.siginfo[4]=5;m.siginfo[5]=m.siginfo[6]=m.siginfo[7]=0;
    m.siginfo[8]=7;m.siginfo[9]=m.siginfo[10]=m.siginfo[11]=0;
    Request request{ordinary,mode&1?alternate:ordinary,(mode&1?alternate.high:ordinary.high)-((mode&2)?7:0),handler,0xfeedfff0,30,true};
    Image frame=Serialize(state,m,request);
    Check(!(frame.base&15)&&frame.frame_record==frame.base+kFrameSize&&frame.bytes.size()==4704,"Linux frame placement/alignment/record length");
    Check(frame.handler_state.gpr.sp.qword==frame.base&&frame.handler_state.gpr.x29.qword==frame.frame_record&&frame.handler_state.gpr.x30.qword==request.restorer,"handler SP/FP/LR chain setup");
    Check(Get(frame.bytes,kFrameSize)==state.gpr.x29.qword&&Get(frame.bytes,kFrameSize+8)==state.gpr.x30.qword,"unwind record preserves interrupted FP/LR");
    const uint64_t expected_pstate=(m.pstate&~0xf0000000ULL)|(uint64_t(state.sr.n)<<31)|(uint64_t(state.sr.z)<<30)|(uint64_t(state.sr.c)<<29)|(uint64_t(state.sr.v)<<28);
    const uint32_t flags=state.sr.ioc|(state.sr.dzc<<1)|(state.sr.ofc<<2)|(state.sr.ufc<<3)|(state.sr.ixc<<4)|(state.sr.idc<<7);
    Check(frame.handler_pstate==(expected_pstate&~(1ULL<<25)),"handler TCO cleared while interrupted full PSTATE stays saved");
    auto plain=request;plain.siginfo_handler=false;auto one_argument=Serialize(state,m,plain);
    Check(one_argument.handler_state.gpr.x0.qword==30&&one_argument.handler_state.gpr.x1.qword==state.gpr.x1.qword&&one_argument.handler_state.gpr.x2.qword==state.gpr.x2.qword,"non-SA_SIGINFO entry preserves X1/X2");
    Check(Get(frame.bytes,kMachineOffset+272)==expected_pstate&&Get(frame.bytes,kFpsimdOffset+8,4)==((1u<<27)|flags),"canonical SR replaces stale NZCV/FPSR mirrors");
    Check(Get(frame.bytes,kMachineOffset+8+19*8)==(addr_t)roots.data()&&Get(frame.bytes,kFpsimdOffset+16+31*16)==(addr_t)roots.data(),"register-only pointer roots are physically present in stack frame bytes");
    const auto baseline=state;
    auto roundtrip=Restore({frame.base,frame.bytes.data(),frame.bytes.size()},frame.base,ordinary,baseline);
    for(unsigned i=0;i<31;++i)Check(Gp(roundtrip.state,i)==Gp(state,i),"all GPRs round trip");
    Check(std::memcmp(&roundtrip.state.simd,&state.simd,sizeof(state.simd))==0,"all SIMD bits round trip");
    Check(roundtrip.metadata.pstate==expected_pstate&&roundtrip.metadata.mask==m.mask&&roundtrip.metadata.siginfo==m.siginfo&&roundtrip.metadata.fault_address==m.fault_address,"PSTATE/mask/siginfo/fault preserve full metadata");
    FrameReport report{};report.mutate=mode&1;report.new_root=(addr_t)roots.data()+16;
    State setup{};setup.gpr.sp.qword=ordinary.high-8192;setup.gpr.x30.qword=0xfeedfff0;setup.gpr.x0.qword=(addr_t)&report;
    runtime.Run(setup,install);
    recomp::WriteGuestMemory(frame.base,frame.bytes.data(),frame.bytes.size());
    auto live=frame.handler_state;runtime.Run(live,handler);
    Check(live.gpr.pc.qword==request.restorer&&live.gpr.sp.qword==frame.base,"actual translated handler returns to supplied context with correct SP");
    const uint64_t layout[]={128,4560,4384,24,8,16,40,176,8,256,264,272,288,528,16,8};
    for(unsigned i=0;i<16;++i)Check(report.layout[i]==layout[i],"NDK header size/offset independently agrees");
    Check(report.signo==30&&report.info_signo==30&&report.info_errno==5&&report.info_code==7,"actual NDK siginfo reader");
    Check(report.magic==kFpsimdMagic&&report.record_size==528&&report.fpcr==state.fpcr.flat&&report.fpsr==((1u<<27)|flags),"actual NDK FPSIMD reader");
    Check(report.entry_sp==frame.base&&report.entry_fp==frame.frame_record&&report.chain_fp==state.gpr.x29.qword&&report.chain_lr==state.gpr.x30.qword,"NDK handler entry and Linux FP chain");
    for(unsigned i=0;i<31;++i)Check(report.gpr[i]==Gp(state,i),"NDK reader sees all saved GPRs");
    Check(std::memcmp(report.vectors,&state.simd,sizeof(state.simd))==0,"NDK reader sees all saved SIMD bits");
    Check(report.pstate==expected_pstate&&report.mask==m.mask&&report.alt_pointer==m.altstack.pointer&&report.alt_flags==m.altstack.flags&&report.alt_size==m.altstack.size,"NDK mask/altstack/PSTATE access");
    recomp::ReadGuestMemory(frame.bytes.data(),frame.base,frame.bytes.size());
    auto restored=Restore({frame.base,frame.bytes.data(),frame.bytes.size()},frame.base,ordinary,baseline);
    Check(restored.state.sr.tpidr_el0.qword==baseline.sr.tpidr_el0.qword&&restored.state.sr.tpidrro_el0.qword==baseline.sr.tpidrro_el0.qword,"TLS supplied solely by baseline");
    Check(restored.state.gpr.x19.qword==(report.mutate?report.new_root:state.gpr.x19.qword)&&restored.state.gpr.sp.qword==state.gpr.sp.qword-(report.mutate?16:0)&&restored.state.gpr.pc.qword==state.gpr.pc.qword+(report.mutate?4:0),"NDK-written GPR/SP/PC restored");
    Check(restored.metadata.pstate==(expected_pstate^(report.mutate?1ULL<<31:0))&&restored.metadata.mask==(m.mask^(report.mutate?0x20:0)),"NDK-written PSTATE/mask restored");
    Check(restored.state.fpcr.flat==(state.fpcr.flat^(report.mutate?1u<<22:0))&&restored.state.fpsr.flat==(((1u<<27)|flags)^(report.mutate?0x9f:0)),"NDK-written FPCR/FPSR restored");
    const auto &sr=restored.state.sr;
    Check(uint64_t(sr.ioc|(sr.dzc<<1)|(sr.ofc<<2)|(sr.ufc<<3)|(sr.ixc<<4)|(sr.idc<<7))==(restored.state.fpsr.flat&0x9f),"restored FPSR updates all canonical SR exception flags");
    Check(((uint64_t(sr.n)<<31)|(uint64_t(sr.z)<<30)|(uint64_t(sr.c)<<29)|(uint64_t(sr.v)<<28))==(restored.metadata.pstate&0xf0000000ULL)&&restored.state.nzcv.flat==(restored.metadata.pstate&0xf0000000ULL),"restored PSTATE updates canonical NZCV and mirror");
    Check(restored.metadata.altstack.pointer==m.altstack.pointer&&restored.metadata.altstack.size==m.altstack.size&&restored.metadata.altstack.flags==(report.mutate?1u:0u),"NDK-written altstack metadata restored");
    if(report.mutate){uint64_t changed[2];std::memcpy(changed,&restored.state.simd.v[31],16);Check(changed[0]==report.new_root&&changed[1]==report.new_root+8&&restored.metadata.siginfo[4]==17,"NDK-written SIMD root and siginfo preserved");}
    // Rejected parsing never changes either baseline or source bytes.
    auto reject_bytes=[&](auto change,const char*why){auto broken=frame.bytes;change(broken);auto saved=broken;Reject([&]{Restore({frame.base,broken.data(),broken.size()},frame.base,ordinary,baseline);},why);Check(broken==saved&&!std::memcmp(&baseline,&state,sizeof(state)),"failed restore is transactional");};
    reject_bytes([](auto&b){Put(b,kFpsimdOffset+4,527,4);},"misaligned FPSIMD record rejected");
    reject_bytes([](auto&b){Put(b,kFpsimdOffset,0x53564501,4);},"unsupported SVE extension rejected");
    reject_bytes([](auto&b){Put(b,kFpsimdOffset,0,8);},"missing FPSIMD rejected");
    reject_bytes([](auto&b){Put(b,kFpsimdOffset+kFpsimdSize,kFpsimdMagic,4);Put(b,kFpsimdOffset+kFpsimdSize+4,kFpsimdSize,4);},"duplicate FPSIMD rejected");
    reject_bytes([](auto&b){Put(b,kFpsimdOffset+kFpsimdSize,0,4);Put(b,kFpsimdOffset+kFpsimdSize+4,16,4);},"malformed null terminator rejected");
    reject_bytes([](auto&b){Put(b,kMachineOffset+256,0);},"out-of-range restored SP rejected");
    reject_bytes([](auto&b){Put(b,kMachineOffset+264,3);},"misaligned restored PC rejected");
    Reject([&]{Restore({frame.base,frame.bytes.data(),frame.bytes.size()-1},frame.base,ordinary,baseline);},"short frame/FP record rejected");
    Reject([&]{Restore({frame.base,frame.bytes.data(),frame.bytes.size()},frame.base+1,ordinary,baseline);},"unaligned frame rejected");
    auto small=request;small.delivery_stack.low=request.stack_top-128;Reject([&]{Serialize(state,m,small);},"stack guard underflow rejected");
    auto bad=request;bad.handler|=1;Reject([&]{Serialize(state,m,bad);},"unaligned handler rejected");
    auto metadata=m;metadata.altstack={UINT64_MAX-7,0,16};Reject([&]{Serialize(state,metadata,request);},"overflowing altstack rejected");
    auto misaligned=state;misaligned.gpr.sp.qword-=1;Reject([&]{Serialize(misaligned,m,request);},"misaligned interrupted SP rejected");
    auto high_fpcr=state;high_fpcr.fpcr.flat|=1ULL<<40;Reject([&]{Serialize(high_fpcr,m,request);},"nonarchitectural high FPCR bits rejected");
    Reject([&]{Restore({UINT64_MAX-15,frame.bytes.data(),frame.bytes.size()},frame.base,ordinary,baseline);},"overflowing input byte view rejected");
    ++successes;
  }
  std::printf("AArch64 signal-frame bytes: %u checks/%u NDK translated reader-writer cases; no delivery or GC implementation.\n",checks,successes);
}
