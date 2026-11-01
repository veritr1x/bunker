#pragma once
#include "jni_host.h"
#include <memory>
#include <string>
#include <vector>

namespace bunker::windows {
// A closed, explicit path catalog. The owner must register/mount the translated
// modules separately; this service performs no loading or host filesystem I/O.
class JavaNativeLibraries {
 public:
  struct Library {std::u16string name,guest_path;};
  struct Config {
    addr_t application_loader=0;
    // A real application jclass proves that this is Host's actual app loader,
    // not a newly fabricated ClassLoader instance or bootstrap loader.
    addr_t application_class=0;
    std::vector<Library> libraries;
  };
  JavaNativeLibraries(jni::Host&,const Config&);
  ~JavaNativeLibraries();
  JavaNativeLibraries(const JavaNativeLibraries&)=delete;
  JavaNativeLibraries&operator=(const JavaNativeLibraries&)=delete;
  void Revoke()noexcept;
  bool Active()const noexcept;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}  // namespace bunker::windows
