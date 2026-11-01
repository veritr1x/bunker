#pragma once
#include "jni_host.h"
#include <set>

namespace bunker::windows {
class ApkAssets;
struct LaunchExtra {
  enum Kind {kNull,kString,kInteger,kBoolean} kind=kNull;
  std::u16string text;int32_t integer=0;bool boolean=false;
  static LaunchExtra String(std::u16string value){LaunchExtra e;e.kind=kString;e.text=std::move(value);return e;}
  static LaunchExtra Integer(int32_t value){LaunchExtra e;e.kind=kInteger;e.integer=value;return e;}
  static LaunchExtra Boolean(bool value){LaunchExtra e;e.kind=kBoolean;e.boolean=value;return e;}
};
struct AndroidContextConfig {
  struct PackageVersion {std::u16string name;int32_t code=0;};
  struct MainActivityFilter {std::u16string component;std::set<std::u16string> categories;bool enabled=true;};
  std::u16string package_name;
  std::u16string source_dir = u"/data/app/bunker/base.apk";
  std::u16string native_library_dir = u"/data/app/bunker/lib/arm64";
  std::u16string data_dir = u"/data/user/0/bunker";
  int32_t target_sdk = 0;
  // Explicit installed-profile value. Manifest attributes alone do not establish
  // the complete PackageParser/default/user-state bitmask; no such claim is made.
  int32_t flags = 0;
  std::string activity_class = "android/app/Activity";
  std::map<std::u16string,LaunchExtra> launch_extras;
  std::optional<std::u16string> launch_data;
  std::shared_ptr<ApkAssets> apk_assets;
  std::optional<PackageVersion> version;
  std::map<std::u16string,LaunchExtra> application_metadata;
  // Complete MAIN/no-data filter catalog for this one installed APK. An absent
  // catalog means unknown, not an empty resolver result.
  std::optional<std::vector<MainActivityFilter>> main_activity_filters;
  // Closed host capability catalog; playback low latency is not advertised
  // merely because a Windows audio endpoint can be observed.
  std::set<std::u16string> supported_android_features;
  // Internal-only storage. Called for exactly data_dir+/files or /cache, outside
  // JNI/provider locks; 0 means a real directory was verified, otherwise a
  // positive Android errno. An absent callback cannot return a directory File.
  std::function<int32_t(const std::u16string&)> prepare_internal_directory;
};

// Explicit host implementations of the Java context metadata Unity requests.
// The configured APK reader supplies real asset streams; launch/package metadata
// and the closed capability catalog are host implementations. Other Android
// services and Java bytecode/class initialization remain explicit requirements.
class AndroidContext {
 public:
  AndroidContext(jni::Host &host, const AndroidContextConfig &config);
  ~AndroidContext();
  AndroidContext(const AndroidContext &) = delete;
  AndroidContext &operator=(const AndroidContext &) = delete;
  addr_t Activity();
 private:
  jni::Host &host_;
  addr_t activity_ = 0, info_ = 0, assets_ = 0, package_ = 0;
};
}  // namespace bunker::windows
