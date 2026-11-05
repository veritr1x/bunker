#pragma once
#include "jni_host.h"
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// The original Unity caller exports accepted issuers to its own TLS verifier.
// This service supplies public trust-anchor DER; it does not verify TLS peers.
class JavaTlsTrust {
 public:
  using Der = std::vector<uint8_t>;
  struct RootSnapshot {
    std::vector<Der> certificates;
    size_t enumerated_roots = 0, disallowed_certificates = 0;
    size_t excluded_disallowed = 0, excluded_usage = 0, duplicates = 0;
    size_t excluded_explicit_distrust = 0;
  };
  struct Event {
    std::string operation;
    bool reader_used = false;
    size_t certificate_count = 0;
  };
  using Reader = std::function<RootSnapshot()>;
  struct Config { Reader read_roots; std::function<void(const Event&)> observer; };
  explicit JavaTlsTrust(jni::Host&);
  JavaTlsTrust(jni::Host&, Config);
  ~JavaTlsTrust();
  JavaTlsTrust(const JavaTlsTrust&) = delete;
  JavaTlsTrust& operator=(const JavaTlsTrust&) = delete;
  void Revoke() noexcept;
  bool Active() const noexcept;
  // Read-only logical CURRENT_USER ROOT (including its LocalMachine sibling),
  // less CU/LM Disallowed, effective EKUs that exclude TLS server auth, and
  // anchors with explicit distrust reported by the cache-only chain engine.
  // Copies public DER only, with no key access, store writes or network fetch.
  static RootSnapshot ReadWindowsRootCertificates();
 private:
  struct Shared;
  std::shared_ptr<Shared> state_;
};
}  // namespace bunker::windows
