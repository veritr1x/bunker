#include <cfenv>
#include "java_tls_trust.h"
#include <atomic>
#include <cerrno>
#include <cstring>
#include <limits>
#include <mutex>
#include <set>
#include <stdexcept>
#include <utility>
#ifdef _WIN32
#include <windows.h>
#include <wincrypt.h>
#endif

namespace bunker::windows {
namespace {
constexpr const char* kFactory = "javax/net/ssl/TrustManagerFactory";
constexpr const char* kTrust = "javax/net/ssl/TrustManager";
constexpr const char* kX509Trust = "javax/net/ssl/X509TrustManager";
constexpr const char* kCertificate = "java/security/cert/Certificate";
constexpr const char* kX509Certificate = "java/security/cert/X509Certificate";
constexpr const char* kManagerImpl = "bunker/windows/RootTrustManager";
constexpr const char* kCertificateImpl = "bunker/windows/RootCertificate";
struct Environment {
#ifdef _WIN32
  DWORD last_error = GetLastError();
#endif
  int saved_errno = errno;
  fenv_t floating{};
  Environment() { std::fegetenv(&floating); }
  ~Environment() { std::fesetenv(&floating); errno = saved_errno;
#ifdef _WIN32
    SetLastError(last_error);
#endif
  }
};
addr_t Env(jni::Host& host, size_t slot, addr_t a = 0, addr_t b = 0,
           addr_t c = 0, addr_t d = 0) {
  ::State state{};
  state.gpr.x0.qword = host.EnvAddress(); state.gpr.x1.qword = a;
  state.gpr.x2.qword = b; state.gpr.x3.qword = c; state.gpr.x4.qword = d;
  host.InvokeEnv(slot, state); return state.gpr.x0.qword;
}
addr_t Array(jni::Host& host, const char* component, size_t count) {
  if (count > static_cast<size_t>(std::numeric_limits<int32_t>::max())) {
    host.ThrowException("java/lang/OutOfMemoryError"); return 0;
  }
  const auto clazz = Env(host, 6, reinterpret_cast<addr_t>(component));
  if (!clazz) return 0;
  return Env(host, 172, count, clazz, 0);
}
bool Pkix(std::u16string algorithm) {
  for (auto& c : algorithm) if (c >= u'a' && c <= u'z') c -= u'a' - u'A';
  return algorithm == u"PKIX";
}
using Certificates = std::vector<JavaTlsTrust::Der>;
struct FactoryState {
  const void* owner;
  std::mutex mutex;
  std::shared_ptr<const Certificates> certificates;
  explicit FactoryState(const void* value) : owner(value) {}
};
struct ManagerState { const void* owner; std::shared_ptr<const Certificates> certificates; };
struct CertificateState { const void* owner; std::shared_ptr<const Certificates> certificates; size_t index; };
#ifdef _WIN32
[[noreturn]] void NativeError(const char* operation, DWORD code) {
  throw std::runtime_error(std::string("Windows public TLS roots: ") + operation +
                           " failed, error " + std::to_string(code));
}
struct Crypto {
  HMODULE module = nullptr;
  decltype(&::CertOpenStore) open = nullptr;
  decltype(&::CertCloseStore) close = nullptr;
  decltype(&::CertEnumCertificatesInStore) next = nullptr;
  decltype(&::CertFreeCertificateContext) free_context = nullptr;
  decltype(&::CertGetEnhancedKeyUsage) usage = nullptr;
  decltype(&::CertGetCertificateChain) chain = nullptr;
  decltype(&::CertFreeCertificateChain) free_chain = nullptr;
  template<class T> T Symbol(const char* name) {
    const auto symbol = GetProcAddress(module, name);
    if (!symbol) NativeError(name, GetLastError());
    T result = nullptr; static_assert(sizeof(result) == sizeof(symbol));
    std::memcpy(&result, &symbol, sizeof(result)); return result;
  }
  Crypto() {
    module = LoadLibraryExW(L"crypt32.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!module) NativeError("load System32 crypt32.dll", GetLastError());
    try {
      open = Symbol<decltype(open)>("CertOpenStore");
      close = Symbol<decltype(close)>("CertCloseStore");
      next = Symbol<decltype(next)>("CertEnumCertificatesInStore");
      free_context = Symbol<decltype(free_context)>("CertFreeCertificateContext");
      usage = Symbol<decltype(usage)>("CertGetEnhancedKeyUsage");
      chain = Symbol<decltype(chain)>("CertGetCertificateChain");
      free_chain = Symbol<decltype(free_chain)>("CertFreeCertificateChain");
    } catch (...) { FreeLibrary(module); module = nullptr; throw; }
  }
  ~Crypto() { if (module) FreeLibrary(module); }
};
struct Store {
  Crypto& api;
  HCERTSTORE handle;
  Store(Crypto& value, DWORD location, const wchar_t* name, bool absent_ok = false)
      : api(value), handle(api.open(CERT_STORE_PROV_SYSTEM_W, 0, 0,
          location | CERT_STORE_READONLY_FLAG | CERT_STORE_OPEN_EXISTING_FLAG, name)) {
    if (!handle) {
      const auto error = GetLastError();
      if (!absent_ok || (error != static_cast<DWORD>(CRYPT_E_NOT_FOUND) && error != ERROR_FILE_NOT_FOUND))
        NativeError("open read-only certificate store", error);
    }
  }
  ~Store() { if (handle) api.close(handle, 0); }
};
template<class Visitor> void Enumerate(Store& store, Visitor visit) {
  if (!store.handle) return;
  struct Cursor {
    Crypto& api; PCCERT_CONTEXT context = nullptr;
    ~Cursor() { if (context) api.free_context(context); }
  } cursor{store.api};
  for (;;) {
    // The API consumes the previous context even if advancing fails.
    cursor.context = store.api.next(store.handle, cursor.context);
    if (!cursor.context) {
      const auto error = GetLastError();
      if (error == static_cast<DWORD>(CRYPT_E_NOT_FOUND) || error == ERROR_NO_MORE_FILES) return;
      NativeError("enumerate certificate store", error);
    }
    visit(cursor.context);
  }
}
JavaTlsTrust::Der CopyDer(PCCERT_CONTEXT context) {
  if (!context->pbCertEncoded || !context->cbCertEncoded)
    throw std::runtime_error("Windows public TLS roots: empty encoded certificate");
  return {context->pbCertEncoded, context->pbCertEncoded + context->cbCertEncoded};
}
bool ServerUsage(Crypto& api, PCCERT_CONTEXT context) {
  DWORD bytes = 0;
  if (!api.usage(context, 0, nullptr, &bytes)) NativeError("query effective EKU size", GetLastError());
  if (bytes < sizeof(CERT_ENHKEY_USAGE)) throw std::runtime_error("Windows public TLS roots: invalid effective EKU size");
  std::vector<DWORD> buffer((bytes + sizeof(DWORD) - 1) / sizeof(DWORD));
  auto* usage = reinterpret_cast<PCERT_ENHKEY_USAGE>(buffer.data());
  SetLastError(ERROR_SUCCESS);
  if (!api.usage(context, 0, usage, &bytes)) NativeError("query effective EKU", GetLastError());
  const auto error = GetLastError();
  if (!usage->cUsageIdentifier) {
    if (error == static_cast<DWORD>(CRYPT_E_NOT_FOUND)) return true; // No restriction exists.
    if (error == ERROR_SUCCESS) return false; // Explicitly disabled for every use.
    NativeError("interpret empty effective EKU", error);
  }
  for (DWORD i = 0; i < usage->cUsageIdentifier; ++i)
    if (!std::strcmp(usage->rgpszUsageIdentifier[i], szOID_PKIX_KP_SERVER_AUTH) ||
        !std::strcmp(usage->rgpszUsageIdentifier[i], szOID_ANY_ENHANCED_KEY_USAGE)) return true;
  return false;
}
bool ExplicitlyDistrusted(Crypto& api, PCCERT_CONTEXT context) {
  CERT_CHAIN_PARA parameters{}; parameters.cbSize = sizeof(parameters);
  LPSTR server_auth = const_cast<LPSTR>(szOID_PKIX_KP_SERVER_AUTH);
  parameters.RequestedUsage.dwType = USAGE_MATCH_TYPE_AND;
  parameters.RequestedUsage.Usage.cUsageIdentifier = 1;
  parameters.RequestedUsage.Usage.rgpszUsageIdentifier = &server_auth;
  struct Chain {
    Crypto& api; PCCERT_CHAIN_CONTEXT context = nullptr;
    ~Chain() { if (context) api.free_chain(context); }
  } chain{api};
  constexpr DWORD flags = CERT_CHAIN_CACHE_ONLY_URL_RETRIEVAL |
      CERT_CHAIN_DISABLE_AUTH_ROOT_AUTO_UPDATE | CERT_CHAIN_DISABLE_AIA;
  if (!api.chain(HCCE_CURRENT_USER, context, nullptr, nullptr, &parameters,
                 flags, nullptr, &chain.context))
    NativeError("query cached anchor explicit distrust", GetLastError());
  if (!chain.context) throw std::runtime_error("Windows public TLS roots: chain query returned no context");
  // A successful API call is not a successful validation. This narrowly checks
  // actual distrust metadata; all other flags remain the original verifier's
  // responsibility. No Java/SSL peer-chain policy is implemented here.
  return (chain.context->TrustStatus.dwErrorStatus & CERT_TRUST_IS_EXPLICIT_DISTRUST) != 0;
}
#endif
}  // namespace

JavaTlsTrust::RootSnapshot JavaTlsTrust::ReadWindowsRootCertificates() {
  Environment environment;
#ifdef _WIN32
  Crypto api;
  std::set<Der> disallowed, accepted;
  for (DWORD location : {DWORD(CERT_SYSTEM_STORE_CURRENT_USER), DWORD(CERT_SYSTEM_STORE_LOCAL_MACHINE)}) {
    Store store(api, location, L"Disallowed", true);
    Enumerate(store, [&](PCCERT_CONTEXT context) { disallowed.insert(CopyDer(context)); });
  }
  RootSnapshot result; result.disallowed_certificates = disallowed.size();
  Store roots(api, CERT_SYSTEM_STORE_CURRENT_USER, L"ROOT");
  Enumerate(roots, [&](PCCERT_CONTEXT context) {
    ++result.enumerated_roots;
    auto der = CopyDer(context);
    if (disallowed.count(der)) { ++result.excluded_disallowed; return; }
    if (!ServerUsage(api, context)) { ++result.excluded_usage; return; }
    if (ExplicitlyDistrusted(api, context)) { ++result.excluded_explicit_distrust; return; }
    if (!accepted.insert(std::move(der)).second) ++result.duplicates;
  });
  result.certificates.assign(accepted.begin(), accepted.end());
  return result;
#else
  throw std::runtime_error("Windows public TLS roots unavailable on this host");
#endif
}

struct JavaTlsTrust::Shared {
  jni::Host& host;
  Config config;
  std::atomic<bool> active{false};
  Shared(jni::Host& h, Config c) : host(h), config(std::move(c)) {}
  void Check() const {
    if (!active.load(std::memory_order_acquire)) throw std::runtime_error("Java public TLS trust service is revoked");
  }
  void Observe(const char* operation, bool reader_used = false, size_t count = 0) {
    Check();
    if (config.observer) config.observer(Event{operation, reader_used, count});
    Check();
  }
};
JavaTlsTrust::JavaTlsTrust(jni::Host& host) : JavaTlsTrust(host, Config{}) {}
JavaTlsTrust::JavaTlsTrust(jni::Host& host, Config config) {
  if (!host.PendingException().empty() || !host.EnvAddress())
    throw std::invalid_argument("TLS trust service requires an attached thread without a pending exception");
  if (!config.read_roots) config.read_roots = ReadWindowsRootCertificates;
  auto s = std::make_shared<Shared>(host, std::move(config));
  host.DefineClass("java/security/GeneralSecurityException", {}, "java/lang/Exception", true);
  host.DefineClass("java/security/NoSuchAlgorithmException", {}, "java/security/GeneralSecurityException", true);
  host.DefineClass("java/security/KeyStoreException", {}, "java/security/GeneralSecurityException", true);
  host.DefineClass("java/security/KeyStore", {}, "java/lang/Object", true);
  host.DefineInterface(kTrust, {});
  host.DefineInterface(kX509Trust, {{"getAcceptedIssuers", "()[Ljava/security/cert/X509Certificate;"}}, true, {kTrust});
  host.DefineClass(kCertificate, {{"getEncoded", "()[B"}}, "java/lang/Object", true);
  host.DefineClass(kX509Certificate, {}, kCertificate, true);
  host.DefineClass(kCertificateImpl, {}, kX509Certificate, true);
  host.DefineClass(kManagerImpl, {}, "java/lang/Object", true, {kX509Trust});
  host.DefineClass(kFactory, {}, "java/lang/Object", true);

  host.DefineStaticObjectMethod(kFactory, "getDefaultAlgorithm", "()Ljava/lang/String;",
    [s](addr_t, const jni::Host::MethodArguments&) -> addr_t {
      Environment environment; s->Observe("getDefaultAlgorithm"); return s->host.NewString(u"PKIX");
    });
  host.DefineStaticObjectMethod(kFactory, "getInstance", "(Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;",
    [s](addr_t, const jni::Host::MethodArguments& arguments) -> addr_t {
      Environment environment; s->Check(); auto& h = s->host;
      if (!arguments[0]) { h.ThrowException("java/lang/NullPointerException"); return 0; }
      const auto name = h.StringValue(arguments[0]);
      if (!name || !h.PendingException().empty()) return 0;
      if (!Pkix(*name)) { h.ThrowException("java/security/NoSuchAlgorithmException"); return 0; }
      s->Observe("getInstance");
      return h.NewHostInstance(kFactory, std::make_shared<FactoryState>(s.get()));
    });
  host.DefineVoidMethod(kFactory, "init", "(Ljava/security/KeyStore;)V",
    [s](addr_t receiver, const jni::Host::MethodArguments& arguments) {
      Environment environment; s->Check(); auto& h = s->host;
      auto factory = h.ReadHostState<FactoryState>(receiver);
      if (!factory || factory->owner != s.get()) { h.ThrowException("java/lang/IllegalArgumentException"); return; }
      if (arguments[0]) { h.ThrowException("java/security/KeyStoreException", u"Only the system-root null KeyStore profile is implemented"); return; }
      RootSnapshot snapshot;
      try { snapshot = s->config.read_roots(); }
      catch (const std::bad_alloc&) { s->Check(); h.ThrowException("java/lang/OutOfMemoryError"); return; }
      catch (const std::exception& error) {
        s->Check();
        const std::string message = error.what();
        h.ThrowException("java/security/KeyStoreException", std::u16string(message.begin(), message.end())); return;
      }
      s->Check();
      auto certificates = std::make_shared<const Certificates>(std::move(snapshot.certificates));
      s->Observe("init", true, certificates->size());
      if (!h.PendingException().empty()) return;
      std::lock_guard lock(factory->mutex); factory->certificates = std::move(certificates);
    });
  host.DefineObjectMethod(kFactory, "getTrustManagers", "()[Ljavax/net/ssl/TrustManager;",
    [s](addr_t receiver, const jni::Host::MethodArguments&) -> addr_t {
      Environment environment; s->Check(); auto& h = s->host;
      auto factory = h.ReadHostState<FactoryState>(receiver);
      if (!factory || factory->owner != s.get()) { h.ThrowException("java/lang/IllegalArgumentException"); return 0; }
      std::shared_ptr<const Certificates> certificates;
      { std::lock_guard lock(factory->mutex); certificates = factory->certificates; }
      if (!certificates) { h.ThrowException("java/lang/IllegalStateException"); return 0; }
      s->Observe("getTrustManagers", false, certificates->size());
      auto array = Array(h, kTrust, 1); if (!array) return 0;
      auto manager = h.NewHostInstance(kManagerImpl, std::make_shared<ManagerState>(ManagerState{s.get(), certificates}));
      Env(h, 174, array, 0, manager);
      return h.PendingException().empty() ? array : 0;
    });
  host.DefineObjectMethod(kManagerImpl, "getAcceptedIssuers", "()[Ljava/security/cert/X509Certificate;",
    [s](addr_t receiver, const jni::Host::MethodArguments&) -> addr_t {
      Environment environment; s->Check(); auto& h = s->host;
      auto manager = h.ReadHostState<ManagerState>(receiver);
      if (!manager || manager->owner != s.get()) { h.ThrowException("java/lang/IllegalArgumentException"); return 0; }
      s->Observe("getAcceptedIssuers", false, manager->certificates->size());
      auto array = Array(h, kX509Certificate, manager->certificates->size()); if (!array) return 0;
      for (size_t i = 0; i < manager->certificates->size(); ++i) {
        auto certificate = h.NewHostInstance(kCertificateImpl, std::make_shared<CertificateState>(CertificateState{s.get(), manager->certificates, i}));
        Env(h, 174, array, i, certificate);
        if (!h.PendingException().empty()) return 0;
        h.DeleteLocalReference(certificate);
      }
      return array;
    });
  host.DefineObjectMethod(kCertificateImpl, "getEncoded", "()[B",
    [s](addr_t receiver, const jni::Host::MethodArguments&) -> addr_t {
      Environment environment; s->Check(); auto& h = s->host;
      auto certificate = h.ReadHostState<CertificateState>(receiver);
      if (!certificate || certificate->owner != s.get()) { h.ThrowException("java/lang/IllegalArgumentException"); return 0; }
      const auto& der = certificate->certificates->at(certificate->index);
      s->Observe("getEncoded", false, certificate->certificates->size());
      if (der.size() > static_cast<size_t>(std::numeric_limits<int32_t>::max())) { h.ThrowException("java/lang/OutOfMemoryError"); return 0; }
      auto bytes = Env(h, 176, der.size()); if (!bytes) return 0;
      if (!der.empty()) Env(h, 208, bytes, 0, der.size(), reinterpret_cast<addr_t>(der.data()));
      return h.PendingException().empty() ? bytes : 0;
    });
  state_ = std::move(s); state_->active.store(true, std::memory_order_release);
}
JavaTlsTrust::~JavaTlsTrust() { Revoke(); }
void JavaTlsTrust::Revoke() noexcept { if (state_) state_->active.store(false, std::memory_order_release); }
bool JavaTlsTrust::Active() const noexcept { return state_ && state_->active.load(std::memory_order_acquire); }
}  // namespace bunker::windows
