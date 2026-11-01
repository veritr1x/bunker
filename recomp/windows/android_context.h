#pragma once
#include "jni_host.h"

namespace bunker::windows {
struct LaunchExtra {
  enum Kind {kNull,kString,kInteger,kBoolean} kind=kNull;
  std::u16string text;int32_t integer=0;bool boolean=false;
  static LaunchExtra String(std::u16string value){LaunchExtra e;e.kind=kString;e.text=std::move(value);return e;}
  static LaunchExtra Integer(int32_t value){LaunchExtra e;e.kind=kInteger;e.integer=value;return e;}
  static LaunchExtra Boolean(bool value){LaunchExtra e;e.kind=kBoolean;e.boolean=value;return e;}
};
struct AndroidContextConfig {
  std::u16string package_name;
  std::u16string source_dir = u"/data/app/bunker/base.apk";
  std::u16string native_library_dir = u"/data/app/bunker/lib/arm64";
  std::u16string data_dir = u"/data/user/0/bunker";
  int32_t target_sdk = 0;
  int32_t flags = 0;
  std::string activity_class = "android/app/Activity";
  std::map<std::u16string,LaunchExtra> launch_extras;
  std::optional<std::u16string> launch_data;
};

// Explicit host implementations of the Java context metadata Unity requests.
// AssetManager is a typed Java object here; Java stream/AssetManager.open and
// other Android services are not implemented or reported as successful.
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
