#pragma once
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>

#include "../whole/runtime.h"
#include "android_types.h"

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

// Exact Android AArch64 constants, verified with the installed NDK preprocessor.
namespace linux_flags {
constexpr int read_only = 0, write_only = 1, read_write = 2;
constexpr int create = 0x40, exclusive = 0x80, truncate = 0x200, append = 0x400;
constexpr int directory = 0x4000, no_follow = 0x8000, large_file = 0x20000, close_on_exec = 0x80000;
constexpr int map_shared = 1, map_private = 2, map_fixed = 0x10, map_anonymous = 0x20, map_fixed_no_replace = 0x100000;
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
  void Install(recomp::Runtime &runtime);
  addr_t ErrnoAddress();
  int Error();
  // Android's legacy __sF is three opaque 152-byte FILE objects. Their guest
  // addresses identify independently owned binary duplicates of host stdio.
  addr_t StandardStreamsAddress();
  int Open(const char *path, int flags, uint32_t mode = 0666);
  int Close(int descriptor);
  int64_t Read(int descriptor, void *buffer, uint64_t count);
  int64_t Write(int descriptor, const void *buffer, uint64_t count);
  int64_t Seek(int descriptor, int64_t offset, int whence);
  int Stat(const char *path, AndroidStat *result, bool no_follow = false);
  int FStat(int descriptor, AndroidStat *result);
  int Access(const char *path, int mode);
  addr_t FOpen(const char *path, const char *mode);
  int FClose(addr_t stream);
  uint64_t FRead(void *buffer, uint64_t size, uint64_t count, addr_t stream);
  uint64_t FWrite(const void *buffer, uint64_t size, uint64_t count, addr_t stream);
  int FSeek(addr_t stream, int64_t offset, int whence);
  int64_t FTell(addr_t stream);
  int FEof(addr_t stream);
  int FError(addr_t stream);
  int FFlush(addr_t stream);
  addr_t Mmap(addr_t address, uint64_t length, int protection, int flags, int descriptor, int64_t offset);
  int Munmap(addr_t address, uint64_t length);
  int Mprotect(addr_t address, uint64_t length, int protection);
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace bunker::windows
