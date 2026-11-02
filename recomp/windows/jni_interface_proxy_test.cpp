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
int main(int argc,char **argv){
  using namespace bunker::windows;elf_image image{};Check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"strict NDK proxy fixture loads");
  if(argc>1){
    Session h(image);AndroidContext context(h.host,Config());JniInterfaceProxy adapter(h.host);auto service=h.find(kService),array=h.call(172,1,h.find("java/lang/Class"),service);std::string mode=argv[1];
    if(mode=="--wrong-profile")h.call(174,array,0,h.find("java/io/Serializable"));
    if(mode=="--null-list")array=0;
    if(mode=="--duplicate-profile")array=h.call(172,2,h.find("java/lang/Class"),service);
    if(mode=="--null-interface")h.call(174,array,0,0);
    auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,array,1});
    if(mode=="--active-service")h.run("proxy_service",{h.host.EnvAddress(),proxy,0,1});
    if(mode=="--active-toString")h.run("proxy_object",{h.host.EnvAddress(),proxy,0});
    if(mode=="--active-equals")h.run("proxy_object",{h.host.EnvAddress(),proxy,1});
    if(mode=="--active-hashCode")h.run("proxy_object",{h.host.EnvAddress(),proxy,2});
    if(mode=="--wrong-disable")h.run("proxy_disable",{h.host.EnvAddress(),h.host.NewString(u"not proxy"),1});
    if(mode=="--enabled-unload")adapter.CheckNoEnabledProxies();
    throw std::runtime_error("negative proxy boundary returned success");
  }
  for(unsigned mode=0;mode<3;++mode){
    Session h(image);AndroidContext context(h.host,Config());auto adapter=std::make_unique<JniInterfaceProxy>(h.host);
    Check(!h.run("proxy_TEST_register",{h.host.EnvAddress()})&&h.host.PendingException().empty(),"TEST bindings registered by real NDK RegisterNatives");
    Check(h.host.NativeEntry(kBridge,"delete","(J)V")==reinterpret_cast<addr_t>(elf_symbol(&image,"proxy_TEST_native_delete")),"TEST native entry is actual translated fixture, not a fake original address");
    auto service=h.find(kService),classes=h.call(172,1,h.find("java/lang/Class"),service);
    auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,mode});Check(proxy&&h.host.PendingException().empty(),"actual NDK direct/V/A factory creates backed proxy");
    Check(adapter->Inspect(proxy).handle==kHigh&&adapter->Inspect(proxy).interfaces==std::vector<std::string>{kService},"all64 handle bits and ordered exact interface snapshot preserved");
    Check(h.call(32,proxy,service)&&h.call(32,proxy,h.find("java/lang/reflect/Proxy"))&&h.call(32,proxy,h.find("java/io/Serializable")),"generated proxy has real superclass and implemented interface graph");
    auto actual=h.call(31,proxy);Check(h.call(24,h.call(10,actual),h.find("java/lang/reflect/Proxy")),"proxy direct superclass is actual reflect.Proxy");
    auto class_class=h.find("java/lang/Class"),get_loader=h.call(33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
    auto loader=h.call(34,h.find(kBridge),get_loader);Check(h.call(24,loader,h.call(34,actual,get_loader)),"proxy has actual JNIBridge application loader while service is bootstrap-visible");
    auto array=h.call(172,1,service,proxy),element=h.call(173,array,0);Check(array&&h.call(24,element,proxy),"real interface array stores backed implementing proxy");h.host.DeleteLocalReference(element);h.host.DeleteLocalReference(array);
    h.call(174,classes,0,0);Check(adapter->Inspect(proxy).interfaces==std::vector<std::string>{kService}&&h.call(32,proxy,service),"mutating caller Class[] cannot change proxy type/snapshot");
    auto global=h.host.NewGlobalReference(proxy),weak=h.call(226,proxy);h.host.DeleteLocalReference(proxy);Check(!h.call(24,weak,0),"native GlobalRef actually retains proxy after factory local is released");
    Check(!h.run("proxy_TEST_counts"),"factory/local release trigger no native invoke/delete");
    for(unsigned form=0;form<3;++form){h.run("proxy_disable",{h.host.EnvAddress(),global,form});Check(!adapter->Inspect(global).handle,"actual direct/V/A disable zeros opaque handle idempotently");h.run("proxy_disable",{h.host.EnvAddress(),0,form});}
    for(unsigned which=0;which<4;++which)for(unsigned form=0;form<3;++form){h.run("proxy_service",{h.host.EnvAddress(),global,which,form});Check(h.host.PendingException().empty(),"disabled service void callback follows proven b==0 branch");}
    std::atomic<bool> concurrent{true};std::vector<std::thread> workers;
    for(unsigned i=0;i<3;++i)workers.emplace_back([&]{State s{};addr_t env=0;s.gpr.x0.qword=h.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);h.host.InvokeVm(4,s);for(unsigned n=0;n<8;++n){h.run("proxy_disable",{env,global,1});if(adapter->Inspect(global).handle)concurrent=false;}s={};s.gpr.x0.qword=h.host.VmAddress();h.host.InvokeVm(5,s);});
    for(auto &worker:workers){worker.join();}
    Check(concurrent,"concurrent actual disabled-handler monitor access is ordered");
    adapter->CheckNoEnabledProxies();Check(!h.run("proxy_TEST_counts"),"disable/callback branch/audit never invoke native callbacks or finalizers");
    h.host.DeleteGlobalReference(global);Check(h.call(24,weak,0),"weak ledger has no hidden strong proxy root");h.call(227,weak);adapter->CheckNoEnabledProxies();adapter.reset();Check(!h.run("proxy_TEST_counts"),"adapter destruction does not call native delete");
  }
  {Session h(image);AndroidContext context(h.host,Config());auto adapter=std::make_unique<JniInterfaceProxy>(h.host);auto classes=h.call(172,1,h.find("java/lang/Class"),h.find(kService));auto proxy=h.run("proxy_factory",{h.host.EnvAddress(),kHigh,classes,0});auto weak=h.call(226,proxy);h.host.DeleteLocalReference(proxy);Check(h.call(24,weak,0),"enabled proxy can retire without a manufactured strong root");bool stopped=false;try{adapter->CheckNoEnabledProxies();}catch(const std::runtime_error &e){stopped=std::string(e.what()).find("retired while enabled")!=std::string::npos;}Check(stopped,"retired enabled handle is explicit ownership failure, never silently deleted");adapter.reset();Check(!h.run("proxy_TEST_counts"),"retired enabled payload/adapter destruction runs no native callbacks");}
  std::printf("JNI interface proxy: %u checks passed; strict NDK factory/disable direct/V/A, opaque handles, real types and passive weak lifetime audit; no native callbacks/GC claimed\n",checks.load());
}
