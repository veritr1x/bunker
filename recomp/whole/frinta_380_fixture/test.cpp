#define NOMINMAX
#include <windows.h>
#include "runtime.h"
#include "cases.h"
#include <array>
#include <stdexcept>
extern "C" Memory*sub_7042dee4(State&,addr_t,Memory*);
extern "C" Memory*sub_70416c5c(State&,addr_t,Memory*);
extern "C" Memory*sub_7029cae8(State&,addr_t,Memory*);
#include "sentinels.inc"
static void require(bool v,const char*why){if(!v)throw std::runtime_error(why);}
static Memory*width(State&s,addr_t,Memory*m){require(s.gpr.x0.qword==owned,"width real TESTobject identity");s.gpr.x9.qword=get32(owned+0x30)+1;put32(owned+0x30,s.gpr.x9.dword);s.gpr.x0.qword=get32(owned+0x20);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
static Memory*height(State&s,addr_t,Memory*m){require(s.gpr.x0.qword==owned,"height real TESTobject identity");s.gpr.x9.qword=get32(owned+0x34)+1;put32(owned+0x34,s.gpr.x9.dword);s.gpr.x0.qword=get32(owned+0x24);s.gpr.pc.qword=s.gpr.x30.qword;return m;}
static uint64_t fpsr(const State&s){return(s.fpsr.flat&~UINT64_C(0x9f))|uint64_t(s.sr.ioc)|(uint64_t(s.sr.dzc)<<1)|(uint64_t(s.sr.ofc)<<2)|(uint64_t(s.sr.ufc)<<3)|(uint64_t(s.sr.ixc)<<4)|(uint64_t(s.sr.idc)<<7);}
int main(int argc,char**argv){try{
 static_assert(sizeof(State)==1200&&alignof(State)==16&&sizeof(Out)==104);
 require(argc==2&&!map_original(argv[1]),"map real original ELF/data");
 recomp::Runtime runtime;const recomp::Trace traces[]={{0x7042dee4,sub_7042dee4},{0x70416c5c,sub_70416c5c},{0x7029cae8,sub_7029cae8},{0x51000000,width},{0x51000004,height}};runtime.AddTraces(traces,5);unsigned count=0;
 for(unsigned n=0;n<sizeof(cases)/sizeof(*cases);n++)for(unsigned mode=0;mode<4;mode++)for(unsigned initial=0;initial<2;initial++){
  seed(n,0x51000000,0x51000004);uint64_t before=hashdata(),globals=globalhash();State s{};memset(&s.simd,0x5a,sizeof(s.simd));reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;
  s.gpr.x0.qword=owned;s.gpr.sp.qword=owned+0x1f000;s.gpr.x30.qword=0xfeedffff;
  s.gpr.x19.qword=0xaaaa000000001919ULL;s.gpr.x20.qword=0xbbbb000000002020ULL;s.gpr.x21.qword=0x2121;s.gpr.x22.qword=0x2222;s.gpr.x23.qword=0x2323;s.gpr.x24.qword=0x2424;s.gpr.x25.qword=0x2525;s.gpr.x29.qword=0xe123456789abcdefULL;
  s.fpcr.flat=(uint64_t)mode<<22;s.fpsr.flat=initial?0x0800009f:0;s.sr.ioc=initial;s.sr.dzc=initial;s.sr.ofc=initial;s.sr.ufc=initial;s.sr.ixc=initial;s.sr.idc=initial;s.nzcv.flat=0xa0000000;s.sr.n=1;s.sr.c=1;
  std::array<uint64_t,8>opaque;opaque.fill(0xa7a7a7a7a7a7a7a7ULL);auto*token=reinterpret_cast<Memory*>(opaque.data());auto copied=opaque;
  require(runtime.Run(s,0x7042dee4,token)==token&&opaque==copied,"opaque Memory64 preserved");
  require(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==owned+0x1f000&&s.gpr.x19.qword==0xaaaa000000001919ULL&&s.gpr.x20.qword==0xbbbb000000002020ULL&&s.gpr.x21.qword==0x2121&&s.gpr.x22.qword==0x2222&&s.gpr.x23.qword==0x2323&&s.gpr.x24.qword==0x2424&&s.gpr.x25.qword==0x2525&&s.gpr.x29.qword==0xe123456789abcdefULL,"PC/SP/GPR callee-save ABI");
  std::array<unsigned char,16>v;v.fill(0x5a);require(!memcmp(v.data(),&s.simd.v[31],16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200 highcells preserved");
  require(hashdata()==before&&globalhash()==globals&&valid_counts(n),"owneddata preserved, real virtualcalls/counts");
  Out out;memset(&out,0x5a,sizeof(out));out.fpsr=fpsr(s);out.nzcv=(uint64_t(s.sr.n)<<31)|(uint64_t(s.sr.z)<<30)|(uint64_t(s.sr.c)<<29)|(uint64_t(s.sr.v)<<28);out.fpcr=s.fpcr.flat;memcpy(out.v,&s.simd.v[0],64);out.abi_ok=1;record(n,mode,initial,&out);count++;
 }
 printf("WINDOWS380-PASS executions=%u State1200=1 Memory64=1 realhelpers=2\n",count);return 0;
}catch(const std::exception&e){fprintf(stderr,"380 fixture: %s\n",e.what());return 1;}}
