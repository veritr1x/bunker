#pragma once
#include <functional>
#include <mutex>
#include <string>
#include <string_view>
#include "../whole/runtime.h"

namespace bunker::windows {
// All text remains byte strings. FILE handles belong to FileSystem; callers can
// inject its FWrite adapter without exposing native CRT FILE pointers to guests.
class Logging {
 public:
  using Writer = std::function<bool(std::string_view)>;
  using LogWriter = std::function<bool(int, std::string_view, std::string_view)>;
  using StreamWriter = std::function<uint64_t(addr_t, std::string_view)>;
  explicit Logging(addr_t marker_base = 0x7ff800000000ULL);
  addr_t Marker(const std::string &name) const;
  void Install(recomp::Runtime &runtime);
  // Callbacks execute without provider locks and may run concurrently. A sink
  // that shares mutable host state must provide its own synchronization.
  void SetOutput(Writer writer) { std::lock_guard lock(mutex_); output_ = std::move(writer); }
  void SetLog(LogWriter writer) { std::lock_guard lock(mutex_); log_ = std::move(writer); }
  void SetStream(StreamWriter writer) { std::lock_guard lock(mutex_); stream_ = std::move(writer); }
  void SetAllocator(std::function<void *(uint64_t)> allocator) { std::lock_guard lock(mutex_); allocator_ = std::move(allocator); }
  void SetErrorSink(std::function<void(int)> sink) { std::lock_guard lock(mutex_); error_sink_ = std::move(sink); }
  int Error() const;
 private:
  void Invoke(size_t index, State &state) noexcept;
  void Fail(int error) noexcept;
  Writer output_;
  LogWriter log_;
  StreamWriter stream_;
  std::function<void *(uint64_t)> allocator_;
  std::function<void(int)> error_sink_;
  addr_t marker_base_;
  std::string ident_;
  std::recursive_mutex mutex_;
  bool installed_ = false;
};
}  // namespace bunker::windows
