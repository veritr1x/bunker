#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "firebase_app.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstring>
#include <exception>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>

namespace bunker::windows {
namespace {
void Need(bool yes,const char *message){if(!yes)throw std::runtime_error(message);}
struct Environment {
  DWORD error=GetLastError();int saved_errno=errno;std::fenv_t floating{};
  Environment(){std::fegetenv(&floating);}
  void Restore()const noexcept{std::fesetenv(&floating);errno=saved_errno;SetLastError(error);}
};
struct BoundaryEnvironment {
  Environment entry;
  ~BoundaryEnvironment(){entry.Restore();}
};
struct NativeCall {
  static thread_local NativeCall *current;
  Environment entry;NativeCall *previous=current;
  NativeCall(){current=this;std::fenv_t held;std::feholdexcept(&held);}
  ~NativeCall(){current=previous;entry.Restore();}
};
thread_local NativeCall *NativeCall::current=nullptr;
// Suspend the SDK environment while actual original guest code executes. No
// adapter mutex or active native FP scope surrounds the callback runner.
struct CallbackEnvironment {
  Environment native;NativeCall *suspended=NativeCall::current;
  CallbackEnvironment(){NativeCall::current=nullptr;if(suspended)suspended->entry.Restore();}
  ~CallbackEnvironment(){NativeCall::current=suspended;native.Restore();}
};
struct PublishedString {
  std::vector<char> bytes;
  explicit PublishedString(const char *text){
    if(!text)return;
    const size_t n=std::strlen(text)+1;bytes.resize(n);
    recomp::WriteGuestMemory(reinterpret_cast<addr_t>(bytes.data()),text,n);
  }
  ~PublishedString(){if(!bytes.empty())recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(bytes.data()),bytes.size());}
  addr_t Address()const{return bytes.empty()?0:reinterpret_cast<addr_t>(bytes.data());}
};
const std::vector<std::string> kCommands={
  "SWIGRegisterExceptionCallbacks_AppUtil",
  "SWIGRegisterExceptionArgumentCallbacks_AppUtil",
  "SWIGRegisterStringCallback_AppUtil",
  "Firebase_App_CSharp_SetLogFunction",
  "Firebase_App_CSharp_SetLogLevel",
  "Firebase_App_CSharp_GetLogLevel",
  "Firebase_App_CSharp_AppEnableLogCallback",
  "Firebase_App_CSharp_AppGetLogLevel",
  "Firebase_App_CSharp_SetEnabledAllAppCallbacks",
  "Firebase_App_CSharp_SetEnabledAppCallbackByName",
  "Firebase_App_CSharp_GetEnabledAppCallbackByName",
  "Firebase_App_CSharp_PollCallbacks",
  "Firebase_App_CSharp_CheckAndroidDependencies",
  "Firebase_App_CSharp_InitializePlayServicesInternal",
  "Firebase_App_CSharp_FirebaseApp_RegisterLibraryInternal",
  "Firebase_App_CSharp_FirebaseApp_SetLogLevelInternal",
  "Firebase_App_CSharp_FirebaseApp_GetLogLevelInternal",
  "Firebase_App_CSharp_FirebaseApp_DefaultName_get"
};
}
struct FirebaseAppService::Impl {
  using Exception=void(*)(const char*);
  using ArgumentException=void(*)(const char*,const char*);
  using StringCallback=const char*(*)(const char*);
  using LogCallback=void(*)(int32_t,const char*);
  using RegisterExceptions=void(*)(Exception,Exception,Exception,Exception,Exception,Exception,Exception,Exception,Exception,Exception,Exception);
  using RegisterArguments=void(*)(ArgumentException,ArgumentException,ArgumentException);
  Config config;HMODULE library=nullptr;
  std::map<std::string,FARPROC> exports;
  mutable std::mutex mutex;bool revoked=false,registering=false;size_t imports=0,callbacks=0;
  std::thread::id call_owner;
  std::exception_ptr failure;
  std::array<addr_t,11> exceptions{};std::array<addr_t,3> arguments{};
  addr_t string_callback=0,log_callback=0;
  static std::mutex global_mutex;
  static std::shared_ptr<Impl> global;
  static bool generation_used;
  explicit Impl(Config value):config(std::move(value)){}
  template<typename T>T Function(const std::string &name)const{static_assert(sizeof(T)==sizeof(FARPROC));auto symbol=exports.at(name);T result;std::memcpy(&result,&symbol,sizeof(result));return result;}
  void Healthy()const{std::exception_ptr error;{std::lock_guard lock(mutex);error=failure;}if(error)std::rethrow_exception(error);}
  void Failed(std::exception_ptr error)noexcept{try{std::lock_guard lock(mutex);if(!failure)failure=error;}catch(...){std::abort();}}
  struct Import {
    Impl &owner;
    explicit Import(Impl &value):owner(value){
      owner.Healthy();std::lock_guard lock(owner.mutex);
      Need(!owner.revoked,"Firebase SDK service is revoked");
      Need(!owner.registering,"Firebase SDK import overlaps native callback registration");
      Need(!owner.imports||owner.call_owner==std::this_thread::get_id(),"concurrent Firebase SDK guest import is outside the admitted synchronous profile");
      if(!owner.imports)owner.call_owner=std::this_thread::get_id();
      ++owner.imports;
    }
    ~Import(){std::lock_guard lock(owner.mutex);if(!--owner.imports)owner.call_owner={};}
  };
  struct Callback {
    std::shared_ptr<Impl> owner;
    Callback(){
      {std::lock_guard lock(global_mutex);owner=global;}
      Need(bool(owner),"Firebase callback has no live service owner");
      {std::lock_guard lock(owner->mutex);
        Need(!owner->revoked,"Firebase callback service is revoked");
        Need(!owner->registering,"Firebase callback overlaps native callback registration");
        Need(owner->imports&&owner->call_owner==std::this_thread::get_id(),"asynchronous/foreign Firebase callback is outside the admitted synchronous SDK-call profile");
        ++owner->callbacks;
      }
    }
    ~Callback(){if(owner){std::lock_guard lock(owner->mutex);--owner->callbacks;}}
  };
  uint64_t Run(addr_t entry,const std::vector<addr_t>&values){
    Need(recomp::CurrentExecutionState()!=nullptr,"Firebase native callback arrived outside a guest execution");
    Need(config.admitted_thread(),"Firebase callback guest thread is not admitted");
    Need(entry&&config.translated_entry(entry),"Firebase callback target is not a live translated entry");
    return config.runner(entry,values);
  }
  template<size_t Index>static void ExceptionThunk(const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->exceptions[Index];}
      owner->Run(entry,{message.Address()});
    }catch(...){Report(owner,std::current_exception());}
  }
  template<size_t Index>static void ArgumentThunk(const char *text,const char *parameter)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text),argument(parameter);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->arguments[Index];}
      owner->Run(entry,{message.Address(),argument.Address()});
    }catch(...){Report(owner,std::current_exception());}
  }
  static const char *StringThunk(const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->string_callback;}
      // The original reverse-P/Invoke thunk returns its genuine marshaled C
      // allocation. Pass it unchanged; the original P/Invoke caller owns/free's
      // it. Never return a pointer into the temporary input snapshot.
      return reinterpret_cast<const char*>(owner->Run(entry,{message.Address()}));
    }catch(...){Report(owner,std::current_exception());return nullptr;}
  }
  static void LogThunk(int32_t level,const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->log_callback;}
      owner->Run(entry,{static_cast<uint32_t>(level),message.Address()});
    }catch(...){Report(owner,std::current_exception());}
  }
  static void Report(std::shared_ptr<Impl> owner,std::exception_ptr error)noexcept{
    if(!owner){try{std::lock_guard lock(global_mutex);owner=global;}catch(...){std::abort();}}
    if(owner)owner->Failed(error);
    else{std::fputs("Firebase callback reached a retired process service\n",stderr);std::abort();}
  }
  struct Registration {
    Impl &owner;
    Registration(Impl &value,const std::vector<addr_t>&entries,bool null_allowed=false):owner(value){
      for(addr_t entry:entries)Need((null_allowed&&!entry)||(entry&&owner.config.translated_entry(entry)),"Firebase registration requires actual translated callback entries");
      std::lock_guard lock(owner.mutex);
      Need(owner.imports==1&&owner.callbacks==0&&!owner.registering&&owner.call_owner==std::this_thread::get_id(),"Firebase callback registration requires exclusive SDK-call ownership");
      owner.registering=true;
    }
    ~Registration(){std::lock_guard lock(owner.mutex);owner.registering=false;}
  };
  void Register(const std::array<addr_t,11>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);exceptions=entries;}
    Function<RegisterExceptions>(kCommands[0])(&ExceptionThunk<0>,&ExceptionThunk<1>,&ExceptionThunk<2>,&ExceptionThunk<3>,&ExceptionThunk<4>,&ExceptionThunk<5>,&ExceptionThunk<6>,&ExceptionThunk<7>,&ExceptionThunk<8>,&ExceptionThunk<9>,&ExceptionThunk<10>);
  }
  void Register(const std::array<addr_t,3>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);arguments=entries;}
    Function<RegisterArguments>(kCommands[1])(&ArgumentThunk<0>,&ArgumentThunk<1>,&ArgumentThunk<2>);
  }
  void Register(addr_t entry,bool string){
    Registration registration(*this,{entry},!string);{std::lock_guard lock(mutex);(string?string_callback:log_callback)=entry;}
    if(string)Function<void(*)(StringCallback)>(kCommands[2])(&StringThunk);
    else Function<void(*)(LogCallback)>(kCommands[3])(entry?&LogThunk:nullptr);
  }
  void Revoke(){
    {std::lock_guard lock(mutex);if(revoked)return;Need(imports==0&&callbacks==0&&!registering,"Firebase revoke requires actual SDK import/callback quiescence");revoked=true;}
    NativeCall native;
    Function<void(*)(LogCallback)>(kCommands[3])(nullptr);
    Function<void(*)(StringCallback)>(kCommands[2])(nullptr);
    Function<RegisterArguments>(kCommands[1])(nullptr,nullptr,nullptr);
    Function<RegisterExceptions>(kCommands[0])(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr);
    {std::lock_guard lock(global_mutex);if(global.get()==this)global.reset();}
  }
};
std::mutex FirebaseAppService::Impl::global_mutex;
std::shared_ptr<FirebaseAppService::Impl> FirebaseAppService::Impl::global;
bool FirebaseAppService::Impl::generation_used=false;

FirebaseAppService::FirebaseAppService(Config config,addr_t base):marker_base_(base){
  Environment environment;
  try{
    Need((base&7)==0&&base<=UINT64_MAX-kCommands.size()*8,"invalid Firebase SDK marker base");
    Need(bool(config.verify_library)&&bool(config.runner)&&bool(config.admitted_thread)&&bool(config.translated_entry),"Firebase SDK requires file verification and actual guest callback admission");
    const auto &path=config.dll_path;
    Need(path.size()>3&&((path[1]==L':'&&(path[2]==L'\\'||path[2]==L'/'))||(path[0]==L'\\'&&path[1]==L'\\')),"Firebase SDK requires an absolute Windows DLL path");
    const auto split=path.find_last_of(L"/\\");
    Need(split!=path.npos&&path.substr(split+1)==L"FirebaseCppApp-9_6_0.dll","Firebase SDK DLL filename differs from qualified package");
    config.verify_library(path,kDllSha256);
    auto impl=std::make_shared<Impl>(std::move(config));
    {std::lock_guard lock(Impl::global_mutex);Need(!Impl::generation_used&&!Impl::global,"only one Firebase SDK service generation is admitted per process");}
    impl->library=LoadLibraryExW(impl->config.dll_path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    Need(impl->library!=nullptr,"cannot load the verified Firebase Windows SDK DLL");
    // Verify the actual loaded module as well: a preloaded same-name DLL must
    // never substitute unverified code for the caller's requested file.
    try{std::vector<wchar_t> loaded(32768);auto length=GetModuleFileNameW(impl->library,loaded.data(),static_cast<DWORD>(loaded.size()));
      Need(length&&length<loaded.size(),"cannot identify the actual loaded Firebase SDK DLL");
      impl->config.verify_library(std::wstring(loaded.data(),length),kDllSha256);
      for(const auto&name:kCommands){auto symbol=GetProcAddress(impl->library,name.c_str());Need(symbol!=nullptr,"qualified Firebase DLL is missing a closed typed export");impl->exports.emplace(name,symbol);}}
    catch(...){FreeLibrary(impl->library);throw;}
    {std::lock_guard lock(Impl::global_mutex);if(Impl::generation_used||Impl::global){FreeLibrary(impl->library);throw std::runtime_error("concurrent/repeated Firebase SDK service construction");}Impl::generation_used=true;Impl::global=impl;}
    // Successful loads intentionally retain their reference until process exit:
    // process-global native SDK callback state cannot outlive its code mapping.
    impl_=std::move(impl);
  }catch(...){environment.Restore();throw;}
  environment.Restore();
}
FirebaseAppService::~FirebaseAppService(){try{Revoke();}catch(...){std::fputs("Firebase SDK destroyed before callback quiescence\n",stderr);std::abort();}}
const std::vector<std::string>&FirebaseAppService::Commands(){return kCommands;}
addr_t FirebaseAppService::Marker(const std::string&name)const{auto it=std::find(kCommands.begin(),kCommands.end(),name);if(it==kCommands.end())throw std::invalid_argument("unknown typed Firebase SDK export");return marker_base_+8*static_cast<addr_t>(it-kCommands.begin());}
void FirebaseAppService::CheckHealthy()const{BoundaryEnvironment boundary;impl_->Healthy();}
void FirebaseAppService::Revoke(){BoundaryEnvironment boundary;if(impl_)impl_->Revoke();}
Module FirebaseAppService::MakeModule()const{
  Module module;module.name="libFirebaseCppApp-9_6_0.so";module.aliases={"FirebaseCppApp-9_6_0","FirebaseCppApp-9_6_0.so","FirebaseCppApp-9_6_0.dll","libFirebaseCppApp-9_6_0","libFirebaseCppApp-9_6_0.dll"};
  module.kind=Module::Kind::TypedService;for(const auto&name:kCommands)module.exports.emplace(name,Marker(name));module.reset_image=[]{};return module;
}
void FirebaseAppService::Install(recomp::Runtime&runtime){for(const auto&name:kCommands)runtime.AddImport(Marker(name),[this,name](State&s){Invoke(name,s);});}
void FirebaseAppService::Invoke(const std::string&name,State&state){
  BoundaryEnvironment boundary;
  (void)Marker(name);auto owner=impl_;Impl::Import active(*owner);
  {
    boundary.entry.Restore();
    NativeCall native;
    using A=addr_t;
    if(name==kCommands[0])recomp::MakeBridge<void(A,A,A,A,A,A,A,A,A,A,A)>([&](A a,A b,A c,A d,A e,A f,A g,A h,A i,A j,A k){owner->Register(std::array<A,11>{a,b,c,d,e,f,g,h,i,j,k});})(state);
    else if(name==kCommands[1])recomp::MakeBridge<void(A,A,A)>([&](A a,A b,A c){owner->Register(std::array<A,3>{a,b,c});})(state);
    else if(name==kCommands[2]||name==kCommands[3])recomp::MakeBridge<void(A)>([&](A a){owner->Register(a,name==kCommands[2]);})(state);
    else if(name==kCommands[4]||name==kCommands[15])recomp::MakeBridge<void(int32_t)>([&](int32_t value){owner->Function<void(*)(int32_t)>(name)(value);})(state);
    else if(name==kCommands[5]||name==kCommands[7]||name==kCommands[12]||name==kCommands[16])recomp::MakeBridge<int32_t()>([&]{return owner->Function<int32_t(*)()>(name)();})(state);
    else if(name==kCommands[6]||name==kCommands[8])recomp::MakeBridge<void(uint32_t)>([&](uint32_t value){owner->Function<void(*)(uint32_t)>(name)(value?1u:0u);})(state);
    else if(name==kCommands[9])recomp::MakeBridge<void(A,uint32_t)>([&](A address,uint32_t value){auto text=recomp::ReadGuestString(address);owner->Function<void(*)(const char*,uint32_t)>(name)(text.c_str(),value?1u:0u);})(state);
    else if(name==kCommands[10])recomp::MakeBridge<uint32_t(A)>([&](A address){auto text=recomp::ReadGuestString(address);return owner->Function<uint32_t(*)(const char*)>(name)(text.c_str());})(state);
    else if(name==kCommands[11]||name==kCommands[13])owner->Function<void(*)()>(name)();
    else if(name==kCommands[14])recomp::MakeBridge<void(A,A)>([&](A a,A b){auto first=recomp::ReadGuestString(a),second=recomp::ReadGuestString(b);owner->Function<void(*)(const char*,const char*)>(name)(first.c_str(),second.c_str());})(state);
    else if(name==kCommands[17])recomp::MakeBridge<A()>([&]{{std::lock_guard lock(owner->mutex);Need(owner->string_callback!=0,"Firebase default-name getter requires the registered original string callback");}return reinterpret_cast<A>(owner->Function<const char*(*)()>(name)());})(state);
    else throw std::logic_error("unbound typed Firebase SDK export");
  }
  owner->Healthy();
}
}  // namespace bunker::windows



