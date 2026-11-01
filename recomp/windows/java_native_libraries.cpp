#include "java_native_libraries.h"
#include <atomic>
#include <map>
#include <stdexcept>

namespace bunker::windows {
namespace {
constexpr const char *signature="(Ljava/lang/String;)Ljava/lang/String;";
void Need(bool value,const char *why){if(!value)throw std::invalid_argument(why);}
bool Utf16(const std::u16string&s){
  for(size_t i=0;i<s.size();++i){
    auto c=s[i];if(!c)return false;
    if(c>=0xd800&&c<=0xdbff){if(++i==s.size()||s[i]<0xdc00||s[i]>0xdfff)return false;}
    else if(c>=0xdc00&&c<=0xdfff)return false;
  }return true;
}
bool Name(const std::u16string&s){
  return !s.empty()&&s!=u"."&&s!=u".."&&Utf16(s)&&s.find_first_of(u"/\\:!")==s.npos;
}
bool Path(const std::u16string&s){
  if(s.empty()||s.front()!=u'/'||!Utf16(s)||s.find_first_of(u"\\:!")!=s.npos)return false;
  size_t begin=1;
  while(begin<=s.size()){
    auto end=s.find(u'/',begin);if(end==s.npos)end=s.size();
    auto part=s.substr(begin,end-begin);if(part.empty()||part==u"."||part==u"..")return false;
    if(end==s.size())return true;begin=end+1;
  }return false;
}
addr_t Env(jni::Host&host,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){
  ::State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;
  host.InvokeEnv(slot,s);return s.gpr.x0.qword;
}
struct Locals {
  jni::Host&host;std::vector<addr_t> refs;
  addr_t Keep(addr_t ref){if(ref)refs.push_back(ref);return ref;}
  ~Locals(){for(auto ref:refs)host.DeleteLocalReference(ref);}
};
}
struct JavaNativeLibraries::State {
  jni::Host *host=nullptr;
  jni::Host::ObjectValue loader;
  std::map<std::u16string,addr_t> paths;
  std::atomic<bool> active{false};
};
JavaNativeLibraries::JavaNativeLibraries(jni::Host&host,const Config&config){
  std::map<std::u16string,std::u16string> paths;
  for(auto &library:config.libraries){
    Need(Name(library.name),"native library needs a nonempty logical name without path syntax");
    Need(Path(library.guest_path),"native library path must be canonical absolute POSIX guest path");
    auto basename=library.guest_path.substr(library.guest_path.find_last_of(u'/')+1);
    Need(basename==u"lib"+library.name+u".so","native library path basename differs from Android mapLibraryName");
    Need(paths.emplace(library.name,library.guest_path).second,"duplicate native library logical name");
  }
  // These checks precede all JNI identity operations. Never clear/replace a
  // pending application exception in order to configure a host service.
  Need(host.PendingException().empty(),"native library catalog cannot initialize with a pending Java exception");
  Need(host.EnvAddress()!=0,"native library catalog requires an attached JNI thread");
  Need(config.application_loader&&config.application_class,"native library catalog needs actual loader and application class references");
  Locals locals{host,{}};
  auto class_class=locals.Keep(Env(host,6,reinterpret_cast<addr_t>("java/lang/Class")));
  auto get_loader=Env(host,33,class_class,reinterpret_cast<addr_t>("getClassLoader"),reinterpret_cast<addr_t>("()Ljava/lang/ClassLoader;"));
  auto actual=locals.Keep(Env(host,34,config.application_class,get_loader));
  Need(host.PendingException().empty()&&actual,"application class did not provide a valid loader");
  auto same=Env(host,24,actual,config.application_loader);
  Need(host.PendingException().empty()&&same,"configured native loader is not the application's actual loader");
  auto bootstrap_class=locals.Keep(Env(host,6,reinterpret_cast<addr_t>("java/lang/String")));
  auto bootstrap=locals.Keep(Env(host,34,bootstrap_class,get_loader));
  auto is_bootstrap=Env(host,24,actual,bootstrap);
  Need(host.PendingException().empty()&&!is_bootstrap,"bootstrap loader cannot be configured as native application loader");
  auto state=std::make_shared<State>();state->host=&host;state->loader=host.CaptureValue(actual);
  std::vector<addr_t> globals;globals.reserve(paths.size());
  try{
    for(auto &[name,path]:paths){
      auto local=host.NewString(path);auto global=host.NewGlobalReference(local);host.DeleteLocalReference(local);
      Need(global&&host.PendingException().empty(),"cannot retain native path string");
      globals.push_back(global);state->paths.emplace(name,global);
    }
    host.DefineObjectMethod("java/lang/ClassLoader","findLibrary",signature,
      [state](addr_t receiver,const jni::Host::MethodArguments&arguments)->addr_t{
        if(!state->active.load(std::memory_order_acquire))return 0;
        auto &host=*state->host;
        if(!host.PendingException().empty())return 0;
        auto expected=host.LocalValue(state->loader);
        auto same=Env(host,24,receiver,expected);host.DeleteLocalReference(expected);
        if(!host.PendingException().empty()||!same)return 0; // Base/other loaders' default.
        auto name=host.StringValue(arguments[0]);
        if(!host.PendingException().empty())return 0;
        if(!name){host.ThrowException("java/lang/NullPointerException");return 0;}
        auto path=state->paths.find(*name);
        return path==state->paths.end()?0:path->second;
      });
  }catch(...){for(auto global:globals)host.DeleteGlobalReference(global);throw;}
  // The installed Host method owns the immutable state and bounded global
  // String references until Host teardown. Revoke never deletes a reference
  // that CallObject is about to clone for another thread.
  state_=std::move(state);state_->active.store(true,std::memory_order_release);
}
JavaNativeLibraries::~JavaNativeLibraries(){Revoke();}
void JavaNativeLibraries::Revoke()noexcept{if(state_)state_->active.store(false,std::memory_order_release);}
bool JavaNativeLibraries::Active()const noexcept{return state_&&state_->active.load(std::memory_order_acquire);}
}  // namespace bunker::windows
