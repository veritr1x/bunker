#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cctype>
#include <climits>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <io.h>
#include <map>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <sys/stat.h>
#include <windows.h>

#include "filesystem.h"
#include "../whole/bridge.h"

namespace bunker::windows {
namespace fs = std::filesystem;
namespace {
uint64_t ThreadKey() {
  static std::atomic<uint64_t> next{1};
  thread_local const uint64_t key = next.fetch_add(1, std::memory_order_relaxed);
  return key;
}
constexpr addr_t kMapFailed = UINT64_MAX;
constexpr uint64_t kPage = 4096;
const char *names[] = {"__errno", "open", "close", "read", "write", "lseek", "lseek64", "stat", "lstat", "fstat", "access",
  "fopen", "fclose", "fread", "fwrite", "fseek", "fseeko", "ftell", "ftello", "feof", "ferror", "fflush", "mmap", "munmap", "mprotect"};
int GuestCrtError(int error) {
  switch (error) {
    case 0: return 0;
    case ENOENT: return 2; case EINTR: return 4; case EIO: return 5; case EBADF: return 9;
    case EAGAIN: return 11; case ENOMEM: return 12; case EACCES: return 13; case EFAULT: return 14;
    case EEXIST: return 17; case ENOTDIR: return 20; case EISDIR: return 21; case EINVAL: return 22;
    case EMFILE: return 24; case EFBIG: return 27; case ENOSPC: return 28; case EROFS: return 30;
    case EPIPE: return 32; case ENAMETOOLONG: return 36; case ENOSYS: return 38;
    default: return 5;
  }
}
int GuestWinError(DWORD error) {
  switch (error) {
    case ERROR_FILE_NOT_FOUND: case ERROR_PATH_NOT_FOUND: return 2;
    case ERROR_ACCESS_DENIED: case ERROR_SHARING_VIOLATION: case ERROR_LOCK_VIOLATION: return 13;
    case ERROR_INVALID_HANDLE: return 9;
    case ERROR_NOT_ENOUGH_MEMORY: case ERROR_OUTOFMEMORY: return 12;
    case ERROR_FILE_EXISTS: case ERROR_ALREADY_EXISTS: return 17;
    case ERROR_DIRECTORY: return 20;
    case ERROR_INVALID_PARAMETER: case ERROR_MAPPED_ALIGNMENT: return 22;
    case ERROR_TOO_MANY_OPEN_FILES: return 24;
    case ERROR_FILE_TOO_LARGE: return 27;
    case ERROR_DISK_FULL: case ERROR_HANDLE_DISK_FULL: return 28;
    case ERROR_OPERATION_ABORTED: return 4;
    default: return 5;
  }
}
bool Within(const fs::path &root, const fs::path &path) {
  auto a = root.begin(), b = path.begin();
  for (; a != root.end(); ++a, ++b) if (b == path.end() || *a != *b) return false;
  return true;
}
uint64_t RoundPage(uint64_t value) { return (value + kPage - 1) & ~(kPage - 1); }
DWORD Protection(int protection, bool private_file = false) {
  if (!(protection & 7)) return PAGE_NOACCESS;
  if (protection & 4) return protection & 2 ? (private_file ? PAGE_EXECUTE_WRITECOPY : PAGE_EXECUTE_READWRITE) : PAGE_EXECUTE_READ;
  return protection & 2 ? (private_file ? PAGE_WRITECOPY : PAGE_READWRITE) : PAGE_READONLY;
}
AndroidTimespec Timestamp(int64_t ticks) {
  ticks -= 116444736000000000LL;
  auto seconds = ticks / 10000000, remainder = ticks % 10000000;
  if (remainder < 0) { --seconds; remainder += 10000000; }
  return {seconds, remainder * 100};
}
}  // namespace

struct FileSystem::Impl {
  struct Mount { std::string guest; fs::path host; bool directory, writable; uint64_t device; };
  struct Descriptor { int native, flags; bool writable; uint64_t device; };
  struct Stream { FILE *native; bool writable; uint64_t device; };
  struct Mapping { void *native; HANDLE object; uint64_t rounded_length; bool file, private_file; };
  std::recursive_mutex mutex;
  std::vector<Mount> mounts;
  std::map<int, Descriptor> descriptors;
  std::map<addr_t, Stream> streams;
  alignas(8) std::array<uint8_t, 3*152> standard_objects{};
  bool standards_ready = false;
  std::map<addr_t, Mapping> mappings;
  std::map<uint64_t, int32_t> errors;
  std::string cwd = "/";
  int next_descriptor = 1000;
  addr_t next_stream = 0x7ff700000000ULL, marker_base;
  bool installed = false;
  explicit Impl(addr_t base) : marker_base(base) {}
  ~Impl() {
    for (auto &entry : streams) std::fclose(entry.second.native);
    for (auto &entry : descriptors) _close(entry.second.native);
    for (auto &entry : mappings) {
      if (entry.second.file) { UnmapViewOfFile(entry.second.native); CloseHandle(entry.second.object); }
      else VirtualFree(entry.second.native, 0, MEM_RELEASE);
    }
  }
  void Error(int value) { errors[ThreadKey()] = value; }
  void CrtError() { Error(GuestCrtError(errno)); }
  void WinError() { Error(GuestWinError(GetLastError())); }
  std::string Normalize(const std::string &raw) {
    if (raw.empty() || raw.find_first_of("\\:") != std::string::npos) { Error(22); return {}; }
    auto path = raw.front() == '/' ? raw : cwd + "/" + raw;
    std::vector<std::string> parts;
    size_t start = 0;
    while (start <= path.size()) {
      auto end = path.find('/', start); if (end == std::string::npos) end = path.size();
      auto part = path.substr(start, end - start);
      if (part == "..") { if (!parts.empty()) parts.pop_back(); }
      else if (!part.empty() && part != ".") parts.push_back(part);
      if (end == path.size()) break;
      start = end + 1;
    }
    std::string result; for (auto &part : parts) result += "/" + part;
    return result.empty() ? "/" : result;
  }
  bool Resolve(const char *raw, bool writing, fs::path &result, const Mount *&mount, bool no_follow = false) {
    if (!raw) { Error(14); return false; }
    auto normalized = Normalize(raw); if (normalized.empty()) return false;
    mount = nullptr;
    for (const auto &candidate : mounts) {
      bool match = normalized == candidate.guest || (candidate.directory && normalized.size() > candidate.guest.size() &&
          normalized.compare(0, candidate.guest.size(), candidate.guest) == 0 && (candidate.guest == "/" || normalized[candidate.guest.size()] == '/'));
      if (match && (!mount || candidate.guest.size() > mount->guest.size())) mount = &candidate;
    }
    if (!mount) { Error(2); return false; }
    if (writing && !mount->writable) { Error(30); return false; }
    auto suffix = normalized.substr(mount->guest.size()); while (!suffix.empty() && suffix.front() == '/') suffix.erase(suffix.begin());
    result = mount->host;
    if (!suffix.empty()) result /= fs::u8path(suffix);
    // Block Windows device/ADS/path aliases; guest asset names use POSIX names.
    for (auto &part : fs::u8path(suffix)) {
      auto value = part.u8string();
      if (!value.empty() && (value.back() == '.' || value.back() == ' ')) { Error(22); return false; }
      auto stem = value.substr(0, value.find('.'));
      std::transform(stem.begin(), stem.end(), stem.begin(), [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
      if (stem == "CON" || stem == "CONIN$" || stem == "CONOUT$" || stem == "PRN" || stem == "AUX" || stem == "NUL" ||
          (stem.size() == 4 && (stem.compare(0, 3, "COM") == 0 || stem.compare(0, 3, "LPT") == 0) && stem[3] >= '1' && stem[3] <= '9')) { Error(22); return false; }
    }
    std::error_code error;
    auto attributes = GetFileAttributesW(result.c_str());
    if (no_follow && attributes != INVALID_FILE_ATTRIBUTES && attributes & FILE_ATTRIBUTE_REPARSE_POINT) { Error(95); return false; }
    auto canonical = fs::weakly_canonical(result, error);
    if (error) { Error(GuestWinError(error.value())); return false; }
    if (mount->directory ? !Within(mount->host, canonical) : canonical != mount->host) { Error(13); return false; }
    result = canonical;
    return true;
  }
  int NativeFlags(int flags) {
    constexpr int allowed = 3 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800 | 0x1000 | 0x4000 | 0x8000 | 0x20000 | 0x80000 | 0x100000;
    if (flags & ~allowed || (flags & 3) == 3) { Error(22); return -1; }
    if (flags & linux_flags::directory) { Error(95); return -1; }
    int native = (flags & 3) == 0 ? _O_RDONLY : (flags & 3) == 1 ? _O_WRONLY : _O_RDWR;
    native |= _O_BINARY | _O_NOINHERIT;
    if (flags & linux_flags::create) native |= _O_CREAT;
    if (flags & linux_flags::exclusive && flags & linux_flags::create) native |= _O_EXCL;
    if (flags & linux_flags::truncate) native |= _O_TRUNC;
    if (flags & linux_flags::append) native |= _O_APPEND;
    return native;
  }
  bool Fill(HANDLE handle, uint64_t device, bool writable, AndroidStat *output) {
    if (!output) { Error(14); return false; }
    BY_HANDLE_FILE_INFORMATION info{}; FILE_BASIC_INFO times{};
    if (!GetFileInformationByHandle(handle, &info) || !GetFileInformationByHandleEx(handle, FileBasicInfo, &times, sizeof(times))) { WinError(); return false; }
    AndroidStat value{};
    value.device = device; value.inode = (static_cast<uint64_t>(info.nFileIndexHigh) << 32) | info.nFileIndexLow;
    bool directory = info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY;
    value.mode = (directory ? 0040000 : 0100000) | (directory ? (writable ? 0755 : 0555) : (writable ? 0644 : 0444));
    value.links = info.nNumberOfLinks; value.uid = value.gid = 10000;
    value.size = directory ? 0 : static_cast<int64_t>((static_cast<uint64_t>(info.nFileSizeHigh) << 32) | info.nFileSizeLow);
    value.block_size = 4096; value.blocks = value.size / 512 + (value.size % 512 != 0);
    value.access_time = Timestamp(times.LastAccessTime.QuadPart); value.modification_time = Timestamp(times.LastWriteTime.QuadPart); value.change_time = Timestamp(times.ChangeTime.QuadPart);
    std::memcpy(output, &value, sizeof(value)); return true;
  }
};

FileSystem::FileSystem(addr_t base) : impl_(std::make_unique<Impl>(base)) { if (base % 8) throw std::invalid_argument("file marker base must be aligned"); }
FileSystem::~FileSystem() = default;
void FileSystem::MountFile(const std::string &guest, const fs::path &host, bool writable) {
  std::lock_guard lock(impl_->mutex);
  auto normalized = impl_->Normalize(guest);
  if (normalized.empty() || guest.front() != '/' || !fs::is_regular_file(host)) throw std::invalid_argument("invalid file mount");
  for (auto &mount : impl_->mounts) if (mount.guest == normalized) throw std::invalid_argument("duplicate mount");
  impl_->mounts.push_back({normalized, fs::canonical(host), false, writable, impl_->mounts.size() + 1});
}
void FileSystem::MountDirectory(const std::string &guest, const fs::path &host, bool writable) {
  std::lock_guard lock(impl_->mutex);
  auto normalized = impl_->Normalize(guest);
  if (normalized.empty() || guest.front() != '/' || !fs::is_directory(host)) throw std::invalid_argument("invalid directory mount");
  for (auto &mount : impl_->mounts) if (mount.guest == normalized) throw std::invalid_argument("duplicate mount");
  impl_->mounts.push_back({normalized, fs::canonical(host), true, writable, impl_->mounts.size() + 1});
}
void FileSystem::SetWorkingDirectory(const std::string &guest) {
  std::lock_guard lock(impl_->mutex); fs::path path; const Impl::Mount *mount;
  if (!impl_->Resolve(guest.c_str(), false, path, mount) || !fs::is_directory(path)) throw std::invalid_argument("invalid virtual working directory");
  impl_->cwd = impl_->Normalize(guest);
}
addr_t FileSystem::ErrnoAddress() { std::lock_guard lock(impl_->mutex); return reinterpret_cast<addr_t>(&impl_->errors[ThreadKey()]); }
int FileSystem::Error() { std::lock_guard lock(impl_->mutex); return impl_->errors[ThreadKey()]; }
addr_t FileSystem::StandardStreamsAddress() {
  std::lock_guard lock(impl_->mutex);
  auto base = reinterpret_cast<addr_t>(impl_->standard_objects.data());
  if (impl_->standards_ready) return base;
  FILE *source[] = {stdin, stdout, stderr};
  FILE *copies[3]{};
  for (unsigned i = 0; i < 3; ++i) {
    int descriptor = _dup(_fileno(source[i]));
    if (descriptor >= 0) copies[i] = _fdopen(descriptor, i ? "wb" : "rb");
    if (!copies[i]) {
      if (descriptor >= 0) _close(descriptor);
      for (unsigned j = 0; j < i; ++j) std::fclose(copies[j]);
      throw std::runtime_error("cannot duplicate native standard streams for Android __sF");
    }
    // Match standard interactive diagnostics without buffering away a crash.
    if (i == 2) std::setvbuf(copies[i], nullptr, _IONBF, 0);
  }
  for (unsigned i = 0; i < 3; ++i) impl_->streams.emplace(base + i*152, Impl::Stream{copies[i], i != 0, 0});
  impl_->standards_ready = true;
  return base;
}
int FileSystem::Open(const char *path, int flags, uint32_t mode) {
  std::lock_guard lock(impl_->mutex);
  int native_flags = impl_->NativeFlags(flags); if (native_flags < 0) return -1;
  fs::path host; const Impl::Mount *mount;
  bool writing = (flags & 3) != 0 || flags & (linux_flags::create | linux_flags::truncate);
  if (!impl_->Resolve(path, writing, host, mount, flags & linux_flags::no_follow)) return -1;
  int native = _wopen(host.c_str(), native_flags, mode & 0200 ? _S_IREAD | _S_IWRITE : _S_IREAD);
  if (native < 0) { impl_->CrtError(); return -1; }
  int guest = impl_->next_descriptor++;
  impl_->descriptors.emplace(guest, Impl::Descriptor{native, flags, mount->writable, mount->device}); return guest;
}
int FileSystem::Close(int descriptor) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end()) { impl_->Error(9); return -1; }
  int result = _close(found->second.native); impl_->descriptors.erase(found); if (result < 0) impl_->CrtError(); return result;
}
int64_t FileSystem::Read(int descriptor, void *buffer, uint64_t count) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end() || (found->second.flags & 3) == 1) { impl_->Error(9); return -1; }
  if ((!buffer && count) || count > INT64_MAX) { impl_->Error(!buffer ? 14 : 22); return -1; }
  uint64_t total = 0;
  while (total < count) {
    auto chunk = static_cast<unsigned>(std::min<uint64_t>(count - total, INT_MAX));
    int got = _read(found->second.native, static_cast<uint8_t *>(buffer) + total, chunk);
    if (got < 0) { impl_->CrtError(); return total ? static_cast<int64_t>(total) : -1; }
    total += got; if (static_cast<unsigned>(got) < chunk) break;
  }
  return static_cast<int64_t>(total);
}
int64_t FileSystem::Write(int descriptor, const void *buffer, uint64_t count) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end() || !(found->second.flags & 3)) { impl_->Error(9); return -1; }
  if ((!buffer && count) || count > INT64_MAX) { impl_->Error(!buffer ? 14 : 22); return -1; }
  uint64_t total = 0;
  while (total < count) {
    auto chunk = static_cast<unsigned>(std::min<uint64_t>(count - total, INT_MAX));
    int got = _write(found->second.native, static_cast<const uint8_t *>(buffer) + total, chunk);
    if (got < 0) { impl_->CrtError(); return total ? static_cast<int64_t>(total) : -1; }
    total += got; if (static_cast<unsigned>(got) < chunk) break;
  }
  if (found->second.flags & 0x1000 && _commit(found->second.native)) { impl_->CrtError(); return -1; }
  return static_cast<int64_t>(total);
}
int64_t FileSystem::Seek(int descriptor, int64_t offset, int whence) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end()) { impl_->Error(9); return -1; }
  if (whence < 0 || whence > 2) { impl_->Error(22); return -1; }
  auto position = _lseeki64(found->second.native, offset, whence); if (position < 0) impl_->CrtError(); return position;
}
int FileSystem::Stat(const char *path, AndroidStat *result, bool no_follow) {
  std::lock_guard lock(impl_->mutex); fs::path host; const Impl::Mount *mount;
  if (!impl_->Resolve(path, false, host, mount, no_follow)) return -1;
  HANDLE file = CreateFileW(host.c_str(), FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  if (file == INVALID_HANDLE_VALUE) { impl_->WinError(); return -1; }
  bool filled = impl_->Fill(file, mount->device, mount->writable, result); CloseHandle(file); return filled ? 0 : -1;
}
int FileSystem::FStat(int descriptor, AndroidStat *result) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end()) { impl_->Error(9); return -1; }
  return impl_->Fill(reinterpret_cast<HANDLE>(_get_osfhandle(found->second.native)), found->second.device, found->second.writable, result) ? 0 : -1;
}
int FileSystem::Access(const char *path, int mode) {
  std::lock_guard lock(impl_->mutex); if (mode & ~7) { impl_->Error(22); return -1; }
  fs::path host; const Impl::Mount *mount;
  if (!impl_->Resolve(path, mode & 2, host, mount)) return -1;
  if (mode & 1 && !fs::is_directory(host)) { impl_->Error(13); return -1; }
  if (_waccess(host.c_str(), mode & 6)) { impl_->CrtError(); return -1; }
  return 0;
}
addr_t FileSystem::FOpen(const char *path, const char *mode) {
  std::lock_guard lock(impl_->mutex);
  if (!mode || !*mode || !std::strchr("rwa", *mode)) { impl_->Error(22); return 0; }
  bool plus = false, exclusive = false;
  for (const char *at = mode + 1; *at; ++at) {
    if (*at == '+') { if (plus) { impl_->Error(22); return 0; } plus = true; }
    else if (*at == 'x') exclusive = true;
    else if (*at != 'b' && *at != 'e') { impl_->Error(22); return 0; }
  }
  if (exclusive && *mode != 'w') { impl_->Error(22); return 0; }
  int flags = plus ? 2 : *mode == 'r' ? 0 : 1;
  if (*mode != 'r') flags |= linux_flags::create;
  if (*mode == 'w') flags |= linux_flags::truncate;
  if (*mode == 'a') flags |= linux_flags::append;
  if (exclusive) flags |= linux_flags::exclusive;
  fs::path host; const Impl::Mount *mount;
  if (!impl_->Resolve(path, *mode != 'r' || plus, host, mount)) return 0;
  int native = _wopen(host.c_str(), impl_->NativeFlags(flags), _S_IREAD | _S_IWRITE);
  if (native < 0) { impl_->CrtError(); return 0; }
  std::wstring native_mode(1, static_cast<wchar_t>(*mode)); if (plus) native_mode += L'+'; native_mode += L'b';
  FILE *file = _wfdopen(native, native_mode.c_str());
  if (!file) { impl_->CrtError(); _close(native); return 0; }
  auto handle = impl_->next_stream++; impl_->streams.emplace(handle, Impl::Stream{file, mount->writable, mount->device}); return handle;
}
int FileSystem::FClose(addr_t stream) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream);
  if (found == impl_->streams.end()) { impl_->Error(9); return -1; }
  int result = std::fclose(found->second.native); impl_->streams.erase(found); if (result) impl_->CrtError(); return result;
}
uint64_t FileSystem::FRead(void *buffer, uint64_t size, uint64_t count, addr_t stream) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream);
  if (found == impl_->streams.end()) { impl_->Error(9); return 0; }
  if (!size || !count) return 0;
  if (!buffer || count > SIZE_MAX / size) { impl_->Error(!buffer ? 14 : 75); return 0; }
  auto result = std::fread(buffer, size, count, found->second.native);
  if (result < count && std::ferror(found->second.native)) impl_->CrtError(); return result;
}
uint64_t FileSystem::FWrite(const void *buffer, uint64_t size, uint64_t count, addr_t stream) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream);
  if (found == impl_->streams.end()) { impl_->Error(9); return 0; }
  if (!size || !count) return 0;
  if (!buffer || count > SIZE_MAX / size) { impl_->Error(!buffer ? 14 : 75); return 0; }
  auto result = std::fwrite(buffer, size, count, found->second.native); if (result < count) impl_->CrtError(); return result;
}
int FileSystem::FSeek(addr_t stream, int64_t offset, int whence) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream);
  if (found == impl_->streams.end()) { impl_->Error(9); return -1; }
  if (whence < 0 || whence > 2) { impl_->Error(22); return -1; }
  int result = _fseeki64(found->second.native, offset, whence); if (result) impl_->CrtError(); return result;
}
int64_t FileSystem::FTell(addr_t stream) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream);
  if (found == impl_->streams.end()) { impl_->Error(9); return -1; }
  auto result = _ftelli64(found->second.native); if (result < 0) impl_->CrtError(); return result;
}
int FileSystem::FEof(addr_t stream) { std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream); if (found == impl_->streams.end()) { impl_->Error(9); return 0; } return std::feof(found->second.native); }
int FileSystem::FError(addr_t stream) { std::lock_guard lock(impl_->mutex); auto found = impl_->streams.find(stream); if (found == impl_->streams.end()) { impl_->Error(9); return 1; } return std::ferror(found->second.native); }
int FileSystem::FFlush(addr_t stream) {
  std::lock_guard lock(impl_->mutex);
  if (!stream) { int result = 0; for (auto &entry : impl_->streams) if (std::fflush(entry.second.native)) { impl_->CrtError(); result = -1; } return result; }
  auto found = impl_->streams.find(stream); if (found == impl_->streams.end()) { impl_->Error(9); return -1; }
  int result = std::fflush(found->second.native); if (result) impl_->CrtError(); return result;
}
addr_t FileSystem::Mmap(addr_t address, uint64_t length, int protection, int flags, int descriptor, int64_t offset) {
  std::lock_guard lock(impl_->mutex);
  constexpr int allowed = 3 | 0x10 | 0x20 | 0x4000 | 0x20000 | 0x100000;
  if (!length || length > SIZE_MAX - kPage || protection & ~7 || flags & ~allowed || (flags & 3) == 0 || (flags & 3) == 3 || offset < 0 || offset % kPage) { impl_->Error(22); return kMapFailed; }
  if (flags & linux_flags::map_fixed) { impl_->Error(95); return kMapFailed; }
  const bool no_replace = flags & linux_flags::map_fixed_no_replace;
  if (no_replace && (!address || address % kPage)) { impl_->Error(22); return kMapFailed; }
  uint64_t rounded = RoundPage(length);
  if (flags & linux_flags::map_anonymous) {
    if (offset || (flags & 3) == linux_flags::map_shared) { impl_->Error(95); return kMapFailed; }
    void *result = VirtualAlloc(reinterpret_cast<void *>(address), rounded, MEM_RESERVE | MEM_COMMIT, Protection(protection));
    if (!result && address && !no_replace) result = VirtualAlloc(nullptr, rounded, MEM_RESERVE | MEM_COMMIT, Protection(protection));
    if (!result) { if (no_replace && GetLastError() == ERROR_INVALID_ADDRESS) impl_->Error(17); else impl_->WinError(); return kMapFailed; }
    if (no_replace && reinterpret_cast<addr_t>(result) != address) { VirtualFree(result, 0, MEM_RELEASE); impl_->Error(17); return kMapFailed; }
    auto pointer = reinterpret_cast<addr_t>(result); impl_->mappings.emplace(pointer, Impl::Mapping{result, nullptr, rounded, false, false}); return pointer;
  }
  auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end() || (found->second.flags & 3) == 1) { impl_->Error(9); return kMapFailed; }
  const bool private_file = (flags & 3) == linux_flags::map_private;
  if (!private_file && protection & 2 && !(found->second.flags & 3)) { impl_->Error(13); return kMapFailed; }
  auto native = reinterpret_cast<HANDLE>(_get_osfhandle(found->second.native));
  LARGE_INTEGER file_size; if (!GetFileSizeEx(native, &file_size)) { impl_->WinError(); return kMapFailed; }
  if (static_cast<uint64_t>(offset) >= static_cast<uint64_t>(file_size.QuadPart) ||
      static_cast<uint64_t>(offset) > UINT64_MAX - length || static_cast<uint64_t>(offset) + length > RoundPage(file_size.QuadPart)) { impl_->Error(22); return kMapFailed; }
  SYSTEM_INFO system; GetSystemInfo(&system);
  uint64_t aligned_offset = static_cast<uint64_t>(offset) / system.dwAllocationGranularity * system.dwAllocationGranularity;
  uint64_t delta = offset - aligned_offset;
  if (no_replace && (address < delta || (address - delta) % system.dwAllocationGranularity)) { impl_->Error(95); return kMapFailed; }
  DWORD object_protection = private_file ? (protection & 4 ? PAGE_EXECUTE_WRITECOPY : PAGE_WRITECOPY) :
      (protection & 2 ? (protection & 4 ? PAGE_EXECUTE_READWRITE : PAGE_READWRITE) : (protection & 4 ? PAGE_EXECUTE_READ : PAGE_READONLY));
  HANDLE object = CreateFileMappingW(native, nullptr, object_protection, 0, 0, nullptr);
  if (!object) { impl_->WinError(); return kMapFailed; }
  DWORD access = private_file ? FILE_MAP_COPY : protection & 2 ? FILE_MAP_WRITE : FILE_MAP_READ;
  if (protection & 4) access |= FILE_MAP_EXECUTE;
  uint64_t map_length = std::min<uint64_t>(delta + length, file_size.QuadPart - aligned_offset);
  void *hint = address && address >= delta && !((address - delta) % system.dwAllocationGranularity) ? reinterpret_cast<void *>(address - delta) : nullptr;
  void *view = MapViewOfFileEx(object, access, static_cast<DWORD>(aligned_offset >> 32), static_cast<DWORD>(aligned_offset), map_length, hint);
  if (!view && hint && !no_replace) view = MapViewOfFile(object, access, static_cast<DWORD>(aligned_offset >> 32), static_cast<DWORD>(aligned_offset), map_length);
  if (!view) { impl_->WinError(); CloseHandle(object); return kMapFailed; }
  auto pointer = reinterpret_cast<addr_t>(view) + delta;
  DWORD previous;
  if (!VirtualProtect(reinterpret_cast<void *>(pointer), length, Protection(protection, private_file), &previous)) { impl_->WinError(); UnmapViewOfFile(view); CloseHandle(object); return kMapFailed; }
  impl_->mappings.emplace(pointer, Impl::Mapping{view, object, rounded, true, private_file}); return pointer;
}
int FileSystem::Munmap(addr_t address, uint64_t length) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->mappings.find(address);
  if (!length || length > UINT64_MAX - kPage || address % kPage) { impl_->Error(22); return -1; }
  if (found == impl_->mappings.end()) { impl_->Error(22); return -1; }
  if (RoundPage(length) != found->second.rounded_length) { impl_->Error(95); return -1; }
  bool result = found->second.file ? !!UnmapViewOfFile(found->second.native) : !!VirtualFree(found->second.native, 0, MEM_RELEASE);
  if (!result) { impl_->WinError(); return -1; }
  if (found->second.object) CloseHandle(found->second.object); impl_->mappings.erase(found); return 0;
}
int FileSystem::Mprotect(addr_t address, uint64_t length, int protection) {
  std::lock_guard lock(impl_->mutex);
  if (!length || length > UINT64_MAX - kPage || address % kPage || protection & ~7) { impl_->Error(22); return -1; }
  for (auto &entry : impl_->mappings) {
    if (address >= entry.first && address - entry.first <= entry.second.rounded_length && RoundPage(length) <= entry.second.rounded_length - (address - entry.first)) {
      DWORD previous;
      if (!VirtualProtect(reinterpret_cast<void *>(address), length, Protection(protection, entry.second.private_file), &previous)) { impl_->WinError(); return -1; }
      return 0;
    }
  }
  impl_->Error(12); return -1;
}
addr_t FileSystem::Marker(const std::string &name) const {
  if (name == "__sF") return const_cast<FileSystem *>(this)->StandardStreamsAddress();
  for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) if (name == names[i]) return impl_->marker_base + i * 8;
  throw std::invalid_argument("unsupported file-system import " + name);
}
void FileSystem::Install(recomp::Runtime &runtime) {
  std::lock_guard lock(impl_->mutex); if (impl_->installed) throw std::logic_error("file system already installed");
  runtime.AddImport(Marker("__errno"), recomp::MakeBridge<addr_t()>([this] { return ErrnoAddress(); }));
  runtime.AddImport(Marker("open"), recomp::MakeBridge<int32_t(const char *, int32_t, uint32_t)>([this](auto path, auto flags, auto mode) { return Open(path, flags, mode); }));
  runtime.AddImport(Marker("close"), recomp::MakeBridge<int32_t(int32_t)>([this](auto fd) { return Close(fd); }));
  runtime.AddImport(Marker("read"), recomp::MakeBridge<int64_t(int32_t, void *, uint64_t)>([this](auto fd, auto buffer, auto count) { return Read(fd, buffer, count); }));
  runtime.AddImport(Marker("write"), recomp::MakeBridge<int64_t(int32_t, const void *, uint64_t)>([this](auto fd, auto buffer, auto count) { return Write(fd, buffer, count); }));
  for (const char *name : {"lseek", "lseek64"}) runtime.AddImport(Marker(name), recomp::MakeBridge<int64_t(int32_t, int64_t, int32_t)>([this](auto fd, auto offset, auto whence) { return Seek(fd, offset, whence); }));
  for (const char *name : {"stat", "lstat"}) runtime.AddImport(Marker(name), recomp::MakeBridge<int32_t(const char *, AndroidStat *)>([this, follow = std::string(name) == "lstat"](auto path, auto result) { return Stat(path, result, follow); }));
  runtime.AddImport(Marker("fstat"), recomp::MakeBridge<int32_t(int32_t, AndroidStat *)>([this](auto fd, auto result) { return FStat(fd, result); }));
  runtime.AddImport(Marker("access"), recomp::MakeBridge<int32_t(const char *, int32_t)>([this](auto path, auto mode) { return Access(path, mode); }));
  runtime.AddImport(Marker("fopen"), recomp::MakeBridge<addr_t(const char *, const char *)>([this](auto path, auto mode) { return FOpen(path, mode); }));
  runtime.AddImport(Marker("fclose"), recomp::MakeBridge<int32_t(addr_t)>([this](auto stream) { return FClose(stream); }));
  runtime.AddImport(Marker("fread"), recomp::MakeBridge<uint64_t(void *, uint64_t, uint64_t, addr_t)>([this](auto buffer, auto size, auto count, auto stream) { return FRead(buffer, size, count, stream); }));
  runtime.AddImport(Marker("fwrite"), recomp::MakeBridge<uint64_t(const void *, uint64_t, uint64_t, addr_t)>([this](auto buffer, auto size, auto count, auto stream) { return FWrite(buffer, size, count, stream); }));
  for (const char *name : {"fseek", "fseeko"}) runtime.AddImport(Marker(name), recomp::MakeBridge<int32_t(addr_t, int64_t, int32_t)>([this](auto stream, auto offset, auto whence) { return FSeek(stream, offset, whence); }));
  for (const char *name : {"ftell", "ftello"}) runtime.AddImport(Marker(name), recomp::MakeBridge<int64_t(addr_t)>([this](auto stream) { return FTell(stream); }));
  runtime.AddImport(Marker("feof"), recomp::MakeBridge<int32_t(addr_t)>([this](auto stream) { return FEof(stream); }));
  runtime.AddImport(Marker("ferror"), recomp::MakeBridge<int32_t(addr_t)>([this](auto stream) { return FError(stream); }));
  runtime.AddImport(Marker("fflush"), recomp::MakeBridge<int32_t(addr_t)>([this](auto stream) { return FFlush(stream); }));
  runtime.AddImport(Marker("mmap"), recomp::MakeBridge<addr_t(addr_t, uint64_t, int32_t, int32_t, int32_t, int64_t)>([this](auto address, auto length, auto prot, auto flags, auto fd, auto offset) { return Mmap(address, length, prot, flags, fd, offset); }));
  runtime.AddImport(Marker("munmap"), recomp::MakeBridge<int32_t(addr_t, uint64_t)>([this](auto address, auto length) { return Munmap(address, length); }));
  runtime.AddImport(Marker("mprotect"), recomp::MakeBridge<int32_t(addr_t, uint64_t, int32_t)>([this](auto address, auto length, auto prot) { return Mprotect(address, length, prot); }));
  impl_->installed = true;
}
}  // namespace bunker::windows
