#include "module_registry.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>

int main() {
  using namespace bunker::windows;
  unsigned checks = 0;
  auto require = [&](bool value, const char *message) { if (!value) throw std::runtime_error(message); ++checks; };
  std::vector<addr_t> calls;
  unsigned resets = 0;
  ModuleRegistry registry([&](addr_t address) { calls.push_back(address); });
  registry.Add({"libtest.so", {"/guest/lib/libtest.so"}, {{"exported", 0x123400}, {"absolute_zero", 0}}, {0x100, 0x200}, {0x300, 0x400}, [&] { ++resets; }});
  auto handle = registry.Open("/guest/lib/libtest.so", 1);
  require(handle && calls == std::vector<addr_t>{0x100, 0x200} && resets == 1, "constructors execute in order");
  require(registry.Symbol(handle, "exported") == 0x123400, "guest export address");
  require(registry.Symbol(handle, "absolute_zero") == 0 && !registry.Error(), "valid zero-valued ELF absolute export has no dlerror");
  require(registry.Open("libtest.so", 2) == handle && registry.ReferenceCount("libtest.so") == 2 && calls.size() == 2, "dlopen reference count");
  require(registry.Close(handle) == 0 && registry.ReferenceCount("libtest.so") == 1 && calls.size() == 2, "nonfinal dlclose");
  require(registry.Close(handle) == 0 && calls == std::vector<addr_t>{0x100, 0x200, 0x400, 0x300}, "finalizers execute in reverse order");
  require(!registry.Symbol(handle, "exported") && registry.Error(), "stale handle rejected");
  require(!registry.Error(), "dlerror clears pending error");
  auto reopened = registry.Open("libtest.so", 1);
  require(reopened && reopened != handle && resets == 2 && registry.ReferenceCount("libtest.so") == 1, "reopen resets image and handle generation");
  require(!registry.Open("/missing/libtest.so", 1), "unregistered path unavailable");
  auto error = registry.Error(); require(error && std::strstr(reinterpret_cast<const char *>(error), "unavailable"), "missing-path error text");
  require(!registry.Symbol(reopened, "missing"), "missing export unavailable");
  require(registry.Error() && !registry.Error(), "missing-symbol dlerror lifecycle");
  require(registry.Close(0xbad) == -1 && registry.Error(), "invalid dlclose error");
  require(!registry.Open(nullptr, 1) && registry.Error(), "no default native process fallback");
  require(!registry.Open("libtest.so", 0x10000) && registry.Error(), "unsupported flags rejected");
  registry.Add({"one-shot.so", {}, {}, {}, {}, {}});
  auto one = registry.Open("one-shot.so", 1);
  require(one && registry.Close(one) == 0 && !registry.Open("one-shot.so", 1) && registry.Error(), "reopen without reset rejected");
  ModuleRegistry bad([](addr_t) { throw std::runtime_error("synthetic constructor failure"); });
  bad.Add({"bad.so", {}, {}, {1}, {}, [] {}});
  require(!bad.Open("bad.so", 1) && bad.ReferenceCount("bad.so") == 0 && bad.Error(), "failed initialization does not publish a live module");
  std::thread worker([&] {
    require(!registry.Error(), "dlerror thread isolation");
    registry.Open("worker-missing.so", 1);
    require(registry.Error() != 0, "worker dlerror");
  });
  worker.join(); require(!registry.Error(), "worker errors do not leak to main thread");
  recomp::Runtime runtime;
  registry.Install(runtime);
  State state{}; state.gpr.x0.qword = reinterpret_cast<addr_t>("libtest.so"); state.gpr.x1.qword = 1; state.gpr.x30.qword = 0xfeedffff;
  runtime.Run(state, registry.Marker("dlopen"));
  require(state.gpr.x0.qword == reopened && state.gpr.pc.qword == 0xfeedffff, "typed libdl marker bridge");
  std::printf("Translated module registry: %u checks passed.\n", checks);
}
