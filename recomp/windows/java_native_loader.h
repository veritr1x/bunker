#pragma once
#include "jni_host.h"
#include "module_registry.h"
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// A closed application-loader adapter. ModuleRegistry and the runner must
// outlive the installed Host handler and all of its active calls.
class JavaNativeLoader {
 public:
  struct Library {
    std::u16string name;
    std::string guest_path;
    // Optional extra original-entry pin for adoption or
    // a fresh load. ModuleRegistry validates exact handle/path ownership.
    addr_t expected_onload=0;
  };
  struct Event {
    std::u16string name;
    std::string path,detail;
    bool success=false,cached=false,recursive=false,adopted=false;
    addr_t handle=0,onload=0;
  };
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  struct Config {
    addr_t application_class=0,application_loader=0;
    std::vector<Library> libraries;
    Runner runner;
    std::function<void(const Event&)> observer;
    // Original UnityPlayer.loadLibraryStatic catches/logs load failures at
    // severity6. The owner supplies the real diagnostic sink for this port.
    std::function<void(int,const std::u16string&)> diagnostic;
  };
  JavaNativeLoader(jni::Host&,ModuleRegistry&,const Config&);
  ~JavaNativeLoader();
  JavaNativeLoader(const JavaNativeLoader&)=delete;
  JavaNativeLoader&operator=(const JavaNativeLoader&)=delete;
  void BindUnityPlayer();
  // completed_version=0 only when the original image has no JNI_OnLoad.
  void Adopt(const std::u16string&name,addr_t existing_handle,int32_t completed_version);
  bool LoadForLoader(addr_t loader,const std::u16string&name);
  void Revoke()noexcept;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
} // namespace bunker::windows
