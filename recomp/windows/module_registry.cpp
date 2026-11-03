#include "module_registry.h"
#include "../whole/bridge.h"
#include "../whole/guest_memory.h"

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <set>
#include <stdexcept>

namespace bunker::windows {
namespace {
uint64_t ThreadKey() {
  static std::atomic<uint64_t> next{1};
  thread_local const uint64_t key = next.fetch_add(1, std::memory_order_relaxed);
  return key;
}
void ValidateAddressImage(const ModuleAddressImage &image){
  const auto maximum=std::numeric_limits<addr_t>::max();
  if(image.filename.empty()||image.filename.find('\0')!=std::string::npos||!image.base||!image.span||image.span>maximum-image.base||image.loads.empty())throw std::invalid_argument("invalid translated ELF address catalog");
  for(const auto &load:image.loads){
    if(load.virtual_address>maximum-image.load_bias||load.memory_size>maximum-(image.load_bias+load.virtual_address))throw std::invalid_argument("translated PT_LOAD address overflow");
    const auto start=image.load_bias+load.virtual_address;
    if(start<image.base||start>image.base+image.span||load.memory_size>image.base+image.span-start)throw std::invalid_argument("translated PT_LOAD outside registered image bounds");
  }
  for(const auto &symbol:image.symbols)if(symbol.name.find('\0')!=std::string::npos||symbol.size>maximum-symbol.value)throw std::invalid_argument("invalid translated ELF address symbol");
}
void PublishAddressNames(const ModuleAddressImage &image){
  recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(image.filename.c_str()),image.filename.size()+1);
  for(const auto &symbol:image.symbols)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(symbol.name.c_str()),symbol.name.size()+1);
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
ModuleRegistry::~ModuleRegistry(){
  // Registry/import users must quiesce before destruction. These are passive
  // owned metadata strings, not guest/module destructor callbacks.
  for(const auto &entry:images_)if(entry.second->module.address_image)PublishAddressNames(*entry.second->module.address_image);
}
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
  if(module.export_policy!=Module::ExportPolicy::DeclaredAddresses&&module.export_policy!=Module::ExportPolicy::BionicRawSymbols)throw std::invalid_argument("unknown translated export policy");
  if(module.kind!=Module::Kind::TranslatedElf&&module.kind!=Module::Kind::TypedService)throw std::invalid_argument("unknown registered module kind");
  if(module.kind==Module::Kind::TypedService){
    if(module.address_image||!module.initializers.empty()||!module.finalizers.empty()||module.export_policy!=Module::ExportPolicy::DeclaredAddresses)
      throw std::invalid_argument("typed service cannot declare an ELF image or guest lifecycle");
    for(const auto &entry:module.exports)if(!entry.second||(entry.second&7))throw std::invalid_argument("invalid typed service function marker");
  }
  if(module.export_policy==Module::ExportPolicy::BionicRawSymbols&&!module.address_image)throw std::invalid_argument("Bionic raw export policy requires complete ELF metadata");
  if(module.address_image){
    ValidateAddressImage(*module.address_image);
    for(const auto &entry:images_)if(entry.second->module.address_image){
      const auto &other=*entry.second->module.address_image;
      for(const auto &a:module.address_image->loads)for(const auto &b:other.loads){
        const auto left=module.address_image->load_bias+a.virtual_address,right=other.load_bias+b.virtual_address;
        if(a.memory_size&&b.memory_size&&left<right+b.memory_size&&right<left+a.memory_size)throw std::invalid_argument("ambiguous translated ELF PT_LOAD ownership");
      }
    }
  }
  std::set<std::string> names{Path(module.name)};
  for (const auto &alias : module.aliases) {
    if (alias.empty()) throw std::invalid_argument("empty translated module alias");
    names.insert(Path(alias));
  }
  for (const auto &name : names) if (aliases_.count(name)) throw std::invalid_argument("translated module alias collision");
  auto image = std::make_unique<Image>(); image->module = std::move(module);
  if(image->module.address_image)PublishAddressNames(*image->module.address_image);
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
  if(found->second->module.export_policy==Module::ExportPolicy::BionicRawSymbols){
    const auto &metadata=*found->second->module.address_image;const ModuleAddressSymbol *match=nullptr;
    for(const auto &entry:metadata.symbols){
      if(entry.name!=name_snapshot||!entry.lookup_eligible||!entry.section||(entry.binding!=1&&entry.binding!=2))continue;
      // Ordinary dlsym has vi==nullptr: skip hidden versions, then accept any
      // non-hidden default (including Unity's real version index2).
      if(entry.version&0x8000)continue;
      if(match)throw std::runtime_error("unsupported ambiguous default Bionic raw ELF export");
      match=&entry;
    }
    if(!match){SetError("translated raw ELF export is unavailable: "+found->second->module.name+": "+name_snapshot);return 0;}
    if(match->type==10||match->type==6)throw std::runtime_error("unsupported Bionic raw ELF IFUNC/TLS export");
    if(match->value>std::numeric_limits<addr_t>::max()-metadata.load_bias)throw std::overflow_error("Bionic raw ELF export address overflow");
    return metadata.load_bias+match->value;
  }
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
int32_t ModuleRegistry::Address(addr_t address,AndroidDlInfo *output){
  std::lock_guard lock(mutex_);
  for(const auto &entry:images_)if(entry.second->status!=Image::kUnloaded&&entry.second->module.kind!=Module::Kind::TypedService&&!entry.second->module.address_image)
    throw std::runtime_error("unsupported dladdr with incomplete active translated ELF catalog");
  // Android13 untags only membership; symbol lookup below receives the original
  // argument, exactly as do_dladdr/find_symbol_by_address do on AArch64.
  const addr_t membership=address&UINT64_C(0x00ffffffffffffff);
  for(const auto &entry:images_){
    if(entry.second->status==Image::kUnloaded||entry.second->module.kind==Module::Kind::TypedService)continue;
    const auto &image=*entry.second->module.address_image;
    if(membership<image.base||membership-image.base>=image.span)continue;
    bool contains=false;
    for(const auto &load:image.loads)if(membership>=image.load_bias+load.virtual_address&&membership-(image.load_bias+load.virtual_address)<load.memory_size){contains=true;break;}
    if(!contains)continue;
    AndroidDlInfo result{reinterpret_cast<addr_t>(image.filename.c_str()),image.base,0,0};
    const uint64_t relative=address-image.load_bias;
    for(const auto &symbol:image.symbols){
      if(!symbol.section||symbol.type==6||relative<symbol.value||relative-symbol.value>=symbol.size)continue;
      if(symbol.type==10)throw std::runtime_error("unsupported dladdr matched GNU IFUNC resolver");
      if(symbol.value>std::numeric_limits<addr_t>::max()-image.load_bias)throw std::overflow_error("dladdr resolved symbol address overflow");
      result.symbol_name=reinterpret_cast<addr_t>(symbol.name.c_str());
      // Bionic's ordinary resolver adds load_bias even for SHN_ABS. Existing
      // explicitly declared Module.exports/dlsym addresses are unchanged.
      result.symbol_address=image.load_bias+symbol.value;break;
    }
    if(!output)throw std::invalid_argument("unsupported dladdr null output for known translated image");
    recomp::WriteGuestMemory(reinterpret_cast<addr_t>(output),&result,sizeof(result));return 1;
  }
  return 0; // Unknown does not touch output, errno or the existing dlerror slot.
}
addr_t ModuleRegistry::Marker(const std::string &name) const {
  if (name == "dlopen") return marker_base_;
  if (name == "dlsym") return marker_base_ + 8;
  if (name == "dlclose") return marker_base_ + 16;
  if (name == "dlerror") return marker_base_ + 24;
  if (name == "dladdr") return marker_base_ + 32;
  throw std::invalid_argument("unknown libdl bridge name");
}
void ModuleRegistry::Install(recomp::Runtime &runtime) {
  std::lock_guard lock(mutex_);
  if (installed_) throw std::logic_error("module registry already installed");
  runtime.AddImport(Marker("dlopen"), recomp::MakeBridge<addr_t(const char *, int32_t)>([this](const char *path, int32_t flags) { return Open(path, flags); }));
  auto symbol=recomp::MakeBridge<addr_t(addr_t,const char*)>([this](addr_t handle,const char*name){return Symbol(handle,name);});
  runtime.AddImport(Marker("dlsym"),[symbol](State &state){try{symbol(state);}catch(const std::exception&e){std::fprintf(stderr,"module registry dlsym: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fputs("module registry dlsym: unknown exception\n",stderr);std::fflush(stderr);std::abort();}});
  runtime.AddImport(Marker("dlclose"), recomp::MakeBridge<int32_t(addr_t)>([this](addr_t handle) { return Close(handle); }));
  runtime.AddImport(Marker("dlerror"), recomp::MakeBridge<addr_t()>([this] { return Error(); }));
  auto address=recomp::MakeBridge<int32_t(addr_t,AndroidDlInfo*)>([this](auto value,auto output){return Address(value,output);});
  runtime.AddImport(Marker("dladdr"),[address](State &state){try{address(state);}catch(const std::exception &e){std::fprintf(stderr,"module registry dladdr: %s\n",e.what());std::fflush(stderr);std::abort();}catch(...){std::fputs("module registry dladdr: unknown exception\n",stderr);std::fflush(stderr);std::abort();}});
  installed_ = true;
}
size_t ModuleRegistry::ReferenceCount(const std::string &name) const {
  std::lock_guard lock(mutex_); auto found = images_.find(name); return found == images_.end() ? 0 : found->second->references;
}
}  // namespace bunker::windows
