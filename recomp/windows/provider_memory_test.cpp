#include "jni_host.h"
#include "logging.h"
#include "../whole/guest_memory.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

namespace {
unsigned checks;
void Check(bool value, const char *message) {
  ++checks;
  if (!value) throw std::runtime_error(message);
}
thread_local const std::function<void(State &)> *body;
Memory *Entry(State &state, addr_t, Memory *memory) {
  (*body)(state);
  state.gpr.pc.qword = state.gpr.x30.qword;
  return memory;
}
void Run(recomp::Runtime &runtime, const std::function<void(State &)> &callback) {
  body = &callback;
  State state{};
  state.gpr.x30.qword = 0xfeedffff;
  runtime.Run(state, 0x6000);
  body = nullptr;
}
uint32_t Reservation(recomp::Runtime &runtime, addr_t address, const std::function<void()> &write) {
  uint32_t result = 9;
  Run(runtime, [&](State &state) {
    auto original = __remill_aarch64_load_exclusive(state, address, 8, 0);
    std::thread worker(write);
    worker.join();
    result = __remill_aarch64_store_exclusive(state, address, original, 8, 0);
  });
  return result;
}
}  // namespace

int main() {
  try {
    recomp::Runtime runtime;
    const recomp::Trace trace = {0x6000, Entry};
    runtime.AddTraces(&trace, 1);
    bunker::windows::Logging logging;
    logging.Install(runtime);
    auto print = [&](char *buffer, uint64_t size, const char *format, addr_t a = 0, addr_t b = 0) {
      State state{};
      state.gpr.x0.qword = reinterpret_cast<addr_t>(buffer);
      state.gpr.x1.qword = size;
      state.gpr.x2.qword = reinterpret_cast<addr_t>(format);
      state.gpr.x3.qword = a; state.gpr.x4.qword = b;
      state.gpr.x30.qword = 0xfeedffff;
      runtime.Run(state, logging.Marker("snprintf"));
      return static_cast<int32_t>(state.gpr.x0.qword);
    };
    alignas(64) char buffer[128]{};
    std::memcpy(buffer, "abc", 4);
    Check(Reservation(runtime, reinterpret_cast<addr_t>(buffer), [&] {
      if (print(buffer, 8, "abc") != 3) throw std::runtime_error("snprintf worker failed");
    }) == 1, "same-value snprintf from another thread invalidates the reservation");
    Check(Reservation(runtime, reinterpret_cast<addr_t>(buffer), [&] {
      if (print(buffer, 0, "abc") != 3) throw std::runtime_error("size-zero worker failed");
    }) == 0, "size-zero formatting preserves another thread's reservation");

    bunker::jni::Host java([](addr_t) { return false; });
    alignas(64) addr_t vm_output = java.VmAddress();
    Check(Reservation(runtime, reinterpret_cast<addr_t>(&vm_output), [&] {
      addr_t env = 0;
      State attach{};
      attach.gpr.x0.qword = java.VmAddress(); attach.gpr.x1.qword = reinterpret_cast<addr_t>(&env);
      java.InvokeVm(4, attach);
      if (attach.gpr.x0.dword || !env) throw std::runtime_error("JNI worker attachment failed");
      State get{};
      get.gpr.x0.qword = env; get.gpr.x1.qword = reinterpret_cast<addr_t>(&vm_output);
      java.InvokeEnv(219, get);
      if (get.gpr.x0.dword) throw std::runtime_error("JNI GetJavaVM failed");
    }) == 1, "same-value JNI GetJavaVM output invalidates another thread's reservation");

#ifdef _WIN32
    SYSTEM_INFO info; GetSystemInfo(&info); const size_t page = info.dwPageSize;
    auto area = static_cast<char *>(VirtualAlloc(nullptr, page * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!area) throw std::runtime_error("guard allocation failed");
    DWORD previous;
    if (!VirtualProtect(area + page, page, PAGE_NOACCESS, &previous)) throw std::runtime_error("guard protection failed");
#else
    const size_t page = static_cast<size_t>(sysconf(_SC_PAGESIZE));
    auto area = static_cast<char *>(mmap(nullptr, page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
    if (area == MAP_FAILED || mprotect(area + page, page, PROT_NONE)) throw std::runtime_error("guard allocation failed");
#endif
    std::memcpy(area + page - 3, "abc", 3);
    Check(print(buffer, sizeof(buffer), "%.*s", 3, reinterpret_cast<addr_t>(area + page - 3)) == 3 &&
          !std::strcmp(buffer, "abc"), "precision-bounded string snapshot stops before an inaccessible page");
    Check(print(buffer, sizeof(buffer), "%.0s", 1) == 0 && !buffer[0], "zero precision never reads the string pointer");
#ifdef _WIN32
    VirtualFree(area, 0, MEM_RELEASE);
#else
    munmap(area, page * 2);
#endif
    unsigned allocations = 0;
    logging.SetAllocator([&](uint64_t size) { ++allocations; return std::malloc(static_cast<size_t>(size)); });
    char *allocated = nullptr;
    State output{};
    output.gpr.x0.qword = reinterpret_cast<addr_t>(&allocated);
    output.gpr.x1.qword = reinterpret_cast<addr_t>("allocated");
    output.gpr.x30.qword = 0xfeedffff;
    runtime.Run(output, logging.Marker("asprintf"));
    Check(allocations == 1 && allocated && !std::strcmp(allocated, "allocated"), "asprintf uses its configured allocation owner");
    std::free(allocated);
    std::printf("Tracked JNI/logging memory: %u checks passed (cross-thread same-value writes and guarded string snapshots).\n", checks);
    return 0;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "provider memory test: %s\n", error.what());
    return 1;
  }
}
