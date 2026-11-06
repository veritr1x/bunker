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
#include <limits>
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
  "Firebase_App_CSharp_FirebaseApp_DefaultName_get",
  "Firebase_App_CSharp_FirebaseApp_AppSetDefaultConfigPath",
  "Firebase_App_CSharp_FirebaseApp_CreateInternal__SWIG_0",
  "Firebase_App_CSharp_FirebaseApp_NameInternal_get",
  "Firebase_App_CSharp_FirebaseApp_ReleaseReferenceInternal",
  "SWIGRegisterExceptionCallbacks_CrashlyticsInternal",
  "SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal",
  "SWIGRegisterStringCallback_CrashlyticsInternal",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_GetInstance__SWIG_0",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_Log",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_SetCustomKey",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_SetUserId",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsInternal_LogException",
  "Firebase_Crashlytics_CSharp_new_FirebaseCrashlyticsFrame",
  "Firebase_Crashlytics_CSharp_delete_FirebaseCrashlyticsFrame",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsFrame_library_set",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsFrame_symbol_set",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsFrame_fileName_set",
  "Firebase_Crashlytics_CSharp_FirebaseCrashlyticsFrame_lineNumber_set",
  "Firebase_Crashlytics_CSharp_new_StackFrames__SWIG_0",
  "Firebase_Crashlytics_CSharp_delete_StackFrames",
  "Firebase_Crashlytics_CSharp_StackFrames_Add",
  "Firebase_Crashlytics_CSharp_StackFrames_size",
  "Firebase_Crashlytics_CSharp_StackFrames_getitem",
  "SWIGRegisterExceptionCallbacks_FirebaseMessaging",
  "SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging",
  "SWIGRegisterStringCallback_FirebaseMessaging",
  "Firebase_Messaging_CSharp_SetListenerCallbacks",
  "Firebase_Messaging_CSharp_SetListenerCallbacksEnabled",
  "Firebase_Messaging_CSharp_SendPendingEvents",
  "Firebase_Messaging_CSharp_delete_FirebaseMessage"
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
  // Preserve the SDK's actual opaque App pointer and one reference for each
  // successful default-create result. No forged pointer reaches the DLL.
  std::vector<std::pair<addr_t,size_t>> apps;
  unsigned config_observations=0,create_observations=0;
  std::array<addr_t,11> crash_exceptions{};std::array<addr_t,3> crash_arguments{};
  addr_t crash_string_callback=0;
  struct CrashInstance {addr_t pointer,parent_app;};
  struct CrashFrame {addr_t pointer,vector_owner;}; // zero owner: own native new/delete
  std::vector<CrashInstance> crash_instances;
  std::vector<CrashFrame> crash_frames;
  std::vector<addr_t> crash_vectors;
  std::array<addr_t,11> messaging_exceptions{};std::array<addr_t,3> messaging_arguments{};
  addr_t messaging_string_callback=0,messaging_message_callback=0,messaging_token_callback=0,messaging_parent_app=0;
  struct MessagingMessage {addr_t pointer;bool pending,deleted;};
  std::vector<MessagingMessage> messaging_messages;
  using MessageCallback=int32_t(*)(void*);using TokenCallback=void(*)(const char*);
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
  template<size_t Index,size_t Family=0>static void ExceptionThunk(const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=Family==2?owner->messaging_exceptions[Index]:Family?owner->crash_exceptions[Index]:owner->exceptions[Index];}
      owner->Run(entry,{message.Address()});
    }catch(...){Report(owner,std::current_exception());}
  }
  template<size_t Index,size_t Family=0>static void ArgumentThunk(const char *text,const char *parameter)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text),argument(parameter);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=Family==2?owner->messaging_arguments[Index]:Family?owner->crash_arguments[Index]:owner->arguments[Index];}
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
  static const char *CrashStringThunk(const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->crash_string_callback;}
      return reinterpret_cast<const char*>(owner->Run(entry,{message.Address()}));
    }catch(...){Report(owner,std::current_exception());return nullptr;}
  }
  static const char *MessagingStringThunk(const char *text)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;PublishedString message(text);
      addr_t entry;{std::lock_guard lock(owner->mutex);entry=owner->messaging_string_callback;}
      return reinterpret_cast<const char*>(owner->Run(entry,{message.Address()}));
    }catch(...){Report(owner,std::current_exception());return nullptr;}
  }
  static int32_t MessageThunk(void *message)noexcept{
    std::shared_ptr<Impl> owner;const auto pointer=reinterpret_cast<addr_t>(message);bool tracked=false;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;addr_t entry;
      {std::lock_guard lock(owner->mutex);entry=owner->messaging_message_callback;
        Need(pointer&&owner->messaging_parent_app,"Messaging callback has no real message/live listener");
        Need(std::none_of(owner->messaging_messages.begin(),owner->messaging_messages.end(),[&](const auto&r){return r.pointer==pointer;}),"Messaging callback aliases an outstanding native message");
        owner->messaging_messages.push_back({pointer,true,false});tracked=true;}
      const auto result=static_cast<int32_t>(static_cast<uint32_t>(owner->Run(entry,{pointer})));
      bool destroy=false;
      {std::lock_guard lock(owner->mutex);auto row=std::find_if(owner->messaging_messages.begin(),owner->messaging_messages.end(),[&](const auto&r){return r.pointer==pointer;});
        destroy=result&&row->deleted;
        if(!result||row->deleted)owner->messaging_messages.erase(row);else row->pending=false;}
      if(destroy){NativeCall native;owner->Function<void(*)(void*)>(kCommands[47])(message);}
      return result;
    }catch(...){auto error=std::current_exception();
      // Pending guest Dispose requests are deferred. The native caller keeps
      // ownership on zero or failed callback and deletes its actual copy.
      if(owner&&tracked){std::lock_guard lock(owner->mutex);auto row=std::find_if(owner->messaging_messages.begin(),owner->messaging_messages.end(),[&](const auto&r){return r.pointer==pointer;});
        if(row!=owner->messaging_messages.end())owner->messaging_messages.erase(row);}
      Report(owner,error);return 0;
    }
  }
  static void TokenThunk(const char *token)noexcept{
    std::shared_ptr<Impl> owner;
    try{Callback active;owner=active.owner;CallbackEnvironment environment;addr_t entry;
      {std::lock_guard lock(owner->mutex);entry=owner->messaging_token_callback;Need(owner->messaging_parent_app!=0,"Messaging token has no live listener");}
      // SWIG already passed its real allocating string callback result. Keep
      // that exact pointer/ownership for the original reverse-PInvoke thunk.
      owner->Run(entry,{reinterpret_cast<addr_t>(token)});
    }catch(...){Report(owner,std::current_exception());}
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
  void RegisterCrash(const std::array<addr_t,11>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);crash_exceptions=entries;}
    Function<RegisterExceptions>(kCommands[22])(&ExceptionThunk<0,true>,&ExceptionThunk<1,true>,&ExceptionThunk<2,true>,&ExceptionThunk<3,true>,&ExceptionThunk<4,true>,&ExceptionThunk<5,true>,&ExceptionThunk<6,true>,&ExceptionThunk<7,true>,&ExceptionThunk<8,true>,&ExceptionThunk<9,true>,&ExceptionThunk<10,true>);
  }
  void RegisterCrash(const std::array<addr_t,3>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);crash_arguments=entries;}
    Function<RegisterArguments>(kCommands[23])(&ArgumentThunk<0,true>,&ArgumentThunk<1,true>,&ArgumentThunk<2,true>);
  }
  void RegisterCrash(addr_t entry){
    Registration registration(*this,{entry});{std::lock_guard lock(mutex);crash_string_callback=entry;}
    Function<void(*)(StringCallback)>(kCommands[24])(&CrashStringThunk);
  }
  void RegisterMessaging(const std::array<addr_t,11>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);messaging_exceptions=entries;}
    Function<RegisterExceptions>(kCommands[41])(&ExceptionThunk<0,2>,&ExceptionThunk<1,2>,&ExceptionThunk<2,2>,&ExceptionThunk<3,2>,&ExceptionThunk<4,2>,&ExceptionThunk<5,2>,&ExceptionThunk<6,2>,&ExceptionThunk<7,2>,&ExceptionThunk<8,2>,&ExceptionThunk<9,2>,&ExceptionThunk<10,2>);
  }
  void RegisterMessaging(const std::array<addr_t,3>&entries){
    Registration registration(*this,{entries.begin(),entries.end()});{std::lock_guard lock(mutex);messaging_arguments=entries;}
    Function<RegisterArguments>(kCommands[42])(&ArgumentThunk<0,2>,&ArgumentThunk<1,2>,&ArgumentThunk<2,2>);
  }
  void RegisterMessaging(addr_t entry){
    Registration registration(*this,{entry});{std::lock_guard lock(mutex);messaging_string_callback=entry;}
    Function<void(*)(StringCallback)>(kCommands[43])(&MessagingStringThunk);
  }
  void MessagingReady(){
    std::lock_guard lock(mutex);
    Need(messaging_string_callback&&std::all_of(messaging_exceptions.begin(),messaging_exceptions.end(),[](addr_t e){return e!=0;})&&
        std::all_of(messaging_arguments.begin(),messaging_arguments.end(),[](addr_t e){return e!=0;}),"Messaging call requires its separate original SWIG callback cohort");
  }
  void SetMessagingListener(addr_t message,addr_t token){
    MessagingReady();Registration registration(*this,{message,token},true);addr_t parent=0;
    // SDK stores each callback independently even when a partial registration
    // destroys its listener. Already queued deliveries can still use that slot.
    if(message||token){std::lock_guard lock(mutex);Need(apps.size()==1&&apps[0].second,"Messaging callback registration requires its real default App reference");parent=apps[0].first;}
    Function<void(*)(MessageCallback,TokenCallback)>(kCommands[44])(message?&MessageThunk:nullptr,token?&TokenThunk:nullptr);
    {std::lock_guard lock(mutex);messaging_message_callback=message;messaging_token_callback=token;messaging_parent_app=parent;}
  }
  void DeleteMessage(addr_t pointer){
    MessagingReady();{std::lock_guard lock(mutex);auto row=std::find_if(messaging_messages.begin(),messaging_messages.end(),[&](const auto&r){return r.pointer==pointer&&!r.deleted;});
      Need(pointer&&row!=messaging_messages.end(),"Messaging delete requires a native callback-owned message");
      if(row->pending){row->deleted=true;return;}}
    Function<void(*)(void*)>(kCommands[47])(reinterpret_cast<void*>(pointer));
    {std::lock_guard lock(mutex);auto row=std::find_if(messaging_messages.begin(),messaging_messages.end(),[&](const auto&r){return r.pointer==pointer;});messaging_messages.erase(row);}
  }
  void AppCall() {
    std::lock_guard lock(mutex);
    Need(imports==1&&callbacks==0&&call_owner==std::this_thread::get_id(),
        "Firebase App call requires exclusive non-callback SDK-call ownership");
    Need(string_callback&&std::all_of(exceptions.begin(),exceptions.end(),[](addr_t entry){return entry!=0;})&&
        std::all_of(arguments.begin(),arguments.end(),[](addr_t entry){return entry!=0;}),
        "Firebase App call requires the original registered SWIG callback cohort");
  }
  void SetConfig(addr_t address) {
    AppCall();auto original=recomp::ReadGuestString(address);
    auto path=config.resolve_config_path?config.resolve_config_path(original):original;
    if(config_observations++<8)std::fprintf(stderr,"Windows Firebase SDK App: config path input_bytes=%zu native_bytes=%zu mapped=%d; configuration values supplied unchanged\n",original.size(),path.size(),int(path!=original));
    Function<void(*)(const char*)>(kCommands[18])(path.c_str());
  }
  addr_t CreateApp() {
    AppCall();
    {
      std::lock_guard lock(mutex);
      for(const auto &entry:apps)Need(entry.second<std::numeric_limits<size_t>::max(),"Firebase App reference count exhausted");
      // Reserve bookkeeping before the native SDK can create an owned App.
      apps.reserve(apps.size()+1);
    }
    const auto result=reinterpret_cast<addr_t>(Function<void*(*)()>(kCommands[19])());
    if(result){
      std::lock_guard lock(mutex);
      auto found=std::find_if(apps.begin(),apps.end(),[&](const auto &entry){return entry.first==result;});
      if(found==apps.end())apps.emplace_back(result,1);else ++found->second;
    }
    if(create_observations++<8)std::fprintf(stderr,"Windows Firebase SDK App: genuine default CreateInternal returned=%#llx; no synthetic App or dependency result\n",static_cast<unsigned long long>(result));
    return result;
  }
  void RequireApp(addr_t address,bool string) {
    AppCall();std::lock_guard lock(mutex);
    Need(address&&std::any_of(apps.begin(),apps.end(),[&](const auto &entry){return entry.first==address&&entry.second;}),"Firebase App handle is not a live service-owned native reference");
    if(string)Need(string_callback!=0,"Firebase App name getter requires the registered original string callback");
  }
  addr_t AppName(addr_t address) {
    RequireApp(address,true);
    return reinterpret_cast<addr_t>(Function<const char*(*)(void*)>(kCommands[20])(reinterpret_cast<void*>(address)));
  }
  void ReleaseApp(addr_t address) {
    RequireApp(address,false);
    {std::lock_guard lock(mutex);auto row=std::find_if(apps.begin(),apps.end(),[&](const auto&r){return r.first==address;});
      Need(row->second!=1||messaging_parent_app!=address,"detach the native Messaging listener before releasing its last App reference");}
    Function<void(*)(void*)>(kCommands[21])(reinterpret_cast<void*>(address));
    // A deferred callback error does not undo a completed native release.
    std::lock_guard lock(mutex);
    auto found=std::find_if(apps.begin(),apps.end(),[&](const auto &entry){return entry.first==address;});
    if(!--found->second){
      apps.erase(found);
      crash_instances.erase(std::remove_if(crash_instances.begin(),crash_instances.end(),[&](const auto &entry){return entry.parent_app==address;}),crash_instances.end());
    }
  }
  void CrashCall(){
    AppCall();std::lock_guard lock(mutex);
    Need(crash_string_callback&&std::all_of(crash_exceptions.begin(),crash_exceptions.end(),[](addr_t entry){return entry!=0;})&&
        std::all_of(crash_arguments.begin(),crash_arguments.end(),[](addr_t entry){return entry!=0;}),
        "Crashlytics call requires its own original registered SWIG callback cohort");
  }
  addr_t CrashInstanceFor(addr_t app,addr_t status_address){
    RequireApp(app,false);CrashCall();
    Need(status_address&&!(status_address&3)&&status_address<=UINT64_MAX-sizeof(int32_t),"Crashlytics init result requires a nonnull aligned guest int32");
    int32_t status=0;recomp::ReadGuestMemory(&status,status_address,sizeof(status));
    {std::lock_guard lock(mutex);crash_instances.reserve(crash_instances.size()+1);}
    const auto result=reinterpret_cast<addr_t>(Function<void*(*)(void*,int32_t*)>(kCommands[25])(reinterpret_cast<void*>(app),&status));
    recomp::WriteGuestMemory(status_address,&status,sizeof(status));
    if(result){std::lock_guard lock(mutex);auto found=std::find_if(crash_instances.begin(),crash_instances.end(),[&](const auto &entry){return entry.pointer==result;});
      Need(found==crash_instances.end()||found->parent_app==app,"Crashlytics instance aliases another live App");
      if(found==crash_instances.end())crash_instances.push_back({result,app});}
    return result;
  }
  void RequireCrash(addr_t instance){
    CrashCall();std::lock_guard lock(mutex);
    auto found=std::find_if(crash_instances.begin(),crash_instances.end(),[&](const auto &entry){return entry.pointer==instance;});
    Need(instance&&found!=crash_instances.end()&&std::any_of(apps.begin(),apps.end(),[&](const auto &entry){return entry.first==found->parent_app&&entry.second;}),"Crashlytics instance has no live owned parent App reference");
  }
  void RequireVector(addr_t pointer){
    CrashCall();std::lock_guard lock(mutex);
    Need(pointer&&std::find(crash_vectors.begin(),crash_vectors.end(),pointer)!=crash_vectors.end(),"Crashlytics vector is not a live owned native object");
  }
  CrashFrame RequireFrame(addr_t pointer){
    CrashCall();std::lock_guard lock(mutex);auto found=std::find_if(crash_frames.begin(),crash_frames.end(),[&](const auto &entry){return entry.pointer==pointer;});
    Need(pointer&&found!=crash_frames.end(),"Crashlytics frame is not a live owned object or current borrowed view");return *found;
  }
  addr_t NewCrashObject(bool vector){
    CrashCall();{std::lock_guard lock(mutex);if(vector)crash_vectors.reserve(crash_vectors.size()+1);else crash_frames.reserve(crash_frames.size()+1);}
    const auto result=reinterpret_cast<addr_t>(Function<void*(*)()>(kCommands[vector?36:30])());
    if(result){std::lock_guard lock(mutex);if(vector)crash_vectors.push_back(result);else crash_frames.push_back({result,0});}return result;
  }
  void ForgetViews(addr_t vector){
    crash_frames.erase(std::remove_if(crash_frames.begin(),crash_frames.end(),[&](const auto &entry){return entry.vector_owner==vector;}),crash_frames.end());
  }
  void DeleteCrashObject(addr_t pointer,bool vector){
    if(vector)RequireVector(pointer);else Need(!RequireFrame(pointer).vector_owner,"borrowed Crashlytics frame must not be deleted");
    Function<void(*)(void*)>(kCommands[vector?37:31])(reinterpret_cast<void*>(pointer));
    std::lock_guard lock(mutex);
    if(vector){ForgetViews(pointer);crash_vectors.erase(std::find(crash_vectors.begin(),crash_vectors.end(),pointer));}
    else crash_frames.erase(std::find_if(crash_frames.begin(),crash_frames.end(),[&](const auto &entry){return entry.pointer==pointer;}));
  }
  void AddFrame(addr_t vector,addr_t frame){
    RequireVector(vector);RequireFrame(frame);
    // Native vector mutation may relocate all borrowed item addresses, even
    // when the SDK reports an exception. Revoke those views conservatively.
    {std::lock_guard lock(mutex);ForgetViews(vector);}
    Function<void(*)(void*,void*)>(kCommands[38])(reinterpret_cast<void*>(vector),reinterpret_cast<void*>(frame));
  }
  addr_t ItemFrame(addr_t vector,int32_t index){
    RequireVector(vector);{std::lock_guard lock(mutex);crash_frames.reserve(crash_frames.size()+1);}
    const auto result=reinterpret_cast<addr_t>(Function<void*(*)(void*,int32_t)>(kCommands[40])(reinterpret_cast<void*>(vector),index));
    if(result){std::lock_guard lock(mutex);auto found=std::find_if(crash_frames.begin(),crash_frames.end(),[&](const auto &entry){return entry.pointer==result;});
      Need(found==crash_frames.end()||found->vector_owner==vector,"Crashlytics borrowed frame aliases another object");
      if(found==crash_frames.end())crash_frames.push_back({result,vector});}return result;
  }
  void Revoke(){
    {std::lock_guard lock(mutex);if(revoked)return;Need(imports==0&&callbacks==0&&!registering,"Firebase revoke requires actual SDK import/callback quiescence");Need(apps.empty(),"Firebase revoke requires all native App references released");Need(crash_vectors.empty()&&crash_frames.empty(),"Firebase revoke requires all native Crashlytics frame/vector objects released");Need(!messaging_parent_app&&messaging_messages.empty(),"Firebase revoke requires detached Messaging listener and released native messages");revoked=true;}
    NativeCall native;
    Function<void(*)(MessageCallback,TokenCallback)>(kCommands[44])(nullptr,nullptr);
    Function<void(*)(StringCallback)>(kCommands[43])(nullptr);
    Function<RegisterArguments>(kCommands[42])(nullptr,nullptr,nullptr);
    Function<RegisterExceptions>(kCommands[41])(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr);
    Function<void(*)(LogCallback)>(kCommands[3])(nullptr);
    Function<void(*)(StringCallback)>(kCommands[2])(nullptr);
    Function<RegisterArguments>(kCommands[1])(nullptr,nullptr,nullptr);
    Function<RegisterExceptions>(kCommands[0])(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr);
    Function<void(*)(StringCallback)>(kCommands[24])(nullptr);
    Function<RegisterArguments>(kCommands[23])(nullptr,nullptr,nullptr);
    Function<RegisterExceptions>(kCommands[22])(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr);
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
    else if(name==kCommands[18])recomp::MakeBridge<void(A)>([&](A address){owner->SetConfig(address);})(state);
    else if(name==kCommands[19])recomp::MakeBridge<A()>([&]{return owner->CreateApp();})(state);
    else if(name==kCommands[20])recomp::MakeBridge<A(A)>([&](A address){return owner->AppName(address);})(state);
    else if(name==kCommands[21])recomp::MakeBridge<void(A)>([&](A address){owner->ReleaseApp(address);})(state);
    else if(name==kCommands[22])recomp::MakeBridge<void(A,A,A,A,A,A,A,A,A,A,A)>([&](A a,A b,A c,A d,A e,A f,A g,A h,A i,A j,A k){owner->RegisterCrash(std::array<A,11>{a,b,c,d,e,f,g,h,i,j,k});})(state);
    else if(name==kCommands[23])recomp::MakeBridge<void(A,A,A)>([&](A a,A b,A c){owner->RegisterCrash(std::array<A,3>{a,b,c});})(state);
    else if(name==kCommands[24])recomp::MakeBridge<void(A)>([&](A entry){owner->RegisterCrash(entry);})(state);
    else if(name==kCommands[25])recomp::MakeBridge<A(A,A)>([&](A app,A status){return owner->CrashInstanceFor(app,status);})(state);
    else if(name==kCommands[26]||name==kCommands[28])recomp::MakeBridge<void(A,A)>([&](A instance,A text){owner->RequireCrash(instance);auto copy=recomp::ReadGuestString(text);owner->Function<void(*)(void*,const char*)>(name)(reinterpret_cast<void*>(instance),copy.c_str());})(state);
    else if(name==kCommands[27])recomp::MakeBridge<void(A,A,A)>([&](A instance,A key,A value){owner->RequireCrash(instance);auto first=recomp::ReadGuestString(key),second=recomp::ReadGuestString(value);owner->Function<void(*)(void*,const char*,const char*)>(name)(reinterpret_cast<void*>(instance),first.c_str(),second.c_str());})(state);
    else if(name==kCommands[29])recomp::MakeBridge<void(A,A,A,A)>([&](A instance,A type,A message,A frames){owner->RequireCrash(instance);owner->RequireVector(frames);auto first=recomp::ReadGuestString(type),second=recomp::ReadGuestString(message);owner->Function<void(*)(void*,const char*,const char*,void*)>(name)(reinterpret_cast<void*>(instance),first.c_str(),second.c_str(),reinterpret_cast<void*>(frames));})(state);
    else if(name==kCommands[30]||name==kCommands[36])recomp::MakeBridge<A()>([&]{return owner->NewCrashObject(name==kCommands[36]);})(state);
    else if(name==kCommands[31]||name==kCommands[37])recomp::MakeBridge<void(A)>([&](A pointer){owner->DeleteCrashObject(pointer,name==kCommands[37]);})(state);
    else if(name==kCommands[32]||name==kCommands[33]||name==kCommands[34]||name==kCommands[35])recomp::MakeBridge<void(A,A)>([&](A frame,A text){owner->RequireFrame(frame);auto copy=recomp::ReadGuestString(text);owner->Function<void(*)(void*,const char*)>(name)(reinterpret_cast<void*>(frame),copy.c_str());})(state);
    else if(name==kCommands[38])recomp::MakeBridge<void(A,A)>([&](A vector,A frame){owner->AddFrame(vector,frame);})(state);
    else if(name==kCommands[39])recomp::MakeBridge<uint32_t(A)>([&](A vector){owner->RequireVector(vector);return owner->Function<uint32_t(*)(void*)>(name)(reinterpret_cast<void*>(vector));})(state);
    else if(name==kCommands[40])recomp::MakeBridge<A(A,int32_t)>([&](A vector,int32_t index){return owner->ItemFrame(vector,index);})(state);
    else if(name==kCommands[41])recomp::MakeBridge<void(A,A,A,A,A,A,A,A,A,A,A)>([&](A a,A b,A c,A d,A e,A f,A g,A h,A i,A j,A k){owner->RegisterMessaging(std::array<A,11>{a,b,c,d,e,f,g,h,i,j,k});})(state);
    else if(name==kCommands[42])recomp::MakeBridge<void(A,A,A)>([&](A a,A b,A c){owner->RegisterMessaging(std::array<A,3>{a,b,c});})(state);
    else if(name==kCommands[43])recomp::MakeBridge<void(A)>([&](A entry){owner->RegisterMessaging(entry);})(state);
    else if(name==kCommands[44])recomp::MakeBridge<void(A,A)>([&](A message,A token){owner->SetMessagingListener(message,token);})(state);
    else if(name==kCommands[45])recomp::MakeBridge<void(uint32_t,uint32_t)>([&](uint32_t message,uint32_t token){owner->MessagingReady();owner->Function<void(*)(uint32_t,uint32_t)>(name)(message?1u:0u,token?1u:0u);})(state);
    else if(name==kCommands[46]){owner->MessagingReady();owner->Function<void(*)()>(name)();}
    else if(name==kCommands[47])recomp::MakeBridge<void(A)>([&](A message){owner->DeleteMessage(message);})(state);
    else throw std::logic_error("unbound typed Firebase SDK export");
  }
  owner->Healthy();
}
}  // namespace bunker::windows



