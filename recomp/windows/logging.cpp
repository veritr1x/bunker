#include "logging.h"
#include "../whole/format.h"
#include "../whole/guest_memory.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#include <stdexcept>

namespace bunker::windows {
namespace {
const char *const names[] = {"__android_log_print", "__android_log_vprint", "__android_log_write",
    "__android_log_assert", "snprintf", "vsnprintf", "sprintf", "vsprintf", "printf", "vprintf",
    "puts", "syslog", "openlog", "closelog", "asprintf", "vasprintf", "fprintf", "vfprintf"};
thread_local int last_error;
bool Write(FILE *file, std::string_view text) {
  return std::fwrite(text.data(), 1, text.size(), file) == text.size();
}
std::string Text(const char *value) { return value ? recomp::ReadGuestString(reinterpret_cast<addr_t>(value)) : ""; }
}
Logging::Logging(addr_t base) : marker_base_(base) {
  if ((base & 7) || base > UINT64_MAX - sizeof(names) / sizeof(*names) * 8)
    throw std::invalid_argument("invalid logging marker base");
  allocator_ = [](uint64_t size) { return std::malloc(static_cast<size_t>(size)); };
  output_ = [](std::string_view text) { return Write(stdout, text); };
  log_ = [](int, std::string_view tag, std::string_view text) {
    return Write(stderr, tag) && Write(stderr, ": ") && Write(stderr, text) && Write(stderr, "\n");
  };
}
int Logging::Error() const { return last_error; }
void Logging::Fail(int error) noexcept {
  last_error = error;
  if (error_sink_) { try { error_sink_(error); } catch (...) {} }
}
addr_t Logging::Marker(const std::string &name) const {
  for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i)
    if (name == names[i]) return marker_base_ + i * 8;
  throw std::invalid_argument("unsupported logging import: " + name);
}
void Logging::Install(recomp::Runtime &runtime) {
  if (installed_) throw std::logic_error("logging provider already installed");
  for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i)
    runtime.AddImport(marker_base_ + i * 8, [this, i](State &s) { Invoke(i, s); });
  installed_ = true;
}
void Logging::Invoke(size_t index, State &state) noexcept {
  int result = -1;
  const bool fatal = index == 3;
  bool fatal_reported = false;
  try {
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    recomp::bridge_detail::Arguments args(state);
    auto formatted = [&](bool va) {
      const char *format = args.Read<const char *>();
      if (va) { recomp::VaArguments list(args.Read<const void *>()); return recomp::Format(format, list); }
      return recomp::Format(format, args);
    };
    if (index <= 2) {
      int priority = args.Read<int32_t>();
      const char *tag = args.Read<const char *>();
      std::string text = index == 2 ? Text(args.Read<const char *>()) : formatted(index == 1);
      if (!log_ || !log_(priority, Text(tag), text)) { Fail(1); result = -1; }
      else result = 1;  // liblog's documented success value, not the text length.
    } else if (fatal) {
      const char *condition = args.Read<const char *>();
      const char *tag = args.Read<const char *>();
      const char *format = args.Read<const char *>();
      std::string text = format ? recomp::Format(format, args) :
          (condition ? "Assertion failed: " + Text(condition) : "Unspecified assertion failed");
      if (log_) log_(7, Text(tag), text);
      Write(stderr, text); Write(stderr, "\n");
      fatal_reported = true;
    } else if (index >= 4 && index <= 7) {
      char *destination = args.Read<char *>();
      uint64_t capacity = index <= 5 ? args.Read<uint64_t>() : UINT64_MAX;
      std::string text = formatted(index == 5 || index == 7);
      if (capacity && !destination) throw std::invalid_argument("null formatted destination");
      if (capacity) {
        size_t count = static_cast<size_t>(std::min<uint64_t>(text.size(), capacity - 1));
        recomp::WithGuestMemoryWrite(reinterpret_cast<addr_t>(destination), count + 1, [&] {
          std::memcpy(destination, text.data(), count); destination[count] = 0;
        });
      }
      result = static_cast<int>(text.size());
    } else if (index == 8 || index == 9 || index == 10) {
      std::string text;
      if (index == 10) { auto value = args.Read<const char *>(); if (!value) throw std::invalid_argument("null puts string"); text = Text(value); text += '\n'; }
      else text = formatted(index == 9);
      if (!output_ || !output_(text)) Fail(5);
      else result = index == 10 ? 0 : static_cast<int>(text.size());
    } else if (index == 11) {
      int priority = args.Read<int32_t>();
      auto text = formatted(false);
      if (!log_ || !log_(priority, ident_, text)) Fail(5);
      else result = 0;
    } else if (index == 12) {
      ident_ = Text(args.Read<const char *>()); result = 0;
    } else if (index == 13) { ident_.clear(); result = 0;
    } else if (index == 14 || index == 15) {
      char **destination = args.Read<char **>();
      if (!destination) throw std::invalid_argument("null asprintf result pointer");
      char *empty = nullptr;
      recomp::WriteGuestMemory(reinterpret_cast<addr_t>(destination), &empty, sizeof(empty));
      auto text = formatted(index == 15);
      auto buffer = static_cast<char *>(allocator_ ? allocator_(text.size() + 1) : nullptr);
      if (!buffer) throw std::bad_alloc();
      std::memcpy(buffer, text.data(), text.size()); buffer[text.size()] = 0;
      recomp::WriteGuestMemory(reinterpret_cast<addr_t>(destination), &buffer, sizeof(buffer));
      result = static_cast<int>(text.size());
    } else {
      addr_t stream = args.Read<addr_t>();
      auto text = formatted(index == 17);
      if (!stream_) { Fail(38); }  // ENOSYS: never reinterpret an opaque guest FILE.
      else if (stream_(stream, text) != text.size()) Fail(5);
      else result = static_cast<int>(text.size());
    }
  } catch (const std::bad_alloc &) { Fail(12);
  } catch (const std::length_error &) { Fail(75);
  } catch (...) { Fail(22); }
  recomp::bridge_detail::Return(state, static_cast<int32_t>(result));
  if (fatal) {
    if (!fatal_reported) Write(stderr, "Fatal Android assertion (format or logging failed)\n");
    std::abort();  // A guest assertion must never return successfully.
  }
}
}  // namespace bunker::windows
