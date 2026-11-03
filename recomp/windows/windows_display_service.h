#pragma once
#include "jni_host.h"
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>
namespace bunker::windows {
// Logical Windows desktop outputs mapped to this port's Android display IDs.
// ID0 is the current primary; non-primary names retain IDs for this owner.
// Dimensions/rotation/refresh/scale are native observations. Wide color and
// timing below describe this port's SDR, no-Choreographer scheduling policy.
class WindowsDisplayService {
 public:
  struct DisplayInfo {
    int32_t id=0,width=0,height=0,rotation=0,density_dpi=0;
    uint32_t refresh_numerator=0,refresh_denominator=0,refresh_bits=0;
    uint32_t windows_scale_percent=0,windows_effective_dpi_x=0,windows_effective_dpi_y=0;
    int64_t app_vsync_offset_ns=0,nominal_presentation_budget_ns=0;
    std::u16string device;
  };
  using Observer=std::function<void(const DisplayInfo&)>;
  // Construct after AndroidContext. Observer is diagnostics only: no guest
  // calls/provider mutation; runs outside native inventory/adapter locks and
  // preserves errno, LastError and fenv. Callbacks expire with this owner.
  explicit WindowsDisplayService(jni::Host&,Observer={});
  ~WindowsDisplayService();
  WindowsDisplayService(const WindowsDisplayService&)=delete;
  WindowsDisplayService&operator=(const WindowsDisplayService&)=delete;
  std::vector<DisplayInfo> Displays();
  // Quiescent setup only, once per Activity. Retains Java object values, not
  // borrowed JNI locals. The reader must be the owning NativeWindows weak
  // HWND reader; it returns null after close/expiry. No window is retained.
  // This owner and Host must outlive calls. No Activity lifecycle is invented.
  void BindActivityWindow(addr_t activity,std::function<void*()> native_handle_reader);
 private:
  struct Impl;
  std::shared_ptr<Impl> impl_;
};
}
