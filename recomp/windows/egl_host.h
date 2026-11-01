#pragma once
#include "native_window.h"
#include <memory>
#include <string>

namespace bunker::windows {
// The evidenced Unity EGL subset backed by the pinned, real ANGLE Vulkan DLLs.
// Own this before NativeWindows and retire all worker-thread current contexts
// before destruction. Native handles stay private; guest function pointers are
// Runtime markers, never Windows code addresses. Unknown GL signatures fail.
class EglHost {
 public:
  EglHost(NativeWindows &, const std::wstring &absolute_dll_directory,
          addr_t marker_base=0x7ff420000000ULL);
  ~EglHost();
  EglHost(const EglHost&)=delete;
  EglHost &operator=(const EglHost&)=delete;
  void Install(recomp::Runtime &);
  addr_t Marker(const std::string &)const;
  void Invoke(const std::string &,State &);
  // Resolver must return an installed guest marker or reject the signature.
  // Called without guest-memory locks; it must not reenter this EglHost.
  void SetProcedureResolver(std::function<addr_t(const std::string&)>);
  // Call on the native worker itself before it exits. No guest callback runs.
  void ReleaseCurrentThread();
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
