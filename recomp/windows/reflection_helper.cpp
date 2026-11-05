#include "reflection_helper.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <mutex>
#include <set>
#include <stdexcept>
#include <utility>
#ifdef _WIN32
#include <windows.h>
#endif

namespace bunker::windows {
namespace {
constexpr const char *kOwner="com/unity3d/player/ReflectionHelper";
constexpr const char *kHandler="com/unity3d/player/ReflectionHelper$1";
constexpr const char *kProxy="com/unity3d/player/HostReflectionRunnableProxy";
constexpr const char *kInvoke="(JLjava/lang/String;[Ljava/lang/Object;)Ljava/lang/Object;";
using Value=jni::Host::ObjectValue;
struct NativeEnvironment {
  int error=errno;std::fenv_t floating{};
#ifdef _WIN32
  DWORD last_error=GetLastError();
#endif
  NativeEnvironment(){std::fegetenv(&floating);}
  ~NativeEnvironment(){std::fesetenv(&floating);errno=error;
#ifdef _WIN32
    SetLastError(last_error);
#endif
  }
};
addr_t Env(jni::Host &host,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
  State state{};state.gpr.x0.qword=host.EnvAddress();state.gpr.x1.qword=a;
  state.gpr.x2.qword=b;state.gpr.x3.qword=c;host.InvokeEnv(slot,state);return state.gpr.x0.qword;
}
void Healthy(jni::Host &host){if(!host.PendingException().empty())throw std::runtime_error("ReflectionHelper metadata operation failed: "+host.PendingException());}
Value Keep(jni::Host &host,addr_t local){auto value=host.CaptureValue(local);if(local)host.DeleteLocalReference(local);return value;}
std::string ModifiedUtf8(const std::u16string &text){
  std::string result;
  for(uint16_t c:text){if(c&&c<0x80)result.push_back(char(c));
    else if(c<0x800){result.push_back(char(0xc0|(c>>6)));result.push_back(char(0x80|(c&63)));}
    else{result.push_back(char(0xe0|(c>>12)));result.push_back(char(0x80|((c>>6)&63)));result.push_back(char(0x80|(c&63)));}}
  return result;
}
std::u16string Utf16(const std::string &text){
  std::u16string result;
  for(size_t i=0;i<text.size();){const auto a=uint8_t(text[i++]);uint16_t c=a;
    if((a&0xe0)==0xc0){if(i==text.size())throw std::runtime_error("Invalid reflected modified UTF8");c=uint16_t((a&31)<<6)|(uint8_t(text[i++])&63);}
    else if((a&0xf0)==0xe0){if(text.size()-i<2)throw std::runtime_error("Invalid reflected modified UTF8");c=uint16_t((a&15)<<12)|(uint16_t(uint8_t(text[i])&63)<<6)|(uint8_t(text[i+1])&63);i+=2;}
    else if(a>=0x80)throw std::runtime_error("Unsupported reflected modified UTF8");
    result.push_back(char16_t(c));}
  return result;
}
uint32_t StringHash(const std::u16string &text){uint32_t hash=0;for(uint16_t c:text)hash=hash*31+c;return hash;}
std::vector<std::string> Types(const std::string &signature){
  std::vector<std::string> result;size_t at=0;
  while(at<signature.size()){
    if(signature[at]=='('||signature[at]==')'){++at;continue;}
    const auto start=at;while(at<signature.size()&&signature[at]=='[')++at;
    if(at==signature.size())throw std::runtime_error("Incomplete ReflectionHelper descriptor");
    if(signature[at]=='L'){const auto end=signature.find(';',at);if(end==std::string::npos||end==at+1)throw std::runtime_error("Incomplete ReflectionHelper reference descriptor");at=end+1;}
    else if(std::string("VZBCSIJFD").find(signature[at])!=std::string::npos)++at;
    else throw std::runtime_error("ReflectionHelper descriptor is outside the supported grammar");
    result.push_back(signature.substr(start,at-start));
  }
  return result;
}
struct ProxyState {
  uint64_t handle=0,epoch=0;std::vector<std::string> interfaces;
  std::atomic<uint64_t> native_exception{0};std::atomic<bool> default_method{false};
  Value loader;std::vector<Value> classes;
};
struct ProxyPayload {std::shared_ptr<ProxyState> state;Value handler;};
struct HandlerPayload {std::shared_ptr<ProxyState> state;};
}

struct ReflectionHelper::Shared {
  jni::Host &host;Config config;std::function<uint64_t()> epoch;std::atomic<bool> active{true};
  struct CacheEntry {std::string clazz;std::u16string name,signature;Value member;};
  std::mutex cache_mutex;std::array<std::optional<CacheEntry>,4096> cache{};
  Shared(jni::Host &h,Config c,std::function<uint64_t()> e):host(h),config(std::move(c)),epoch(std::move(e)){}
  void RequireActive(){if(!active.load(std::memory_order_acquire))throw std::runtime_error("ReflectionHelper owner retired");}
  bool String(addr_t reference,std::u16string &result){
    auto text=host.StringValue(reference);if(!text){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException");return false;}
    result=std::move(*text);return true;
  }
  float TypeScore(const std::string &actual,const std::string &requested){
    if(actual==requested)return 1.0f;
    if(actual.size()==1||requested.size()==1)return 0.0f;
    auto class_name=[](const std::string &type){return type.front()=='['?type:type.substr(1,type.size()-2);};
    const auto actual_name=class_name(actual),requested_name=class_name(requested);
    auto a=Env(host,6,reinterpret_cast<addr_t>(actual_name.c_str()));if(!a)return 0;
    auto b=Env(host,6,reinterpret_cast<addr_t>(requested_name.c_str()));if(!b){host.DeleteLocalReference(a);return 0;}
    const bool subtype=Env(host,11,a,b)!=0,supertype=!subtype&&Env(host,11,b,a)!=0;
    host.DeleteLocalReference(a);host.DeleteLocalReference(b);return subtype?0.5f:supertype?0.1f:0.0f;
  }
  float MemberScore(const std::vector<std::string> &actual,const std::vector<std::string> &requested){
    if(requested.empty())return 0.1f;
    if(actual.size()!=requested.size())return 0;
    float score=1.0f;for(size_t i=0;i<actual.size();++i){score*=TypeScore(actual[i],requested[i]);if(!host.PendingException().empty())return 0;}
    return score;
  }
  addr_t Lookup(addr_t clazz,addr_t name_ref,addr_t signature_ref,bool is_static,bool field,bool constructor){
    NativeEnvironment native;RequireActive();auto class_name=host.ClassNameValue(clazz);
    if(!class_name){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException");return 0;}
    std::u16string name,signature;if((!constructor&&!String(name_ref,name))||!String(signature_ref,signature))return 0;
    auto system=Env(host,6,reinterpret_cast<addr_t>("java/lang/System"));
    auto hash_method=Env(host,113,system,reinterpret_cast<addr_t>("identityHashCode"),reinterpret_cast<addr_t>("(Ljava/lang/Object;)I"));
    State hash{};hash.gpr.x0.qword=host.EnvAddress();hash.gpr.x1.qword=system;hash.gpr.x2.qword=hash_method;hash.gpr.x3.qword=clazz;host.InvokeEnv(129,hash);Healthy(host);host.DeleteLocalReference(system);
    // Class inherits Object.hashCode. The same real per-object identity is
    // exposed by System.identityHashCode; Java String hashing wraps modulo32.
    const auto index=(((uint32_t(hash.gpr.x0.qword)+527)*31+StringHash(name))*31+StringHash(signature))&4095;
    {
      std::lock_guard lock(cache_mutex);const auto &entry=cache[index];
      if(entry&&entry->clazz==*class_name&&entry->name==name&&entry->signature==signature){
        auto member=host.LocalValue(entry->member);
        if(!member)host.ThrowException(field?"java/lang/NoSuchFieldError":"java/lang/NoSuchMethodError",constructor?u"<init>"+signature:name+signature);
        return member;
      }
    }
    const auto member_name=constructor?std::string("<init>"):ModifiedUtf8(name),descriptor=ModifiedUtf8(signature);
    const auto requested=Types(descriptor);std::string selected_owner,selected_signature;float best=0;
    auto current=host.NewLocalReference(clazz);std::fesetround(FE_TONEAREST);
    while(current){
      if(field){for(const auto &candidate:host.DeclaredFields(current)){
        if(candidate.name!=member_name||candidate.is_static!=is_static)continue;
        const auto score=MemberScore(Types(candidate.signature),requested);if(!host.PendingException().empty()){host.DeleteLocalReference(current);return 0;}
        if(score>best){best=score;selected_owner=candidate.declaring_class;selected_signature=candidate.signature;if(score==1)break;}
      }}else{for(const auto &candidate:host.DeclaredMethods(current)){
        if(candidate.name!=member_name||candidate.is_static!=is_static||(!constructor&&candidate.name.front()=='<'))continue;
        const auto score=MemberScore(Types(candidate.signature),requested);if(!host.PendingException().empty()){host.DeleteLocalReference(current);return 0;}
        if(score>best){best=score;selected_owner=candidate.declaring_class;selected_signature=candidate.signature;if(score==1)break;}
      }}
      if(!host.PendingException().empty()){host.DeleteLocalReference(current);return 0;}
      auto metadata_name=host.ClassNameValue(current);auto class_class=Env(host,6,reinterpret_cast<addr_t>("java/lang/Class"));
      auto is_interface=Env(host,33,class_class,reinterpret_cast<addr_t>("isInterface"),reinterpret_cast<addr_t>("()Z"));
      const bool stop=constructor||best==1||Env(host,37,current,is_interface)||!metadata_name||*metadata_name=="java/lang/Object";
      host.DeleteLocalReference(class_class);auto parent=stop?0:Env(host,10,current);host.DeleteLocalReference(current);current=parent;
    }
    if(selected_owner.empty()){
      {std::lock_guard lock(cache_mutex);cache[index]=CacheEntry{*class_name,name,signature,host.CaptureValue(0)};}
      host.ThrowException(field?"java/lang/NoSuchFieldError":"java/lang/NoSuchMethodError",Utf16(member_name+descriptor));return 0;
    }
    auto selected_class=Env(host,6,reinterpret_cast<addr_t>(selected_owner.c_str()));
    const auto id=Env(host,field?(is_static?144:94):(is_static?113:33),selected_class,reinterpret_cast<addr_t>(member_name.c_str()),reinterpret_cast<addr_t>(selected_signature.c_str()));
    if(!id){host.DeleteLocalReference(selected_class);return 0;}
    auto reflected=Env(host,field?12:9,selected_class,id,is_static?1:0);host.DeleteLocalReference(selected_class);
    if(!reflected)return 0;
    auto retained=host.CaptureValue(reflected);Healthy(host);
    {std::lock_guard lock(cache_mutex);cache[index]=CacheEntry{*class_name,std::move(name),std::move(signature),std::move(retained)};}
    return reflected;
  }
  addr_t FieldSignature(addr_t field){NativeEnvironment native;RequireActive();auto info=host.DescribeReflectedField(field);if(!info)return 0;return host.NewString(Utf16(info->signature));}
  std::shared_ptr<ProxyState> Proxy(addr_t reference){
    auto value=host.ReadHostState<ProxyPayload>(reference);if(!value){Healthy(host);host.ThrowException("java/lang/IllegalArgumentException",u"not this ReflectionHelper proxy");return {};}
    return value->state;
  }
  addr_t Create(uint64_t handle,addr_t classes,bool single){
    NativeEnvironment native;RequireActive();std::vector<std::string> names;std::vector<Value> values;
    const auto count=single?1:classes?int32_t(Env(host,171,classes)):-1;Healthy(host);
    if(count<0){host.ThrowException("java/lang/NullPointerException");return 0;}
    for(int32_t i=0;i<count;++i){auto item=single?host.NewLocalReference(classes):Env(host,173,classes,uint32_t(i));auto name=host.ClassNameValue(item);
      if(!name){if(item)host.DeleteLocalReference(item);if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException");return 0;}
      names.push_back(*name);values.push_back(Keep(host,item));}
    std::fprintf(stderr,"ReflectionHelper: actual proxy handle=%#llx interfaces=[",(unsigned long long)handle);
    for(size_t i=0;i<names.size();++i)std::fprintf(stderr,"%s%s",i?",":"",names[i].c_str());
    std::fprintf(stderr,"]\n");
    // The declared Runnable path has a genuine void/no-argument callback.
    // Other interface/default/primitive boxing profiles need their own evidence.
    if(names!=std::vector<std::string>{"java/lang/Runnable"})throw std::runtime_error("ReflectionHelper proxy interface profile is not qualified");
    auto owner=Env(host,6,reinterpret_cast<addr_t>(kOwner));auto class_class=Env(host,6,reinterpret_cast<addr_t>("java/lang/Class"));
    auto loader_method=Env(host,33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
    auto loader=Env(host,34,owner,loader_method);Healthy(host);
    auto state=std::make_shared<ProxyState>();state->handle=handle;state->epoch=epoch();state->interfaces=std::move(names);state->classes=std::move(values);state->loader=Keep(host,loader);
    auto handler=host.NewHostInstance(kHandler,std::make_shared<HandlerPayload>(HandlerPayload{state}));Healthy(host);
    auto payload=std::make_shared<ProxyPayload>();payload->state=std::move(state);payload->handler=Keep(host,handler);
    auto result=host.NewHostInstance(kProxy,payload);Healthy(host);host.DeleteLocalReference(owner);host.DeleteLocalReference(class_class);return result;
  }
  addr_t Native(const char *name,const char *signature,const std::vector<addr_t> &arguments){
    if(!config.run_native)throw std::runtime_error("ReflectionHelper has no native runner");
    const auto entry=host.NativeEntry(kOwner,name,signature);if(!entry)throw std::runtime_error(std::string("ReflectionHelper native is not registered: ")+name);
    auto owner=Env(host,6,reinterpret_cast<addr_t>(kOwner));Healthy(host);std::vector<addr_t> values{host.EnvAddress(),owner};values.insert(values.end(),arguments.begin(),arguments.end());
    auto result=config.run_native(entry,values);host.DeleteLocalReference(owner);return result;
  }
  addr_t Invoke(const std::shared_ptr<ProxyState> &proxy,addr_t method,addr_t arguments){
    NativeEnvironment native;RequireActive();if(proxy->epoch!=epoch()){
      std::fprintf(stderr,"ReflectionHelper: Scripting proxy object was destroyed, because Unity player was unloaded.\n");return 0;}
    auto info=host.DescribeReflectedMethod(method);if(!info)return 0;
    if(info->declaring_class!="java/lang/Runnable"||info->name!="run"||info->signature!="()V"||info->is_static)throw std::runtime_error("ReflectionHelper callback method profile is not qualified");
    proxy->native_exception.store(0,std::memory_order_relaxed);proxy->default_method.store(false,std::memory_order_relaxed);
    auto name=host.NewString(Utf16(info->name));auto result=Native("nativeProxyInvoke",kInvoke,{proxy->handle,name,arguments});host.DeleteLocalReference(name);
    if(!host.PendingException().empty())return 0;
    const auto exception=proxy->native_exception.load(std::memory_order_relaxed);
    // Runnable.run is abstract. DEX logs its supplied native exception token
    // on the default-method branch as well, including the value zero.
    if(proxy->default_method.load(std::memory_order_relaxed)||exception)Native("nativeProxyLogJNIInvokeException","(J)V",{exception});
    return result;
  }
  void Run(addr_t reference){NativeEnvironment native;auto proxy=Proxy(reference);if(!proxy)return;
    auto clazz=Env(host,6,reinterpret_cast<addr_t>("java/lang/Runnable"));auto method=Env(host,33,clazz,reinterpret_cast<addr_t>("run"),reinterpret_cast<addr_t>("()V"));
    auto reflected=Env(host,9,clazz,method,0);Healthy(host);Invoke(proxy,reflected,0);host.DeleteLocalReference(reflected);host.DeleteLocalReference(clazz);
  }
};

ReflectionHelper::ReflectionHelper(jni::Host &host,ReflectionLaunchEpoch &epoch,Config config):state_(std::make_shared<Shared>(host,std::move(config),epoch.Reader())){
  std::weak_ptr<Shared> weak=state_;auto get=[weak]{auto state=weak.lock();if(!state)throw std::runtime_error("ReflectionHelper owner expired");state->RequireActive();return state;};
  host.BindStaticObjectMethod(kOwner,"getConstructorID","(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/reflect/Constructor;",[get](addr_t,const auto &a){return get()->Lookup(a[0],0,a[1],false,false,true);});
  host.BindStaticObjectMethod(kOwner,"getMethodID","(Ljava/lang/Class;Ljava/lang/String;Ljava/lang/String;Z)Ljava/lang/reflect/Method;",[get](addr_t,const auto &a){return get()->Lookup(a[0],a[1],a[2],(a[3]&255)!=0,false,false);});
  host.BindStaticObjectMethod(kOwner,"getFieldID","(Ljava/lang/Class;Ljava/lang/String;Ljava/lang/String;Z)Ljava/lang/reflect/Field;",[get](addr_t,const auto &a){return get()->Lookup(a[0],a[1],a[2],(a[3]&255)!=0,true,false);});
  host.BindStaticObjectMethod(kOwner,"getFieldSignature","(Ljava/lang/reflect/Field;)Ljava/lang/String;",[get](addr_t,const auto &a){return get()->FieldSignature(a[0]);});
  host.DefineClass(kProxy,{},"java/lang/reflect/Proxy",false,{"java/lang/Runnable"});
  host.BindStaticObjectMethod(kOwner,"newProxyInstance","(JLjava/lang/Class;)Ljava/lang/Object;",[get](addr_t,const auto &a){return get()->Create(a[0],a[1],true);});
  host.BindStaticObjectMethod(kOwner,"newProxyInstance","(J[Ljava/lang/Class;)Ljava/lang/Object;",[get](addr_t,const auto &a){return get()->Create(a[0],a[1],false);});
  host.BindStaticVoidMethod(kOwner,"setNativeExceptionOnProxy","(Ljava/lang/Object;JZ)V",[get](addr_t,const auto &a){NativeEnvironment native;auto state=get();auto proxy=state->Proxy(a[0]);if(proxy){proxy->native_exception.store(a[1],std::memory_order_relaxed);proxy->default_method.store((a[2]&255)!=0,std::memory_order_relaxed);}});
  host.BindObjectMethod(kHandler,"invoke","(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;",[get,&host](addr_t receiver,const auto &a){auto value=host.ReadHostState<HandlerPayload>(receiver);Healthy(host);if(!value)throw std::runtime_error("ReflectionHelper handler has no backed state");return get()->Invoke(value->state,a[1],a[2]);});
  host.BindVoidMethod(kHandler,"a","(JZ)V",[get,&host](addr_t receiver,const auto &a){NativeEnvironment native;get();auto value=host.ReadHostState<HandlerPayload>(receiver);Healthy(host);if(!value)throw std::runtime_error("ReflectionHelper handler has no backed state");value->state->native_exception.store(a[0],std::memory_order_relaxed);value->state->default_method.store((a[1]&255)!=0,std::memory_order_relaxed);});
  host.BindVoidMethod(kHandler,"finalize","()V",[get,&host](addr_t receiver,const auto &){NativeEnvironment native;auto state=get();auto value=host.ReadHostState<HandlerPayload>(receiver);Healthy(host);if(!value)throw std::runtime_error("ReflectionHelper handler has no backed state");if(value->state->epoch==state->epoch())state->Native("nativeProxyFinalize","(J)V",{value->state->handle});});
  host.DefineVoidMethod(kProxy,"run","()V",[get](addr_t receiver,const auto &){get()->Run(receiver);});
  host.DefineIntMethod(kProxy,"hashCode","()I",[](addr_t,const auto&)->int32_t{throw std::runtime_error("ReflectionHelper proxy Object.hashCode callback is not qualified");});
  host.DefineBooleanMethod(kProxy,"equals","(Ljava/lang/Object;)Z",[](addr_t,const auto&)->bool{throw std::runtime_error("ReflectionHelper proxy Object.equals callback is not qualified");});
  host.DefineObjectMethod(kProxy,"toString","()Ljava/lang/String;",[](addr_t,const auto&)->addr_t{throw std::runtime_error("ReflectionHelper proxy Object.toString callback is not qualified");});
  host.MarkClassInitialized(kOwner);host.MarkClassInitialized(kHandler);host.MarkClassInitialized("com/unity3d/player/ReflectionHelper$b");host.MarkClassInitialized(kProxy);
}
ReflectionHelper::~ReflectionHelper(){state_->active.store(false,std::memory_order_release);}
ReflectionHelper::ProxySnapshot ReflectionHelper::InspectProxy(addr_t reference)const{
  NativeEnvironment native;state_->RequireActive();auto value=state_->Proxy(reference);if(!value)return {};
  return {value->handle,value->epoch,state_->epoch(),value->native_exception.load(std::memory_order_relaxed),value->default_method.load(std::memory_order_relaxed),value->interfaces};
}
}
