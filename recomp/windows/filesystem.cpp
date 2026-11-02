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
#include <sddl.h>

#include "filesystem.h"
#include "unicode.h"
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
constexpr size_t kIoChunk = 65536;
std::atomic<uint64_t> next_mapping_generation{1};
uint64_t MappingGeneration(){
  auto current=next_mapping_generation.load(std::memory_order_relaxed);
  do{if(current==UINT64_MAX)throw std::overflow_error("mmap lifetime generation exhausted");}
  while(!next_mapping_generation.compare_exchange_weak(current,current+1,std::memory_order_relaxed));
  return current;
}
bool SnapshotString(const char *source, std::string &value, size_t limit) {
  value.clear();if(!source)return false;
  for(size_t i=0;i<limit;++i){char c;recomp::ReadGuestMemory(&c,reinterpret_cast<addr_t>(source)+i,1);if(!c)return true;value+=c;}
  return false;
}
const char *names[] = {"__errno", "open", "close", "read", "write", "lseek", "lseek64", "stat", "lstat", "fstat", "access",
  "fopen", "fclose", "fread", "fwrite", "fseek", "fseeko", "ftell", "ftello", "feof", "ferror", "fflush", "mmap", "munmap", "mprotect", "madvise", "mkdir", "setvbuf", "unlink", "rmdir", "opendir", "readdir", "closedir"};
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
int DirectoryError(DWORD error) {
  if(error==ERROR_INVALID_NAME)return 22;
  if(error==ERROR_FILENAME_EXCED_RANGE)return 36;
  if(error==ERROR_WRITE_PROTECT)return 30;
  return GuestWinError(error);
}
// Apply privacy at creation, never by changing an existing object's ACL.
// https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createdirectoryw
// https://learn.microsoft.com/windows/win32/secauthz/security-descriptor-string-format
int CreatePrivateDirectory(const fs::path &path) {
  struct SecurityApi {
    HMODULE module=LoadLibraryExW(L"advapi32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    decltype(&OpenProcessToken) open=module?reinterpret_cast<decltype(open)>(GetProcAddress(module,"OpenProcessToken")):nullptr;
    decltype(&GetTokenInformation) query=module?reinterpret_cast<decltype(query)>(GetProcAddress(module,"GetTokenInformation")):nullptr;
    decltype(&ConvertSidToStringSidW) sid=module?reinterpret_cast<decltype(sid)>(GetProcAddress(module,"ConvertSidToStringSidW")):nullptr;
    decltype(&ConvertStringSecurityDescriptorToSecurityDescriptorW) descriptor=module?reinterpret_cast<decltype(descriptor)>(GetProcAddress(module,"ConvertStringSecurityDescriptorToSecurityDescriptorW")):nullptr;
    ~SecurityApi(){if(module)FreeLibrary(module);}
  };
  static const SecurityApi api;
  if(!api.open||!api.query||!api.sid||!api.descriptor)return 95;
  // Filesystems that ignore security descriptors cannot satisfy this contract.
  wchar_t volume[MAX_PATH];DWORD flags=0;
  if(!GetVolumePathNameW(path.parent_path().c_str(),volume,MAX_PATH)||
     !GetVolumeInformationW(volume,nullptr,0,nullptr,nullptr,&flags,nullptr,0))return DirectoryError(GetLastError());
  if(!(flags&FILE_PERSISTENT_ACLS))return 95;
  struct Handle {HANDLE value=nullptr;~Handle(){if(value)CloseHandle(value);}} token;
  if(!api.open(GetCurrentProcess(),TOKEN_QUERY,&token.value))return DirectoryError(GetLastError());
  DWORD size=0;
  if(api.query(token.value,TokenUser,nullptr,0,&size)||GetLastError()!=ERROR_INSUFFICIENT_BUFFER)return 5;
  std::vector<uint8_t> user(size);
  if(!api.query(token.value,TokenUser,user.data(),size,&size))return DirectoryError(GetLastError());
  struct Local {void *value=nullptr;~Local(){if(value)LocalFree(value);}} sid,descriptor;
  if(!api.sid(reinterpret_cast<TOKEN_USER*>(user.data())->User.Sid,reinterpret_cast<LPWSTR*>(&sid.value)))return DirectoryError(GetLastError());
  const auto user_sid=static_cast<const wchar_t*>(sid.value);
  const auto text=std::wstring(L"O:")+user_sid+L"D:P(A;OICI;FA;;;"+user_sid+L")";
  if(!api.descriptor(text.c_str(),SDDL_REVISION_1,&descriptor.value,nullptr))return DirectoryError(GetLastError());
  SECURITY_ATTRIBUTES attributes{sizeof(attributes),descriptor.value,FALSE};
  return CreateDirectoryW(path.c_str(),&attributes)?0:DirectoryError(GetLastError());
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
  struct Descriptor {
    std::mutex io;int native,flags;bool writable;uint64_t device;
    Descriptor(int n,int f,bool w,uint64_t d):native(n),flags(f),writable(w),device(d){}
    ~Descriptor(){if(native>=0)_close(native);}
  };
  struct Stream {
    std::mutex io;FILE *native;bool writable;uint64_t device;bool io_started=false;
    Stream(FILE *n,bool w,uint64_t d):native(n),writable(w),device(d){}
    ~Stream(){if(native)std::fclose(native);}
  };
  struct Directory {
    std::mutex io;HANDLE native;
    alignas(8) std::array<uint8_t,65536> batch{};
    AndroidDirent record{};
    size_t position=0;int64_t cookie=0;
    bool next_batch=true,eof=false,record_live=true;
    explicit Directory(HANDLE h):native(h){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(&record),sizeof(record));}
    void Retire(){if(record_live){recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(&record),sizeof(record));record_live=false;}}
    ~Directory(){Retire();if(native!=INVALID_HANDLE_VALUE)CloseHandle(native);}
  };
  struct Mapping { void *native; HANDLE object; uint64_t rounded_length; bool file, private_file; uint64_t generation; };
  std::recursive_mutex mutex;
  std::vector<Mount> mounts;
  std::map<int, std::shared_ptr<Descriptor>> descriptors;
  std::map<addr_t, std::shared_ptr<Stream>> streams;
  std::map<addr_t, std::shared_ptr<Directory>> directories;
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
    for(auto &entry:errors)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(&entry.second),sizeof(entry.second));
    recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(standard_objects.data()),standard_objects.size());
    for (auto &entry : mappings) {
      recomp::InvalidateGuestMemory(entry.first,entry.second.rounded_length);
      if (entry.second.file) { UnmapViewOfFile(entry.second.native); CloseHandle(entry.second.object); }
      else VirtualFree(entry.second.native, 0, MEM_RELEASE);
    }
  }
  void Error(int value) {std::lock_guard lock(mutex);auto &slot=errors[ThreadKey()];recomp::WriteGuestMemory(reinterpret_cast<addr_t>(&slot),&value,sizeof(value));}
  std::shared_ptr<Descriptor> GetDescriptor(int descriptor){std::lock_guard lock(mutex);auto it=descriptors.find(descriptor);if(it==descriptors.end()){Error(9);return {};}return it->second;}
  std::shared_ptr<Stream> GetStream(addr_t stream){std::lock_guard lock(mutex);auto it=streams.find(stream);if(it==streams.end()){Error(9);return {};}return it->second;}
  std::shared_ptr<Directory> GetDirectory(addr_t token){std::lock_guard lock(mutex);auto it=directories.find(token);if(it==directories.end()){Error(9);return {};}return it->second;}
  addr_t OpaqueToken(){if(next_stream>=0x7ff800000000ULL){Error(75);return 0;}return next_stream++;}
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
  bool Resolve(const char *raw, bool writing, fs::path &result, const Mount *&mount, bool no_follow = false, bool directory_create = false) {
    if (!raw) { Error(14); return false; }
    std::string snapshot;if(!SnapshotString(raw,snapshot,4096)){Error(36);return false;}
    auto normalized = Normalize(snapshot); if (normalized.empty()) return false;
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
    if(directory_create){
      // Check existing ancestors explicitly: Win32 otherwise often reports
      // PATH_NOT_FOUND both for absent parents and for a file used as a parent.
      fs::path parent=mount->host;
      const auto relative=result.lexically_relative(mount->host);
      for(auto at=relative.begin();at!=relative.end();++at){
        auto next=at;++next;if(next==relative.end())break;
        parent/=*at;auto attributes=GetFileAttributesW(parent.c_str());
        if(attributes==INVALID_FILE_ATTRIBUTES){Error(DirectoryError(GetLastError()));return false;}
        if(!(attributes&FILE_ATTRIBUTE_DIRECTORY)){Error(20);return false;}
      }
      if(GetFileAttributesW(result.c_str())!=INVALID_FILE_ATTRIBUTES){Error(17);return false;}
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
  int Remove(const char *path,bool directory) {
    std::lock_guard lock(mutex);
    if(!path){Error(14);return -1;}
    std::string snapshot;
    if(!SnapshotString(path,snapshot,4096)){Error(36);return -1;}
    if(snapshot.empty()){Error(2);return -1;}
    // Match mkdir's rooted write policy; do not normalize a parent traversal
    // into another explicit mount or hide a missing/non-directory ancestor.
    for(size_t start=0;start<=snapshot.size();){
      auto end=snapshot.find('/',start);if(end==std::string::npos)end=snapshot.size();
      if(snapshot.compare(start,end-start,"..")==0){Error(13);return -1;}
      if(end==snapshot.size())break;start=end+1;
    }
    fs::path host;const Mount *mount;
    try{if(!Resolve(snapshot.c_str(),true,host,mount,true))return -1;}
    catch(const fs::filesystem_error &){Error(22);return -1;}
    // Configured capability roots outlive their contents, even when writable.
    if(host==mount->host){Error(16);return -1;}
    fs::path parent=mount->host;
    const auto relative=host.lexically_relative(mount->host);
    for(auto at=relative.begin();at!=relative.end();++at){
      auto next=at;++next;if(next==relative.end())break;
      parent/=*at;auto attributes=GetFileAttributesW(parent.c_str());
      if(attributes==INVALID_FILE_ATTRIBUTES){Error(DirectoryError(GetLastError()));return -1;}
      if(!(attributes&FILE_ATTRIBUTE_DIRECTORY)){Error(20);return -1;}
    }
    auto attributes=GetFileAttributesW(host.c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES){Error(DirectoryError(GetLastError()));return -1;}
    const bool is_directory=(attributes&FILE_ATTRIBUTE_DIRECTORY)!=0;
    if(!is_directory&&(directory||snapshot.back()=='/')){Error(20);return -1;}
    if(is_directory&&!directory){Error(21);return -1;}
    auto final=snapshot.find_last_not_of('/');
    if(final!=std::string::npos&&snapshot[final]=='.'&&(final==0||snapshot[final-1]=='/')){Error(22);return -1;}
    const auto removed=directory?RemoveDirectoryW(host.c_str()):DeleteFileW(host.c_str());
    if(!removed){auto error=GetLastError();Error(error==ERROR_DIR_NOT_EMPTY?39:DirectoryError(error));return -1;}
    return 0;
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
    recomp::WriteGuestMemory(reinterpret_cast<addr_t>(output),&value,sizeof(value)); return true;
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
int FileSystem::Error() {std::lock_guard lock(impl_->mutex);int32_t result;auto &slot=impl_->errors[ThreadKey()];recomp::ReadGuestMemory(&result,reinterpret_cast<addr_t>(&slot),sizeof(result));return result;}
void FileSystem::SetError(int value){impl_->Error(value);}
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
  for (unsigned i = 0; i < 3; ++i) impl_->streams.emplace(base + i*152, std::make_shared<Impl::Stream>(copies[i], i != 0, 0));
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
  impl_->descriptors.emplace(guest, std::make_shared<Impl::Descriptor>(native, flags, mount->writable, mount->device)); return guest;
}
int FileSystem::Close(int descriptor) {
  std::shared_ptr<Impl::Descriptor> file;
  {std::lock_guard lock(impl_->mutex);auto found=impl_->descriptors.find(descriptor);if(found==impl_->descriptors.end()){impl_->Error(9);return -1;}file=found->second;impl_->descriptors.erase(found);}
  std::lock_guard lock(file->io);int result=_close(file->native);file->native=-1;if(result<0)impl_->CrtError();return result;
}
int64_t FileSystem::Read(int descriptor, void *buffer, uint64_t count) {
  auto file=impl_->GetDescriptor(descriptor);if(!file)return -1;std::lock_guard lock(file->io);
  if (file->native<0 || (file->flags & 3) == 1) { impl_->Error(9); return -1; }
  if ((!buffer && count) || count > INT64_MAX) { impl_->Error(!buffer ? 14 : 22); return -1; }
  uint64_t total = 0;
  std::array<uint8_t,kIoChunk> bounce;
  while (total < count) {
    auto chunk = static_cast<unsigned>(std::min<uint64_t>(count - total, bounce.size()));
    int got = _read(file->native,bounce.data(),chunk);
    if (got < 0) { impl_->CrtError(); return total ? static_cast<int64_t>(total) : -1; }
    if(got)recomp::WriteGuestMemory(reinterpret_cast<addr_t>(buffer)+total,bounce.data(),got);
    total += got; if (static_cast<unsigned>(got) < chunk) break;
  }
  return static_cast<int64_t>(total);
}
int64_t FileSystem::Write(int descriptor, const void *buffer, uint64_t count) {
  auto file=impl_->GetDescriptor(descriptor);if(!file)return -1;std::lock_guard lock(file->io);
  if(file->native<0||!(file->flags&3)){impl_->Error(9);return -1;}
  if ((!buffer && count) || count > INT64_MAX) { impl_->Error(!buffer ? 14 : 22); return -1; }
  uint64_t total = 0;
  std::array<uint8_t,kIoChunk> bounce;
  while (total < count) {
    auto chunk = static_cast<unsigned>(std::min<uint64_t>(count-total,bounce.size()));
    recomp::ReadGuestMemory(bounce.data(),reinterpret_cast<addr_t>(buffer)+total,chunk);
    int got = _write(file->native,bounce.data(),chunk);
    if (got < 0) { impl_->CrtError(); return total ? static_cast<int64_t>(total) : -1; }
    total += got; if (static_cast<unsigned>(got) < chunk) break;
  }
  if(file->flags&0x1000&&_commit(file->native)){impl_->CrtError();return -1;}
  return static_cast<int64_t>(total);
}
int64_t FileSystem::Seek(int descriptor, int64_t offset, int whence) {
  auto file=impl_->GetDescriptor(descriptor);if(!file)return -1;std::lock_guard lock(file->io);if(file->native<0){impl_->Error(9);return -1;}
  if (whence < 0 || whence > 2) { impl_->Error(22); return -1; }
  auto position = _lseeki64(file->native,offset,whence); if (position < 0) impl_->CrtError(); return position;
}
int FileSystem::Stat(const char *path, AndroidStat *result, bool no_follow) {
  std::lock_guard lock(impl_->mutex); fs::path host; const Impl::Mount *mount;
  if (!impl_->Resolve(path, false, host, mount, no_follow)) return -1;
  HANDLE file = CreateFileW(host.c_str(), FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  if (file == INVALID_HANDLE_VALUE) { impl_->WinError(); return -1; }
  bool filled = impl_->Fill(file, mount->device, mount->writable, result); CloseHandle(file); return filled ? 0 : -1;
}
int FileSystem::FStat(int descriptor, AndroidStat *result) {
  auto file=impl_->GetDescriptor(descriptor);if(!file)return -1;std::lock_guard lock(file->io);if(file->native<0){impl_->Error(9);return -1;}
  return impl_->Fill(reinterpret_cast<HANDLE>(_get_osfhandle(file->native)),file->device,file->writable,result)?0:-1;
}
int FileSystem::Access(const char *path, int mode) {
  std::lock_guard lock(impl_->mutex); if (mode & ~7) { impl_->Error(22); return -1; }
  fs::path host; const Impl::Mount *mount;
  if (!impl_->Resolve(path, mode & 2, host, mount)) return -1;
  if (mode & 1 && !fs::is_directory(host)) { impl_->Error(13); return -1; }
  if (_waccess(host.c_str(), mode & 6)) { impl_->CrtError(); return -1; }
  return 0;
}
int FileSystem::Mkdir(const char *path,uint32_t mode) {
  std::lock_guard lock(impl_->mutex);
  if(!path){impl_->Error(14);return -1;}
  std::string snapshot;
  if(!SnapshotString(path,snapshot,4096)){impl_->Error(36);return -1;}
  if(snapshot.empty()){impl_->Error(2);return -1;}
  if(mode!=0700&&mode!=0755&&mode!=0777){
    std::fprintf(stderr,"mkdir mode %#o unsupported by owner-private Windows policy\n",mode);
    impl_->Error(95);return -1;
  }
  // Do not let lexical normalization bypass a missing/file ancestor, or turn
  // a parent traversal into a write through some other explicit mount.
  for(size_t start=0;start<=snapshot.size();){
    auto end=snapshot.find('/',start);if(end==std::string::npos)end=snapshot.size();
    if(snapshot.compare(start,end-start,"..")==0){impl_->Error(13);return -1;}
    if(end==snapshot.size())break;start=end+1;
  }
  fs::path host;const Impl::Mount *mount;
  try{
    if(!impl_->Resolve(snapshot.c_str(),true,host,mount,false,true))return -1;
  }catch(const fs::filesystem_error &){impl_->Error(22);return -1;}
  auto error=CreatePrivateDirectory(host);
  if(error){impl_->Error(error);return -1;}
  return 0;
}
int FileSystem::Unlink(const char *path){return impl_->Remove(path,false);}
int FileSystem::Rmdir(const char *path){return impl_->Remove(path,true);}
addr_t FileSystem::OpenDir(const char *path){
  std::lock_guard lock(impl_->mutex);
  if(!path){impl_->Error(14);return 0;}
  std::string snapshot;
  if(!SnapshotString(path,snapshot,4096)){impl_->Error(36);return 0;}
  if(snapshot.empty()){impl_->Error(2);return 0;}
  fs::path host;const Impl::Mount *mount;
  try{
    Utf16(snapshot); // Reject unrepresentable byte paths, never silently replace.
    if(!impl_->Resolve(snapshot.c_str(),false,host,mount,true))return 0;
  }catch(const std::invalid_argument &){impl_->Error(84);return 0;}
  catch(const fs::filesystem_error &){impl_->Error(22);return 0;}
  if(mount->directory){
    fs::path parent=mount->host;const auto relative=host.lexically_relative(parent);
    for(auto at=relative.begin();at!=relative.end();++at){
      auto next=at;++next;if(next==relative.end())break;
      parent/=*at;auto attributes=GetFileAttributesW(parent.c_str());
      if(attributes==INVALID_FILE_ATTRIBUTES){impl_->Error(DirectoryError(GetLastError()));return 0;}
      if(!(attributes&FILE_ATTRIBUTE_DIRECTORY)){impl_->Error(20);return 0;}
    }
  }
  struct OwnedHandle{HANDLE value=INVALID_HANDLE_VALUE;~OwnedHandle(){if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);}}handle;
  handle.value=CreateFileW(host.c_str(),FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(handle.value==INVALID_HANDLE_VALUE){impl_->Error(DirectoryError(GetLastError()));return 0;}
  BY_HANDLE_FILE_INFORMATION info{};
  if(!GetFileInformationByHandle(handle.value,&info)){impl_->WinError();return 0;}
  if(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT){impl_->Error(95);return 0;}
  if(!(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)){impl_->Error(20);return 0;}
  try{
    auto directory=std::make_shared<Impl::Directory>(handle.value);handle.value=INVALID_HANDLE_VALUE;
    auto token=impl_->OpaqueToken();if(!token)return 0;
    impl_->directories.emplace(token,std::move(directory));return token;
  }catch(const std::bad_alloc &){impl_->Error(12);return 0;}
}
addr_t FileSystem::ReadDir(addr_t token){
  auto directory=impl_->GetDirectory(token);if(!directory)return 0;
  std::lock_guard lock(directory->io);
  if(directory->native==INVALID_HANDLE_VALUE){impl_->Error(9);return 0;}
  if(directory->eof)return 0;
  if(directory->next_batch){
    directory->batch.fill(0);
    if(!GetFileInformationByHandleEx(directory->native,FileIdBothDirectoryInfo,directory->batch.data(),DWORD(directory->batch.size()))){
      const auto error=GetLastError();
      if(error==ERROR_NO_MORE_FILES){directory->eof=true;return 0;}
      if(error==ERROR_INVALID_FUNCTION||error==ERROR_NOT_SUPPORTED||error==ERROR_INVALID_PARAMETER)
        throw std::runtime_error("native FileIdBothDirectoryInfo enumeration is unsupported: "+std::to_string(error));
      impl_->Error(DirectoryError(error));return 0;
    }
    directory->position=0;directory->next_batch=false;
  }
  static_assert(sizeof(wchar_t)==2);
  constexpr auto header_size=offsetof(FILE_ID_BOTH_DIR_INFO,FileName);
  if(directory->position>directory->batch.size())throw std::runtime_error("malformed native directory cursor");
  const auto remaining=directory->batch.size()-directory->position;
  if(remaining<header_size)throw std::runtime_error("malformed native directory header range");
  FILE_ID_BOTH_DIR_INFO entry{};std::memcpy(&entry,directory->batch.data()+directory->position,header_size);
  const auto length=size_t(entry.FileNameLength),next=size_t(entry.NextEntryOffset);
  if(!length||(length%2)||length>remaining-header_size||(next&&(next%8||next<header_size+length||next>remaining-header_size)))
    throw std::runtime_error("malformed native directory entry bounds/alignment");
  const auto source=directory->batch.data()+directory->position+header_size;
  if(reinterpret_cast<uintptr_t>(source)%alignof(wchar_t))throw std::runtime_error("unaligned native UTF16 directory name");
  std::u16string wide(length/2,0);std::memcpy(wide.data(),source,length);
  if(wide.find_first_of(u"\0/\\",0,3)!=std::u16string::npos)throw std::runtime_error("malformed native directory name");
  std::string name;
  try{name=Utf8(wide);}catch(const std::invalid_argument &){throw std::runtime_error("native directory name has unsupported invalid UTF16");}
  if(name.size()>=sizeof(AndroidDirent::name))throw std::runtime_error("native directory name exceeds Android dirent UTF8 capacity");
  if(directory->cookie==INT64_MAX)throw std::overflow_error("directory stream cookie exhausted");
  AndroidDirent result{};result.inode=static_cast<uint64_t>(entry.FileId.QuadPart);result.offset=directory->cookie+1;
  result.record_length=uint16_t((offsetof(AndroidDirent,name)+name.size()+1+7)&~size_t(7));
  result.type=(entry.FileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DEVICE))?0:(entry.FileAttributes&FILE_ATTRIBUTE_DIRECTORY)?4:8;
  std::memcpy(result.name,name.data(),name.size());
  const auto address=reinterpret_cast<addr_t>(&directory->record);
  recomp::WriteGuestMemory(address,&result,sizeof(result));
  directory->cookie=result.offset;
  if(next)directory->position+=next;else directory->next_batch=true;
  return address;
}
int FileSystem::CloseDir(addr_t token){
  std::shared_ptr<Impl::Directory> directory;
  {std::lock_guard lock(impl_->mutex);auto found=impl_->directories.find(token);if(found==impl_->directories.end()){impl_->Error(9);return -1;}directory=found->second;impl_->directories.erase(found);}
  std::lock_guard lock(directory->io);directory->Retire();
  const auto handle=directory->native;directory->native=INVALID_HANDLE_VALUE;
  if(handle==INVALID_HANDLE_VALUE){impl_->Error(9);return -1;}
  if(!CloseHandle(handle)){impl_->WinError();return -1;}return 0;
}
addr_t FileSystem::FOpen(const char *path, const char *mode) {
  std::lock_guard lock(impl_->mutex);
  std::string mode_copy;if(!SnapshotString(mode,mode_copy,16)){impl_->Error(22);return 0;}mode=mode_copy.c_str();
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
  auto handle=impl_->OpaqueToken();if(!handle){std::fclose(file);return 0;}impl_->streams.emplace(handle,std::make_shared<Impl::Stream>(file,mount->writable,mount->device));return handle;
}
int FileSystem::FClose(addr_t stream) {
  std::shared_ptr<Impl::Stream> file;
  {std::lock_guard lock(impl_->mutex);auto it=impl_->streams.find(stream);if(it==impl_->streams.end()){impl_->Error(9);return -1;}file=it->second;impl_->streams.erase(it);}
  std::lock_guard lock(file->io);int result=std::fclose(file->native);file->native=nullptr;if(result)impl_->CrtError();return result;
}
int FileSystem::FSetBuffer(addr_t stream, addr_t buffer, int32_t mode, uint64_t size) {
  auto file=impl_->GetStream(stream);if(!file)return -1;
  std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return -1;}
  // Bionic _IOFBF=0, _IOLBF=1, _IONBF=2; Windows values are different.
  if(mode<0||mode>2){impl_->Error(22);return -1;}
  if(file->io_started)throw std::runtime_error("setvbuf after stdio operations is outside the reached pre-I/O scope");
  if(mode!=2||buffer||size)throw std::runtime_error("Unsupported setvbuf shape; only(NULL,Android_IONBF2,size0) before I/O is implemented");
  int result=std::setvbuf(file->native,nullptr,_IONBF,0);
  if(result){impl_->CrtError();return -1;}
  return 0;
}
uint64_t FileSystem::FRead(void *buffer, uint64_t size, uint64_t count, addr_t stream) {
  auto file=impl_->GetStream(stream);if(!file)return 0;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return 0;}
  if (!size || !count) return 0;
  if (!buffer || count > SIZE_MAX / size) { impl_->Error(!buffer ? 14 : 75); return 0; }
  file->io_started=true;
  std::array<uint8_t,kIoChunk> bounce;uint64_t total=0,bytes=size*count;
  while(total<bytes){size_t chunk=static_cast<size_t>(std::min<uint64_t>(bytes-total,bounce.size()));auto got=std::fread(bounce.data(),1,chunk,file->native);int host_error=errno;
    if(got)recomp::WriteGuestMemory(reinterpret_cast<addr_t>(buffer)+total,bounce.data(),got);
    total+=got;if(got<chunk){if(std::ferror(file->native))impl_->Error(GuestCrtError(host_error));break;}}
  // A partial final item still changes its bytes, just as native fread does.
  return total/size;
}
uint64_t FileSystem::FWrite(const void *buffer, uint64_t size, uint64_t count, addr_t stream) {
  auto file=impl_->GetStream(stream);if(!file)return 0;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return 0;}
  if (!size || !count) return 0;
  if (!buffer || count > SIZE_MAX / size) { impl_->Error(!buffer ? 14 : 75); return 0; }
  file->io_started=true;
  std::array<uint8_t,kIoChunk> bounce;uint64_t total=0,bytes=size*count;
  while(total<bytes){size_t chunk=static_cast<size_t>(std::min<uint64_t>(bytes-total,bounce.size()));recomp::ReadGuestMemory(bounce.data(),reinterpret_cast<addr_t>(buffer)+total,chunk);
    auto got=std::fwrite(bounce.data(),1,chunk,file->native);total+=got;if(got<chunk){impl_->CrtError();break;}}
  return total/size;
}
int FileSystem::FSeek(addr_t stream, int64_t offset, int whence) {
  auto file=impl_->GetStream(stream);if(!file)return -1;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return -1;}
  if (whence < 0 || whence > 2) { impl_->Error(22); return -1; }
  file->io_started=true;int result = _fseeki64(file->native,offset,whence); if (result) impl_->CrtError(); return result;
}
int64_t FileSystem::FTell(addr_t stream) {
  auto file=impl_->GetStream(stream);if(!file)return -1;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return -1;}
  file->io_started=true;auto result = _ftelli64(file->native); if (result < 0) impl_->CrtError(); return result;
}
int FileSystem::FEof(addr_t stream){auto file=impl_->GetStream(stream);if(!file)return 0;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return 0;}file->io_started=true;return std::feof(file->native);}
int FileSystem::FError(addr_t stream){auto file=impl_->GetStream(stream);if(!file)return 1;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return 1;}file->io_started=true;return std::ferror(file->native);}
int FileSystem::FFlush(addr_t stream) {
  if(!stream){std::vector<std::shared_ptr<Impl::Stream>> snapshot;{std::lock_guard lock(impl_->mutex);for(auto &entry:impl_->streams)snapshot.push_back(entry.second);}
    int result=0;for(auto &file:snapshot){std::lock_guard lock(file->io);if(file->native){file->io_started=true;if(std::fflush(file->native)){impl_->CrtError();result=-1;}}}return result;}
  auto file=impl_->GetStream(stream);if(!file)return -1;std::lock_guard lock(file->io);if(!file->native){impl_->Error(9);return -1;}
  file->io_started=true;int result=std::fflush(file->native);if(result)impl_->CrtError();return result;
}
addr_t FileSystem::Mmap(addr_t address, uint64_t length, int protection, int flags, int descriptor, int64_t offset) {
  std::unique_lock lock(impl_->mutex);
  constexpr int allowed = 3 | 0x10 | 0x20 | 0x4000 | 0x20000 | 0x100000;
  if (!length || length > SIZE_MAX - kPage || protection & ~7 || flags & ~allowed || (flags & 3) == 0 || (flags & 3) == 3 || offset < 0 || offset % kPage) { impl_->Error(22); return kMapFailed; }
  if (flags & linux_flags::map_fixed) { impl_->Error(95); return kMapFailed; }
  const bool no_replace = flags & linux_flags::map_fixed_no_replace;
  if (no_replace && (!address || address % kPage)) { impl_->Error(22); return kMapFailed; }
  uint64_t rounded = RoundPage(length);
  const auto generation=MappingGeneration();
  if (flags & linux_flags::map_anonymous) {
    if (offset || (flags & 3) == linux_flags::map_shared) { impl_->Error(95); return kMapFailed; }
    void *result = VirtualAlloc(reinterpret_cast<void *>(address), rounded, MEM_RESERVE | MEM_COMMIT, Protection(protection));
    if (!result && address && !no_replace) result = VirtualAlloc(nullptr, rounded, MEM_RESERVE | MEM_COMMIT, Protection(protection));
    if (!result) { if (no_replace && GetLastError() == ERROR_INVALID_ADDRESS) impl_->Error(17); else impl_->WinError(); return kMapFailed; }
    if (no_replace && reinterpret_cast<addr_t>(result) != address) { VirtualFree(result, 0, MEM_RELEASE); impl_->Error(17); return kMapFailed; }
    auto pointer = reinterpret_cast<addr_t>(result);recomp::InvalidateGuestMemory(pointer,rounded);impl_->mappings.emplace(pointer, Impl::Mapping{result, nullptr, rounded, false, false,generation}); return pointer;
  }
  auto found = impl_->descriptors.find(descriptor);
  if (found == impl_->descriptors.end() || (found->second->flags & 3) == 1) { impl_->Error(9); return kMapFailed; }
  auto file=found->second;lock.unlock();std::lock_guard io_lock(file->io);lock.lock();if(file->native<0){impl_->Error(9);return kMapFailed;}
  const bool private_file = (flags & 3) == linux_flags::map_private;
  if (!private_file && protection & 2 && !(file->flags & 3)) { impl_->Error(13); return kMapFailed; }
  auto native = reinterpret_cast<HANDLE>(_get_osfhandle(file->native));
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
  recomp::InvalidateGuestMemory(pointer,rounded);impl_->mappings.emplace(pointer, Impl::Mapping{view, object, rounded, true, private_file,generation}); return pointer;
}
int FileSystem::Munmap(addr_t address, uint64_t length) {
  std::lock_guard lock(impl_->mutex); auto found = impl_->mappings.find(address);
  if (!length || length > UINT64_MAX - kPage || address % kPage) { impl_->Error(22); return -1; }
  if (found == impl_->mappings.end()) { impl_->Error(22); return -1; }
  if (RoundPage(length) != found->second.rounded_length) { impl_->Error(95); return -1; }
  recomp::InvalidateGuestMemory(address,found->second.rounded_length);
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
std::optional<FileSystem::MappingInfo> FileSystem::MappingRegion(addr_t address,uint64_t length,bool writable)const{
  if(!length||length>UINT64_MAX-address)return {};
  std::lock_guard lock(impl_->mutex);auto found=impl_->mappings.upper_bound(address);
  if(found==impl_->mappings.begin())return {};--found;
  const auto base=found->first,size=found->second.rounded_length;
  if(address<base||address-base>size||length>size-(address-base)||size>UINT64_MAX-base)return {};
  for(auto cursor=address;cursor<address+length;){
    MEMORY_BASIC_INFORMATION info{};
    if(!VirtualQuery(reinterpret_cast<const void*>(cursor),&info,sizeof(info))||info.State!=MEM_COMMIT||(info.Protect&PAGE_GUARD))return {};
    const auto protection=info.Protect&0xff;
    const bool read=protection==PAGE_READONLY||protection==PAGE_READWRITE||protection==PAGE_WRITECOPY||
      protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY;
    const bool write=protection==PAGE_READWRITE||protection==PAGE_WRITECOPY||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY;
    if(!read||(writable&&!write))return {};
    const auto region=reinterpret_cast<addr_t>(info.BaseAddress);
    if(cursor<region||cursor-region>=info.RegionSize)return {};
    cursor+=std::min<uint64_t>(address+length-cursor,info.RegionSize-(cursor-region));
  }
  return MappingInfo{base,size,found->second.generation};
}
addr_t FileSystem::Marker(const std::string &name) const {
  if (name == "__sF") return const_cast<FileSystem *>(this)->StandardStreamsAddress();
  for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) if (name == names[i]) return impl_->marker_base + i * 8;
  throw std::invalid_argument("unsupported file-system import " + name);
}
int FileSystem::Madvise(addr_t address, uint64_t length, int advice) {
  std::lock_guard lock(impl_->mutex);
  // Only normal/default policy is implemented. Linux rejects unsupported
  // behavior before alignment/range validation, including for an empty range.
  if (advice != 0 || address % kPage || length > UINT64_MAX - (kPage - 1)) { impl_->Error(22); return -1; }
  const auto rounded = RoundPage(length);
  if (address > UINT64_MAX - rounded) { impl_->Error(22); return -1; }
  const auto end = address + rounded;
  for (auto cursor = address; cursor < end;) {
    uint64_t available = end - cursor;
    auto mapping = impl_->mappings.upper_bound(cursor);
    if (mapping != impl_->mappings.begin()) {
      --mapping;
      const auto offset = cursor - mapping->first;
      if (offset < mapping->second.rounded_length) available = std::min(available, mapping->second.rounded_length - offset);
    }
    // ELF data, guest stacks and CRT guest heap allocations also reside in
    // this shared address space. Verify actual committed pages even when a
    // different provider owns their allocation; reserved/free pages are holes.
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(reinterpret_cast<const void *>(cursor), &info, sizeof(info)) || info.State != MEM_COMMIT) { impl_->Error(12); return -1; }
    const auto region = reinterpret_cast<addr_t>(info.BaseAddress);
    if (cursor < region || cursor - region >= info.RegionSize) { impl_->Error(12); return -1; }
    cursor += std::min<uint64_t>(available, info.RegionSize - (cursor - region));
  }
  // Our VirtualAlloc/MapViewOfFile mappings already use ordinary Windows
  // paging/caching policy. MADV_NORMAL is advisory and changes no contents,
  // protection or lifetime. Never reset/decommit pages or invalidate stores.
  return 0;
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
  runtime.AddImport(Marker("mkdir"), recomp::MakeBridge<int32_t(const char *, uint32_t)>([this](auto path, auto mode) { return Mkdir(path, mode); }));
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
  runtime.AddImport(Marker("madvise"), recomp::MakeBridge<int32_t(addr_t, uint64_t, int32_t)>([this](auto address, auto length, auto advice) { return Madvise(address, length, advice); }));
  runtime.AddImport(Marker("setvbuf"), recomp::MakeBridge<int32_t(addr_t, addr_t, int32_t, uint64_t)>([this](auto stream, auto buffer, auto mode, auto size) { return FSetBuffer(stream, buffer, mode, size); }));
  runtime.AddImport(Marker("unlink"), recomp::MakeBridge<int32_t(const char*)>([this](auto path){return Unlink(path);}));
  runtime.AddImport(Marker("rmdir"), recomp::MakeBridge<int32_t(const char*)>([this](auto path){return Rmdir(path);}));
  runtime.AddImport(Marker("opendir"), recomp::MakeBridge<addr_t(const char*)>([this](auto path){return OpenDir(path);}));
  runtime.AddImport(Marker("readdir"), recomp::MakeBridge<addr_t(addr_t)>([this](auto directory){return ReadDir(directory);}));
  runtime.AddImport(Marker("closedir"), recomp::MakeBridge<int32_t(addr_t)>([this](auto directory){return CloseDir(directory);}));
  impl_->installed = true;
}
}  // namespace bunker::windows
