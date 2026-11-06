#pragma once
#include "jni_host.h"
#include <functional>
#include <memory>
#include <optional>
#include <vector>

namespace bunker::windows {
// A bounded host port of the APK's UnityMain native FIFO. The default profile
// is surface-only; ConfigureOneFrame enables one guarded native render call.
// It never executes DEX, Java class initializers or Java service constructors.
// Host and Runner must outlive this object. Stop before closing the HWND.
class UnitySurfaceLifecycle {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  using WorkerExit=std::function<void()>;
  using WorkerEnter=std::function<void()>;
  struct Entries {addr_t recreate=0,changed=0;};
  struct FrameEntries {addr_t resume=0,focus=0,render=0,pause=0,done=0;};
  struct Status {bool initialized=false,started=false,surface=false,resumed=false;uint64_t completed=0,rendered=0,requested_frames=0;bool native_done=false,process_kill_requested=false;};
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
  // Enqueue native framework work on the actual UnityMain FIFO. Never executes
  // synchronously, including calls from UnityMain itself. False after stop.
  bool Post(std::function<void()> action);
  // Optional bounded native lifecycle port. The owner must complete the real
  // UI resume prerequisites before ActivityResumed, and supply actual platform
  // focus events. It does not implement Java constructors, views or services.
  // APK NEXT_FRAME drains the GL-event FIFO before resume/render checks. The
  // optional port runs on the attached UnityMain; an absent port stays inert.
  void ConfigureOneFrame(FrameEntries,std::function<void()> execute_gl_jobs={});
  void ActivityResumed();
  void WindowFocusChanged(bool focused);
  bool WaitForFrame();
  // Poll the current request without blocking the window/event owner. A ready
  // false is the original render result; pending is nullopt, failures throw.
  std::optional<bool> PollFrame()const;
  // Explicitly continue after a completed true result, on the same UnityMain.
  // False means a transient surface/focus/FIFO prerequisite is not ready.
  // Duplicate, in-flight, prior-false and invalid lifecycle requests throw.
  bool RequestNextFrame();
  // Native PAUSE + acknowledgment Runnable only. Finishing selects the APK's
  // shutdown/nativeDone branch; a normal pause calls nativePause first.
  // Legacy synchronous wait: a four-second timeout does not cancel the native
  // job. Its genuine acknowledgment can still be observed with PollNativePause.
  void PauseNative(bool finishing);
  // Enqueue once without waiting, retaining the same UnityMain/FIFO and native
  // finishing branch. Duplicate outstanding requests and worker self-calls fail.
  void BeginPauseNative(bool finishing);
  // False means pending. True consumes the genuine successful acknowledgment;
  // an acknowledged callback failure is consumed and rethrown. Polling before a
  // request or after consumption fails. Keep HWND/providers alive while pending.
  bool PollNativePause();
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
