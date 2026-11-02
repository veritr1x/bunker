#pragma once
#include "jni_host.h"
#include <memory>
#include <string>
namespace bunker::windows {
// Exact APK's missing PlayCore factory constructor branch, not asset delivery.
// The caller verifies the mounted APK and supplies the accepted complete code-
// catalog/split proof. Unknown/present/changed profiles are unsupported.
class AndroidAssetPackWrapper {
 public:
  struct Profile {std::string apk_sha256,code_catalog_sha256;bool apk_only_closed_application_code=false;};
  AndroidAssetPackWrapper(jni::Host&,const Profile&);
  ~AndroidAssetPackWrapper();
  AndroidAssetPackWrapper(const AndroidAssetPackWrapper&)=delete;
  AndroidAssetPackWrapper&operator=(const AndroidAssetPackWrapper&)=delete;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}
