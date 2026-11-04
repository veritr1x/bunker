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
struct AndroidElf64Phdr {
  uint32_t type,flags;
  uint64_t offset,vaddr,paddr,filesz,memsz,align;
};
static_assert(sizeof(AndroidElf64Phdr)==56&&offsetof(AndroidElf64Phdr,vaddr)==16&&offsetof(AndroidElf64Phdr,memsz)==40);
// Android13 AArch64 layout, including the additions since Android R.
struct AndroidDlPhdrInfo {
  addr_t dlpi_addr,dlpi_name,dlpi_phdr;
  uint16_t dlpi_phnum;
  uint8_t reserved[6];
  uint64_t dlpi_adds,dlpi_subs,dlpi_tls_modid;
  addr_t dlpi_tls_data;
};
static_assert(sizeof(AndroidDlPhdrInfo)==64&&offsetof(AndroidDlPhdrInfo,dlpi_phnum)==24&&offsetof(AndroidDlPhdrInfo,dlpi_adds)==32&&offsetof(AndroidDlPhdrInfo,dlpi_subs)==40&&offsetof(AndroidDlPhdrInfo,dlpi_tls_modid)==48&&offsetof(AndroidDlPhdrInfo,dlpi_tls_data)==56);
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
  // Every original program header in file order. The address is the real
  // table inside a file-backed mapped PT_LOAD, never this vector's native data.
  std::vector<AndroidElf64Phdr> program_headers;
  addr_t mapped_program_headers=0;
};
struct Module {
  enum class ExportPolicy {DeclaredAddresses,BionicRawSymbols};
  enum class Kind {TranslatedElf,TypedService};
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
  // Explicit non-ELF typed marker exports have no guest address-image owner.
  // Keep this trailing/defaulted so existing Module aggregates remain ELF.
  Kind kind=Kind::TranslatedElf;
};

// Guest libdl resolves explicitly registered translated images or typed services.
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
  using ProgramHeaderRunner=std::function<int32_t(addr_t,addr_t,uint64_t,addr_t)>;
  // Configure only while iteration callbacks are quiescent. The runner must
  // call the translated callback on the actual current guest thread/stack.
  void SetProgramHeaderRunner(ProgramHeaderRunner);
  int32_t IterateProgramHeaders(addr_t callback,addr_t data);
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
  ProgramHeaderRunner program_header_runner_;
  uint64_t load_counter_=0,unload_counter_=0;
  size_t active_iterations_=0;
  addr_t marker_base_, next_handle_ = 0x7ff500000000ULL;
  bool installed_ = false;
};
}  // namespace bunker::windows
