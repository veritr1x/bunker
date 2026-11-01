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
struct IntentState {Value action,component,data,data_string;std::shared_ptr<BundleState> extras;};
struct ContextState {Value info,assets,package,intent,manager;};
struct PackageState {AndroidContextConfig config;};
Value Keep(jni::Host &host,addr_t local){auto value=host.CaptureValue(local);host.DeleteLocalReference(local);return value;}
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
}
AndroidContext::AndroidContext(jni::Host &host, const AndroidContextConfig &config) : host_(host) {
  if (config.package_name.empty() || config.source_dir.empty() || config.source_dir.front() != u'/' ||
      config.native_library_dir.empty() || config.native_library_dir.front() != u'/' ||
      config.data_dir.empty() || config.data_dir.front() != u'/' || config.target_sdk <= 0)
    throw std::invalid_argument("Android context needs actual package/SDK metadata and absolute virtual Android paths");
  host.DefineClass("android/content/Context", {}, "java/lang/Object", true);
  host.DefineClass("android/app/Activity", {}, "android/content/Context", true);
  if (config.activity_class != "android/app/Activity") host.DefineClass(config.activity_class, {}, "android/app/Activity");
  host.DefineClass("android/content/pm/ApplicationInfo", {}, "java/lang/Object", true);
  host.DefineClass("android/content/Intent",{},"java/lang/Object",true);
  host.DefineClass("android/content/ComponentName",{},"java/lang/Object",true);
  host.DefineClass("android/os/BaseBundle",{},"java/lang/Object",true);
  host.DefineClass("android/os/Bundle",{},"android/os/BaseBundle",true);
  host.DefineClass("android/content/pm/PackageManager",{},"java/lang/Object",true);
  host.DefineClass("android/app/ApplicationPackageManager",{},"android/content/pm/PackageManager",true);
  host.DefineClass("android/content/pm/PackageInfo",{},"java/lang/Object",true);
  host.DefineClass("android/util/AndroidException",{},"java/lang/Exception",true);
  host.DefineClass("android/content/pm/PackageManager$NameNotFoundException",{},"android/util/AndroidException",true);
  host.DefineClass("android/net/Uri",{},"java/lang/Object",true);
  host.DefineClass("android/net/Uri$StringUri",{},"android/net/Uri",true);
  for (const char *field : {"sourceDir", "nativeLibraryDir", "dataDir", "packageName"})
    host.DefineField("android/content/pm/ApplicationInfo", field, "Ljava/lang/String;");
  host.DefineField("android/content/pm/ApplicationInfo", "targetSdkVersion", "I");
  host.DefineField("android/content/pm/ApplicationInfo", "flags", "I");
  host.DefineField("android/content/pm/ApplicationInfo","metaData","Landroid/os/Bundle;");
  host.DefineField("android/content/pm/ApplicationInfo","splitPublicSourceDirs","[Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","packageName","Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","versionName","Ljava/lang/String;");
  host.DefineField("android/content/pm/PackageInfo","versionCode","I");
  host.DefineField("android/content/pm/PackageInfo","applicationInfo","Landroid/content/pm/ApplicationInfo;");
  for(const char *name:{"GET_META_DATA","GET_ACTIVITIES"})host.DefineField("android/content/pm/PackageManager",name,"I",true);
  host.DefineField("android/content/pm/PackageManager","FEATURE_AUDIO_LOW_LATENCY","Ljava/lang/String;",true);
  // Reached Unity lookup abc49c/abc4a4 uses the Intent class cache130e0f8.
  // This is the SDK's actual initialized String constant, not a Java body.
  host.DefineField("android/content/Intent","ACTION_MAIN","Ljava/lang/String;",true);
  auto env=[&](size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto manager_class=env(6,reinterpret_cast<addr_t>("android/content/pm/PackageManager"));
  for(const auto &[name,value]:std::initializer_list<std::pair<const char*,int32_t>>{{"GET_META_DATA",128},{"GET_ACTIVITIES",1}}){auto field=env(144,manager_class,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>("I"));env(159,manager_class,field,static_cast<uint32_t>(value));}
  auto feature_field=env(144,manager_class,reinterpret_cast<addr_t>("FEATURE_AUDIO_LOW_LATENCY"),reinterpret_cast<addr_t>("Ljava/lang/String;"));auto feature=host.NewString(u"android.hardware.audio.low_latency");env(154,manager_class,feature_field,feature);host.DeleteLocalReference(feature);host.DeleteLocalReference(manager_class);
  auto intent_class=env(6,reinterpret_cast<addr_t>("android/content/Intent")),action_field=env(144,intent_class,reinterpret_cast<addr_t>("ACTION_MAIN"),reinterpret_cast<addr_t>("Ljava/lang/String;"));auto main=host.NewString(u"android.intent.action.MAIN");env(154,intent_class,action_field,main);auto main_action=Keep(host,main);host.DeleteLocalReference(intent_class);
  auto global = [&](addr_t local) { auto result = host.NewGlobalReference(local); host.DeleteLocalReference(local); return result; };
  info_ = global(ApplicationInfo(host,config,true));
  assets_ = global(CreateJavaAssets(host,config.apk_assets));
  package_ = global(host.NewString(config.package_name));
  auto component=std::make_shared<ComponentState>();component->package=host.CaptureValue(package_);
  auto binary=config.activity_class;std::replace(binary.begin(),binary.end(),'/','.');
  component->name=Keep(host,host.NewString(Utf16(binary)));
  auto intent=std::make_shared<IntentState>();intent->action=std::move(main_action);
  intent->component=Keep(host,host.NewHostInstance("android/content/ComponentName",component));
  if(config.launch_data){auto uri=std::make_shared<UriState>();uri->text=Keep(host,host.NewString(*config.launch_data));intent->data_string=uri->text;intent->data=Keep(host,host.NewHostInstance("android/net/Uri$StringUri",uri));}
  if(!config.launch_extras.empty()){
    intent->extras=std::make_shared<BundleState>();
    for(auto &[name,extra]:config.launch_extras){if(extra.kind<LaunchExtra::kNull||extra.kind>LaunchExtra::kBoolean)throw std::invalid_argument("unsupported configured Intent extra type");ExtraState value;value.kind=extra.kind;value.integer=extra.integer;value.boolean=extra.boolean;if(extra.kind==LaunchExtra::kString)value.text=Keep(host,host.NewString(extra.text));intent->extras->values.emplace(name,std::move(value));}
  }
  auto state=std::make_shared<ContextState>();state->info=host.CaptureValue(info_);state->assets=host.CaptureValue(assets_);state->package=host.CaptureValue(package_);
  auto packages=std::make_shared<PackageState>();packages->config=config;state->manager=Keep(host,host.NewHostInstance("android/app/ApplicationPackageManager",packages));
  state->intent=Keep(host,host.NewHostInstance("android/content/Intent",intent));activity_=global(host.NewHostInstance(config.activity_class,state));
  host.DefineObjectMethod("android/content/Context","getApplicationInfo","()Landroid/content/pm/ApplicationInfo;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->info):0;});
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
  host.DefineObjectMethod("android/content/Context","getAssets","()Landroid/content/res/AssetManager;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->assets):0;});
  host.DefineObjectMethod("android/content/Context","getPackageName","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->package):0;});
  host.DefineObjectMethod("android/content/Context","getApplicationContext","()Landroid/content/Context;",[&host](addr_t object){return host.ReadHostState<ContextState>(object)?host.NewLocalReference(object):0;});
  host.DefineObjectMethod("android/app/Activity","getIntent","()Landroid/content/Intent;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->intent):0;});
  host.DefineObjectMethod("android/content/Intent","getAction","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->action):0;});
  host.DefineObjectMethod("android/content/Intent","getComponent","()Landroid/content/ComponentName;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->component):0;});
  host.DefineObjectMethod("android/content/Intent","getPackage","()Ljava/lang/String;",[&host](addr_t object){host.ReadHostState<IntentState>(object);return 0;}); // Explicit component, no package selector.
  host.DefineObjectMethod("android/content/Intent","getData","()Landroid/net/Uri;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->data):0;});
  host.DefineObjectMethod("android/content/Intent","getDataString","()Ljava/lang/String;",[&host](addr_t object){auto state=host.ReadHostState<IntentState>(object);return state?host.LocalValue(state->data_string):0;});
  host.DefineBooleanMethod("android/content/Intent","hasCategory","(Ljava/lang/String;)Z",[&host](addr_t object,const jni::Host::MethodArguments &args){auto state=host.ReadHostState<IntentState>(object);auto name=host.StringValue(args[0]);return state&&name&&*name==u"android.intent.category.LAUNCHER";});
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
}  // namespace bunker::windows
