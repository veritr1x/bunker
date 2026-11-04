#include "reflection_launch_epoch.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <limits>
#include <stdexcept>
using namespace bunker::windows;
namespace {
unsigned checks;
void Check(bool value,const char*why){if(!value)throw std::runtime_error(why);++checks;}
struct Session {
  recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};
  alignas(16)std::array<uint8_t,65536> stack{};elf_image&image;
  explicit Session(elf_image&i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
  void Catalog(bool is_static=true,bool is_native=false){host.DefineClass("com/unity3d/player/ReflectionHelper",{{"endUnityLaunch","()V",is_static,is_native},{"a","()J",true,false},{"newProxyInstance","(J[Ljava/lang/Class;)Ljava/lang/Object;",true,false}});}
  addr_t Env(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t Find(){return Env(6,reinterpret_cast<addr_t>("com/unity3d/player/ReflectionHelper"));}
  addr_t Method(addr_t owner,const char*name="endUnityLaunch",const char*signature="()V"){return Env(113,owner,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(signature));}
  void End(addr_t owner,addr_t method,unsigned mode){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=owner;s.gpr.x2.qword=method;s.gpr.x3.qword=mode;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"reflection_launch_end")));Check(s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff,"actual NDK caller preserves SP and returns");}
};
}
int main(){
  using reflection_launch_detail::NextBits;
  Check(NextBits(0)==1,"zero increments to one");
  Check(NextBits(UINT64_MAX)==0,"Java long wraps modulo 2^64");
  Check(NextBits(0x7fffffffffffffffULL)==0x8000000000000000ULL,"signed boundary preserves bits");
  elf_image image{};Check(!elf_load(REFLECTION_EPOCH_IMAGE,0x73000000,nullptr,&image),"actual NDK fixture image loads");
  for(unsigned bad=0;bad<3;++bad){Session h(image);if(bad)h.Catalog(bad!=1,bad==2);bool rejected=false;try{ReflectionLaunchEpoch epoch(h.host);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"binding requires existing nonnative static declaration");}
  Session first(image),second(image);first.Catalog();second.Catalog();ReflectionLaunchEpoch epoch(first.host),other(second.host);
  Check(epoch.Inspect()==0&&other.Inspect()==0,"independent Hosts begin with default zero epoch");
  auto owner=first.Find(),method=first.Method(owner);Check(owner&&method&&first.host.PendingException().empty(),"real catalog class and checked static method ID");
  for(unsigned mode=0;mode<3;++mode){first.End(owner,method,mode);Check(first.host.PendingException().empty()&&epoch.Inspect()==mode+1,"actual NDK direct V A performs real retained epoch increment");Check(other.Inspect()==0,"end in one Host leaves other Host unchanged");}
  bool duplicate=false;try{ReflectionLaunchEpoch repeated(first.host);}catch(const std::invalid_argument&){duplicate=true;}Check(duplicate&&epoch.Inspect()==3,"duplicate owner binding rejected without resetting existing epoch");
  first.End(owner,method,2);Check(epoch.Inspect()==4&&first.host.PendingException().empty(),"next explicit original method call advances retained epoch");
  auto accessor=first.Method(owner,"a","()J");State attempt{};attempt.gpr.x0.qword=first.host.EnvAddress();attempt.gpr.x1.qword=owner;attempt.gpr.x2.qword=accessor;bool unsupported=false;try{first.host.InvokeEnv(132,attempt);}catch(const std::runtime_error&){unsupported=true;}Check(unsupported,"unported static epoch accessor remains unsupported");
  first.host.ClearException();Check(!first.Env(144,owner,reinterpret_cast<addr_t>("b"),reinterpret_cast<addr_t>("J"))&&first.host.PendingException().find("NoSuchFieldError")!=std::string::npos,"no unbacked static long field metadata fabricated");first.host.ClearException();
  auto class_class=first.Env(6,reinterpret_cast<addr_t>("java/lang/Class"));
  auto get_loader=first.Env(33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  auto loader=first.Env(34,owner,get_loader),name=first.host.NewString(u"com.unity3d.player.ReflectionHelper");
  auto for_name=first.Env(113,class_class,reinterpret_cast<addr_t>("forName"),reinterpret_cast<addr_t>("(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;"));
  std::array<uint64_t,3> args{{name,1,loader}};
  Check(!first.Env(116,class_class,for_name,reinterpret_cast<addr_t>(args.data()))&&first.host.PendingException().find("Java class initialization is not implemented")!=std::string::npos,"end-method binding does not claim the independent reflection cache clinit");first.host.ClearException();
  // The method binding retains its epoch state after the configuration handle
  // is destroyed; no provider-destructor finalizer or Java callback runs.
  Session retired(image);retired.Catalog();auto retiring=std::make_unique<ReflectionLaunchEpoch>(retired.host);auto rc=retired.Find(),rm=retired.Method(rc);retiring.reset();retired.End(rc,rm,1);Check(retired.host.PendingException().empty(),"Host method retains live epoch owner after handle retirement");
  std::printf("REFLECTION-LAUNCH-EPOCH-PASS checks=%u actual_NDK_direct_V_A=1 modulo_wrap=1 proxy_dispatch_unimplemented=1\n",checks);
}
