#include "android_context.h"
#include <algorithm>
#include <codecvt>
#include <locale>
#include <stdexcept>

namespace bunker::windows {
namespace {
using Value=jni::Host::ObjectValue;
struct ComponentState {Value package,name;};
struct UriState {Value text;};
struct ExtraState {LaunchExtra::Kind kind=LaunchExtra::kNull;Value text;int32_t integer=0;bool boolean=false;};
struct BundleState {std::map<std::u16string,ExtraState> values;};
struct IntentState {Value action,component,data,data_string;std::shared_ptr<BundleState> extras;};
struct ContextState {Value info,assets,package,intent;};
Value Keep(jni::Host &host,addr_t local){auto value=host.CaptureValue(local);host.DeleteLocalReference(local);return value;}
const ExtraState *Extra(jni::Host &host,const BundleState &state,addr_t key){auto name=host.StringValue(key);if(!name)return nullptr;auto found=state.values.find(*name);return found==state.values.end()?nullptr:&found->second;}
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
  host.DefineClass("android/content/res/AssetManager", {}, "java/lang/Object", true);
  host.DefineClass("android/content/Intent",{},"java/lang/Object",true);
  host.DefineClass("android/content/ComponentName",{},"java/lang/Object",true);
  host.DefineClass("android/os/BaseBundle",{},"java/lang/Object",true);
  host.DefineClass("android/os/Bundle",{},"android/os/BaseBundle",true);
  host.DefineClass("android/net/Uri",{},"java/lang/Object",true);
  host.DefineClass("android/net/Uri$StringUri",{},"android/net/Uri",true);
  for (const char *field : {"sourceDir", "nativeLibraryDir", "dataDir", "packageName"})
    host.DefineField("android/content/pm/ApplicationInfo", field, "Ljava/lang/String;");
  host.DefineField("android/content/pm/ApplicationInfo", "targetSdkVersion", "I");
  host.DefineField("android/content/pm/ApplicationInfo", "flags", "I");
  auto global = [&](addr_t local) { auto result = host.NewGlobalReference(local); host.DeleteLocalReference(local); return result; };
  info_ = global(host.NewInstance("android/content/pm/ApplicationInfo"));
  assets_ = global(host.NewInstance("android/content/res/AssetManager"));
  package_ = global(host.NewString(config.package_name));
  auto set_string = [&](const char *name, const std::u16string &value) {
    auto local = host.NewString(value); host.SetObjectFieldValue(info_, name, "Ljava/lang/String;", local); host.DeleteLocalReference(local);
  };
  set_string("sourceDir", config.source_dir); set_string("nativeLibraryDir", config.native_library_dir);
  set_string("dataDir", config.data_dir); set_string("packageName", config.package_name);
  host.SetIntFieldValue(info_, "targetSdkVersion", config.target_sdk); host.SetIntFieldValue(info_, "flags", config.flags);
  auto component=std::make_shared<ComponentState>();component->package=host.CaptureValue(package_);
  auto binary=config.activity_class;std::replace(binary.begin(),binary.end(),'/','.');
  component->name=Keep(host,host.NewString(std::wstring_convert<std::codecvt_utf8_utf16<char16_t>,char16_t>{}.from_bytes(binary)));
  auto intent=std::make_shared<IntentState>();intent->action=Keep(host,host.NewString(u"android.intent.action.MAIN"));
  intent->component=Keep(host,host.NewHostInstance("android/content/ComponentName",component));
  if(config.launch_data){auto uri=std::make_shared<UriState>();uri->text=Keep(host,host.NewString(*config.launch_data));intent->data_string=uri->text;intent->data=Keep(host,host.NewHostInstance("android/net/Uri$StringUri",uri));}
  if(!config.launch_extras.empty()){
    intent->extras=std::make_shared<BundleState>();
    for(auto &[name,extra]:config.launch_extras){if(extra.kind<LaunchExtra::kNull||extra.kind>LaunchExtra::kBoolean)throw std::invalid_argument("unsupported configured Intent extra type");ExtraState value;value.kind=extra.kind;value.integer=extra.integer;value.boolean=extra.boolean;if(extra.kind==LaunchExtra::kString)value.text=Keep(host,host.NewString(extra.text));intent->extras->values.emplace(name,std::move(value));}
  }
  auto state=std::make_shared<ContextState>();state->info=host.CaptureValue(info_);state->assets=host.CaptureValue(assets_);state->package=host.CaptureValue(package_);
  state->intent=Keep(host,host.NewHostInstance("android/content/Intent",intent));activity_=global(host.NewHostInstance(config.activity_class,state));
  host.DefineObjectMethod("android/content/Context","getApplicationInfo","()Landroid/content/pm/ApplicationInfo;",[&host](addr_t object){auto state=host.ReadHostState<ContextState>(object);return state?host.LocalValue(state->info):0;});
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
