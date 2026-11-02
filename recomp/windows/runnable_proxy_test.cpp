#include "jni_interface_proxy.h"
#include "android_context.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "sample.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <memory>
#include <stdexcept>
namespace {
constexpr const char *kBridge="bitter/jnibridge/JNIBridge";
constexpr const char *kRunnable="java/lang/Runnable";
constexpr const char *kOld[]={"android/content/ServiceConnection","android/media/AudioManager$OnAudioFocusChangeListener","android/location/LocationListener"};
constexpr uint64_t kHigh=UINT64_C(0xf123456789abcdef);
std::atomic<unsigned> checks{0};
void Check(bool value,const char *message){if(!value)throw std::runtime_error(message);++checks;}
struct Session {
 recomp::Runtime runtime;bunker::jni::Host host{[](addr_t pc){return std::any_of(std::begin(kTraces),std::end(kTraces),[pc](auto &x){return x.address==pc;});}};elf_image &image;
 explicit Session(elf_image &i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));host.DefineClass(kBridge,{{"newInterfaceProxy","(J[Ljava/lang/Class;)Ljava/lang/Object;",true,false},{"disableInterfaceProxy","(Ljava/lang/Object;)V",true,false},{"invoke","(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;",true,true},{"delete","(J)V",true,true}});}
 addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
 addr_t find(const char *name){return call(6,reinterpret_cast<addr_t>(name));}
 addr_t run(const char *name,std::initializer_list<addr_t> args={}){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6};size_t n=0;for(auto a:args)(s.gpr.*r[n++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"strict NDK Runnable caller preserves PC/SP");return s.gpr.x0.qword;}
};
bunker::windows::AndroidContextConfig Config(){bunker::windows::AndroidContextConfig c;c.package_name=kPackageName;c.target_sdk=kTargetSdk;c.activity_class=kLaunchActivity;return c;}
}
int main(int argc,char **argv){try{
 using namespace bunker::windows;elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK Runnable fixture loads");
 if(argc>1){Session h(image);AndroidContext context(h.host,Config());auto adapter=std::make_unique<JniInterfaceProxy>(h.host);std::string mode=argv[1];auto runnable=h.find(kRunnable),classes=h.call(172,1,h.find("java/lang/Class"),runnable);
  if(mode.rfind("--mixed-",0)==0){unsigned which=static_cast<unsigned>(mode.back()-'0');Check(which<3,"negative mixed profile index");classes=h.call(172,2,h.find("java/lang/Class"),runnable);h.call(174,classes,1,h.find(kOld[which]));}
  if(mode=="--duplicate-runnable")classes=h.call(172,2,h.find("java/lang/Class"),runnable);
  auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,1});
  if(mode.rfind("--active-",0)==0)h.run("runnable_callback",{h.host.EnvAddress(),proxy,static_cast<unsigned>(mode[9]-'0'),static_cast<unsigned>(mode[11]-'0')});
  if(mode=="--enabled-unload")adapter->CheckNoEnabledProxies();
  if(mode=="--retired-enabled"){h.host.DeleteLocalReference(proxy);adapter->CheckNoEnabledProxies();}
  if(mode=="--expired-owner"){h.run("proxy_disable",{h.host.EnvAddress(),proxy,0});adapter.reset();h.run("runnable_callback",{h.host.EnvAddress(),proxy,0,1});}
  if(mode.rfind("--object-",0)==0){h.run("proxy_disable",{h.host.EnvAddress(),proxy,0});h.run("proxy_object",{h.host.EnvAddress(),proxy,static_cast<unsigned>(mode.back()-'0')});}
  throw std::runtime_error("negative Runnable boundary returned success");
 }
 for(unsigned mode=0;mode<3;++mode){Session h(image);AndroidContext context(h.host,Config());
  Check(!h.find(kRunnable)&&h.host.PendingException().find("NoClassDefFoundError")!=std::string::npos,"Runnable metadata is supplied by proxy adapter, not Context/core");h.host.ClearException();
  auto adapter=std::make_unique<JniInterfaceProxy>(h.host);
  Check(h.run("runnable_interface_metadata",{h.host.EnvAddress()})==63&&h.host.PendingException().empty(),"actual NDK sees true abstract run()V interface without superclass or constructor");
  Check(!h.run("proxy_TEST_register",{h.host.EnvAddress()}),"actual labelled TEST native registration");
  auto runnable=h.find(kRunnable),classes=h.call(172,1,h.find("java/lang/Class"),runnable),proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,mode});
  Check(proxy&&h.host.PendingException().empty(),"actual NDK direct/V/A creates exact singleton Runnable proxy");
  Check(adapter->Inspect(proxy).handle==kHigh&&adapter->Inspect(proxy).interfaces==std::vector<std::string>{kRunnable},"opaque full64 handle and ordered Runnable snapshot preserved");
  Check(h.call(32,proxy,runnable)&&h.call(32,proxy,h.find("java/lang/reflect/Proxy"))&&h.call(32,proxy,h.find("java/io/Serializable")),"Runnable proxy has actual interface/Proxy/Serializable graph");
  auto actual=h.call(31,proxy),class_class=h.find("java/lang/Class"),get_loader=h.call(33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto loader=h.call(34,h.find(kBridge),get_loader);
  auto boot_loader=h.call(34,runnable,get_loader);
  Check(loader&&h.call(24,loader,h.call(34,actual,get_loader))&&boot_loader&&!h.call(24,loader,boot_loader)&&h.call(24,boot_loader,h.call(34,h.find("java/lang/Object"),get_loader))&&h.call(24,h.call(10,actual),h.find("java/lang/reflect/Proxy")),"generated proxy uses actual app loader; Runnable has Android BootClassLoader and real Proxy superclass");
  for(const char *other:kOld){auto type=h.find(other),list=h.call(172,1,h.find("java/lang/Class"),type),old_proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,list,mode});
   Check(h.call(32,old_proxy,type)&&!h.call(32,old_proxy,runnable)&&!h.call(32,proxy,type)&&!h.call(24,actual,h.call(31,old_proxy)),"all three old profiles retain distinct Class identities and exclusive interface graphs");
   Check(!h.call(33,h.call(31,old_proxy),reinterpret_cast<addr_t>("run"),reinterpret_cast<addr_t>("()V"))&&h.host.PendingException().find("NoSuchMethodError")!=std::string::npos,"old profile has no added run method");h.host.ClearException();
   h.run("proxy_disable",{h.host.EnvAddress(),old_proxy,mode});h.host.DeleteLocalReference(old_proxy);h.host.DeleteLocalReference(list);
  }
  auto typed=h.call(172,1,runnable,proxy),element=h.call(173,typed,0);Check(typed&&h.call(24,element,proxy),"real Runnable[] accepts its backed proxy");h.host.DeleteLocalReference(element);h.host.DeleteLocalReference(typed);
  h.call(174,classes,0,h.find(kOld[0]));Check(adapter->Inspect(proxy).interfaces==std::vector<std::string>{kRunnable}&&h.call(32,proxy,runnable),"caller Class[] mutation cannot change captured Runnable profile");
  auto global=h.host.NewGlobalReference(proxy),weak=h.call(226,proxy);h.host.DeleteLocalReference(proxy);
  Check(!h.call(24,weak,0)&&!h.run("proxy_TEST_counts"),"actual native GlobalRef retains proxy without any invoke/delete call");
  for(unsigned disable=0;disable<3;++disable){h.run("proxy_disable",{h.host.EnvAddress(),global,disable});Check(!adapter->Inspect(global).handle,"direct/V/A disable idempotently zeros actual handler");
   for(unsigned form=0;form<3;++form)for(unsigned interface_method=0;interface_method<2;++interface_method)
    Check(h.run("runnable_callback",{h.host.EnvAddress(),global,form,interface_method})==UINT64_C(0xfedcba9876543210)&&h.host.PendingException().empty(),"disabled run()V through actual interface/concrete direct/V/A is void and preserves unused arguments/canaries");
  }
  adapter->CheckNoEnabledProxies();Check(!h.run("proxy_TEST_counts"),"disabled run and ownership audit invoke no native body or finalizer");h.host.DeleteGlobalReference(global);
  Check(h.call(24,weak,0),"passive weak ledger does not root retired Runnable proxy");h.call(227,weak);
  auto weak_proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,h.call(172,1,class_class,runnable),mode}),weak_only=h.call(226,weak_proxy);
  h.run("proxy_disable",{h.host.EnvAddress(),weak_proxy,mode});h.host.DeleteLocalReference(weak_proxy);Check(h.call(24,weak_only,0),"native weak owner does not become an adapter strong root");h.call(227,weak_only);
  auto zero=h.run("proxy_factory",{h.host.EnvAddress(),0,h.call(172,1,class_class,runnable),mode});Check(!adapter->Inspect(zero).handle&&h.run("runnable_callback",{h.host.EnvAddress(),zero,mode,1})==UINT64_C(0xfedcba9876543210),"actual zero-handle factory follows original disabled branch");h.host.DeleteLocalReference(zero);
  adapter->CheckNoEnabledProxies();adapter.reset();Check(!h.run("proxy_TEST_counts"),"proxy/adapter retirement causes no native finalizer");
 }
 std::printf("Runnable proxy: %u checks; actual NDK metadata/factory/disable/run direct,V,A; distinct singleton, real loader and global/weak lifetimes; no active dispatch/UI/thread/events claimed\n",checks.load());
}catch(const std::exception &error){std::fprintf(stderr,"Runnable proxy: %s\n",error.what());return 1;}}
