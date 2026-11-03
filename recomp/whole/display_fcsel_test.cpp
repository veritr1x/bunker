#include "runtime.h"
#include "jni_host.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
extern "C" Memory *sub_70acc13c(State&,addr_t,Memory*);
recomp::Runtime *active_runtime=nullptr;
#include "display_fcsel_stubs.h"
static void check(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static void* owned(addr_t address,size_t size){
#ifdef _WIN32
 auto p=VirtualAlloc(reinterpret_cast<void*>(address),size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 auto p=mmap(reinterpret_cast<void*>(address),size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);if(p==MAP_FAILED)p=nullptr;
#endif
 check(reinterpret_cast<addr_t>(p)==address,"owned exact fixture mapping");return p;
}
int main(){try{
 auto globals=static_cast<uint8_t*>(owned(0x71300000,0x10000))+0xf000;auto stack=static_cast<uint8_t*>(owned(0x48000000,0x10000));
 recomp::Runtime runtime;active_runtime=&runtime;bunker::jni::Host host{[](addr_t){return false;}};host.Install(runtime);
 uint32_t refresh=0;unsigned calls=0,checks=0,post_error=0;
 host.DefineClass("android/view/Display",{},"java/lang/Object",true);host.DefineFloatBitsMethod("android/view/Display","getRefreshRate","()F",[&](addr_t,const bunker::jni::Host::MethodArguments&){++calls;return refresh;});
 auto object=host.NewInstance("android/view/Display");State find{};find.gpr.x0.qword=host.EnvAddress();find.gpr.x1.qword=reinterpret_cast<addr_t>("android/view/Display");host.InvokeEnv(6,find);auto clazz=find.gpr.x0.qword;State id{};id.gpr.x0.qword=host.EnvAddress();id.gpr.x1.qword=clazz;id.gpr.x2.qword=reinterpret_cast<addr_t>("getRefreshRate");id.gpr.x3.qword=reinterpret_cast<addr_t>("()F");host.InvokeEnv(33,id);auto method=id.gpr.x0.qword;check(method&&host.PendingException().empty(),"actual JNI float method ID");
 addr_t holder=0x7130f110;recomp::WriteGuestMemory(0x7130f100,&holder,8);recomp::WriteGuestMemory(holder,&object,8);recomp::WriteGuestMemory(0x7130fa88,&method,8);globals[0xa90]=1;
 runtime.AddImport(0x70ab4e78,[&](State&s){s.gpr.x0.qword=host.EnvAddress();});
 runtime.AddImport(0x70ab4f78,[&](State&s){check(s.gpr.x0.qword==1,"original nonnull assertion input");s.gpr.x0.qword=0;});
 runtime.AddImport(0x70ab5020,[&](State&s){check(s.gpr.x0.qword==host.EnvAddress(),"original exception checker JNIEnv");s.gpr.x0.qword=(++checks==2)?post_error:0;});
 const recomp::Trace target{0x70acc13c,sub_70acc13c};runtime.AddTraces(&target,1);
 for(unsigned n=0;n<4;++n){post_error=n&1;refresh=n<2?0x42f00000:0;calls=checks=0;std::memset(stack,0x5a,0x10000);State s{};std::memset(&s.simd,0xa7,sizeof(s.simd));Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7,&GPR::x8,&GPR::x9,&GPR::x10,&GPR::x11,&GPR::x12,&GPR::x13,&GPR::x14,&GPR::x15,&GPR::x16,&GPR::x17,&GPR::x18,&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29,&GPR::x30};for(unsigned i=0;i<31;++i)(s.gpr.*regs[i]).qword=0x1111000000000000ULL+i;s.gpr.x0.qword=0x7130f100;s.gpr.sp.qword=0x48010000;s.gpr.x30.qword=0xfeedfffc;State before=s;runtime.Run(s,0x70acc13c);
  uint8_t expected[16]{};uint32_t value=post_error?0:refresh;std::memcpy(expected,&value,4);check(!std::memcmp(&s.simd.v[0],expected,16),"original whole wrapper FCSEL result/upper clear");check(s.gpr.pc.qword==0xfeedfffc&&s.gpr.sp.qword==0x48010000&&s.gpr.x30.qword==0xfeedfffc,"original wrapper normal PC/SP/LR");check(calls==1&&checks==2&&host.PendingException().empty(),"real CallFloatMethodV and controlled checker seam counts");for(unsigned i=19;i<30;++i)check((s.gpr.*regs[i]).qword==(before.gpr.*regs[i]).qword,"original callee GPR preservation");check(!std::memcmp(&s.simd.v[8],&before.simd.v[8],8),"original saved D8 preservation");for(unsigned i=0;i<256;++i)check(stack[i]==0x5a,"owned stack lower canary");
  // Only normalize the real host JNIEnv pointer if a volatile scratch register retains it.
  auto env=host.EnvAddress();for(auto reg:regs)if((s.gpr.*reg).qword==env)(s.gpr.*reg).qword=0xeeeeeeeeeeeeeeeeULL;
  uint64_t hash=1469598103934665603ULL;for(size_t i=0;i<sizeof(s);++i){hash^=reinterpret_cast<uint8_t*>(&s)[i];hash*=1099511628211ULL;}
  std::printf("WRAPPER %08x %u %08x %016llx\n",refresh,post_error,value,(unsigned long long)hash);
 }
 std::puts("DISPLAY-FCSEL-WRAPPER-SUCCESS 4; actual original complete wrapper, real JNI float bridge; labelled environment/assertion/exception helper seams only");return 0;
}catch(const std::exception&e){std::fprintf(stderr,"display FCSEL fixture: %s\n",e.what());return 1;}}
