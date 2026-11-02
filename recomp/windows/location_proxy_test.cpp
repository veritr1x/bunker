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
constexpr const char *kLocation="android/location/LocationListener";
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
 using namespace bunker::windows;elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK LocationListener fixture loads");
 if(argc>1){Session h(image);AndroidContext context(h.host,Config());JniInterfaceProxy adapter(h.host);std::string mode=argv[1];auto listener=h.find(kLocation),classes=h.call(172,1,h.find("java/lang/Class"),listener);
  if(mode=="--mixed-service"||mode=="--mixed-audio"){classes=h.call(172,2,h.find("java/lang/Class"),listener);h.call(174,classes,1,h.find(mode=="--mixed-service"?kService:kFocus));}
  if(mode=="--duplicate-location")classes=h.call(172,2,h.find("java/lang/Class"),listener);
  auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,1});
  if(mode.rfind("--active-",0)==0){unsigned which=static_cast<unsigned>(mode[9]-'0'),form=static_cast<unsigned>(mode[11]-'0');auto provider=which>=3?h.host.NewString(u"TEST-provider"):0;h.run("location_callback",{h.host.EnvAddress(),proxy,which,provider,UINT32_MAX,0,form});}
  if(mode=="--enabled-location-unload")adapter.CheckNoEnabledProxies();throw std::runtime_error("negative LocationListener boundary returned success");
 }
 for(unsigned mode=0;mode<3;++mode){Session h(image);AndroidContext context(h.host,Config());auto adapter=std::make_unique<JniInterfaceProxy>(h.host);
  Check(h.run("location_interface_metadata",{h.host.EnvAddress()})==63&&h.host.PendingException().empty(),"actual NDK sees true six-method LocationListener, no superclass/instantiation and ordinary Location metadata");
  Check(!h.run("proxy_TEST_register",{h.host.EnvAddress()}),"actual labelled TEST native registration");
  auto location=h.find("android/location/Location");Check(!h.call(33,location,reinterpret_cast<addr_t>("getLatitude"),reinterpret_cast<addr_t>("()D"))&&h.host.PendingException().find("NoSuchMethodError")!=std::string::npos,"Location argument metadata provides no invented coordinate accessor");h.host.ClearException();
  Check(!h.call(33,location,reinterpret_cast<addr_t>("<init>"),reinterpret_cast<addr_t>("(Ljava/lang/String;)V"))&&h.host.PendingException().find("NoSuchMethodError")!=std::string::npos,"Location constructor/state is not fabricated");h.host.ClearException();
  auto listener=h.find(kLocation),classes=h.call(172,1,h.find("java/lang/Class"),listener),proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,mode});Check(proxy&&h.host.PendingException().empty(),"actual NDK direct/V/A creates exact singleton LocationListener proxy");
  Check(adapter->Inspect(proxy).handle==kHigh&&adapter->Inspect(proxy).interfaces==std::vector<std::string>{kLocation},"raw64 owner and exact ordered location interface snapshot retained");
  Check(h.call(32,proxy,listener)&&!h.call(32,proxy,h.find(kService))&&!h.call(32,proxy,h.find(kFocus))&&h.call(32,proxy,h.find("java/lang/reflect/Proxy"))&&h.call(32,proxy,h.find("java/io/Serializable")),"location proxy implements only its exact interface");
  auto actual=h.call(31,proxy),class_class=h.find("java/lang/Class"),get_loader=h.call(33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));auto loader=h.call(34,h.find(kBridge),get_loader);Check(h.call(24,loader,h.call(34,actual,get_loader))&&h.call(24,h.call(10,actual),h.find("java/lang/reflect/Proxy")),"actual app loader and Proxy superclass retained");
  for(const char *other:{kService,kFocus}){auto type=h.find(other),list=h.call(172,1,h.find("java/lang/Class"),type),old_proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,list,mode});Check(h.call(32,old_proxy,type)&&!h.call(32,old_proxy,listener)&&!h.call(24,actual,h.call(31,old_proxy)),"old profiles retain exclusive interface and Class identities");h.run("proxy_disable",{h.host.EnvAddress(),old_proxy,mode});h.host.DeleteLocalReference(old_proxy);h.host.DeleteLocalReference(list);}
  auto typed=h.call(172,1,listener,proxy),element=h.call(173,typed,0);Check(typed&&h.call(24,element,proxy),"real LocationListener array accepts backed proxy");h.host.DeleteLocalReference(element);h.host.DeleteLocalReference(typed);
  h.call(174,classes,0,h.find(kService));Check(adapter->Inspect(proxy).interfaces==std::vector<std::string>{kLocation},"caller Class[] mutation cannot change location profile");
  auto global=h.host.NewGlobalReference(proxy),weak=h.call(226,proxy);h.host.DeleteLocalReference(proxy);Check(!h.call(24,weak,0)&&!h.run("proxy_TEST_counts"),"native GlobalRef retains actual proxy without native callback/delete");auto provider=h.host.NewGlobalReference(h.host.NewString(u"TEST-provider"));
  for(unsigned form=0;form<3;++form){h.run("proxy_disable",{h.host.EnvAddress(),global,form});Check(!adapter->Inspect(global).handle,"direct/V/A disable zeros location handler");
   for(unsigned which=0;which<6;++which){for(int32_t value:{0,-1,INT32_MIN,INT32_MAX}){auto first=which>=3?provider:0;Check(h.run("location_callback",{h.host.EnvAddress(),global,which,first,static_cast<uint32_t>(value),0,form})==UINT64_C(0xfedcba9876543210)&&h.host.PendingException().empty(),"all six disabled void callbacks preserve actual direct/V/A arguments and canaries without defaults/events");}}
   Check(h.run("location_callback",{h.host.EnvAddress(),global,0,provider,0,0,form})==UINT64_C(0xfedcba9876543210)&&h.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"String cannot masquerade as a Location argument even on disabled profile");h.host.ClearException();
  }
  adapter->CheckNoEnabledProxies();Check(!h.run("proxy_TEST_counts"),"disabled callbacks and ownership audit cause no native dispatch or finalization");h.host.DeleteGlobalReference(global);Check(h.call(24,weak,0),"weak location ledger holds no hidden strong proxy root");h.call(227,weak);h.host.DeleteGlobalReference(provider);adapter.reset();Check(!h.run("proxy_TEST_counts"),"location adapter teardown causes no native finalizer");
 }
 std::printf("LocationListener proxy: %u checks; actual NDK six-method metadata/factory/disable/callback direct,V,A, distinct types and weak lifetime; no GPS/provider/coordinates/default dispatch claimed\n",checks.load());
}catch(const std::exception &error){std::fprintf(stderr,"LocationListener proxy: %s\n",error.what());return 1;}}
