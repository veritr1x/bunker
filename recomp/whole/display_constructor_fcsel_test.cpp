#include "runtime.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#define DECL(h) extern "C" Memory *sub_##h(State&,addr_t,Memory*);
DECL(7042377c) DECL(704238f4) DECL(70423908) DECL(70423918) DECL(70423928)
recomp::Runtime *active_runtime=nullptr;
#include "display_fcsel_stubs.h"
#include "display_constructor_data.h"
static void check(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static void* owned(addr_t address,size_t size){
#ifdef _WIN32
 auto p=VirtualAlloc(reinterpret_cast<void*>(address),size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 auto p=mmap(reinterpret_cast<void*>(address),size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);if(p==MAP_FAILED)p=nullptr;
#endif
 check(reinterpret_cast<addr_t>(p)==address,"owned exact fixture mapping");return p;
}
static void readonly(void*p,size_t size){
#ifdef _WIN32
 DWORD old=0;check(VirtualProtect(p,size,PAGE_READONLY,&old)!=0,"read-only original constant data");
#else
 check(mprotect(p,size,PROT_READ)==0,"read-only original constant data");
#endif
}
int main(){try{
 auto constants=static_cast<uint8_t*>(owned(0x70e70000,0x10000));std::memcpy(constants+0xe464,kOriginalFallback,4);readonly(constants,0x10000);auto table=static_cast<uint8_t*>(owned(0x70ed0000,0x10000));std::memcpy(table+0x8d44,kOriginalRotationTable,16);readonly(table,0x10000);
 auto globals=static_cast<uint8_t*>(owned(0x712c0000,0x10000));globals[0xc78]=1;auto stack=static_cast<uint8_t*>(owned(0x48000000,0x10000));auto output=static_cast<uint8_t*>(owned(0x49000000,0x10000));
 recomp::Runtime runtime;active_runtime=&runtime;uint32_t refresh=0;unsigned refresh_calls=0;
 const auto integer=[&](addr_t h,uint64_t value){runtime.AddImport(h,[value](State&s){s.gpr.x0.qword=value;});};
 integer(0x70acbee4,0);integer(0x70acc1d0,0);integer(0x70acc264,1920);integer(0x70acbf78,1080);integer(0x70417e8c,0x712c0100);integer(0x700b8870,1);integer(0x70acb80c,1920);integer(0x70acb71c,1080);integer(0x70acb62c,224);integer(0x70416c5c,33);integer(0x70acc2f8,0);integer(0x70acbe50,0);integer(0x70acc00c,8333334);runtime.AddImport(0x70acc0a0,[](State&){});
 runtime.AddImport(0x70acc13c,[&](State&s){++refresh_calls;std::memset(&s.simd.v[0],0,16);std::memcpy(&s.simd.v[0],&refresh,4);});
 const recomp::Trace targets[]={{0x7042377c,sub_7042377c},{0x704238f4,sub_704238f4},{0x70423908,sub_70423908},{0x70423918,sub_70423918},{0x70423928,sub_70423928}};runtime.AddTraces(targets,5);
 const uint32_t inputs[]={0x42f00000,0,0x41200000},expected[]={0x42f00000,0x42700000,0x41200000};
 for(unsigned h=0;h<5;++h)for(unsigned n=0;n<3;++n){refresh=inputs[n];refresh_calls=0;std::memset(stack,0x5a,0x10000);std::memset(output,0xab,0x10000);State caller{};std::memset(&caller.simd,0xa7,sizeof(caller.simd));Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7,&GPR::x8,&GPR::x9,&GPR::x10,&GPR::x11,&GPR::x12,&GPR::x13,&GPR::x14,&GPR::x15,&GPR::x16,&GPR::x17,&GPR::x18,&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29,&GPR::x30};for(unsigned i=0;i<31;++i)(caller.gpr.*regs[i]).qword=0x1111000000000000ULL+i;caller.gpr.x30.qword=0xfeedfffc;caller.gpr.sp.qword=0x48010000;State s=caller;
  if(h==0){s.gpr.x0.qword=0x712c0200;s.gpr.x8.qword=0x49000000;}else{s.gpr.sp.qword-=0x40;s.gpr.x0.qword=1080;s.gpr.x19.qword=0x49000000;s.gpr.x20.qword=0x712c0200;s.gpr.x21.qword=1920;s.gpr.x23.qword=3;s.gpr.x24.qword=4;const unsigned saved[]={24,23,22,21,20,19,30};const unsigned offsets[]={0,16,24,32,40,48,56};for(unsigned i=0;i<7;++i){auto value=(caller.gpr.*regs[saved[i]]).qword;recomp::WriteGuestMemory(s.gpr.sp.qword+offsets[i],&value,8);}}
  runtime.Run(s,targets[h].address);uint32_t value=0;std::memcpy(&value,output+0x20,4);check(value==expected[n],"original constructor stored selected refresh bits");check(refresh_calls==1,"one controlled refresh helper call");check(s.gpr.pc.qword==0xfeedfffc&&s.gpr.sp.qword==0x48010000&&s.gpr.x30.qword==0xfeedfffc,"original constructor normal PC/SP/LR");for(unsigned i=19;i<30;++i)check((s.gpr.*regs[i]).qword==(caller.gpr.*regs[i]).qword,"original constructor callee GPR preservation");uint32_t density=0;std::memcpy(&density,output+0x1c,4);check(density==0x43600000,"original density conversion224");uint64_t app=1,budget=0;std::memcpy(&app,output+0x28,8);std::memcpy(&budget,output+0x30,8);check(!app&&budget==8333334&&output[0x39]==0,"SDK33 wide/long tail executed");for(unsigned i=0;i<256;++i)check(stack[i]==0x5a,"owned stack lower canary");for(unsigned i=0x40;i<0x10000;++i)check(output[i]==0xab,"result upper canary");
  uint64_t hash=1469598103934665603ULL;for(size_t i=0;i<sizeof(s);++i){hash^=reinterpret_cast<uint8_t*>(&s)[i];hash*=1099511628211ULL;}for(unsigned i=0;i<0x40;++i){hash^=output[i];hash*=1099511628211ULL;}std::printf("CONSTRUCTOR %llx %08x %08x %016llx\n",(unsigned long long)targets[h].address,inputs[n],value,(unsigned long long)hash);
 }
 std::puts("DISPLAY-CONSTRUCTOR-FCSEL-SUCCESS 15; actual five original selected entries and normal-return paths; labelled C++ getter/assertion/SDK seams only");return 0;
}catch(const std::exception&e){std::fprintf(stderr,"display constructor FCSEL fixture: %s\n",e.what());return 1;}}
