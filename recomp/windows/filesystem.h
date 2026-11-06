#pragma once
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <optional>
#include <string>

#include "../whole/runtime.h"
#include "android_types.h"
#include "guest_descriptors.h"

namespace bunker::windows {
struct AndroidStat {
  uint64_t device, inode;
  uint32_t mode, links, uid, gid;
  uint64_t rdevice, pad1;
  int64_t size;
  int32_t block_size, pad2;
  int64_t blocks;
  AndroidTimespec access_time, modification_time, change_time;
  uint32_t unused4, unused5;
};
static_assert(sizeof(AndroidStat) == 128);
static_assert(offsetof(AndroidStat, size) == 48);
static_assert(offsetof(AndroidStat, access_time) == 72);
static_assert(offsetof(AndroidStat, modification_time) == 88);
static_assert(offsetof(AndroidStat, change_time) == 104);

struct AndroidDirent {
  uint64_t inode;
  int64_t offset;
  uint16_t record_length;
  uint8_t type;
  char name[256];
};
static_assert(sizeof(AndroidDirent)==280);
static_assert(offsetof(AndroidDirent,name)==19);

// Exact Android AArch64 constants, verified with the installed NDK preprocessor.
namespace linux_flags {
constexpr int read_only = 0, write_only = 1, read_write = 2;
constexpr int create = 0x40, exclusive = 0x80, truncate = 0x200, append = 0x400;
constexpr int directory = 0x4000, no_follow = 0x8000, large_file = 0x20000, close_on_exec = 0x80000;
constexpr int map_shared = 1, map_private = 2, map_fixed = 0x10, map_anonymous = 0x20, map_growdown = 0x100, map_fixed_no_replace = 0x100000;
}

// Virtual Android paths map only to explicitly mounted Windows paths. Guest
// descriptors, FILE handles, errno and stat layouts never use Windows ABI data.
class FileSystem {
 public:
  explicit FileSystem(addr_t marker_base = 0x7ff600000000ULL);
  ~FileSystem();
  FileSystem(const FileSystem &) = delete;
  FileSystem &operator=(const FileSystem &) = delete;
  void MountFile(const std::string &guest, const std::filesystem::path &host, bool writable = false);
  void MountDirectory(const std::string &guest, const std::filesystem::path &host, bool writable = false);
  void SetWorkingDirectory(const std::string &guest);
  addr_t Marker(const std::string &name) const;
  void Install(recomp::Runtime &runtime,DescriptorImportInterceptor interceptor={});
  addr_t ErrnoAddress();
  int Error();
  void SetError(int);
  std::shared_ptr<GuestDescriptors> DescriptorTable() const;
  // Android's legacy __sF is three opaque 152-byte FILE objects. Their guest
  // addresses identify independently owned binary duplicates of host stdio.
  addr_t StandardStreamsAddress();
  int Open(const char *path, int flags, uint32_t mode = 0666);
  int Close(int descriptor);
  int32_t Dup(int32_t descriptor);
  int64_t Read(int descriptor, void *buffer, uint64_t count);
  int64_t Write(int descriptor, const void *buffer, uint64_t count);
  int64_t Seek(int descriptor, int64_t offset, int whence);
  int Stat(const char *path, AndroidStat *result, bool no_follow = false);
  int FStat(int descriptor, AndroidStat *result);
  int Access(const char *path, int mode);
  // Creates one directory inside an explicit writable mount; never parents.
  // 0700/0755/0777 are maximum-access requests narrowed to an inheritable,
  // protected Windows DACL for the current process user. Other modes fail95.
  // No Android UID/group/umask/chmod equivalence is implied. Stat's existing
  // virtual0755 directory mode is compatibility metadata, not ACL certification.
  // Parent traversal components are rejected with EACCES for this operation.
  int Mkdir(const char *path, uint32_t mode);
  // Removes one file or one empty directory in a writable mount. Mount roots,
  // parent traversal and final reparse points remain protected; never recursive.
  int Unlink(const char *path);
  int Rmdir(const char *path);
  // Reached absent-destination rename profile: one same-mount native move.
  // Replacement is explicitly unsupported; neither path's contents are deleted.
  int Rename(const char *source,const char *destination);
  // Forward-only native directory streams. The returned tracked record lasts
  // until this stream's next ReadDir or CloseDir. Offsets are opaque cookies;
  // seekdir/telldir and concurrent consumption of one returned record are absent.
  addr_t OpenDir(const char *path);
  addr_t ReadDir(addr_t directory);
  int CloseDir(addr_t directory);
  addr_t FOpen(const char *path, const char *mode);
  int FClose(addr_t stream);
  // Exact reached Android setvbuf shape: owned stream, buffer0, mode2
  // (_IONBF), size0 before I/O. Uses native CRT _IONBF; no guest buffer
  // retained. Other valid modes/shapes are explicit unsupported diagnostics.
  int FSetBuffer(addr_t stream, addr_t buffer, int32_t mode, uint64_t size);
  uint64_t FRead(void *buffer, uint64_t size, uint64_t count, addr_t stream);
  uint64_t FWrite(const void *buffer, uint64_t size, uint64_t count, addr_t stream);
  int FSeek(addr_t stream, int64_t offset, int whence);
  int64_t FTell(addr_t stream);
  int FEof(addr_t stream);
  int FError(addr_t stream);
  int FFlush(addr_t stream);
  // Exact owned GC discard: PRIVATE|FIXED|ANONYMOUS, PROT_NONE, fd-1, offset0.
  // Only one existing ordinary anonymous reservation is eligible; pins exclude
  // its entire owner. Decommit/recommit retains addresses and supplies zeros for
  // later Mprotect. Partial replacement conservatively changes the WHOLE owner
  // generation. Failures after decommit are explicitly destructive/fatal.
  addr_t Mmap(addr_t address, uint64_t length, int protection, int flags, int descriptor, int64_t offset);
  // Opt in to real native downward fault growth: 8MiB additional capacity,
  // 1MiB lower gap, 128 process-active owners/4096 retained lifetime records.
  // Default is a named unsupported MAP_GROWSDOWN boundary. Windows workers
  // and all mapping uses must quiesce before owner/provider destruction.
  void EnableGrowdownMappings();
  int Munmap(addr_t address, uint64_t length);
  int Mprotect(addr_t address, uint64_t length, int protection);
  int Madvise(addr_t address, uint64_t length, int advice);
  struct MappingInfo {addr_t base;uint64_t size,generation;};
  // Identifies an owned mmap lifetime and verifies actual page permissions.
  // Growdown owners use stable reserved usable bounds, while the requested
  // span must be actually committed/protected. Bounds alone imply no access.
  // This is not a lease or evidence of a Unity arena subobject's C lifetime.
  std::optional<MappingInfo> MappingRegion(addr_t address,uint64_t length,bool writable)const;
  struct MappingUse {MappingInfo region;std::shared_ptr<void> lease;};
  // Validates the complete span and pins its entire owning mmap until the last
  // copied lease is released. Munmap/Mprotect reject any pinned-owner mutation.
  // FileSystem must outlive all uses; destruction with a live pin is fatal.
  // Final lease release is atomic-only and never calls back into FileSystem.
  std::optional<MappingUse> AcquireMappingUse(addr_t address,uint64_t length,bool writable)const;
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
