#include "module_registry.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"

#include <algorithm>
#include <atomic>
#include <set>
#include <stdexcept>

namespace bunker::windows {
namespace {
uint64_t ThreadKey() {
  static std::atomic<uint64_t> next{1};
  thread_local const uint64_t key = next.fetch_add(1, std::memory_order_relaxed);
  return key;
}
}
struct ModuleRegistry::Image {
  Module module;
  enum Status { kUnloaded, kLoading, kLoaded, kClosing } status = kUnloaded;
  addr_t handle = 0;
  size_t references = 0;
  bool loaded_before = false;
};
ModuleRegistry::ModuleRegistry(std::function<void(addr_t)> runner, addr_t marker_base)
    : run_lifecycle_(std::move(runner)), marker_base_(marker_base) {
  if (marker_base % 8) throw std::invalid_argument("module marker base must be aligned");
}
ModuleRegistry::~ModuleRegistry() = default;
std::string ModuleRegistry::Path(const std::string &path) {
  auto result = path; std::replace(result.begin(), result.end(), '\\', '/'); return result;
}
void ModuleRegistry::SetError(const std::string &message) { errors_[ThreadKey()].pending = message; }
void ModuleRegistry::Add(Module module) {
  std::lock_guard lock(mutex_);
  if (module.name.empty() || images_.count(module.name)) throw std::invalid_argument("invalid or duplicate translated module");
  if ((!module.initializers.empty() || !module.finalizers.empty()) && !run_lifecycle_) throw std::invalid_argument("module has lifecycle entries but no guest runner");
  // ELF SHN_ABS data exports can legitimately have value zero. Presence in the
  // explicit export map distinguishes that result from a missing dlsym symbol.
  for (const auto &entry : module.exports) if (entry.first.empty()) throw std::invalid_argument("invalid translated export");
  for (auto entry : module.initializers) if (!entry) throw std::invalid_argument("null initializer");
  for (auto entry : module.finalizers) if (!entry) throw std::invalid_argument("null finalizer");
  std::set<std::string> names{Path(module.name)};
  for (const auto &alias : module.aliases) {
    if (alias.empty()) throw std::invalid_argument("empty translated module alias");
    names.insert(Path(alias));
  }
  for (const auto &name : names) if (aliases_.count(name)) throw std::invalid_argument("translated module alias collision");
  auto image = std::make_unique<Image>(); image->module = std::move(module);
  for (const auto &name : names) aliases_.emplace(name, image.get());
  auto key = image->module.name; images_.emplace(key, std::move(image));
}
addr_t ModuleRegistry::Open(const char *path, int flags) {
  std::lock_guard lock(mutex_);
  // Android RTLD_LAZY/RTLD_NOW and optional RTLD_GLOBAL are the supported flags.
  const auto path_snapshot = path ? recomp::ReadGuestString(reinterpret_cast<addr_t>(path)) : std::string();
  if (path_snapshot.empty()) { SetError("translated dlopen requires an explicit registered module path"); return 0; }
  if ((flags & ~0x103) || !(flags & 3) || (flags & 3) == 3) { SetError("unsupported translated dlopen flags"); return 0; }
  auto found = aliases_.find(Path(path_snapshot));
  if (found == aliases_.end()) { SetError(std::string("translated module is unavailable: ") + path_snapshot); return 0; }
  auto &image = *found->second;
  if (image.status == Image::kClosing) { SetError("translated module is being finalized: " + image.module.name); return 0; }
  if (image.status == Image::kLoaded || image.status == Image::kLoading) { ++image.references; return image.handle; }
  if (image.loaded_before && !image.module.reset_image) { SetError("translated module cannot reopen without a data-image reset: " + image.module.name); return 0; }
  image.status = Image::kLoading; image.references = 1; image.handle = next_handle_++;
  handles_.emplace(image.handle, &image);
  try {
    if (image.module.reset_image) image.module.reset_image();
    for (auto entry : image.module.initializers) run_lifecycle_(entry);
  } catch (const std::exception &error) {
    handles_.erase(image.handle); image.handle = 0; image.references = 0; image.status = Image::kUnloaded;
    SetError("translated module initialization failed: " + image.module.name + ": " + error.what()); return 0;
  }
  image.loaded_before = true; image.status = Image::kLoaded; return image.handle;
}
addr_t ModuleRegistry::Symbol(addr_t handle, const char *name) {
  std::lock_guard lock(mutex_);
  auto found = handles_.find(handle);
  if (found == handles_.end()) { SetError("invalid translated module handle"); return 0; }
  const auto name_snapshot = name ? recomp::ReadGuestString(reinterpret_cast<addr_t>(name)) : std::string();
  if (name_snapshot.empty()) { SetError("empty translated export name"); return 0; }
  auto symbol = found->second->module.exports.find(name_snapshot);
  if (symbol == found->second->module.exports.end()) { SetError("translated export is unavailable: " + found->second->module.name + ": " + name_snapshot); return 0; }
  return symbol->second;
}
int ModuleRegistry::Close(addr_t handle) {
  std::lock_guard lock(mutex_);
  auto found = handles_.find(handle);
  if (found == handles_.end() || !found->second->references) { SetError("invalid translated dlclose handle"); return -1; }
  auto &image = *found->second;
  if (image.status != Image::kLoaded) { SetError("translated module cannot close during initialization/finalization"); return -1; }
  if (--image.references) return 0;
  image.status = Image::kClosing;
  try {
    for (auto entry = image.module.finalizers.rbegin(); entry != image.module.finalizers.rend(); ++entry) run_lifecycle_(*entry);
  } catch (const std::exception &error) {
    image.references = 1; image.status = Image::kLoaded;
    SetError("translated module finalization failed: " + image.module.name + ": " + error.what()); return -1;
  }
  handles_.erase(found); image.handle = 0; image.status = Image::kUnloaded; return 0;
}
addr_t ModuleRegistry::Error() {
  std::lock_guard lock(mutex_);
  auto &errors = errors_[ThreadKey()];
  recomp::WithGuestMemoryWrite(reinterpret_cast<addr_t>(errors.retrieved.c_str()), errors.retrieved.size() + 1, [&] {
    errors.retrieved = std::move(errors.pending); errors.pending.clear();
  });
  return errors.retrieved.empty() ? 0 : reinterpret_cast<addr_t>(errors.retrieved.c_str());
}
addr_t ModuleRegistry::Marker(const std::string &name) const {
  if (name == "dlopen") return marker_base_;
  if (name == "dlsym") return marker_base_ + 8;
  if (name == "dlclose") return marker_base_ + 16;
  if (name == "dlerror") return marker_base_ + 24;
  throw std::invalid_argument("unknown libdl bridge name");
}
void ModuleRegistry::Install(recomp::Runtime &runtime) {
  std::lock_guard lock(mutex_);
  if (installed_) throw std::logic_error("module registry already installed");
  runtime.AddImport(Marker("dlopen"), recomp::MakeBridge<addr_t(const char *, int32_t)>([this](const char *path, int32_t flags) { return Open(path, flags); }));
  runtime.AddImport(Marker("dlsym"), recomp::MakeBridge<addr_t(addr_t, const char *)>([this](addr_t handle, const char *name) { return Symbol(handle, name); }));
  runtime.AddImport(Marker("dlclose"), recomp::MakeBridge<int32_t(addr_t)>([this](addr_t handle) { return Close(handle); }));
  runtime.AddImport(Marker("dlerror"), recomp::MakeBridge<addr_t()>([this] { return Error(); }));
  installed_ = true;
}
size_t ModuleRegistry::ReferenceCount(const std::string &name) const {
  std::lock_guard lock(mutex_); auto found = images_.find(name); return found == images_.end() ? 0 : found->second->references;
}
}  // namespace bunker::windows
