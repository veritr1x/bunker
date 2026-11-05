#include "java_native_loader.h"
#include "../whole/guest_memory.h"
#include <atomic>
#include <condition_variable>
#include <map>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace bunker::windows {
namespace {
void Need(bool value,const char*why){if(!value)throw std::invalid_argument(why);}
addr_t Env(jni::Host&h,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
  ::State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(slot,s);return s.gpr.x0.qword;
}
struct Locals {
  jni::Host&host;std::vector<addr_t>refs;
  addr_t Keep(addr_t v){if(v)refs.push_back(v);return v;}
  ~Locals(){for(auto v:refs)host.DeleteLocalReference(v);}
};
std::string Utf8(const std::u16string&s){
  std::string out;
  for(size_t i=0;i<s.size();++i){uint32_t c=s[i];
    if(!c)throw std::invalid_argument("native library text contains NUL");
    if(c>=0xd800&&c<=0xdbff){if(++i==s.size()||s[i]<0xdc00||s[i]>0xdfff)throw std::invalid_argument("invalid native library UTF16");c=0x10000+((c-0xd800)<<10)+(s[i]-0xdc00);}
    else if(c>=0xdc00&&c<=0xdfff)throw std::invalid_argument("invalid native library UTF16");
    if(c<0x80)out+=char(c);else if(c<0x800){out+=char(0xc0|(c>>6));out+=char(0x80|(c&63));}
    else if(c<0x10000){out+=char(0xe0|(c>>12));out+=char(0x80|((c>>6)&63));out+=char(0x80|(c&63));}
    else{out+=char(0xf0|(c>>18));out+=char(0x80|((c>>12)&63));out+=char(0x80|((c>>6)&63));out+=char(0x80|(c&63));}
  }return out;
}
bool Version(int32_t v){return v==0x10001||v==0x10002||v==0x10004||v==jni::kVersion16;}
bool Path(const std::string&p){
  if(p.empty()||p.front()!='/'||p.find_first_of("\\:!")!=p.npos||p.find('\0')!=p.npos)return false;
  size_t at=1;
  while(at<=p.size()){auto end=p.find('/',at);if(end==p.npos)end=p.size();auto part=p.substr(at,end-at);if(part.empty()||part=="."||part=="..")return false;if(end==p.size())return true;at=end+1;}
  return false;
}
}
struct JavaNativeLoader::State {
  struct Image {
    Library library;enum Status{Unloaded,Loading,Success,Failed}status=Unloaded;
    std::thread::id owner;std::condition_variable changed;addr_t handle=0,onload=0;std::string failure;bool adopted=false;
  };
  jni::Host*host=nullptr;ModuleRegistry*modules=nullptr;jni::Host::ObjectValue loader;
  Runner runner;std::function<void(const Event&)>observer;std::function<void(int,const std::u16string&)>diagnostic;
  std::map<std::u16string,std::unique_ptr<Image>>images;std::mutex mutex;
  std::atomic<bool>active{true},bound{false};
  bool SameLoader(addr_t value){auto&h=*host;Locals locals{h,{}};auto expected=locals.Keep(h.LocalValue(loader));return expected&&Env(h,24,value,expected)&&h.PendingException().empty();}
  void Observe(const Event&e){observer(e);}
  bool Failure(Event e,bool unknown=true){
    e.success=false;Observe(e);
    diagnostic(6,(unknown?std::u16string(u"Unknown error "):std::u16string(u"Unable to find "))+(unknown?std::u16string(e.detail.begin(),e.detail.end()):e.name));return false;
  }
  bool CatchFresh(const std::u16string&name){
    // This is the original Java wrapper's catch, not the lower native load.
    // Retain the actual Throwable before clearing it for type tests/formatting.
    auto&h=*host;Locals locals{h,{}};auto exception=locals.Keep(Env(h,15));
    if(!exception)throw std::logic_error("fresh Java load exception has no Throwable");
    h.ClearException();
    auto unsatisfied=locals.Keep(Env(h,6,reinterpret_cast<addr_t>("java/lang/UnsatisfiedLinkError")));
    auto exceptions=locals.Keep(Env(h,6,reinterpret_cast<addr_t>("java/lang/Exception")));
    if(!h.PendingException().empty())throw std::runtime_error("native load catch classes unavailable");
    if(Env(h,32,exception,unsatisfied)){diagnostic(6,u"Unable to find "+name);return false;}
    if(Env(h,32,exception,exceptions)){
      auto throwable=locals.Keep(Env(h,6,reinterpret_cast<addr_t>("java/lang/Throwable")));
      auto method=Env(h,33,throwable,reinterpret_cast<addr_t>("toString"),reinterpret_cast<addr_t>("()Ljava/lang/String;"));
      auto text=locals.Keep(Env(h,34,exception,method));auto value=h.StringValue(text);
      if(!h.PendingException().empty())return false; // Formatting itself threw.
      if(!value)throw std::runtime_error("Throwable.toString returned null during native load catch");
      diagnostic(6,u"Unknown error "+*value);return false;
    }
    Env(h,13,exception);return false; // Other Errors propagate the same object.
  }
  bool Load(addr_t supplied,const std::u16string&name){
    Event event;event.name=name;
    if(!host->PendingException().empty()){event.detail="preexisting Java exception preserved";Observe(event);return false;}
    if(!active.load(std::memory_order_acquire)){event.detail="native library loader revoked";return Failure(event);}
    if(!SameLoader(supplied)){event.detail="native library belongs to the configured application loader";return Failure(event);}
    // Validate the logical name without reading or loading any host path.
    if(name.empty()||name.find_first_of(u"/\\:!")!=name.npos){event.detail="invalid logical library name";return Failure(event,false);}
    try{(void)Utf8(name);}catch(const std::invalid_argument&){event.detail="invalid logical library name encoding";return Failure(event,false);}
    auto found=images.find(name);if(found==images.end()){event.detail="library is outside the registered translated catalog";return Failure(event,false);}
    auto&image=*found->second;event.path=image.library.guest_path;
    // Resolve through the existing actual-app-loader ClassLoader catalog. A
    // configured path is not evidence of a successful module or JNI load.
    {auto&h=*host;Locals locals{h,{}};auto cls=locals.Keep(Env(h,6,reinterpret_cast<addr_t>("java/lang/ClassLoader")));
      auto method=Env(h,33,cls,reinterpret_cast<addr_t>("findLibrary"),reinterpret_cast<addr_t>("(Ljava/lang/String;)Ljava/lang/String;"));
      if(!h.PendingException().empty()){event.detail="ClassLoader lookup raised a Java exception";Observe(event);return false;}
      auto text=locals.Keep(h.NewString(name));auto result=locals.Keep(Env(h,34,supplied,method,text));auto path=h.StringValue(result);
      if(!h.PendingException().empty()){event.detail="ClassLoader resolution raised a Java exception";Observe(event);return false;}
      if(!path||Utf8(*path)!=image.library.guest_path){event.detail="ClassLoader did not resolve the registered translated path";return Failure(event,false);}
    }
    {std::unique_lock lock(mutex);
      while(image.status==Image::Loading&&image.owner!=std::this_thread::get_id())image.changed.wait(lock);
      if(image.status!=Image::Unloaded){
        event.cached=true;event.handle=image.handle;event.onload=image.onload;event.adopted=image.adopted;
        if(image.status==Image::Loading){event.success=true;event.recursive=true;event.detail="same-thread recursive in-progress load";}
        else{event.success=image.status==Image::Success;event.detail=image.failure;}
        lock.unlock();if(event.success){Observe(event);return true;}return Failure(event,false);
      }
      image.status=Image::Loading;image.owner=std::this_thread::get_id();
    }
    bool success=false;std::string failure;addr_t handle=0,onload=0;std::exception_ptr exception;
    try{
      handle=modules->Open(image.library.guest_path.c_str(),2);
      if(!handle){auto error=modules->Error();failure=error?recomp::ReadGuestString(error):"translated module open failed";}
      else{
        (void)modules->Error();onload=modules->Symbol(handle,"JNI_OnLoad");auto error=modules->Error();auto message=error?recomp::ReadGuestString(error):std::string();
        auto basename=image.library.guest_path.substr(image.library.guest_path.find_last_of('/')+1);
        if(!onload){success=message=="translated export is unavailable: "+basename+": JNI_OnLoad";if(!success)failure="JNI_OnLoad lookup did not establish an absent optional symbol: "+message;}
        else if(image.library.expected_onload&&onload!=image.library.expected_onload)failure="JNI_OnLoad differs from the pinned original entry";
        else{auto version=static_cast<int32_t>(runner(onload,{host->VmAddress(),0}));success=Version(version)&&host->PendingException().empty();if(!success)failure="original JNI_OnLoad returned an invalid version or pending Java exception";}
      }
    }catch(...){exception=std::current_exception();failure="native library host/translated execution failed closed";}
    {std::lock_guard lock(mutex);image.handle=handle;image.onload=onload;image.failure=failure;image.status=success?Image::Success:Image::Failed;image.owner={};image.changed.notify_all();}
    event.success=success;event.handle=handle;event.onload=onload;event.detail=failure;
    if(exception){Observe(event);std::rethrow_exception(exception);}
    if(success){Observe(event);return true;}
    // Do not close an OnLoad-failed image: original native registrations or TLS
    // may already reference it. The failure remains cached for this owner.
    if(!host->PendingException().empty()){Observe(event);return false;}
    return Failure(event,false);
  }
};
JavaNativeLoader::JavaNativeLoader(jni::Host&host,ModuleRegistry&modules,const Config&config){
  Need(host.PendingException().empty(),"native loader configuration cannot replace a pending exception");
  Need(config.application_class&&config.application_loader&&host.EnvAddress(),"native loader needs attached application class and loader");
  Need(bool(config.runner)&&bool(config.observer)&&bool(config.diagnostic),"native loader needs runner, observer and diagnostic callbacks");
  auto state=std::make_shared<State>();state->host=&host;state->modules=&modules;state->runner=config.runner;state->observer=config.observer;state->diagnostic=config.diagnostic;
  std::map<std::string,bool>paths;
  for(const auto&library:config.libraries){
    auto name=Utf8(library.name);Need(!name.empty()&&name!="."&&name!=".."&&name.find_first_of("/\\:!")==name.npos,"invalid native library logical name");
    Need(Path(library.guest_path)&&library.guest_path.substr(library.guest_path.find_last_of('/')+1)=="lib"+name+".so","invalid native library canonical path");
    Need(paths.emplace(library.guest_path,true).second,"duplicate native library path");auto image=std::make_unique<State::Image>();image->library=library;Need(state->images.emplace(library.name,std::move(image)).second,"duplicate native library name");
  }
  Locals locals{host,{}};auto cls=locals.Keep(Env(host,6,reinterpret_cast<addr_t>("java/lang/Class")));
  auto get_loader=Env(host,33,cls,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  auto actual=locals.Keep(Env(host,34,config.application_class,get_loader));Need(host.PendingException().empty()&&actual&&Env(host,24,actual,config.application_loader),"native loader requires the class's actual application loader");
  auto string=locals.Keep(Env(host,6,reinterpret_cast<addr_t>("java/lang/String")));auto bootstrap=locals.Keep(Env(host,34,string,get_loader));Need(host.PendingException().empty()&&!Env(host,24,actual,bootstrap),"bootstrap loader cannot own this application service");
  state->loader=host.CaptureValue(actual);state_=std::move(state);
}
JavaNativeLoader::~JavaNativeLoader(){Revoke();}
void JavaNativeLoader::Revoke()noexcept{if(state_)state_->active.store(false,std::memory_order_release);}
void JavaNativeLoader::BindUnityPlayer(){
  auto state=state_;bool expected=false;if(!state->bound.compare_exchange_strong(expected,true))throw std::invalid_argument("native library Unity binding already installed");
  try{state->host->BindBooleanMethod("com/unity3d/player/UnityPlayer","loadLibrary","(Ljava/lang/String;)Z",[state](addr_t receiver,const jni::Host::MethodArguments&args){
    auto&host=*state->host;if(!host.PendingException().empty())return uint64_t{0};auto name=host.StringValue(args[0]);
    if(!host.PendingException().empty())return uint64_t{0};
    if(!name){host.ThrowException("java/lang/NullPointerException");return uint64_t(state->CatchFresh({}));}
    Locals locals{host,{}};auto clazz=locals.Keep(Env(host,31,receiver));auto class_class=locals.Keep(Env(host,6,reinterpret_cast<addr_t>("java/lang/Class")));
    auto get_loader=Env(host,33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
    auto loader=locals.Keep(Env(host,34,clazz,get_loader));
    if(!host.PendingException().empty())return uint64_t{0};
    auto result=state->Load(loader,*name);
    return uint64_t(host.PendingException().empty()?result:state->CatchFresh(*name));
  });}catch(...){state->bound.store(false);throw;}
}
void JavaNativeLoader::Adopt(const std::u16string&name,addr_t handle,int32_t version){
  auto state=state_;Need(state->active.load()&&state->host->PendingException().empty(),"cannot adopt with revoked loader or pending exception");
  auto found=state->images.find(name);Need(found!=state->images.end()&&handle,"invalid completed library adoption");auto&image=*found->second;
  Need(state->modules->IsOpenHandleFor(image.library.guest_path,handle),"adoption handle is not the exact live registered module");
  (void)state->modules->Error();auto actual=state->modules->Symbol(handle,"JNI_OnLoad");auto error=state->modules->Error();
  auto message=error?recomp::ReadGuestString(error):std::string();auto basename=image.library.guest_path.substr(image.library.guest_path.find_last_of('/')+1);
  if(actual)Need(Version(version)&&(!image.library.expected_onload||actual==image.library.expected_onload),"adopted JNI_OnLoad entry or completed version mismatch");
  else Need(version==0&&!image.library.expected_onload&&message=="translated export is unavailable: "+basename+": JNI_OnLoad","adoption does not prove absent optional JNI_OnLoad");
  {std::lock_guard lock(state->mutex);Need(image.status==State::Image::Unloaded,"cannot adopt an attempted library");image.handle=handle;image.onload=actual;image.adopted=true;image.status=State::Image::Success;}
  Event e;e.name=name;e.path=image.library.guest_path;e.success=true;e.adopted=true;e.handle=handle;e.onload=actual;e.detail="adopted independently completed original JNI_OnLoad";state->Observe(e);
}
bool JavaNativeLoader::LoadForLoader(addr_t loader,const std::u16string&name){return state_->Load(loader,name);}
} // namespace bunker::windows
