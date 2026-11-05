#include <cfenv>
#include "jni_interface_proxy.h"
#include <cerrno>
#include <cstdio>
#include <mutex>
#include <stdexcept>
#include <utility>
#ifdef _WIN32
#include <windows.h>
#endif
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
constexpr const char *kRunnable="java/lang/Runnable";
constexpr const char *kRunnableProxy="bitter/jnibridge/HostRunnableProxy";
constexpr const char *kMessageCallback="android/os/Handler$Callback";
constexpr const char *kFrameCallback="android/view/Choreographer$FrameCallback";
constexpr const char *kChoreographerProxy="bitter/jnibridge/HostChoreographerProxy";
constexpr const char *kMessageProxy="bitter/jnibridge/HostHandlerCallbackProxy";
constexpr const char *kInvokeSignature="(JLjava/lang/Class;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;";
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
struct CallbackLong {int64_t value;};
struct CallbackBoolean {bool value;};
struct Environment {
#ifdef _WIN32
  DWORD error=GetLastError();
#endif
  int saved_errno=errno;fenv_t floating{};
  Environment(){std::fegetenv(&floating);}
  ~Environment(){std::fesetenv(&floating);errno=saved_errno;
#ifdef _WIN32
    SetLastError(error);
#endif
  }
};
bool ClassExists(jni::Host& host,const char* name){
  const auto clazz=Env(host,6,reinterpret_cast<addr_t>(name));
  if(clazz){host.DeleteLocalReference(clazz);Healthy(host);return true;}
  const auto error=host.PendingException();
  if(error!="java/lang/NoClassDefFoundError: "+std::string(name))throw std::runtime_error("unexpected callback boxing class-lookup failure: "+error);
  host.ClearException();return false;
}
}
struct JniInterfaceProxy::State {
  jni::Host &host;Config config;std::mutex mutex;bool active=true;uint64_t next_generation=1;
  struct Entry {addr_t weak=0;std::shared_ptr<Passive> passive;};
  std::vector<Entry> ledger;
  State(jni::Host &h,Config c):host(h),config(std::move(c)){}
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
    const bool service_profile=names==std::vector<std::string>{kService},focus_profile=names==std::vector<std::string>{kFocus},location_profile=names==std::vector<std::string>{kLocation},runnable_profile=names==std::vector<std::string>{kRunnable};
    const bool choreographer_profile=config.run_native&&names==std::vector<std::string>{kMessageCallback,kFrameCallback};
    const bool message_profile=config.run_native&&names==std::vector<std::string>{kMessageCallback};
    if(!service_profile&&!focus_profile&&!location_profile&&!runnable_profile&&!choreographer_profile&&!message_profile)throw std::runtime_error("JNI interface proxy unsupported loader/interface profile (requires actual app loader and an exact supported interface[])");
    const char *proxy_class=service_profile?kProxy:focus_profile?kFocusProxy:location_profile?kLocationProxy:runnable_profile?kRunnableProxy:choreographer_profile?kChoreographerProxy:kMessageProxy;
    const char *interface_class=service_profile?kService:focus_profile?kFocus:location_profile?kLocation:runnable_profile?kRunnable:kMessageCallback;
    auto expected_proxy=Env(host,6,reinterpret_cast<addr_t>(proxy_class));auto proxy_loader=Env(host,34,expected_proxy,method);Healthy(host);
    const bool actual_loader=loader&&Env(host,24,loader,proxy_loader);Healthy(host);
    if(!actual_loader)throw std::runtime_error("JNI interface proxy unsupported loader/interface profile (requires actual app loader)");
    auto service=Env(host,6,reinterpret_cast<addr_t>(interface_class));auto actual=host.LocalValue(snapshot[0]);
    if(!Env(host,24,service,actual))throw std::runtime_error("JNI interface proxy interface Class identity differs");Healthy(host);
    if(choreographer_profile){
      auto frame=Env(host,6,reinterpret_cast<addr_t>(kFrameCallback));auto supplied=host.LocalValue(snapshot[1]);
      if(!Env(host,24,frame,supplied))throw std::runtime_error("JNI interface proxy FrameCallback Class identity differs");Healthy(host);
      host.DeleteLocalReference(frame);host.DeleteLocalReference(supplied);
    }
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
  void RunnableCall(addr_t proxy){
    RequireActive();auto payload=Proxy(proxy);uint64_t handle=0;{std::lock_guard monitor(payload->passive->monitor);handle=payload->passive->handle;}
    if(!handle)return;
    throw std::runtime_error("JNI interface proxy active Runnable callback is unsupported: run()V; original native/reflected Method dispatch is not ported");
  }
  addr_t InvokeActive(addr_t proxy,const char* owner,const char* name,const char* signature,addr_t argument,bool boxed_long){
    Environment native;RequireActive();auto payload=Proxy(proxy);
    // This is the actual JNIBridge$a invocation monitor. Native invocation may
    // reenter disable on the same handler, so it must remain recursive.
    std::lock_guard monitor(payload->passive->monitor);
    if(!payload->passive->handle)return 0;
    if(!config.run_native)throw std::runtime_error("active Android callback has no original native runner");
    auto declaring=Env(host,6,reinterpret_cast<addr_t>(owner));Healthy(host);
    auto method=Env(host,33,declaring,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(signature));Healthy(host);
    auto reflected=Env(host,9,declaring,method,0);Healthy(host);
    auto object=Env(host,6,reinterpret_cast<addr_t>("java/lang/Object"));
    auto arguments=Env(host,172,1,object,0);Healthy(host);
    if(boxed_long)argument=host.NewHostInstance("java/lang/Long",std::make_shared<CallbackLong>(CallbackLong{static_cast<int64_t>(argument)}));
    Env(host,174,arguments,0,argument);Healthy(host);
    const auto entry=host.NativeEntry(kBridge,"invoke",kInvokeSignature);
    if(!entry)throw std::runtime_error("original JNIBridge.invoke is not registered");
    const auto bridge=Env(host,6,reinterpret_cast<addr_t>(kBridge));Healthy(host);
    // FromReflectedMethod in the actual registered native body recovers the
    // same real interface MethodID that its own native dispatcher cached.
    return config.run_native(entry,{host.EnvAddress(),bridge,payload->passive->handle,declaring,reflected,arguments});
  }
  bool MessageCall(addr_t proxy,addr_t message){
    Environment native;const auto result=InvokeActive(proxy,kMessageCallback,"handleMessage","(Landroid/os/Message;)Z",message,false);
    if(!host.PendingException().empty())return false; // Preserve the original throwable.
    if(!result){host.ThrowException("java/lang/NullPointerException",u"Handler.Callback proxy returned null for boolean");return false;}
    const auto clazz=Env(host,6,reinterpret_cast<addr_t>("java/lang/Boolean"));
    const auto method=Env(host,33,clazz,reinterpret_cast<addr_t>("booleanValue"),reinterpret_cast<addr_t>("()Z"));Healthy(host);
    return Env(host,37,result,method)!=0;
  }
  void FrameCall(addr_t proxy,addr_t time){Environment native;InvokeActive(proxy,kFrameCallback,"doFrame","(J)V",time,true);}
  [[noreturn]] void ObjectCall(const char *name){RequireActive();throw std::runtime_error(std::string("JNI interface proxy Object callback is unsupported: ")+name);}
};
JniInterfaceProxy::JniInterfaceProxy(jni::Host &host):JniInterfaceProxy(host,Config{}){}
JniInterfaceProxy::JniInterfaceProxy(jni::Host &host,Config config):state_(std::make_shared<State>(host,std::move(config))){
  Healthy(host);
  host.DefineInterface("android/os/IBinder",{});
  host.DefineInterface(kRunnable,{{"run","()V"}});
  host.DefineInterface("java/lang/reflect/InvocationHandler",{{"invoke","(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;"}});
  host.DefineClass("java/lang/reflect/Proxy",{},"java/lang/Object",true,{"java/io/Serializable"});
  host.DefineClass(kHandler,{{"<init>","(J)V"},{"a","()V"},{"finalize","()V"},{"invoke","(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;"}},"java/lang/Object",false,{"java/lang/reflect/InvocationHandler"});
  // Explicit Object declarations prevent identity/default behavior from leaking
  // through Proxy.toString/hashCode/equals. Active callbacks/defaults are unported.
  host.DefineClass(kProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kService});
  host.DefineClass(kFocusProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kFocus});
  host.DefineClass(kLocationProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kLocation});
  host.DefineClass(kRunnableProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kRunnable});
  if(state_->config.run_native){
    host.DefineClass(kChoreographerProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kMessageCallback,kFrameCallback});
    host.DefineClass(kMessageProxy,{{"hashCode","()I"}},"java/lang/reflect/Proxy",false,{kMessageCallback});
    if(!ClassExists(host,"java/lang/Number"))host.DefineClass("java/lang/Number",{},"java/lang/Object",true,{"java/io/Serializable"});
    if(!ClassExists(host,"java/lang/Long"))host.DefineClass("java/lang/Long",{},"java/lang/Number",true);
    if(!ClassExists(host,"java/lang/Boolean"))host.DefineClass("java/lang/Boolean",{},"java/lang/Object",true,{"java/io/Serializable"});
    host.DefineConstructor("java/lang/Boolean","(Z)V",[&host](const auto& a){Environment native;return host.NewHostInstance("java/lang/Boolean",std::make_shared<CallbackBoolean>(CallbackBoolean{(a[0]&0xff)!=0}));});
    host.DefineBooleanMethod("java/lang/Boolean","booleanValue","()Z",[&host](addr_t receiver,const auto&){Environment native;auto value=host.ReadHostState<CallbackBoolean>(receiver);Healthy(host);if(!value)throw std::runtime_error("Boolean value is outside the native callback boxing profile");return value->value;});
    host.DefineLongMethod("java/lang/Long","longValue","()J",[&host](addr_t receiver,const auto&){Environment native;auto value=host.ReadHostState<CallbackLong>(receiver);Healthy(host);if(!value)throw std::runtime_error("Long value is outside the native callback boxing profile");return value->value;});
  }
  std::weak_ptr<State> weak=state_;
  auto get=[weak]{auto state=weak.lock();if(!state)throw std::runtime_error("JNI interface proxy adapter owner expired");return state;};
  host.BindStaticObjectMethod(kBridge,"newInterfaceProxy",kFactorySignature,[get](addr_t,const jni::Host::MethodArguments &args){return get()->Create(args[0],args[1]);});
  host.BindStaticVoidMethod(kBridge,"disableInterfaceProxy","(Ljava/lang/Object;)V",[get](addr_t,const jni::Host::MethodArguments &args){get()->Disable(args[0]);});
  if(state_->config.run_native){
    for(const char* owner:{kChoreographerProxy,kMessageProxy})
      host.DefineBooleanMethod(owner,"handleMessage","(Landroid/os/Message;)Z",[get](addr_t proxy,const auto& a){return get()->MessageCall(proxy,a[0]);});
    host.DefineVoidMethod(kChoreographerProxy,"doFrame","(J)V",[get](addr_t proxy,const auto& a){get()->FrameCall(proxy,a[0]);});
    for(const char* owner:{kChoreographerProxy,kMessageProxy}){
      host.DefineObjectMethod(owner,"toString","()Ljava/lang/String;",[get](addr_t,const auto&)->addr_t{get()->ObjectCall("toString");});
      host.DefineBooleanMethod(owner,"equals","(Ljava/lang/Object;)Z",[get](addr_t,const auto&)->bool{get()->ObjectCall("equals");});
    }
  }
  for(const auto &[name,sig]:std::vector<std::pair<const char*,const char*>>{{"onServiceConnected","(Landroid/content/ComponentName;Landroid/os/IBinder;)V"},{"onServiceDisconnected","(Landroid/content/ComponentName;)V"},{"onBindingDied","(Landroid/content/ComponentName;)V"},{"onNullBinding","(Landroid/content/ComponentName;)V"}})
    host.DefineVoidMethod(kProxy,name,sig,[get,method_name=name](addr_t proxy,const jni::Host::MethodArguments&){get()->ServiceCall(proxy,method_name);});
  host.DefineVoidMethod(kFocusProxy,"onAudioFocusChange","(I)V",[get](addr_t proxy,const jni::Host::MethodArguments&){get()->FocusCall(proxy);});
  host.DefineVoidMethod(kRunnableProxy,"run","()V",[get](addr_t proxy,const jni::Host::MethodArguments&){get()->RunnableCall(proxy);});
  for(const auto &[name,sig]:std::vector<std::pair<const char*,const char*>>{
      {"onLocationChanged","(Landroid/location/Location;)V"},
      {"onLocationChanged","(Ljava/util/List;)V"},
      {"onFlushComplete","(I)V"},
      {"onStatusChanged","(Ljava/lang/String;ILandroid/os/Bundle;)V"},
      {"onProviderEnabled","(Ljava/lang/String;)V"},
      {"onProviderDisabled","(Ljava/lang/String;)V"}})
    host.DefineVoidMethod(kLocationProxy,name,sig,[get,method_name=std::string(name)+sig](addr_t proxy,const jni::Host::MethodArguments&){get()->LocationCall(proxy,method_name);});
  for(const char *proxy_class:{kProxy,kFocusProxy,kLocationProxy,kRunnableProxy}){
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
