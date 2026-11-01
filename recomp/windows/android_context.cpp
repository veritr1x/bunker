#include "android_context.h"
#include <stdexcept>

namespace bunker::windows {
AndroidContext::AndroidContext(jni::Host &host, const AndroidContextConfig &config) : host_(host) {
  if (config.package_name.empty() || config.source_dir.empty() || config.source_dir.front() != u'/' ||
      config.native_library_dir.empty() || config.native_library_dir.front() != u'/' ||
      config.data_dir.empty() || config.data_dir.front() != u'/' || config.target_sdk <= 0)
    throw std::invalid_argument("Android context needs actual package/SDK metadata and absolute virtual Android paths");
  host.DefineClass("android/content/Context");
  host.DefineClass("android/app/Activity", {}, "android/content/Context");
  if (config.activity_class != "android/app/Activity") host.DefineClass(config.activity_class, {}, "android/app/Activity");
  host.DefineClass("android/content/pm/ApplicationInfo");
  host.DefineClass("android/content/res/AssetManager");
  for (const char *field : {"sourceDir", "nativeLibraryDir", "dataDir", "packageName"})
    host.DefineField("android/content/pm/ApplicationInfo", field, "Ljava/lang/String;");
  host.DefineField("android/content/pm/ApplicationInfo", "targetSdkVersion", "I");
  host.DefineField("android/content/pm/ApplicationInfo", "flags", "I");
  auto global = [&](addr_t local) { auto result = host.NewGlobalReference(local); host.DeleteLocalReference(local); return result; };
  activity_ = global(host.NewInstance(config.activity_class));
  info_ = global(host.NewInstance("android/content/pm/ApplicationInfo"));
  assets_ = global(host.NewInstance("android/content/res/AssetManager"));
  package_ = global(host.NewString(config.package_name));
  auto set_string = [&](const char *name, const std::u16string &value) {
    auto local = host.NewString(value); host.SetObjectFieldValue(info_, name, "Ljava/lang/String;", local); host.DeleteLocalReference(local);
  };
  set_string("sourceDir", config.source_dir); set_string("nativeLibraryDir", config.native_library_dir);
  set_string("dataDir", config.data_dir); set_string("packageName", config.package_name);
  host.SetIntFieldValue(info_, "targetSdkVersion", config.target_sdk); host.SetIntFieldValue(info_, "flags", config.flags);
  host.DefineObjectMethod("android/content/Context", "getApplicationInfo", "()Landroid/content/pm/ApplicationInfo;", [&host, ref = info_](addr_t) { return host.NewLocalReference(ref); });
  host.DefineObjectMethod("android/content/Context", "getAssets", "()Landroid/content/res/AssetManager;", [&host, ref = assets_](addr_t) { return host.NewLocalReference(ref); });
  host.DefineObjectMethod("android/content/Context", "getPackageName", "()Ljava/lang/String;", [&host, ref = package_](addr_t) { return host.NewLocalReference(ref); });
  host.DefineObjectMethod("android/content/Context", "getApplicationContext", "()Landroid/content/Context;", [&host, ref = activity_](addr_t) { return host.NewLocalReference(ref); });
  if (!host.PendingException().empty()) throw std::runtime_error("Android context initialization failed: " + host.PendingException());
}
AndroidContext::~AndroidContext() {
  host_.DeleteGlobalReference(activity_); host_.DeleteGlobalReference(info_); host_.DeleteGlobalReference(assets_); host_.DeleteGlobalReference(package_);
}
addr_t AndroidContext::Activity() { return host_.NewLocalReference(activity_); }
}  // namespace bunker::windows
