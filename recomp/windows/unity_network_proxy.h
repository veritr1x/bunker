#pragma once
#include "jni_host.h"
#include <functional>
#include <memory>
#include <optional>
#include <string>

namespace bunker::windows {
// Manual Java-property compatibility only. Automatic configuration metadata is
// reported separately and is never interpreted as an effective network route.
class UnityNetworkProxy {
 public:
  struct PropertySnapshot {
    std::optional<std::u16string> httpHost, httpPort, httpsHost, httpsPort, nonProxyHosts;
    bool autoDetect = false;
    std::optional<std::u16string> autoConfigUrl;
    std::optional<std::u16string> rawManualServer, rawManualBypass;
  };
  struct Event {
    std::string scheme;
    bool reader_used = false;
    std::optional<PropertySnapshot> manual_properties;
    std::optional<std::u16string> result;
  };
  using Reader = std::function<PropertySnapshot()>;
  struct Config { Reader read_manual_properties; std::function<void(const Event&)> observer; };
  explicit UnityNetworkProxy(jni::Host&);
  UnityNetworkProxy(jni::Host&, Config);
  ~UnityNetworkProxy();
  UnityNetworkProxy(const UnityNetworkProxy&) = delete;
  UnityNetworkProxy& operator=(const UnityNetworkProxy&) = delete;
  void Revoke() noexcept;
  bool Active() const noexcept;
  // Pure exact DEX formatting; a null URL throws invalid_argument here. The
  // bound Java method instead publishes a genuine NullPointerException.
  static std::optional<std::u16string> Format(const std::optional<std::u16string>& URL, const PropertySnapshot&);
  static PropertySnapshot ParseWindowsManualSettings(std::optional<std::u16string> server,
      std::optional<std::u16string> bypass, bool autoDetect = false,
      std::optional<std::u16string> autoConfigUrl = {});
  // Queries only configuration. No WinHttpGetProxyForUrl, PAC fetch, WPAD,
  // authentication, request, cookie, or system-setting operation occurs.
  static PropertySnapshot ReadWindowsManualProperties();
 private:
  struct Shared;
  std::shared_ptr<Shared> state_;
};
}  // namespace bunker::windows
