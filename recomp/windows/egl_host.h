#pragma once
#include "native_window.h"
#include <memory>
#include <optional>
#include <string>

namespace bunker::windows {
// The evidenced Unity EGL subset backed by the pinned, real ANGLE Vulkan DLLs.
// Destroy this before NativeWindows and retire all worker-thread current contexts
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
  // Read-only context identity/lifetime for GL-side state. Tokens are never
  // reused, include deferred-deleted current contexts, and reveal no native
  // pointers. Neither operation consumes EGL error flags or calls guests.
  addr_t CurrentContextToken();
  bool ContextAlive(addr_t token);
  bool UsesGlesModule(const void *native_module);
  struct ReadPbufferExtent {addr_t context,surface;int32_t width,height;};
  // Read-only, actual owned EGL_READ pbuffer. Window/surfaceless/foreign
  // surfaces are excluded. Internal queries preserve the public EGL error.
  std::optional<ReadPbufferExtent> CurrentReadPbufferExtent();
  // Call on the native worker itself before it exits. No guest callback runs.
  void ReleaseCurrentThread();
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
