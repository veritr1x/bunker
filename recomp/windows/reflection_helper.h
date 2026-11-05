#pragma once
#include "jni_host.h"
#include "reflection_launch_epoch.h"
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// APK ReflectionHelper's metadata lookup path and distinct native proxy
// protocol. Host, native runner and modules must outlive every callback.
class ReflectionHelper {
 public:
  struct Config {
    std::function<addr_t(addr_t,const std::vector<addr_t>&)> run_native;
  };
  struct ProxySnapshot {
    uint64_t handle=0,launch_epoch=0,current_epoch=0,native_exception=0;
    bool default_method=false;
    std::vector<std::string> interfaces;
  };
  ReflectionHelper(jni::Host&,ReflectionLaunchEpoch&,Config);
  ~ReflectionHelper();
  ReflectionHelper(const ReflectionHelper&)=delete;
  ReflectionHelper& operator=(const ReflectionHelper&)=delete;
  ProxySnapshot InspectProxy(addr_t proxy)const;
 private:
  struct Shared;
  std::shared_ptr<Shared> state_;
};
}
