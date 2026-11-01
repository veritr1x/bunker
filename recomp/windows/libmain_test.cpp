#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifndef LIBMAIN_IMAGE
#error LIBMAIN_IMAGE must name the original libmain.so data image
#endif
constexpr addr_t kBase = 0x40000000, kImport = 0x7ff300000000ULL;
const char *imports[] = {"__cxa_finalize", "snprintf", "__stack_chk_fail", "dlclose", "dlsym", "dlerror", "dlopen", "malloc", "memcpy", "free", "__cxa_atexit"};
static void *resolve(const char *name) {
  for (size_t i = 0; i < sizeof(imports) / sizeof(imports[0]); ++i)
    if (!std::strcmp(name, imports[i])) return reinterpret_cast<void *>(kImport + i * 8);
  return nullptr;
}
int main() {
  elf_image image;
  if (elf_load(LIBMAIN_IMAGE, kBase, resolve, &image)) return 1;
  recomp::Runtime runtime;
  runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
  bunker::jni::Host host([](addr_t entry) {
    return std::any_of(std::begin(kTraces), std::end(kTraces), [entry](const auto &trace) { return trace.address == entry; });
  });
  host.DefineClass("com/unity3d/player/NativeLoader", {{"load", "(Ljava/lang/String;)Z", true, true}, {"unload", "()Z", true, true}});
  host.Install(runtime);
  for (size_t i = 0; i < sizeof(imports) / sizeof(imports[0]); ++i) {
    runtime.AddImport(kImport + i * 8, [i](State &) {
      std::fprintf(stderr, "libmain JNI_OnLoad unexpectedly called %s\n", imports[i]); std::abort();
    });
  }
  alignas(16) static uint8_t stack[1 << 20];
  auto run = [&](addr_t entry, addr_t x0) {
    State state{}; state.gpr.x0.qword = x0; state.gpr.x30.qword = 0xfeedffff;
    state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + sizeof(stack)); state.gpr.pc.qword = entry;
    runtime.Run(state, entry);
    if (state.gpr.pc.qword != 0xfeedffff || state.gpr.sp.qword != reinterpret_cast<addr_t>(stack + sizeof(stack))) std::abort();
    return state.gpr.x0.dword;
  };
  for (auto initializer : kInitializers) run(initializer, 0);
  auto entry = reinterpret_cast<addr_t>(elf_symbol(&image, "JNI_OnLoad"));
  auto result = run(entry, host.VmAddress());
  auto load = host.NativeEntry("com/unity3d/player/NativeLoader", "load", "(Ljava/lang/String;)Z");
  auto unload = host.NativeEntry("com/unity3d/player/NativeLoader", "unload", "()Z");
  if (result != bunker::jni::kVersion16 || !host.PendingException().empty() ||
      host.NativeCount("com/unity3d/player/NativeLoader") != 2 || load != kBase + 0x9ac || unload != kBase + 0xb7c) {
    std::fprintf(stderr, "JNI_OnLoad failed: result=%#x load=%#llx unload=%#llx exception=%s\n", result,
        static_cast<unsigned long long>(load), static_cast<unsigned long long>(unload), host.PendingException().c_str());
    return 1;
  }
  std::printf("Real libmain.so JNI_OnLoad passed on Windows: JNI 1.6; NativeLoader.load @ %#llx, unload @ %#llx registered.\n",
      static_cast<unsigned long long>(load), static_cast<unsigned long long>(unload));
}
