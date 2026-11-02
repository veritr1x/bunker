#pragma once
#include "jni_host.h"
#include <memory>
namespace bunker::windows {
// APK JNIBridge factory/disable port for exact singleton ServiceConnection[]
// OnAudioFocusChangeListener[], LocationListener[] and Runnable[] profiles, each with its
// own distinct implementing class.
// Host/context metadata must outlive this adapter and its callbacks.
// Owner drains workers first and destroys this on an attached JNI thread.
// This owns no native handle and never runs a native callback or finalizer.
class JniInterfaceProxy {
 public:
  struct Snapshot {uint64_t handle=0;std::vector<std::string> interfaces;};
  explicit JniInterfaceProxy(jni::Host&);
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
