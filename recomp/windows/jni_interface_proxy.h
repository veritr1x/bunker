#pragma once
#include "jni_host.h"
#include <functional>
#include <memory>
namespace bunker::windows {
// APK JNIBridge factory/disable port for four passive singleton interface
// profiles and, with Config.run_native, the exact Handler/Frame callback pair
// and shutdown Handler.Callback singleton. Each has its own implementing type.
// Host/context metadata must outlive this adapter and its callbacks.
// Owner drains workers first and destroys this on an attached JNI thread.
// Native owners retain their opaque handles. Only active profiles invoke the
// actually registered native body; no automatic native delete/finalizer runs.
class JniInterfaceProxy {
 public:
  struct Snapshot {uint64_t handle=0;std::vector<std::string> interfaces;};
  struct Config {
    // Active Handler/Frame callback profiles enter the actual registered
    // JNIBridge native method through the owning Runtime/Pthreads runner.
    std::function<addr_t(addr_t,const std::vector<addr_t>&)> run_native;
  };
  explicit JniInterfaceProxy(jni::Host&);
  JniInterfaceProxy(jni::Host&,Config);
  ~JniInterfaceProxy();
  JniInterfaceProxy(const JniInterfaceProxy&)=delete;
  JniInterfaceProxy&operator=(const JniInterfaceProxy&)=delete;
  Snapshot Inspect(addr_t proxy)const;
  // Call after factory/callback callers quiesce, while all owners remain alive;
  // this is a snapshot, not a concurrent close fence. A live
  // enabled proxy or a retired enabled proxy is an unresolved ownership boundary.
  void CheckNoEnabledProxies()const;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}
