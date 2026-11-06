#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "regex_nonleaf_cases.h"
#include "component_entries.h"
#include "component_helpers.h"
#include <array>
#include <stdexcept>
#include "unexecuted-sentinels.inc"
static unsigned checks=0,track_hits=0,stop_hits=0,helper_hits=0;
static void check(bool value,const char*why){++checks;if(!value)throw std::runtime_error(why);}
static Memory*Observe(State&s,addr_t pc,Memory*m){for(auto&t:bunker::regex_nonleaf_entries::kAddedTraces)if(t.address==pc){if(pc==0x84315bd4)++track_hits;if(pc==0x84316814)++stop_hits;return t.entry(s,pc,m);}throw std::runtime_error("unknown regex interior target");}
static Memory*Helper(State&s,addr_t pc,Memory*m){for(auto&t:bunker::regex_fixture::kExistingTraces)if(t.address==pc)return t.entry(s,pc,m);throw std::runtime_error("unknown real regex helper");}
extern "C" Memory*__real___bunker_guest_call(State&,addr_t,Memory*,addr_t,addr_t,recomp::Entry)noexcept;
extern "C" Memory*__wrap___bunker_guest_call(State&s,addr_t pc,Memory*m,addr_t ret,addr_t sp,recomp::Entry direct)noexcept{if(pc==0x84314790||pc==0x843148c0||pc==0x84314708||pc==0x84b72054)++helper_hits;return __real___bunker_guest_call(s,pc,m,ret,sp,direct);}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{static_assert(sizeof(State)==1200&&alignof(State)==16);check(argc==2&&!regex_map(argv[1]),"original IL2CPP image and TEST storage map");((unsigned char*)0x8799a452)[0]=1;recomp::Runtime runtime;for(auto&t:bunker::regex_nonleaf_entries::kAddedTraces){recomp::Trace w{t.address,Observe};runtime.AddTraces(&w,1);}for(auto&t:bunker::regex_fixture::kExistingTraces){recomp::Trace w{t.address,Helper};runtime.AddTraces(&w,1);}unsigned records=0;
for(unsigned which=0;which<2;which++)for(unsigned n=0;n<4;n++)for(unsigned profile=0;profile<2;profile++){
 regex_seed(which,n,profile);std::array<unsigned char,0x4000>before;memcpy(before.data(),(void*)regex_owned,before.size());State s{};memcpy(&s.simd,(void*)(regex_owned+0x1c100),512);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;
 for(unsigned i=0;i<31;i++){memcpy(reinterpret_cast<unsigned char*>(&s.gpr)+i*16+8,(void*)(regex_owned+0x1c000+i*8),8);}
 s.gpr.sp.qword=regex_sp+(which?0:0x60);s.gpr.x30.qword=which?0x843167fc:0xfeedffff;regex_p64(regex_sp+88,0xfeedffff);
 s.fpcr.flat=profile?0x03c00000:0;s.fpsr.flat=profile?0x0800009f:0;s.sr.ioc=s.fpsr.flat&1;s.sr.dzc=(s.fpsr.flat>>1)&1;s.sr.ofc=(s.fpsr.flat>>2)&1;s.sr.ufc=(s.fpsr.flat>>3)&1;s.sr.ixc=(s.fpsr.flat>>4)&1;s.sr.idc=(s.fpsr.flat>>7)&1;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;State expected=s;
 if(which){for(unsigned i=0;i<10;i++){const unsigned reg=28-i;memcpy(reinterpret_cast<unsigned char*>(&expected.gpr)+reg*16+8,&regex_saved[i],8);}expected.gpr.x29.qword=regex_saved[10];}expected.gpr.sp.qword=regex_sp+0x60;expected.gpr.x30.qword=0xfeedffff;
 std::array<uint64_t,8>memory;memory.fill(0xa7a7a7a7a7a7a7a7ULL);auto copy=memory;auto*opaque=reinterpret_cast<Memory*>(memory.data());check(runtime.Run(s,regex_entries[which],opaque)==opaque&&memory==copy,"Memory64 opaque object retained");check(s.gpr.pc.qword==0xfeedffff&&regex_check(before.data(),which,profile),"real entry/TrackPush model and all16384 owned bytes");
 for(unsigned i=0;i<19;i++){memcpy(reinterpret_cast<unsigned char*>(&expected.gpr)+i*16+8,reinterpret_cast<unsigned char*>(&s.gpr)+i*16+8,8);}
 expected.gpr.pc=s.gpr.pc;expected.sr.n=s.sr.n;expected.sr.z=s.sr.z;expected.sr.c=s.sr.c;expected.sr.v=s.sr.v;check(!memcmp(&s,&expected,sizeof(s)),"whole State1200 preserved except actual volatile registers/NZCV");
 for(unsigned i=0;i<30;i++){memcpy((void*)(regex_sp+0x60+i*8),reinterpret_cast<unsigned char*>(&s.gpr)+i*16+8,8);}
 regex_p64(regex_sp+0x60+240,s.gpr.sp.qword);regex_p64(regex_sp+0x60+248,s.fpcr.flat);regex_p64(regex_sp+0x60+256,fpsr(s));regex_p64(regex_sp+0x60+264,(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28));memcpy((void*)(regex_sp+0x60+272),&s.simd,512);regex_record(which,n,profile);++records;
}check(records==16&&track_hits==8&&stop_hits==16&&helper_hits==40,"actual reached TrackPush andStop plus real helpers executed");printf("REGEX-WINDOWS-PASS records=%u checks=%u TrackPush=%u Stop=%u helpers=%u State=1200 Memory64=1\n",records,checks,track_hits,stop_hits,helper_hits);return 0;}catch(const std::exception&e){fprintf(stderr,"regex gate: %s\n",e.what());return 1;}}
