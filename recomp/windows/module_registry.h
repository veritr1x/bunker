#pragma once
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "../whole/runtime.h"

namespace bunker::windows {
struct Module {
  std::string name;
  std::vector<std::string> aliases;
  std::map<std::string, addr_t> exports;
  std::vector<addr_t> initializers, finalizers;
  // Restore the relocated data-image snapshot before a new load generation.
  // Required for reopening a module after its last dlclose.
  // Publish restored guest bytes through recomp::WriteGuestMemory.
  std::function<void()> reset_image;
};

// Guest libdl resolves only modules explicitly registered as translated code.
// It never LoadLibrary/dlopen's ARM64 bytes or falls back to native execution.
class ModuleRegistry {
 public:
  explicit ModuleRegistry(std::function<void(addr_t)> run_lifecycle,
                          addr_t marker_base = 0x7ff400000000ULL);
  ~ModuleRegistry();
  void Add(Module module);
  addr_t Open(const char *path, int flags);
  addr_t Symbol(addr_t handle, const char *name);
  int Close(addr_t handle);
  addr_t Error();
  addr_t Marker(const std::string &name) const;
  void Install(recomp::Runtime &runtime);
  size_t ReferenceCount(const std::string &name) const;
 private:
  struct Image;
  struct Errors { std::string pending, retrieved; };
  void SetError(const std::string &message);
  static std::string Path(const std::string &path);
  mutable std::recursive_mutex mutex_;
  std::map<std::string, std::unique_ptr<Image>> images_;
  std::map<std::string, Image *> aliases_;
  std::map<addr_t, Image *> handles_;
  std::map<uint64_t, Errors> errors_;
  std::function<void(addr_t)> run_lifecycle_;
  addr_t marker_base_, next_handle_ = 0x7ff500000000ULL;
  bool installed_ = false;
};
}  // namespace bunker::windows
