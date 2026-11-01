#include "combined_java_class.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <atomic>
#include <cstdio>
#include <stdexcept>
#include <thread>
using bunker::jni::Host;
namespace{
size_t checks=0;void Check(bool v,const char*why){++checks;if(!v)throw std::runtime_error(why);}
addr_t J(Host&h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);return s.gpr.x0.qword;}
void Attach(Host&h){addr_t env=0;State s{};s.gpr.x0.qword=h.VmAddress();s.gpr.x1.qword=(addr_t)&env;h.InvokeVm(4,s);if(s.gpr.x0.qword||!env)throw std::runtime_error("attach");}
}
int main(){
 recomp::Runtime r;r.AddTraces(kTraces,std::size(kTraces));Host h([](addr_t){return false;});h.Install(r);
 h.DefineClass("profile/Base");h.DefineClass("profile/Child",{},"profile/Base");
 h.ThrowException("java/lang/IllegalStateException",u"preserve");auto pending=J(h,15);bool reject=false;
 try{bunker::windows::DefineCombinedRuntimeClass(h);}catch(const std::invalid_argument&){reject=true;}
 Check(reject&&J(h,24,pending,J(h,15)),"installation preserves pending exception identity");h.ClearException();
 bunker::windows::DefineCombinedRuntimeClass(h);
 auto object_class=J(h,6,(addr_t)"java/lang/Object"),method=J(h,33,object_class,(addr_t)"getClass",(addr_t)"()Ljava/lang/Class;");
 Check(method!=0,"actual runtime-class method metadata");
 elf_image image{};Check(!elf_load(GETCLASS_CALLER,0x5d000000,nullptr,&image),"actual NDK caller ELF");
 auto entry=(addr_t)elf_symbol(&image,"guest_find_library");Check(entry!=0,"actual NDK caller entry");
 auto run=[&](addr_t object,unsigned mode){
  alignas(16)std::array<uint8_t,65536>stack{};State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=object;s.gpr.x2.qword=method;s.gpr.x3.qword=0;s.gpr.x4.qword=mode;s.gpr.sp.qword=(addr_t)(stack.data()+stack.size());s.gpr.x30.qword=0xfeedfff0;r.Run(s,entry);return s.gpr.x0.qword;
 };
 // Reuse the independently translated NDK direct/V/A/stack-V caller. The
 // getClass descriptor has zero arguments; its spare argument is never read.
 for(auto receiver:{h.NewInstance("profile/Child"),h.NewString(u"text"),J(h,6,(addr_t)"profile/Base"),h.NewInstance("java/lang/ClassLoader")}){
  auto actual=J(h,31,receiver);
  for(unsigned mode=0;mode<4;++mode){auto result=run(receiver,mode);Check(result&&J(h,24,result,actual),"NDK getClass preserves exact receiver runtime-class identity");Check(J(h,232,result)==1,"returned class is caller-local");h.DeleteLocalReference(result);}
  h.DeleteLocalReference(actual);h.DeleteLocalReference(receiver);
 }
 for(unsigned mode=0;mode<4;++mode){Check(!run(0,mode)&&!h.PendingException().empty(),"null receiver rejected");h.ClearException();}
 auto stale=h.NewInstance("profile/Base");h.DeleteLocalReference(stale);Check(!run(stale,0)&&!h.PendingException().empty(),"stale receiver rejected");h.ClearException();
 auto original=h.NewInstance("profile/Child"),global=h.NewGlobalReference(original),clazz=h.NewGlobalReference(J(h,31,original));
 std::atomic<unsigned>ok{0};std::vector<std::thread>threads;
 for(unsigned i=0;i<4;++i)threads.emplace_back([&]{Attach(h);for(unsigned n=0;n<64;++n){auto result=run(global,n%4);if(result&&J(h,24,result,clazz)&&J(h,232,result)==1)++ok;h.DeleteLocalReference(result);}State s{};s.gpr.x0.qword=h.VmAddress();h.InvokeVm(5,s);});
 for(auto&t:threads)t.join();Check(ok==256,"concurrent worker-local returns from stable cached global classes");
 h.DeleteGlobalReference(global);h.DeleteGlobalReference(clazz);
 std::printf("%zu runtime-class adapter checks +256 concurrent actual NDK calls passed\n",checks);
}
