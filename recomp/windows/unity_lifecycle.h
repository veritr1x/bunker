#pragma once
#include "jni_host.h"
#include <functional>
#include <memory>
#include <vector>

namespace bunker::windows {
// A bounded host port of the APK's UnityMain surface FIFO. It does not execute
// DEX, initialize Java classes, resume the player or schedule render messages.
// Host and Runner must outlive this object. Stop before closing the HWND.
class UnitySurfaceLifecycle {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  using WorkerExit=std::function<void()>;
  using WorkerEnter=std::function<void()>;
  struct Entries {addr_t recreate=0,changed=0;};
  struct Status {bool initialized=false,started=false,surface=false,resumed=false;uint64_t completed=0;};
  // WorkerExit releases the runner's per-thread TLS/stack while JNI remains
  // attached (for Pthreads, call ReleaseCurrent and check its return).
  UnitySurfaceLifecycle(jni::Host &,Runner,Entries,addr_t unity_player,WorkerExit);
  ~UnitySurfaceLifecycle();
  UnitySurfaceLifecycle(const UnitySurfaceLifecycle&)=delete;
  UnitySurfaceLifecycle &operator=(const UnitySurfaceLifecycle&)=delete;
  // Call only after the real initJni entry completed without exception events:
  // constructor DEX0x554a3c/0x554a40 then performs o.c(true).
  void AfterInitJni();
  // Optional virtual-thread registration after JNI attach, before startup ack.
  // Capture inherited state on the caller immediately before Start; the hook
  // executes on UnityMain and may not assume its guest stack is allocated yet.
  void Start(WorkerEnter enter={});
  void SurfaceCreated(addr_t surface);
  void SurfaceChanged(addr_t surface);
  // APK updateDisplayInternal waits up to four seconds for null-surface ack.
  // A timeout is an error; callers must retain the HWND until the worker stops.
  void SurfaceDestroyed();
  void WaitIdle();
  void Stop();
  Status Describe()const;
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
} // namespace bunker::windows
