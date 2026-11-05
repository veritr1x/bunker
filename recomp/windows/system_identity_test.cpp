#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>
using bunker::jni::Host;
static std::atomic<unsigned>checks{0},calls{0};
static void Check(bool b,const char*s){if(!b)throw std::runtime_error(s);++checks;}
int main(){
 elf_image image{};Check(!elf_load(IDENTITY_LIBRARY,0x5f000000,nullptr,&image),"NDK identity ELF maps");
 recomp::Runtime runtime;Host h([](addr_t p){for(auto&t:kTraces)if(t.address==p)return true;return false;});h.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
 auto envcall=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);Check(h.PendingException().empty(),"host reference operation healthy");return s.gpr.x0.qword;};
 auto run=[&](const char*name,addr_t object,int form){alignas(16)std::array<unsigned char,65536>stack{};State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=object;s.gpr.x2.dword=form;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeed1230;Reg GPR::*saved[]={&GPR::x19,&GPR::x20,&GPR::x21,&GPR::x22,&GPR::x23,&GPR::x24,&GPR::x25,&GPR::x26,&GPR::x27,&GPR::x28,&GPR::x29};for(size_t i=0;i<std::size(saved);++i)(s.gpr.*saved[i]).qword=0xcafe000000000000ULL+i;auto before=s;const auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,name));++calls;runtime.Run(s,pc);Check(s.gpr.pc.qword==0xfeed1230&&s.gpr.sp.qword==before.gpr.sp.qword,"actual NDK preserves return/SP");for(auto r:saved)Check((s.gpr.*r).qword==(before.gpr.*r).qword,"actual NDK callee-saved GPR");Check(h.PendingException().empty(),"actual JNI call healthy");return s.gpr.x0.dword;};
 for(int f=0;f<3;++f)Check(run("identity_hash",0,f)==0,"null identity is zero direct/V/A");
 auto plain=h.NewInstance("java/lang/Object");auto plain_hash=run("identity_hash",plain,0);auto global=h.NewGlobalReference(plain),local=h.NewLocalReference(global),weak=envcall(226,plain);
 for(auto r:{plain,global,local,weak})for(int f=0;f<3;++f)Check(run("identity_hash",r,f)==plain_hash,"same object aliases preserve identity");
 auto cls=envcall(6,reinterpret_cast<addr_t>("java/lang/Object"));auto method=envcall(33,cls,reinterpret_cast<addr_t>("toString"),reinterpret_cast<addr_t>("()Ljava/lang/String;"));auto text=envcall(34,plain,method);auto value=h.StringValue(text);char expected[64];std::snprintf(expected,sizeof(expected),"java.lang.Object@%x",plain_hash);Check(value&&std::string(value->begin(),value->end())==expected,"identity shares actual Object.toString allocation");h.DeleteLocalReference(text);
 std::atomic<unsigned>overrides{0};h.DefineClass("TEST/IdentityOverride",{},"java/lang/Object",true);h.DefineIntMethod("TEST/IdentityOverride","hashCode","()I",[&](addr_t,const Host::MethodArguments&){++overrides;return int32_t(0x13579);});auto object=h.NewInstance("TEST/IdentityOverride");Check(run("identity_override",object,0)==0x13579&&overrides==1,"real virtual override positive control");auto ih=run("identity_hash",object,0);for(int f=0;f<3;++f)Check(run("identity_hash",object,f)==ih,"override object identity stable");Check(overrides==1,"identity bypasses virtual override");
 auto string=h.NewString(u"same content"),string2=h.NewString(u"same content"),bytes=envcall(176,4),array=envcall(172,2,cls,plain);
 for(auto r:{string,string2,bytes,array,cls}){auto hash=run("identity_hash",r,0);for(int f=1;f<3;++f)Check(run("identity_hash",r,f)==hash,"string/primitivearray/objectarray/class identity stable");}
 h.DeleteLocalReference(plain);h.DeleteLocalReference(local);Check(run("identity_hash",global,1)==plain_hash,"global root survives local deletion");
 std::thread worker([&]{State s{};addr_t e=0;s.gpr.x0.qword=h.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&e);h.InvokeVm(4,s);Check(!s.gpr.x0.dword&&e,"real worker attaches");for(int f=0;f<3;++f)Check(run("identity_hash",global,f)==plain_hash,"global identity across attached threads");s={};s.gpr.x0.qword=h.VmAddress();h.InvokeVm(5,s);Check(!s.gpr.x0.dword,"worker detaches");});worker.join();
 h.DeleteLocalReference(array);h.DeleteGlobalReference(global);Check(envcall(24,weak,0)==1,"weak root clears after final strong ownership release");envcall(227,weak);
 std::printf("SYSTEM-IDENTITY-PASS checks=%u actual_NDK_calls=%u forms=3 State=%zu Memory64=%zu override_calls=%u\n",checks.load(),calls.load(),sizeof(State),sizeof(addr_t),overrides.load());
}
