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
#include <thread>
namespace {
constexpr const char *kBridge="bitter/jnibridge/JNIBridge";
constexpr const char *kService="android/content/ServiceConnection";
constexpr const char *kFocus="android/media/AudioManager$OnAudioFocusChangeListener";
constexpr uint64_t kHigh=UINT64_C(0xf123456789abcdef);
std::atomic<unsigned> checks{0};
void Check(bool value,const char *message){if(!value)throw std::runtime_error(message);++checks;}
struct Session {
  recomp::Runtime runtime;bunker::jni::Host host{[](addr_t pc){return std::any_of(std::begin(kTraces),std::end(kTraces),[pc](auto &x){return x.address==pc;});}};elf_image &image;
  explicit Session(elf_image &i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));host.DefineClass(kBridge,{{"newInterfaceProxy","(J[Ljava/lang/Class;)Ljava/lang/Object;",true,false},{"disableInterfaceProxy","(Ljava/lang/Object;)V",true,false},{"invoke","(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;",true,true},{"delete","(J)V",true,true}});}
  addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t find(const char *name){return call(6,reinterpret_cast<addr_t>(name));}
  addr_t run(const char *name,std::initializer_list<addr_t> args={}){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6};size_t n=0;for(auto a:args)(s.gpr.*r[n++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"strict NDK proxy caller preserves PC/SP");return s.gpr.x0.qword;}
};
bunker::windows::AndroidContextConfig Config(){bunker::windows::AndroidContextConfig c;c.package_name=kPackageName;c.target_sdk=kTargetSdk;c.activity_class=kLaunchActivity;return c;}
}
int main(int argc,char **argv){try{
 using namespace bunker::windows;elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK audio-focus fixture loads");
 if(argc>1){Session h(image);AndroidContext context(h.host,Config());JniInterfaceProxy adapter(h.host);std::string mode=argv[1];auto focus=h.find(kFocus),classes=h.call(172,1,h.find("java/lang/Class"),focus);
  if(mode=="--mixed-profile"){classes=h.call(172,2,h.find("java/lang/Class"),focus);h.call(174,classes,1,h.find(kService));}
  if(mode=="--duplicate-focus")classes=h.call(172,2,h.find("java/lang/Class"),focus);
  auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,1});
  if(mode.rfind("--active-focus-",0)==0)h.run("focus_callback",{h.host.EnvAddress(),proxy,UINT32_C(0xffffffff),static_cast<addr_t>(mode.back()-'0')});
  if(mode=="--enabled-focus-unload")adapter.CheckNoEnabledProxies();
  throw std::runtime_error("negative audio-focus boundary returned success");
 }
 for(unsigned mode=0;mode<3;++mode){Session h(image);AndroidContext context(h.host,Config());auto adapter=std::make_unique<JniInterfaceProxy>(h.host);
  Check(h.run("focus_interface_metadata",{h.host.EnvAddress()})==31&&h.host.PendingException().empty(),"actual NDK listener is an interface with null superclass, exact abstract callback and no instantiation");
  Check(!h.run("proxy_TEST_register",{h.host.EnvAddress()})&&h.host.PendingException().empty(),"actual labelled TEST native registrations install");
  auto focus=h.find(kFocus),service=h.find(kService),classes=h.call(172,1,h.find("java/lang/Class"),focus);
  auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,mode});Check(proxy&&h.host.PendingException().empty(),"actual NDK direct/V/A factory creates exact focus profile");
  Check(adapter->Inspect(proxy).handle==kHigh&&adapter->Inspect(proxy).interfaces==std::vector<std::string>{kFocus},"actual ordered singleton snapshot and all64 native handle bits retained");
  Check(h.call(32,proxy,focus)&&!h.call(32,proxy,service)&&h.call(32,proxy,h.find("java/lang/reflect/Proxy"))&&h.call(32,proxy,h.find("java/io/Serializable")),"audio proxy implements only its exact interface with genuine Proxy superclass");
  auto service_classes=h.call(172,1,h.find("java/lang/Class"),service),service_proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,service_classes,mode});Check(h.call(32,service_proxy,service)&&!h.call(32,service_proxy,focus),"existing ServiceConnection proxy remains a separate class and interface graph");
  auto actual=h.call(31,proxy),service_actual=h.call(31,service_proxy);Check(!h.call(24,actual,service_actual)&&h.call(24,h.call(10,actual),h.find("java/lang/reflect/Proxy")),"profiles have distinct generated Class identities");
  auto class_class=h.find("java/lang/Class"),get_loader=h.call(33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto loader=h.call(34,h.find(kBridge),get_loader);Check(h.call(24,loader,h.call(34,actual,get_loader)),"audio proxy preserves actual JNIBridge application loader");
  auto typed=h.call(172,1,focus,proxy),element=h.call(173,typed,0);Check(typed&&h.call(24,element,proxy),"real audio-listener array accepts the backed proxy");h.host.DeleteLocalReference(element);h.host.DeleteLocalReference(typed);
  Check(!h.call(172,1,service,proxy)&&h.host.PendingException().find("ArrayStoreException")!=std::string::npos,"audio proxy cannot enter a ServiceConnection array");h.host.ClearException();
  h.call(174,classes,0,service);Check(adapter->Inspect(proxy).interfaces==std::vector<std::string>{kFocus}&&h.call(32,proxy,focus),"mutated caller Class[] cannot change retained audio profile");
  auto global=h.host.NewGlobalReference(proxy),weak=h.call(226,proxy);h.host.DeleteLocalReference(proxy);Check(!h.call(24,weak,0),"actual native GlobalRef owns audio proxy after factory local release");Check(!h.run("proxy_TEST_counts"),"audio proxy creation invokes no native callback/finalizer");
  h.run("proxy_disable",{h.host.EnvAddress(),service_proxy,mode});h.host.DeleteLocalReference(service_proxy);
  for(unsigned form=0;form<3;++form){h.run("proxy_disable",{h.host.EnvAddress(),global,form});Check(!adapter->Inspect(global).handle,"actual direct/V/A disable zeros audio handler idempotently");for(int32_t value:{0,1,-1,3,-3,INT32_MIN,INT32_MAX})Check(h.run("focus_callback",{h.host.EnvAddress(),global,static_cast<uint32_t>(value),form})==UINT64_C(0xfedcba9876543210)&&h.host.PendingException().empty(),"disabled audio void callback consumes actual jint without native effect");}
  adapter->CheckNoEnabledProxies();Check(!h.run("proxy_TEST_counts"),"disabled callback and lifetime audit never invoke labelled native handlers");h.host.DeleteGlobalReference(global);Check(h.call(24,weak,0),"audio weak ledger holds no manufactured strong proxy root");h.call(227,weak);adapter.reset();Check(!h.run("proxy_TEST_counts"),"audio proxy/provider destruction performs no native finalizer");
 }
 std::printf("Audio-focus interface proxy: %u checks; actual NDK metadata/factory/disable/int callback direct,V,A, distinct exact types and weak lifetime; no focus request, event, gain or native dispatch claimed\n",checks.load());
}catch(const std::exception &error){std::fprintf(stderr,"audio-focus proxy: %s\n",error.what());return 1;}}
