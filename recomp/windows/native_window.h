#pragma once
#include "jni_host.h"
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// Match the actual HWND's DPI awareness while a native EGL/Win32 API queries
// pixel geometry, then restore the calling worker's previous thread policy.
class WindowDpiScope {
 public:
  explicit WindowDpiScope(void *hwnd);
  ~WindowDpiScope();
  WindowDpiScope(const WindowDpiScope&)=delete;
  WindowDpiScope &operator=(const WindowDpiScope&)=delete;
 private:void *previous_=nullptr;
};
// A real Win32 window and the checked Android opaque-window reference layer.
// The UI thread never invokes guest callbacks; its events are drained by the
// lifecycle owner. Destroy EGL surfaces before closing/destroying this host.
class NativeWindows {
 public:
  struct Geometry {int32_t width,height,format,client_width,client_height;bool fixed_size=false;};
  struct MouseData {
    enum class Button {None,Left,Right,Middle,X1,X2};
    int32_t x=0,y=0;bool client_position_valid=false;
    int32_t screen_x=0,screen_y=0;bool screen_position_valid=false;
    uint32_t client_position_error=0,button_state=0;
    Button button=Button::None;uint16_t x_button_id=0;
    int32_t wheel_delta=0;bool horizontal_wheel=false;
  };
  struct KeyData {
    uint32_t virtual_key=0;uint16_t repeat_count=0;uint8_t scan_code=0;
    bool extended=false,alt_context=false,previous_down=false,transition_up=false,system=false;
  };
  struct Event {
    // Existing kind ordinals and the first four aggregate fields stay stable.
    enum Kind {Resized,Focus,CloseRequested,Destroyed,MouseMove,MouseButtonDown,MouseButtonUp,MouseWheel,KeyDown,KeyUp};
    Kind kind;int32_t width=0,height=0;bool focused=false;
    // Raw dequeued Win32 MSG time (wrapping milliseconds), not a new clock.
    uint32_t native_message=0,message_time_ms=0;
    MouseData mouse{};KeyData key{};
  };
  class Window;
  using Handle=std::shared_ptr<Window>;
  // Nondefault buffer geometry requires a renderer which really supplies those
  // buffers and scales them to the client. The callback runs without registry,
  // window-state or guest-memory locks; do not reenter geometry mutation.
  using ApplyGeometry=std::function<int(addr_t,const Geometry&)>;
  explicit NativeWindows(jni::Host &,addr_t marker_base=0x7ff440000000ULL);
  ~NativeWindows();
  NativeWindows(const NativeWindows&)=delete;
  NativeWindows &operator=(const NativeWindows&)=delete;
  void Install(recomp::Runtime &);
  addr_t Marker(const std::string &)const;
  Handle Create(int32_t width,int32_t height,const std::u16string &title,bool visible=false);
  addr_t NewSurface(const Handle &);
  addr_t FromSurface(addr_t surface);
  void Acquire(addr_t native_window);
  void Release(addr_t native_window);
  int32_t Width(addr_t native_window)const;
  int32_t Height(addr_t native_window)const;
  int SetBuffersGeometry(addr_t,int32_t width,int32_t height,int32_t format);
  Geometry Describe(addr_t native_window)const;
  // Actual native HWND, represented opaquely here so headers stay lightweight.
  void *NativeHandle(addr_t native_window)const;
  // Weak observation only: no provider/window retention or native token lease.
  // Creation requires a live owned handle; later close/expiry returns nullptr.
  std::function<void*()> NativeHandleReader(const Handle &)const;
  void SetGeometryBackend(ApplyGeometry);
  std::vector<Event> DrainEvents(const Handle &);
  void ResizeClient(const Handle &,int32_t width,int32_t height);
  void Close(const Handle &);
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
