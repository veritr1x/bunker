#include "logging.h"
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <thread>

namespace {
struct Watchdog {
  std::mutex lock;
  std::condition_variable condition;
  bool done = false;
  std::thread worker;
  Watchdog() : worker([this] {
    std::unique_lock guard(lock);
    if (!condition.wait_for(guard, std::chrono::seconds(10), [this] { return done; })) {
      std::fprintf(stderr, "logging callback test: provider lock deadlock\n");
      std::_Exit(90);
    }
  }) {}
  ~Watchdog() {
    { std::lock_guard guard(lock); done = true; }
    condition.notify_one(); worker.join();
  }
};
unsigned checks;
void Check(bool value, const char *message) {
  ++checks;
  if (!value) throw std::runtime_error(message);
}
}  // namespace

int main() {
  Watchdog watchdog;
  try {
    bunker::windows::Logging logging;
    recomp::Runtime runtime;
    logging.Install(runtime);
    auto pointer = [](auto p) { return reinterpret_cast<uint64_t>(p); };
    auto call = [&](const char *name, std::initializer_list<uint64_t> arguments) {
      State state{};
      Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2, &GPR::x3, &GPR::x4, &GPR::x5};
      size_t index = 0;
      for (auto argument : arguments) (state.gpr.*registers[index++]).qword = argument;
      state.gpr.x30.qword = 0xfeedffff;
      runtime.Run(state, logging.Marker(name));
      return static_cast<int32_t>(state.gpr.x0.qword);
    };
    auto join_formatter = [&] {
      bool complete = false;
      std::thread worker([&] {
        char buffer[16];
        complete = call("snprintf", {pointer(buffer), sizeof(buffer), pointer("%d"), 42}) == 2 && !std::strcmp(buffer, "42");
      });
      worker.join();
      if (!complete) throw std::runtime_error("callback worker formatter failed");
    };
    logging.SetOutput([&](std::string_view) { join_formatter(); return true; });
    Check(call("printf", {pointer("output")}) == 6, "output callback can join a logging worker");
    logging.SetLog([&](int, std::string_view, std::string_view) { join_formatter(); return true; });
    Check(call("__android_log_write", {4, pointer("tag"), pointer("record")}) == 1, "log callback can join a logging worker");
    logging.SetStream([&](addr_t, std::string_view text) { join_formatter(); return text.size(); });
    Check(call("fprintf", {0x1234, pointer("stream")}) == 6, "stream callback can join a logging worker");
    bool error_callback = false;
    logging.SetErrorSink([&](int) { join_formatter(); error_callback = true; });
    char buffer[16];
    Check(call("sprintf", {pointer(buffer), pointer("%n"), 0}) == -1 && error_callback,
          "error callback can join a logging worker");
    logging.SetAllocator([&](uint64_t size) { join_formatter(); return std::malloc(static_cast<size_t>(size)); });
    char *allocated = nullptr;
    Check(call("asprintf", {pointer(&allocated), pointer("alloc")}) == 5 && allocated && !std::strcmp(allocated, "alloc"),
          "allocator callback can join a logging worker");
    std::free(allocated);
    unsigned next_output = 0;
    logging.SetOutput([&](std::string_view) {
      std::thread worker([&] { logging.SetOutput([&](std::string_view) { ++next_output; return true; }); });
      worker.join(); return true;
    });
    Check(call("printf", {pointer("first")}) == 5 && call("printf", {pointer("next")}) == 4 && next_output == 1,
          "callback can join a worker replacing the sink");
    logging.SetOutput([](std::string_view) -> bool { throw std::runtime_error("sink failure"); });
    Check(call("printf", {pointer("throw")}) == -1, "callback exception is reported");
    logging.SetOutput([](std::string_view) { return true; });
    Check(call("printf", {pointer("recovered")}) == 9, "callback exception leaves the provider usable");
    std::printf("Logging callbacks: %u checks passed (worker joins, synchronized setters, exceptions).\n", checks);
    return 0;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "logging callback test: %s\n", error.what());
    return 1;
  }
}
