#pragma once
#include "module_registry.h"
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// Exact Firebase Unity 9.6.0 Windows SDK service. This is not an Android ELF
// translation and advertises no JNI_OnLoad. The caller verifies the pinned DLL
// before loading; guest callbacks remain original translated entries.
class FirebaseAppService {
 public:
  using Runner=std::function<uint64_t(addr_t,const std::vector<addr_t>&)>;
  struct Config {
    std::wstring dll_path;
    // Must hash the absolute file against expected_sha256 or throw.
    std::function<void(const std::wstring&,const std::string&)> verify_library;
    Runner runner;
    // Called only after CurrentExecutionState()!=nullptr; must not allocate a
    // guest thread. Admission includes the live guest owner and module lifetime.
    std::function<bool()> admitted_thread;
    std::function<bool(addr_t)> translated_entry;
    // Optional, exact virtual-asset path mapping supplied by the qualified
    // platform owner. It must preserve all configuration bytes; when absent,
    // AppSetDefaultConfigPath forwards its original path unchanged.
    std::function<std::string(const std::string&)> resolve_config_path{};
  };
  static constexpr const char *kDllSha256="f85bb9f82d79176d3d5da322780d437c023191370e608c45723ad6d83c4d1a12";
  explicit FirebaseAppService(Config,addr_t marker_base=0x7fef00000000ULL);
  ~FirebaseAppService();
  FirebaseAppService(const FirebaseAppService&)=delete;
  FirebaseAppService&operator=(const FirebaseAppService&)=delete;
  static const std::vector<std::string>&Commands();
  addr_t Marker(const std::string&)const;
  void Invoke(const std::string&,State&);
  void Install(recomp::Runtime&);
  Module MakeModule()const;
  // Callback trampolines never unwind through the foreign MSVC DLL. A caught
  // callback failure makes subsequent imports/CheckHealthy fail explicitly.
  void CheckHealthy()const;
  // Owner must stop all SDK use and reach callback/import quiescence first.
  // Only synchronous callbacks on the current SDK import owner are admitted.
  // Default App create/name/release retains genuine native references. Every
  // nonnull create result must be released before revoke. App calls are not
  // admitted from reentrant callbacks; unowned/released handles fail closed.
  // Options overloads, Futures and asynchronous callbacks remain unsupported.
  // The native DLL remains loaded for process lifetime; no stale code unload.
  // A revoked service cannot be replaced by another generation in this process.
  void Revoke();
 private:
  struct Impl;
  std::shared_ptr<Impl> impl_;
  addr_t marker_base_;
};
}  // namespace bunker::windows
