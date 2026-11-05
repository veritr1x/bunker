#include <cfenv>
#include "unity_network_proxy.h"
#include <atomic>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <utility>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#endif

namespace bunker::windows {
namespace {
constexpr const char* kPlayer = "com/unity3d/player/UnityPlayer";
struct Environment {
#ifdef _WIN32
  DWORD error = GetLastError();
#endif
  int saved_errno = errno;
  fenv_t floating{};
  Environment() { std::fegetenv(&floating); }
  ~Environment() { std::fesetenv(&floating); errno = saved_errno;
#ifdef _WIN32
    SetLastError(error);
#endif
  }
};
int Scheme(const std::u16string& text) {
  if (text.compare(0, 5, u"http:") == 0) return 1;
  if (text.compare(0, 6, u"https:") == 0) return 2;
  return 0;
}
std::u16string Trim(const std::u16string& s) {
  const auto a = s.find_first_not_of(u" \t");
  if (a == s.npos) return {};
  return s.substr(a, s.find_last_not_of(u" \t") - a + 1);
}
[[noreturn]] void Unsupported(const char* why) {
  throw std::runtime_error(std::string("unqualified Windows manual proxy configuration: ") + why);
}
bool HostChar(char16_t c) {
  return (c >= u'a' && c <= u'z') || (c >= u'A' && c <= u'Z') ||
      (c >= u'0' && c <= u'9') || c == u'.' || c == u'-';
}
bool Hex(char16_t c) {
  return (c >= u'0' && c <= u'9') || (c >= u'a' && c <= u'f') || (c >= u'A' && c <= u'F');
}
bool IPv6(const std::u16string& s) {
  if (s.empty() || s.find(u":::") != s.npos) return false;
  const auto gap = s.find(u"::");
  if (gap != s.npos && s.find(u"::", gap + 2) != s.npos) return false;
  unsigned groups = 0;
  size_t at = 0;
  while (at < s.size()) {
    if (s[at] == u':') { ++at; continue; }
    auto end = s.find(u':', at); if (end == s.npos) end = s.size();
    if (end - at > 4) return false;
    for (auto i = at; i < end; ++i) if (!Hex(s[i])) return false;
    ++groups; at = end;
  }
  if (gap == s.npos) return groups == 8 && s.front() != u':' && s.back() != u':';
  if ((s.front() == u':' && gap != 0) || (s.back() == u':' && gap + 2 != s.size())) return false;
  return groups < 8;
}
struct Endpoint { std::u16string host; std::optional<std::u16string> port; };
Endpoint ParseEndpoint(const std::u16string& text) {
  if (text.empty()) Unsupported("empty proxy endpoint");
  Endpoint result;
  size_t colon = text.npos;
  if (text.front() == u'[') {
    auto end = text.find(u']');
    if (end == text.npos || !IPv6(text.substr(1, end - 1))) Unsupported("invalid or unqualified bracketed IPv6 endpoint");
    result.host = text.substr(0, end + 1);
    if (end + 1 != text.size()) {
      if (text[end + 1] != u':') Unsupported("characters after bracketed proxy host");
      colon = end + 1;
    }
  } else {
    colon = text.find(u':');
    result.host = text.substr(0, colon);
    if (result.host.empty()) Unsupported("empty proxy host");
    for (auto c : result.host) if (!HostChar(c)) Unsupported("proxy host syntax");
  }
  if (colon != text.npos) {
    result.port = text.substr(colon + 1);
    if (result.port->empty() || result.port->size() > 5) Unsupported("proxy port syntax");
    unsigned value = 0;
    for (auto c : *result.port) { if (c < u'0' || c > u'9') Unsupported("proxy port syntax"); value = value * 10 + (c - u'0'); }
    if (!value || value > 65535) Unsupported("proxy port range");
  }
  return result;
}
std::optional<std::u16string> ParseBypass(const std::optional<std::u16string>& raw) {
  if (!raw || Trim(*raw).empty()) return {};
  std::u16string out;
  size_t at = 0;
  while (at <= raw->size()) {
    auto end = raw->find(u';', at); if (end == raw->npos) end = raw->size();
    auto entry = Trim(raw->substr(at, end - at));
    if (entry.empty()) Unsupported("empty bypass entry");
    // Only literal hosts and the conventional leading-domain wildcard have a
    // qualified mapping to Java's raw pipe-separated exclusion property.
    auto host = entry == u"*" ? std::u16string{} : entry.compare(0, 2, u"*.") == 0 ? entry.substr(2) : entry;
    if (entry != u"*" && host.empty()) Unsupported("empty bypass host");
    for (auto c : host) if (!HostChar(c)) Unsupported("bypass syntax (including <local>)");
    if (!out.empty()) out.push_back(u'|');
    out += entry;
    if (end == raw->size()) break;
    at = end + 1;
  }
  return out;
}
}  // namespace

std::optional<std::u16string> UnityNetworkProxy::Format(const std::optional<std::u16string>& URL, const PropertySnapshot& p) {
  if (!URL) throw std::invalid_argument("proxy formatter: null URL");
  const auto scheme = Scheme(*URL);
  if (!scheme) return {};
  const auto& host = scheme == 1 ? p.httpHost : p.httpsHost;
  if (!host || host->empty()) return {};
  std::u16string result = *host;
  const auto& port = scheme == 1 ? p.httpPort : p.httpsPort;
  if (port && !port->empty()) { result.push_back(u':'); result += *port; }
  if (p.nonProxyHosts && !p.nonProxyHosts->empty()) { result.push_back(u'\n'); result += *p.nonProxyHosts; }
  return result;
}

UnityNetworkProxy::PropertySnapshot UnityNetworkProxy::ParseWindowsManualSettings(
    std::optional<std::u16string> server, std::optional<std::u16string> bypass,
    bool autoDetect, std::optional<std::u16string> autoConfigUrl) {
  PropertySnapshot p;
  p.autoDetect = autoDetect; p.autoConfigUrl = std::move(autoConfigUrl);
  p.rawManualServer = server; p.rawManualBypass = bypass;
  if (!server || Trim(*server).empty()) return p; // No manual properties, not an effective direct route.
  auto text = Trim(*server);
  if (text.find(u'=') == text.npos) {
    auto endpoint = ParseEndpoint(text);
    p.httpHost = p.httpsHost = endpoint.host; p.httpPort = p.httpsPort = endpoint.port;
  } else {
    size_t at = 0;
    while (at <= text.size()) {
      auto end = text.find(u';', at); if (end == text.npos) end = text.size();
      auto part = Trim(text.substr(at, end - at));
      auto eq = part.find(u'=');
      if (eq == part.npos) Unsupported("mixed proxy list or fallback");
      auto name = part.substr(0, eq); auto endpoint = ParseEndpoint(Trim(part.substr(eq + 1)));
      if (name == u"http" && !p.httpHost) { p.httpHost = endpoint.host; p.httpPort = endpoint.port; }
      else if (name == u"https" && !p.httpsHost) { p.httpsHost = endpoint.host; p.httpsPort = endpoint.port; }
      else Unsupported("unknown or duplicate proxy scheme");
      if (end == text.size()) break;
      at = end + 1;
    }
  }
  p.nonProxyHosts = ParseBypass(bypass);
  return p;
}

UnityNetworkProxy::PropertySnapshot UnityNetworkProxy::ReadWindowsManualProperties() {
  Environment environment;
#ifdef _WIN32
  struct Module { HMODULE value = nullptr; ~Module() { if (value) FreeLibrary(value); } } module;
  module.value = LoadLibraryExW(L"winhttp.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
  if (!module.value) throw std::runtime_error("manual proxy query: cannot load System32 winhttp.dll, error " + std::to_string(GetLastError()));
  using Query = BOOL (WINAPI*)(WINHTTP_CURRENT_USER_IE_PROXY_CONFIG*);
  auto symbol = GetProcAddress(module.value, "WinHttpGetIEProxyConfigForCurrentUser");
  Query query = nullptr; static_assert(sizeof(query) == sizeof(symbol));
  std::memcpy(&query, &symbol, sizeof(query));
  if (!query) throw std::runtime_error("manual proxy query: WinHTTP configuration API unavailable");
  struct Info {
    WINHTTP_CURRENT_USER_IE_PROXY_CONFIG value{};
    ~Info() { if (value.lpszAutoConfigUrl) GlobalFree(value.lpszAutoConfigUrl); if (value.lpszProxy) GlobalFree(value.lpszProxy); if (value.lpszProxyBypass) GlobalFree(value.lpszProxyBypass); }
  } info;
  if (!query(&info.value)) throw std::runtime_error("manual proxy configuration query failed, error " + std::to_string(GetLastError()));
  static_assert(sizeof(wchar_t) == sizeof(char16_t));
  auto copy = [](const wchar_t* at) -> std::optional<std::u16string> {
    if (!at) return {};
    std::u16string value; while (*at) value.push_back(static_cast<char16_t>(*at++)); return value;
  };
  return ParseWindowsManualSettings(copy(info.value.lpszProxy), copy(info.value.lpszProxyBypass), info.value.fAutoDetect != FALSE, copy(info.value.lpszAutoConfigUrl));
#else
  throw std::runtime_error("manual Windows proxy configuration unavailable on this host");
#endif
}

struct UnityNetworkProxy::Shared {
  jni::Host& host;
  Config config;
  std::atomic<bool> active{false};
  Shared(jni::Host& h, Config c) : host(h), config(std::move(c)) {}
};
UnityNetworkProxy::UnityNetworkProxy(jni::Host& host) : UnityNetworkProxy(host, Config{}) {}
UnityNetworkProxy::UnityNetworkProxy(jni::Host& host, Config config) {
  if (!host.PendingException().empty() || !host.EnvAddress()) throw std::invalid_argument("proxy service requires an attached thread without a pending Java exception");
  if (!config.read_manual_properties) config.read_manual_properties = ReadWindowsManualProperties;
  auto s = std::make_shared<Shared>(host, std::move(config));
  host.BindObjectMethod(kPlayer, "getNetworkProxySettings", "(Ljava/lang/String;)Ljava/lang/String;",
    [s](addr_t, const jni::Host::MethodArguments& arguments) -> addr_t {
      Environment environment;
      if (!s->active.load(std::memory_order_acquire)) throw std::runtime_error("manual proxy service is revoked");
      auto& host = s->host;
      if (!host.PendingException().empty()) return 0;
      auto URL = host.StringValue(arguments[0]);
      if (!host.PendingException().empty()) return 0;
      if (!URL) { host.ThrowException("java/lang/NullPointerException"); return 0; }
      Event event;
      const auto scheme = Scheme(*URL); event.scheme = scheme == 1 ? "http" : scheme == 2 ? "https" : "other";
      if (scheme) {
        event.reader_used = true; event.manual_properties = s->config.read_manual_properties();
        event.result = Format(URL, *event.manual_properties);
      }
      if (!s->active.load(std::memory_order_acquire)) throw std::runtime_error("manual proxy service revoked during query");
      if (s->config.observer) s->config.observer(event);
      if (!s->active.load(std::memory_order_acquire)) throw std::runtime_error("manual proxy service revoked during observation");
      if (!host.PendingException().empty()) return 0;
      return event.result ? host.NewString(*event.result) : 0;
    });
  state_ = std::move(s); state_->active.store(true, std::memory_order_release);
}
UnityNetworkProxy::~UnityNetworkProxy() { Revoke(); }
void UnityNetworkProxy::Revoke() noexcept { if (state_) state_->active.store(false, std::memory_order_release); }
bool UnityNetworkProxy::Active() const noexcept { return state_ && state_->active.load(std::memory_order_acquire); }
}  // namespace bunker::windows
