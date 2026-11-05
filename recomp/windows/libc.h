#pragma once
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include "../whole/runtime.h"

namespace bunker::windows {
// Android LP64 scalar libc with Bionic C/C.UTF-8 locale objects. Platform I/O, wide strings,
// pthreads and stdio are deliberately provided elsewhere or remain unresolved.
// Keep this object alive until its imports and guest callbacks are finished.
class LibC {
 public:
  using Runner = std::function<uint64_t(addr_t, const std::vector<addr_t> &)>;
  explicit LibC(Runner runner = {}, addr_t marker_base = 0x7ffb00000000ULL);
  ~LibC();
  addr_t Marker(const std::string &) const;
  void Install(recomp::Runtime &);
  void SetErrorSink(std::function<void(int)> sink) { error_sink_ = std::move(sink); }
  int Error() const;
  void SetEnvironment(std::map<std::string, std::string> values);
  char *Getenv(const char *name);
  int Setenv(const char *name, const char *value, int overwrite);
  int Unsetenv(const char *name);
  void *Malloc(uint64_t size);
  void *Calloc(uint64_t count, uint64_t size);
  void *Realloc(void *, uint64_t size);
  void Free(void *);
  void *Memalign(uint64_t alignment, uint64_t size);
  int PosixMemalign(void **, uint64_t alignment, uint64_t size);
  uint64_t ParseInteger(const char *, char **, int base, bool is_signed);
  // Exact Android 13 %llu profile: one unsigned64 output, no general scanf claims.
  int32_t ScanUnsignedLongLong(const char *input, const char *format, uint64_t *output);
  // Exact original URL scanset/character profiles plus the unchanged %llu API.
  // Up to four AArch64 GP output pointers; no foreign native va_list cast.
  int32_t Scan(const char *input,const char *format,addr_t output0,addr_t output1,addr_t output2,addr_t output3);
  // Comparator is an original guest address dispatched through the owned Runner.
  void *BinarySearch(const void *key, const void *base, uint64_t count, uint64_t size, addr_t comparator);
  int RegisterExit(addr_t callback, addr_t argument, addr_t dso, bool plain = false);
  void Finalize(addr_t dso = 0);
  addr_t NewLocale(int32_t mask, const char *name, addr_t base);
  void FreeLocale(addr_t locale);
  addr_t UseLocale(addr_t locale);
  char *SetLocale(int32_t category, const char *name);
  uint64_t LocaleMbCurMax();
  int64_t ProcessClock();
  int64_t Sysconf(int32_t name);
  int32_t GetTimeOfDay(addr_t timeval, addr_t timezone);
  int32_t ProcessId() const;
  // Current-process /proc/self/exe or /proc/<actual-pid>/exe only. Returns the
  // real native image path as UTF-8 (Windows separators rendered as '/'). This
  // metadata query creates no Android VFS mount or permission to reopen it.
  int64_t ReadLink(const char *path,void *output,uint64_t size);
 private:
  struct Aligned { void *base; uint64_t size, alignment; };
  struct Exit { addr_t callback, argument, dso; bool plain, called; };
  struct Locale { uint64_t *storage; bool active; };
  void *AlignedAllocate(uint64_t alignment, uint64_t size, bool set_errno);
  void BuildEnvironment();
  void Fail(int error) noexcept;
  [[noreturn]] void Fatal(const char *) noexcept;
  template <typename Signature, typename F> void Add(recomp::Runtime &, const char *, F);
  Runner runner_;
  std::function<void(int)> error_sink_;
  std::recursive_mutex mutex_;
  std::map<void *, Aligned> aligned_;
  std::vector<Exit> exits_;
  std::map<std::string, std::string> environment_;
  std::vector<char *> environment_strings_;
  char **environment_array_ = nullptr;
  char **environment_slot_ = nullptr;
  std::string abort_message_;
  std::map<addr_t, Locale> locales_;
  uint64_t locale_owner_;
  addr_t marker_base_;
  bool global_locale_is_utf8_ = true;  // Protected by mutex_; one guest-process locale.
  bool installed_ = false;
};
}  // namespace bunker::windows
