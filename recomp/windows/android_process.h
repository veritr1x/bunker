#pragma once
#include "jni_host.h"
#include "thread_priority.h"
namespace bunker::windows {
// Selected Android13 framework native API only. No constructor, fields,
// thread creation, cgroups, Java worker execution or other Process methods.
class AndroidProcess {
 public:
  struct Observation {
    enum class Phase { Enter,Return } phase;
    uint32_t tid;int32_t nice;int error;
  };
  using Observer=std::function<void(const Observation&)>;
  // Optional diagnostics only, outside JNI/registry/service locks. Must return
  // normally without guest execution or priority/provider mutation. Each call
  // preserves native errno/fenv/LastError. Enter.error is not a result.
  AndroidProcess(jni::Host&,ThreadPriorities&,Observer={});
  ~AndroidProcess();
  AndroidProcess(const AndroidProcess&)=delete;
  AndroidProcess&operator=(const AndroidProcess&)=delete;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}
