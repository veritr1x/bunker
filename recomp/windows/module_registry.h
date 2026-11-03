#pragma once
#include <cstddef>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include "../whole/runtime.h"

namespace bunker::windows {
struct AndroidDlInfo {
  addr_t filename,base,symbol_name,symbol_address;
};
static_assert(sizeof(AndroidDlInfo)==32);
static_assert(offsetof(AndroidDlInfo,base)==8&&offsetof(AndroidDlInfo,symbol_name)==16&&offsetof(AndroidDlInfo,symbol_address)==24);
struct ModuleLoadSegment {uint64_t virtual_address,memory_size;};
struct ModuleAddressSymbol {
  std::string name;
  uint64_t value,size;
  uint16_t section;
  uint8_t type;
  uint8_t binding=0,visibility=0;
  uint16_t version=0;
  bool lookup_eligible=true;
};
struct ModuleAddressImage {
  std::string filename;
  addr_t base,load_bias;
  uint64_t span;
  std::vector<ModuleLoadSegment> loads;
  // Complete GNU bucket/chain or SysV index traversal order, not name order.
  std::vector<ModuleAddressSymbol> symbols;
};
struct Module {
  enum class ExportPolicy {DeclaredAddresses,BionicRawSymbols};
  std::string name;
  std::vector<std::string> aliases;
  std::map<std::string, addr_t> exports;
  std::vector<addr_t> initializers, finalizers;
  // Restore the relocated data-image snapshot before a new load generation.
  // Required for reopening a module after its last dlclose.
  // Publish restored guest bytes through recomp::WriteGuestMemory.
  std::function<void()> reset_image;
  std::optional<ModuleAddressImage> address_image;
  ExportPolicy export_policy=ExportPolicy::DeclaredAddresses;
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
  int32_t Address(addr_t address,AndroidDlInfo *output);
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
