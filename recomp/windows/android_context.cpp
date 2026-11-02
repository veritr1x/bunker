#include "android_context.h"
#include "android_assets.h"
#include "unicode.h"
#include <algorithm>
#include <stdexcept>

namespace bunker::windows {
namespace {
using Value=jni::Host::ObjectValue;
struct ComponentState {Value package,name;};
struct UriState {Value text;};
struct ExtraState {LaunchExtra::Kind kind=LaunchExtra::kNull;Value text;int32_t integer=0;bool boolean=false;};
struct BundleState {std::map<std::u16string,ExtraState> values;};
struct IntentState {std::mutex mutex;Value action,component,data,data_string,package_selector;std::set<std::u16string> categories;uint32_t flags=0;std::shared_ptr<BundleState> extras;};
struct StorageState {
  struct Cached {bool set=false;Value file;};
  std::mutex mutex;std::u16string files,cache;
  std::function<int32_t(const std::u16string&)> prepare;
  Cached files_file,cache_file;
};
struct FileState {std::u16string path;Value text;};
struct ResolverState {Value package;};
struct ContextState {Value info,assets,package,intent,manager,code_path,resolver;std::shared_ptr<StorageState> storage;};
struct PackageState {AndroidContextConfig config;};
struct ActivityListState {std::set<std::u16string> components;};
Value Keep(jni::Host &host,addr_t local){auto value=host.CaptureValue(local);host.DeleteLocalReference(local);return value;}
std::optional<std::u16string> Text(jni::Host &host,const Value &value){auto local=host.LocalValue(value);auto text=host.StringValue(local);if(local)host.DeleteLocalReference(local);return text;}
bool Present(jni::Host &host,const Value &value){auto local=host.LocalValue(value);if(!local)return false;host.DeleteLocalReference(local);return true;}
const ExtraState *Extra(jni::Host &host,const BundleState &state,addr_t key){auto name=host.StringValue(key);if(!name)return nullptr;auto found=state.values.find(*name);return found==state.values.end()?nullptr:&found->second;}
addr_t Metadata(jni::Host &host,const std::map<std::u16string,LaunchExtra> &values){
  if(values.empty())return 0;
  auto bundle=std::make_shared<BundleState>();
  for(const auto &[name,extra]:values){
    if(extra.kind<LaunchExtra::kNull||extra.kind>LaunchExtra::kBoolean)throw std::invalid_argument("unsupported application metadata type");
    ExtraState value;value.kind=extra.kind;value.integer=extra.integer;value.boolean=extra.boolean;if(extra.kind==LaunchExtra::kString)value.text=Keep(host,host.NewString(extra.text));bundle->values.emplace(name,std::move(value));
  }
  return host.NewHostInstance("android/os/Bundle",bundle);
}
addr_t ApplicationInfo(jni::Host &host,const AndroidContextConfig &config,bool metadata){
  auto info=host.NewInstance("android/content/pm/ApplicationInfo");
  for(const auto &[name,value]:std::initializer_list<std::pair<const char*,std::u16string>>{{"sourceDir",config.source_dir},{"nativeLibraryDir",config.native_library_dir},{"dataDir",config.data_dir},{"packageName",config.package_name}}){auto text=host.NewString(value);host.SetObjectFieldValue(info,name,"Ljava/lang/String;",text);host.DeleteLocalReference(text);}
  host.SetIntFieldValue(info,"targetSdkVersion",config.target_sdk);host.SetIntFieldValue(info,"flags",config.flags);
  auto bundle=metadata?Metadata(host,config.application_metadata):0;host.SetObjectFieldValue(info,"metaData","Landroid/os/Bundle;",bundle);if(bundle)host.DeleteLocalReference(bundle);
  // This installed profile contains one configured base APK and no splits.
  host.SetObjectFieldValue(info,"splitPublicSourceDirs","[Ljava/lang/String;",0);
  return info;
}
bool KnownPackage(jni::Host &host,const PackageState &state,addr_t name){
  auto text=host.StringValue(name);if(!host.PendingException().empty())return false;
  if(!text){host.ThrowException("android/content/pm/PackageManager$NameNotFoundException");return false;}
  if(*text!=state.config.package_name){host.ThrowException("android/content/pm/PackageManager$NameNotFoundException",*text);return false;}
  return true;
}
addr_t InternalDirectory(jni::Host &host,const std::shared_ptr<StorageState> &storage,bool cache){
  if(!storage->prepare){host.ThrowException("java/lang/UnsupportedOperationException",u"internal directory backing is not configured");return 0;}
  const auto &path=cache?storage->cache:storage->files;
  // The backing callback may block on host filesystem work or attach another
  // JNI thread. Neither the JNI registry nor this cache lock is held here.
  const auto status=storage->prepare(path);
  if(status){host.ThrowException(status<0?"java/lang/IllegalStateException":"java/io/IOException",u"internal directory verification failed; Android errno="+Utf16(std::to_string(status)));return 0;}
  auto &slot=cache?storage->cache_file:storage->files_file;Value value;bool ready;
  {std::lock_guard lock(storage->mutex);ready=slot.set;value=slot.file;}
  if(!ready){
    auto file=std::make_shared<FileState>();file->path=path;file->text=Keep(host,host.NewString(path));auto candidate=Keep(host,host.NewHostInstance("java/io/File",std::move(file)));
    {std::lock_guard lock(storage->mutex);if(!slot.set){slot.file=std::move(candidate);slot.set=true;}value=slot.file;}
  }
  return host.LocalValue(value);
}
addr_t Env(jni::Host &host,size_t slot,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0){
  State state{};state.gpr.x0.qword=host.EnvAddress();state.gpr.x1.qword=a;state.gpr.x2.qword=b;state.gpr.x3.qword=c;state.gpr.x4.qword=d;host.InvokeEnv(slot,state);return state.gpr.x0.qword;
}
addr_t Call(jni::Host &host,addr_t receiver,const char *name,const char *signature,const jni::Host::MethodArguments &args={},bool boolean=false){
  if(!receiver){host.ThrowException("java/lang/NullPointerException");return 0;}
  auto clazz=Env(host,31,receiver);if(!clazz||!host.PendingException().empty())return 0;
  auto method=Env(host,33,clazz,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(signature));host.DeleteLocalReference(clazz);
  if(!method||!host.PendingException().empty())return 0;
  return Env(host,boolean?39:36,receiver,method,reinterpret_cast<addr_t>(args.data()));
}
bool TangoEnabled(jni::Host &host,addr_t player){
  auto context=host.GetObjectFieldValue(player,"mContext","Landroid/content/Context;");
  auto manager=Call(host,context,"getPackageManager","()Landroid/content/pm/PackageManager;");
  auto package=host.PendingException().empty()?Call(host,context,"getPackageName","()Ljava/lang/String;"):0;
  auto info=host.PendingException().empty()?Call(host,manager,"getApplicationInfo","(Ljava/lang/String;I)Landroid/content/pm/ApplicationInfo;",{package,128,0}):0;
  auto bundle=info&&host.PendingException().empty()?host.GetObjectFieldValue(info,"metaData","Landroid/os/Bundle;"):0;
  auto key=host.NewString(u"unity.tango-enable");
  const bool enabled=host.PendingException().empty()&&Call(host,bundle,"getBoolean","(Ljava/lang/String;)Z",{key,0,0},true);
  // The original private helper catches java.lang.Exception, not Error.
  if(!host.PendingException().empty()){
    auto exception=Env(host,15),base=Env(host,6,reinterpret_cast<addr_t>("java/lang/Exception"));
    if(Env(host,32,exception,base))host.ClearException();
    if(exception)host.DeleteLocalReference(exception);if(base)host.DeleteLocalReference(base);
  }
  for(auto local:{context,manager,package,info,bundle,key})if(local)host.DeleteLocalReference(local);
  return enabled&&host.PendingException().empty();
}
}
AndroidContext::AndroidContext(jni::Host &host, const AndroidContextConfig &config) : host_(host) {
  if (config.package_name.empty() || config.source_dir.empty() || config.source_dir.front() != u'/' ||
      config.native_library_dir.empty() || config.native_library_dir.front() != u'/' ||
      config.data_dir.empty() || config.data_dir.front() != u'/' || config.target_sdk <= 0)
    throw std::invalid_argument("Android context needs actual package/SDK metadata and absolute virtual Android paths");
  if(config.main_activity_filters)for(const auto &filter:*config.main_activity_filters)if(filter.component.empty())throw std::invalid_argument("MAIN activity-filter catalog needs component names");
  host.DefineClass("android/content/Context", {}, "java/lang/Object", true);
  host.DefineClass("android/app/Activity", {}, "android/content/Context", true);
  host.DefineClass("android/content/ContentResolver",{},"java/lang/Object",true);
  host.DefineClass("android/app/ContextImpl$ApplicationContentResolver",{},"android/content/ContentResolver",true);
  host.DefineInterface("android/content/ServiceConnection",{
    {"onServiceConnected","(Landroid/content/ComponentName;Landroid/os/IBinder;)V"},
    {"onServiceDisconnected","(Landroid/content/ComponentName;)V"},
    {"onBindingDied","(Landroid/content/ComponentName;)V"},
    {"onNullBinding","(Landroid/content/ComponentName;)V"}});
  if (config.activity_class != "android/app/Activity") host.DefineClass(config.activity_class, {}, "android/app/Activity");
  host.DefineClass("android/content/pm/PackageItemInfo", {}, "java/lang/Object", true);
  host.DefineClass("android/content/pm/ApplicationInfo", {}, "android/content/pm/PackageItemInfo", true);
  // File overrides Object.toString in Android. Declare the unsupported override
  // so virtual dispatch cannot silently substitute Object's identity formatter.
  host.DefineClass("java/io/File",{{"toString","()Ljava/lang/String;"}},"java/lang/Object",true);
  host.DefineClass("android/os/Environment",{},"java/lang/Object",true);
  host.DefineClass("android/content/Intent",{},"java/lang/Object",true);
  host.DefineClass("android/content/ComponentName",{},"java/lang/Object",true);
  host.DefineClass("android/os/BaseBundle",{},"java/lang/Object",true);
  host.DefineClass("android/os/Bundle",{},"android/os/BaseBundle",true);
  host.DefineClass("android/content/pm/PackageManager",{},"java/lang/Object",true);
  host.DefineClass("android/app/ApplicationPackageManager",{},"android/content/pm/PackageManager",true);
  host.DefineClass("android/content/pm/PackageInfo",{},"java/lang/Object",true);
  host.DefineClass("android/util/AndroidException",{},"java/lang/Exception",true);
  host.DefineClass("android/content/pm/PackageManager$NameNotFoundException",{},"android/util/AndroidException",true);
  // A typed host collection with data-backed isEmpty, not Java bytecode or a
  // general java.util implementation. Unknown collection operations fail.
  host.DefineClass("java/util/List",{},"java/lang/Object",true);
  host.DefineClass("android/net/Uri",{},"java/lang/Object",true);
  host.DefineClass("android/net/Uri$StringUri",{},"android/net/Uri",true);
  for (const char *field : {"sourceDir", "nativeLibraryDir", "dataDir"})
    host.DefineField("android/content/pm/ApplicationInfo", field, "Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageItemInfo","packageName","Ljava/lang/String;");
  host.DefineField("android/content/pm/ApplicationInfo", "targetSdkVersion", "I");
  host.DefineField("android/content/pm/ApplicationInfo", "flags", "I");
  host.DefineField("android/content/pm/PackageItemInfo","metaData","Landroid/os/Bundle;");
  host.DefineField("android/content/pm/ApplicationInfo","splitPublicSourceDirs","[Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","packageName","Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","versionName","Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","versionCode","I");
  host.DefineField("android/content/pm/PackageInfo","applicationInfo","Landroid/content/pm/ApplicationInfo;");
  for(const char *name:{"GET_META_DATA","GET_ACTIVITIES"})host.DefineField("android/content/pm/PackageManager",name,"I",true);
  host.DefineField("android/content/pm/PackageManager","GET_INTENT_FILTERS","I",true);
  host.DefineField("android/content/pm/PackageManager","FEATURE_AUDIO_LOW_LATENCY","Ljava/lang/String;",true);
  // Reached Unity lookup abc49c/abc4a4 uses the Intent class cache130e0f8.
  // This is the SDK's actual initialized String constant, not a Java body.
  host.DefineField("android/content/Intent","ACTION_MAIN","Ljava/lang/String;",true);
  host.DefineField("android/os/Environment","MEDIA_MOUNTED","Ljava/lang/String;",true);
  auto env=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto manager_class=env(6,reinterpret_cast<addr_t>("android/content/pm/PackageManager"));
  for(const auto &[name,value]:std::initializer_list<std::pair<const char*,int32_t>>{{"GET_META_DATA",128},{"GET_ACTIVITIES",1},{"GET_INTENT_FILTERS",32}}){auto field=env(144,manager_class,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>("I"));env(159,manager_class,field,static_cast<uint32_t>(value));}
  auto feature_field=env(144,manager_class,reinterpret_cast<addr_t>("FEATURE_AUDIO_LOW_LATENCY"),reinterpret_cast<addr_t>("Ljava/lang/String;"));auto feature=host.NewString(u"android.hardware.audio.low_latency");env(154,manager_class,feature_field,feature);host.DeleteLocalReference(feature);host.DeleteLocalReference(manager_class);
  auto intent_class=env(6,reinterpret_cast<addr_t>("android/content/Intent")),action_field=env(144,intent_class,reinterpret_cast<addr_t>("ACTION_MAIN"),reinterpret_cast<addr_t>("Ljava/lang/String;"));auto main=host.NewString(u"android.intent.action.MAIN");env(154,intent_class,action_field,main);auto main_action=Keep(host,main);host.DeleteLocalReference(intent_class);
  auto environment=env(6,reinterpret_cast<addr_t>("android/os/Environment")),mounted_field=env(144,environment,reinterpret_cast<addr_t>("MEDIA_MOUNTED"),reinterpret_cast<addr_t>("Ljava/lang/String;")),mounted=host.NewString(u"mounted");env(154,environment,mounted_field,mounted);host.DeleteLocalReference(mounted);host.DeleteLocalReference(environment);
  auto unmounted=Keep(host,host.NewString(u"unmounted"));
  host.DefineStaticObjectMethod("android/os/Environment","getExternalStorageState","()Ljava/lang/String;",[&host,unmounted](addr_t,const jni::Host::MethodArguments&){return host.LocalValue(unmounted);});
  auto global = [&](addr_t local) { auto result = host.NewGlobalReference(local); host.DeleteLocalReference(local); return result; };
  info_ = global(ApplicationInfo(host,config,true));
  assets_ = global(CreateJavaAssets(host,config.apk_assets));
  package_ = global(host.NewString(config.package_name));
  auto component=std::make_shared<ComponentState>();component->package=host.CaptureValue(package_);
  auto binary=config.activity_class;std::replace(binary.begin(),binary.end(),'/','.');
  component->name=Keep(host,host.NewString(Utf16(binary)));
  auto intent=std::make_shared<IntentState>();intent->action=main_action;intent->categories.insert(u"android.intent.category.LAUNCHER");
  intent->component=Keep(host,host.NewHostInstance("android/content/ComponentName",component));
  if(config.launch_data){auto uri=std::make_shared<UriState>();uri->text=Keep(host,host.NewString(*config.launch_data));intent->data_string=uri->text;intent->data=Keep(host,host.NewHostInstance("android/net/Uri$StringUri",uri));}
  if(!config.launch_extras.empty()){
    intent->extras=std::make_shared<BundleState>();
    for(auto &[name,extra]:config.launch_extras){if(extra.kind<LaunchExtra::kNull||extra.kind>LaunchExtra::kBoolean)throw std::invalid_argument("unsupported configured Intent extra type");ExtraState value;value.kind=extra.kind;value.integer=extra.integer;value.boolean=extra.boolean;if(extra.kind==LaunchExtra::kString)value.text=Keep(host,host.NewString(extra.text));intent->extras->values.emplace(name,std::move(value));}
  }
  auto state=std::make_shared<ContextState>();state->info=host.CaptureValue(info_);state->assets=host.CaptureValue(assets_);state->package=host.CaptureValue(package_);
  auto resolver=std::make_shared<ResolverState>();resolver->package=state->package;
  state->resolver=Keep(host,host.NewHostInstance("android/app/ContextImpl$ApplicationContentResolver",resolver));
  state->storage=std::make_shared<StorageState>();auto base=config.data_dir;while(base.size()>1&&base.back()==u'/')base.pop_back();if(base.back()!=u'/')base+=u'/';state->storage->files=base+u"files";state->storage->cache=base+u"cache";state->storage->prepare=config.prepare_internal_directory;
  // LoadedApk stores its installed app path independently of the public mutable
  // ApplicationInfo record. Snapshot the original immutable String object.
  state->code_path=Keep(host,host.GetObjectFieldValue(info_,"sourceDir","Ljava/lang/String;"));
  auto packages=std::make_shared<PackageState>();packages->config=config;state->manager=Keep(host,host.NewHostInstance("android/app/ApplicationPackageManager",packages));
  state->intent=Keep(host,host.NewHostInstance("android/content/Intent",intent));activity_=global(host.NewHostInstance(config.activity_class,state));
  host.DefineObjectMethod("android/content/Context","getApplicationInfo","()Landroid/content/pm/ApplicationInfo;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->info):0;});
  host.DefineObjectMethod("android/content/Context","getContentResolver","()Landroid/content/ContentResolver;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->resolver):0;});
  host.DefineObjectMethod("android/content/Context","getPackageCodePath","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->code_path):0;});
  for(bool cache:{false,true})host.DefineObjectMethod("android/content/Context",cache?"getCacheDir":"getFilesDir","()Ljava/io/File;",[&host,cache](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?InternalDirectory(host,state->storage,cache):0;});
  host.DefineObjectMethod("android/content/Context","getExternalFilesDir","(Ljava/lang/String;)Ljava/io/File;",[&host](addr_t object,const jni::Host::MethodArguments&){host.ReadHostState<ContextState>(object);return addr_t(0);});
  host.DefineObjectMethod("android/content/Context","getExternalCacheDir","()Ljava/io/File;",[&host](addr_t object){host.ReadHostState<ContextState>(object);return addr_t(0);});
  for(const char *method:{"getPath","getAbsolutePath"})host.DefineObjectMethod("java/io/File",method,"()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<FileState>(object);return state?host.LocalValue(state->text):0;});
  host.DefineObjectMethod("java/io/File","getParent","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<FileState>(object);if(!state)return addr_t(0);auto at=state->path.find_last_of(u'/');return at==std::u16string::npos||state->path==u"/"?0:host.NewString(state->path.substr(0,at?at:1));});
  host.DefineObjectMethod("android/content/Context","getPackageManager","()Landroid/content/pm/PackageManager;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->manager):0;});
  host.DefineObjectMethod("android/content/pm/PackageManager","getPackageInfo","(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;",[&host](addr_t object,const jni::Host::MethodArguments &args){
    auto state=host.ReadHostState<PackageState>(object);if(!state||!KnownPackage(host,*state,args[0]))return addr_t(0);
    if(static_cast<int32_t>(args[1])!=0){host.ThrowException("java/lang/UnsupportedOperationException",u"unimplemented PackageInfo flags");return addr_t(0);}
    if(!state->config.version){host.ThrowException("java/lang/UnsupportedOperationException",u"package version metadata is not configured");return addr_t(0);}
    auto result=host.NewInstance("android/content/pm/PackageInfo");
    auto package=host.NewString(state->config.package_name),version=host.NewString(state->config.version->name),info=ApplicationInfo(host,state->config,false);
    host.SetObjectFieldValue(result,"packageName","Ljava/lang/String;",package);host.SetObjectFieldValue(result,"versionName","Ljava/lang/String;",version);host.SetIntFieldValue(result,"versionCode",state->config.version->code);host.SetObjectFieldValue(result,"applicationInfo","Landroid/content/pm/ApplicationInfo;",info);
    host.DeleteLocalReference(package);host.DeleteLocalReference(version);host.DeleteLocalReference(info);return result;
  });
  host.DefineObjectMethod("android/content/pm/PackageManager","getApplicationInfo","(Ljava/lang/String;I)Landroid/content/pm/ApplicationInfo;",[&host](addr_t object,const jni::Host::MethodArguments &args){
    auto state=host.ReadHostState<PackageState>(object);if(!state||!KnownPackage(host,*state,args[0]))return addr_t(0);
    auto flags=static_cast<uint32_t>(args[1]);if(flags&~uint32_t(128)){host.ThrowException("java/lang/UnsupportedOperationException",u"unimplemented ApplicationInfo flags");return addr_t(0);}return ApplicationInfo(host,state->config,flags&128);
  });
  host.DefineBooleanMethod("android/content/pm/PackageManager","hasSystemFeature","(Ljava/lang/String;)Z",[&host](addr_t object,const jni::Host::MethodArguments &args){
    auto state=host.ReadHostState<PackageState>(object);if(!state)return false;auto name=host.StringValue(args[0]);
    // Closed feature profile: this host has not implemented/certified Android
    // low-latency playback or advertised other Android system features.
    return name&&state->config.supported_android_features.count(*name)!=0;
  });
  host.DefineObjectMethod("android/content/pm/PackageManager","queryIntentActivities","(Landroid/content/Intent;I)Ljava/util/List;",[&host](addr_t object,const jni::Host::MethodArguments &args){
    auto packages=host.ReadHostState<PackageState>(object);if(!packages)return addr_t(0);
    if(!args[0]){host.ThrowException("java/lang/NullPointerException",u"null Intent query");return addr_t(0);}auto intent=host.ReadHostState<IntentState>(args[0]);if(!intent)return addr_t(0);
    Value action,selector,component,data;std::set<std::u16string> categories;uint32_t intent_flags;
    {std::lock_guard lock(intent->mutex);action=intent->action;selector=intent->package_selector;categories=intent->categories;intent_flags=intent->flags;component=intent->component;data=intent->data;}
    auto flags=static_cast<uint32_t>(args[1]);auto query_action=Text(host,action),query_package=Text(host,selector);
    if(!packages->config.main_activity_filters||query_action!=std::optional<std::u16string>(u"android.intent.action.MAIN")||query_package!=std::optional<std::u16string>(packages->config.package_name)||Present(host,component)||Present(host,data)||(flags&~uint32_t(32))||(intent_flags&~uint32_t(32))){host.ThrowException("java/lang/UnsupportedOperationException",u"only catalogued current-package MAIN/no-data/no-component queries with flags0/GET_INTENT_FILTERS are implemented");return addr_t(0);}
    auto result=std::make_shared<ActivityListState>();
    for(const auto &filter:*packages->config.main_activity_filters)if(filter.enabled&&std::includes(filter.categories.begin(),filter.categories.end(),categories.begin(),categories.end()))result->components.insert(filter.component);
    return host.NewHostInstance("java/util/List",std::move(result));
  });
  host.DefineBooleanMethod("java/util/List","isEmpty","()Z",[&host](addr_t object,const jni::Host::MethodArguments&){auto state=host.ReadHostState<ActivityListState>(object);return state&&state->components.empty();});
  host.DefineObjectMethod("android/content/Context","getAssets","()Landroid/content/res/AssetManager;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->assets):0;});
  host.DefineObjectMethod("android/content/Context","getPackageName","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->package):0;});
  host.DefineObjectMethod("android/content/Context","getApplicationContext","()Landroid/content/Context;",[&host](addr_t object){return host.ReadHostState<ContextState>(object)?host.NewLocalReference(object):0;});
  host.DefineObjectMethod("android/app/Activity","getIntent","()Landroid/content/Intent;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->intent):0;});
  host.DefineObjectMethod("android/content/Intent","getAction","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->action):0;});
  host.DefineObjectMethod("android/content/Intent","getComponent","()Landroid/content/ComponentName;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->component):0;});
  host.DefineObjectMethod("android/content/Intent","getPackage","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);if(!state)return addr_t(0);Value selector;{std::lock_guard lock(state->mutex);selector=state->package_selector;}return host.LocalValue(selector);});
  host.DefineObjectMethod("android/content/Intent","getData","()Landroid/net/Uri;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->data):0;});
  host.DefineObjectMethod("android/content/Intent","getDataString","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->data_string):0;});
  host.DefineBooleanMethod("android/content/Intent","hasCategory","(Ljava/lang/String;)Z",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<IntentState>(object);auto name=host.StringValue(args[0]);if(!state||!name)return false;std::lock_guard lock(state->mutex);return state->categories.count(*name)!=0;});
  host.DefineConstructor("android/content/Intent","(Ljava/lang/String;)V",[&host,main_action](const jni::Host::MethodArguments &args){auto action=host.StringValue(args[0]);if(action&&*action!=u"android.intent.action.MAIN"){host.ThrowException("java/lang/UnsupportedOperationException",u"Intent action initialization is implemented only for MAIN/null");return addr_t(0);}auto state=std::make_shared<IntentState>();if(action)state->action=main_action;return host.NewHostInstance("android/content/Intent",std::move(state));});
  host.DefineObjectMethod("android/content/Intent","addCategory","(Ljava/lang/String;)Landroid/content/Intent;",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<IntentState>(object);if(!state)return addr_t(0);auto name=host.StringValue(args[0]);if(!name){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException",u"null Intent category");return addr_t(0);}{std::lock_guard lock(state->mutex);state->categories.insert(*name);}return host.NewLocalReference(object);});
  host.DefineObjectMethod("android/content/Intent","addFlags","(I)Landroid/content/Intent;",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<IntentState>(object);if(!state)return addr_t(0);{std::lock_guard lock(state->mutex);state->flags|=static_cast<uint32_t>(args[0]);}return host.NewLocalReference(object);});
  host.DefineObjectMethod("android/content/Intent","setPackage","(Ljava/lang/String;)Landroid/content/Intent;",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<IntentState>(object);if(!state)return addr_t(0);auto selector=host.CaptureValue(args[0]);{std::lock_guard lock(state->mutex);state->package_selector=std::move(selector);}return host.NewLocalReference(object);});
  host.DefineObjectMethod("android/content/Intent","getExtras","()Landroid/os/Bundle;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state&&state->extras?host.NewHostInstance("android/os/Bundle",std::make_shared<BundleState>(*state->extras)):0;});
  host.DefineObjectMethod("android/content/ComponentName","getPackageName","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<ComponentState>(object);return state?host.LocalValue(state->package):0;});
  host.DefineObjectMethod("android/content/ComponentName","getClassName","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<ComponentState>(object);return state?host.LocalValue(state->name):0;});
  host.DefineObjectMethod("android/net/Uri$StringUri","toString","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<UriState>(object);return state?host.LocalValue(state->text):0;});
  host.DefineBooleanMethod("android/os/BaseBundle","containsKey","(Ljava/lang/String;)Z",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<BundleState>(object);return state&&Extra(host,*state,args[0]);});
  host.DefineBooleanMethod("android/os/BaseBundle","getBoolean","(Ljava/lang/String;)Z",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<BundleState>(object);auto extra=state?Extra(host,*state,args[0]):nullptr;return extra&&extra->kind==LaunchExtra::kBoolean&&extra->boolean;});
  for(bool defaults:{false,true})host.DefineObjectMethod("android/os/BaseBundle","getString",defaults?"(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;":"(Ljava/lang/String;)Ljava/lang/String;",[&host,defaults](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<BundleState>(object);if(!state)return addr_t(0);auto extra=Extra(host,*state,args[0]);return extra&&extra->kind==LaunchExtra::kString?host.LocalValue(extra->text):defaults?host.NewLocalReference(args[1]):0;});
  if (!host.PendingException().empty()) throw std::runtime_error("Android context initialization failed: " + host.PendingException());
}
AndroidContext::~AndroidContext() {
  host_.DeleteGlobalReference(activity_); host_.DeleteGlobalReference(info_); host_.DeleteGlobalReference(assets_); host_.DeleteGlobalReference(package_);
}
addr_t AndroidContext::Activity() { return host_.NewLocalReference(activity_); }
void AndroidContext::BindUnityPlayer(addr_t player){
  auto &host=host_;
  if(!unity_methods_bound_){
    host.DefineField("com/unity3d/player/UnityPlayer","mContext","Landroid/content/Context;");
    host.DefineField("com/unity3d/player/UnityPlayer","currentActivity","Landroid/app/Activity;",true);
    host.DefineField("com/unity3d/player/UnityPlayer","m_ARCoreApi","Lcom/unity3d/player/GoogleARCoreApi;");
    host.BindBooleanMethod("com/unity3d/player/UnityPlayer","initializeGoogleAr","()Z",[&host](addr_t receiver,const jni::Host::MethodArguments&){
      auto api=host.GetObjectFieldValue(receiver,"m_ARCoreApi","Lcom/unity3d/player/GoogleARCoreApi;");
      if(api){host.DeleteLocalReference(api);return false;}
      auto clazz=Env(host,6,reinterpret_cast<addr_t>("com/unity3d/player/UnityPlayer"));
      auto field=Env(host,144,clazz,reinterpret_cast<addr_t>("currentActivity"),reinterpret_cast<addr_t>("Landroid/app/Activity;"));
      auto activity=Env(host,145,clazz,field);host.DeleteLocalReference(clazz);
      if(!activity)return false;host.DeleteLocalReference(activity);
      if(TangoEnabled(host,receiver))throw std::runtime_error("enabled Google ARCore requires original native initialize/resume side effects; no host implementation");
      return false;
    });
    unity_methods_bound_=true;
  }
  auto previous=host.GetObjectFieldValue(player,"mContext","Landroid/content/Context;");
  if(previous){host.DeleteLocalReference(previous);throw std::invalid_argument("UnityPlayer context facts are already bound");}
  if(!host.PendingException().empty())throw std::invalid_argument("UnityPlayer binding requires a live typed receiver");
  host.SetObjectFieldValue(player,"mContext","Landroid/content/Context;",activity_);
  host.SetObjectFieldValue(player,"m_ARCoreApi","Lcom/unity3d/player/GoogleARCoreApi;",0);
  auto clazz=Env(host,6,reinterpret_cast<addr_t>("com/unity3d/player/UnityPlayer"));
  auto field=Env(host,144,clazz,reinterpret_cast<addr_t>("currentActivity"),reinterpret_cast<addr_t>("Landroid/app/Activity;"));Env(host,154,clazz,field,activity_);host.DeleteLocalReference(clazz);
  if(!host.PendingException().empty())throw std::runtime_error("Unity AR Activity/context binding failed: "+host.PendingException());
}
}  // namespace bunker::windows
