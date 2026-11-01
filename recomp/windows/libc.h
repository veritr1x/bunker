#pragma once
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include "../whole/runtime.h"

namespace bunker::windows {
// C-locale, Android LP64 scalar libc. Platform I/O, locale objects, wide strings,
// pthreads and stdio are deliberately provided elsewhere or remain unresolved.
// Keep this object alive until its imports and guest callbacks are finished.
class LibC {
 public:
  using Runner = std::function<uint64_t(addr_t, const std::vector<addr_t> &)>;
  explicit LibC(Runner runner = {}, addr_t marker_base = 0x7ffb00000000ULL);
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
  int RegisterExit(addr_t callback, addr_t argument, addr_t dso, bool plain = false);
  void Finalize(addr_t dso = 0);
 private:
  struct Aligned { void *base; uint64_t size, alignment; };
  struct Exit { addr_t callback, argument, dso; bool plain, called; };
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
  std::vector<std::string> environment_text_;
  std::vector<char *> environment_pointers_;
  char **environment_slot_ = nullptr;
  std::string abort_message_;
  addr_t marker_base_;
  bool installed_ = false;
};
}  // namespace bunker::windows
