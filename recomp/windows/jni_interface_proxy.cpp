#include "jni_interface_proxy.h"
#include <cstdio>
#include <mutex>
#include <stdexcept>
namespace bunker::windows {
namespace {
constexpr const char *kBridge="bitter/jnibridge/JNIBridge";
constexpr const char *kHandler="bitter/jnibridge/JNIBridge$a";
constexpr const char *kProxy="bitter/jnibridge/HostServiceConnectionProxy";
constexpr const char *kService="android/content/ServiceConnection";
constexpr const char *kFocus="android/media/AudioManager$OnAudioFocusChangeListener";
constexpr const char *kFocusProxy="bitter/jnibridge/HostAudioFocusChangeProxy";
constexpr const char *kLocation="android/location/LocationListener";
constexpr const char *kLocationProxy="bitter/jnibridge/HostLocationListenerProxy";
constexpr const char *kFactorySignature="(J[Ljava/lang/Class;)Ljava/lang/Object;";
using Value=jni::Host::ObjectValue;
addr_t Env(jni::Host &h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);return s.gpr.x0.qword;}
void Healthy(jni::Host &h){if(!h.PendingException().empty())throw std::runtime_error("JNI interface proxy metadata/reference operation failed: "+h.PendingException());}
Value Keep(jni::Host &h,addr_t local){auto v=h.CaptureValue(local);if(local)h.DeleteLocalReference(local);return v;}
struct Passive {
  std::recursive_mutex monitor;uint64_t handle=0,generation=0;
  std::vector<std::string> interfaces;
};
struct HandlerPayload {std::shared_ptr<Passive> passive;Value monitor_object;};
struct ProxyPayload {std::shared_ptr<Passive> passive;Value handler,loader;std::vector<Value> interfaces;};
}
struct JniInterfaceProxy::State {
  jni::Host &host;std::mutex mutex;bool active=true;uint64_t next_generation=1;
  struct Entry {addr_t weak=0;std::shared_ptr<Passive> passive;};
  std::vector<Entry> ledger;
  explicit State(jni::Host &h):host(h){}
  ~State()=default; // No guest/native finalization from payload/provider destruction.
  void RequireActive(){std::lock_guard lock(mutex);if(!active)throw std::runtime_error("JNI interface proxy adapter is no longer active");}
  std::shared_ptr<ProxyPayload> Proxy(addr_t reference){
    auto payload=host.ReadHostState<ProxyPayload>(reference);Healthy(host);
    if(!payload)throw std::runtime_error("JNI interface proxy requires its actual backed proxy object");return payload;
  }
  addr_t Create(uint64_t handle,addr_t classes){
    RequireActive();
    auto bridge=Env(host,6,reinterpret_cast<addr_t>(kBridge));
    auto class_class=Env(host,6,reinterpret_cast<addr_t>("java/lang/Class"));
    auto method=Env(host,33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
    auto loader=Env(host,34,bridge,method);Healthy(host);
    std::vector<std::string> names;std::vector<Value> snapshot;
    const auto count=classes?static_cast<int32_t>(Env(host,171,classes)):-1;Healthy(host);
    for(int32_t i=0;i<count;++i){auto item=Env(host,173,classes,i);auto name=host.ClassNameValue(item);Healthy(host);names.push_back(name?*name:"<null>");snapshot.push_back(Keep(host,item));}
    std::fprintf(stderr,"JNI interface proxy: actual handle=%#llx loader=%#llx Class[] count=%d [",(unsigned long long)handle,(unsigned long long)loader,count);
    for(size_t i=0;i<names.size();++i)std::fprintf(stderr,"%s%s",i?",":"",names[i].c_str());std::fprintf(stderr,"]\n");
    const bool service_profile=names==std::vector<std::string>{kService},focus_profile=names==std::vector<std::string>{kFocus},location_profile=names==std::vector<std::string>{kLocation};
    if(!service_profile&&!focus_profile&&!location_profile)throw std::runtime_error("JNI interface proxy unsupported loader/interface profile (requires actual app loader and a supported singleton interface[])");
    const char *proxy_class=service_profile?kProxy:focus_profile?kFocusProxy:kLocationProxy,*interface_class=service_profile?kService:focus_profile?kFocus:kLocation;
    auto expected_proxy=Env(host,6,reinterpret_cast<addr_t>(proxy_class));auto proxy_loader=Env(host,34,expected_proxy,method);Healthy(host);
    const bool actual_loader=loader&&Env(host,24,loader,proxy_loader);Healthy(host);
    if(!actual_loader)throw std::runtime_error("JNI interface proxy unsupported loader/interface profile (requires actual app loader)");
    auto service=Env(host,6,reinterpret_cast<addr_t>(interface_class));auto actual=host.LocalValue(snapshot[0]);
    if(!Env(host,24,service,actual))throw std::runtime_error("JNI interface proxy interface Class identity differs");Healthy(host);
    auto passive=std::make_shared<Passive>();passive->handle=handle;passive->interfaces=names;
    {std::lock_guard lock(mutex);if(!active)throw std::runtime_error("JNI interface proxy adapter is no longer active");passive->generation=next_generation++;}
    if(!passive->generation)throw std::runtime_error("JNI interface proxy generation exhausted");
    auto monitor_class=Env(host,6,reinterpret_cast<addr_t>("java/lang/Object"));auto monitor=Env(host,172,0,monitor_class,0);Healthy(host);
    auto handler=std::make_shared<HandlerPayload>();handler->passive=passive;handler->monitor_object=Keep(host,monitor);
    auto handler_object=host.NewHostInstance(kHandler,handler);Healthy(host);
    auto payload=std::make_shared<ProxyPayload>();payload->passive=passive;payload->handler=Keep(host,handler_object);payload->loader=Keep(host,loader);payload->interfaces=std::move(snapshot);
    auto result=host.NewHostInstance(proxy_class,payload);Healthy(host);auto weak=Env(host,226,result);Healthy(host);
    {std::lock_guard lock(mutex);ledger.push_back({weak,passive});}
    for(auto local:{bridge,class_class,expected_proxy,proxy_loader,service,actual,monitor_class})if(local)host.DeleteLocalReference(local);
    return result;
  }
  void Disable(addr_t proxy){RequireActive();if(!proxy)return;auto payload=Proxy(proxy);std::lock_guard monitor(payload->passive->monitor);payload->passive->handle=0;}
  void ServiceCall(addr_t proxy,const char *name){
    RequireActive();auto payload=Proxy(proxy);uint64_t handle=0;{std::lock_guard monitor(payload->passive->monitor);handle=payload->passive->handle;}
    if(!handle)return;
    throw std::runtime_error(std::string("JNI interface proxy active ServiceConnection callback is unsupported: ")+name+"; original native/reflected Method dispatch is not ported");
  }
  void FocusCall(addr_t proxy){
    RequireActive();auto payload=Proxy(proxy);uint64_t handle=0;{std::lock_guard monitor(payload->passive->monitor);handle=payload->passive->handle;}
    if(!handle)return;
    throw std::runtime_error("JNI interface proxy active audio-focus callback is unsupported: onAudioFocusChange; original native/reflected Method dispatch is not ported");
  }
  void LocationCall(addr_t proxy,const std::string &method){
    RequireActive();auto payload=Proxy(proxy);uint64_t handle=0;{std::lock_guard monitor(payload->passive->monitor);handle=payload->passive->handle;}
    if(!handle)return;
    throw std::runtime_error("JNI interface proxy active location callback is unsupported: "+method+"; original native/reflected Method dispatch is not ported");
  }
  [[noreturn]] void ObjectCall(const char *name){RequireActive();throw std::runtime_error(std::string("JNI interface proxy Object callback is unsupported: ")+name);}
};
JniInterfaceProxy::JniInterfaceProxy(jni::Host &host):state_(std::make_shared<State>(host)){
  Healthy(host);
  host.DefineInterface("android/os/IBinder",{});
  host.DefineInterface("java/lang/reflect/InvocationHandler",{{"invoke","(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;"}});
  host.DefineClass("java/lang/reflect/Proxy",{},"java/lang/Object",true,{"java/io/Serializable"});
  host.DefineClass(kHandler,{{"<init>","(J)V"},{"a","()V"},{"finalize","()V"},{"invoke","(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;"}},"java/lang/Object",false,{"java/lang/reflect/InvocationHandler"});
  // Explicit Object declarations prevent identity/default behavior from leaking
  // through Proxy.toString/hashCode/equals. Active callbacks/defaults are unported.
  host.DefineClass(kProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kService});
  host.DefineClass(kFocusProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kFocus});
  host.DefineClass(kLocationProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kLocation});
  std::weak_ptr<State> weak=state_;
  auto get=[weak]{auto state=weak.lock();if(!state)throw std::runtime_error("JNI interface proxy adapter owner expired");return state;};
  host.BindStaticObjectMethod(kBridge,"newInterfaceProxy",kFactorySignature,[get](addr_t,const jni::Host::MethodArguments &args){return get()->Create(args[0],args[1]);});
  host.BindStaticVoidMethod(kBridge,"disableInterfaceProxy","(Ljava/lang/Object;)V",[get](addr_t,const jni::Host::MethodArguments &args){get()->Disable(args[0]);});
  for(const auto &[name,sig]:std::vector<std::pair<const char*,const char*>>{{"onServiceConnected","(Landroid/content/ComponentName;Landroid/os/IBinder;)V"},{"onServiceDisconnected","(Landroid/content/ComponentName;)V"},{"onBindingDied","(Landroid/content/ComponentName;)V"},{"onNullBinding","(Landroid/content/ComponentName;)V"}})
    host.DefineVoidMethod(kProxy,name,sig,[get,method_name=name](addr_t proxy,const jni::Host::MethodArguments&){get()->ServiceCall(proxy,method_name);});
  host.DefineVoidMethod(kFocusProxy,"onAudioFocusChange","(I)V",[get](addr_t proxy,const jni::Host::MethodArguments&){get()->FocusCall(proxy);});
  for(const auto &[name,sig]:std::vector<std::pair<const char*,const char*>>{
      {"onLocationChanged","(Landroid/location/Location;)V"},
      {"onLocationChanged","(Ljava/util/List;)V"},
      {"onFlushComplete","(I)V"},
      {"onStatusChanged","(Ljava/lang/String;ILandroid/os/Bundle;)V"},
      {"onProviderEnabled","(Ljava/lang/String;)V"},
      {"onProviderDisabled","(Ljava/lang/String;)V"}})
    host.DefineVoidMethod(kLocationProxy,name,sig,[get,method_name=std::string(name)+sig](addr_t proxy,const jni::Host::MethodArguments&){get()->LocationCall(proxy,method_name);});
  for(const char *proxy_class:{kProxy,kFocusProxy,kLocationProxy}){
    host.DefineObjectMethod(proxy_class,"toString","()Ljava/lang/String;",[get](addr_t,const jni::Host::MethodArguments&)->addr_t{get()->ObjectCall("toString");});
    host.DefineBooleanMethod(proxy_class,"equals","(Ljava/lang/Object;)Z",[get](addr_t,const jni::Host::MethodArguments&)->bool{get()->ObjectCall("equals");});
  }
}
JniInterfaceProxy::~JniInterfaceProxy(){if(state_){std::vector<State::Entry> retired;{std::lock_guard lock(state_->mutex);state_->active=false;retired.swap(state_->ledger);}for(auto &entry:retired)if(entry.weak)Env(state_->host,227,entry.weak);}}
JniInterfaceProxy::Snapshot JniInterfaceProxy::Inspect(addr_t proxy)const{
  state_->RequireActive();auto payload=state_->Proxy(proxy);std::lock_guard monitor(payload->passive->monitor);return {payload->passive->handle,payload->passive->interfaces};
}
void JniInterfaceProxy::CheckNoEnabledProxies()const{
  state_->RequireActive();std::vector<State::Entry> snapshot;{std::lock_guard lock(state_->mutex);snapshot=state_->ledger;}
  for(const auto &entry:snapshot){uint64_t handle=0;{std::lock_guard monitor(entry.passive->monitor);handle=entry.passive->handle;}if(handle){const bool expired=Env(state_->host,24,entry.weak,0);Healthy(state_->host);throw std::runtime_error(expired?"JNI interface proxy retired while enabled; original native ownership is unresolved":"JNI interface proxy remains enabled before unload; original native owner must disable it");}}
}
}
