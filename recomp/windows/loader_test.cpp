#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <initializer_list>
#include <memory>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

#include "jni_host.h"
#include "module_registry.h"
#include "../whole/bridge.h"
#include "../fastaes/elfload.h"
#define kTraces kMainTraces
#define kInitializers kMainInitializers
#include "main_traces.h"
#undef kTraces
#undef kInitializers
#define kTraces kUnityTraces
#define kInitializers kUnityInitializers
#include "unity_traces.h"
#undef kTraces
#undef kInitializers
#include "synthetic_finalizers.h"

constexpr addr_t kMainBase = 0x40000000, kUnityBase = 0x50000000, kImports = 0x7ff300000000ULL;
const char *names[] = {"__cxa_finalize", "snprintf", "__stack_chk_fail", "dlclose", "dlsym", "dlerror", "dlopen", "malloc", "memcpy", "free", "__cxa_atexit"};
static bunker::windows::ModuleRegistry *registry;
static void *resolve(const char *name) {
  if (!std::strcmp(name, "dlopen") || !std::strcmp(name, "dlsym") || !std::strcmp(name, "dlclose") || !std::strcmp(name, "dlerror"))
    return reinterpret_cast<void *>(registry->Marker(name));
  for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
    if (!std::strcmp(name, names[i])) return reinterpret_cast<void *>(kImports + i * 8);
  return nullptr;
}

int main(int argc, char **argv) {
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
  _set_abort_behavior(0, 3);
#endif
  const std::string scenario = argc > 1 ? argv[1] : "success";
  if (scenario != "success" && scenario != "missing-module" && scenario != "missing-symbol" && scenario != "bad-version") return 2;
  recomp::Runtime runtime;
  runtime.AddTraces(kMainTraces, sizeof(kMainTraces) / sizeof(kMainTraces[0]));
  runtime.AddTraces(kUnityTraces, sizeof(kUnityTraces) / sizeof(kUnityTraces[0]));
  bunker::jni::Host host([](addr_t address) {
    for (auto &trace : kMainTraces) if (trace.address == address) return true;
    for (auto &trace : kUnityTraces) if (trace.address == address) return true;
    return false;
  });
  host.DefineClass("com/unity3d/player/NativeLoader", {{"load", "(Ljava/lang/String;)Z", true, true}, {"unload", "()Z", true, true}});
  host.Install(runtime);
  struct Frame { alignas(16) uint8_t stack[1 << 20]; State state{}; };
  alignas(16) uint8_t tls[256]{};
  std::function<uint64_t(addr_t, std::initializer_list<addr_t>)> run;
  run = [&](addr_t entry, std::initializer_list<addr_t> args) {
    auto frame = std::make_unique<Frame>();
    auto &s = frame->state;
    Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2, &GPR::x3, &GPR::x4, &GPR::x5, &GPR::x6, &GPR::x7};
    size_t i = 0; for (auto argument : args) (s.gpr.*registers[i++]).qword = argument;
    s.gpr.pc.qword = entry; s.gpr.x30.qword = 0xfeedffff;
    s.gpr.sp.qword = reinterpret_cast<addr_t>(frame->stack + sizeof(frame->stack));
    s.sr.tpidr_el0.qword = reinterpret_cast<addr_t>(tls);
    runtime.Run(s, entry);
    if (s.gpr.pc.qword != 0xfeedffff || s.gpr.sp.qword != reinterpret_cast<addr_t>(frame->stack + sizeof(frame->stack))) std::abort();
    return s.gpr.x0.qword;
  };
  bunker::windows::ModuleRegistry modules([&](addr_t entry) { run(entry, {}); });
  registry = &modules; modules.Install(runtime);
  runtime.AddImport(kImports + 7 * 8, recomp::MakeBridge<void *(uint64_t)>([](uint64_t size) { return std::malloc(size); }));
  runtime.AddImport(kImports + 8 * 8, recomp::MakeBridge<void *(void *, const void *, uint64_t)>([](void *dst, const void *src, uint64_t length) { return std::memcpy(dst, src, length); }));
  runtime.AddImport(kImports + 9 * 8, recomp::MakeBridge<void(void *)>([](void *pointer) { std::free(pointer); }));
  runtime.AddImport(kImports + 1 * 8, [](State &s) {
    auto *out = reinterpret_cast<char *>(s.gpr.x0.qword);
    auto capacity = static_cast<size_t>(s.gpr.x1.qword);
    auto *format = reinterpret_cast<const char *>(s.gpr.x2.qword);
    auto *a = reinterpret_cast<const char *>(s.gpr.x3.qword), *b = reinterpret_cast<const char *>(s.gpr.x4.qword);
    if (std::strcmp(format, "%s/%s") && std::strcmp(format, "Unable to load library: %s [%s]")) {
      std::fprintf(stderr, "unimplemented libmain snprintf format: %s\n", format); std::abort();
    }
    s.gpr.x0.qword = static_cast<uint32_t>(std::snprintf(out, capacity, format, a, b));
  });
  for (size_t i : {0U, 2U, 10U}) runtime.AddImport(kImports + i * 8, [i](State &) { std::fprintf(stderr, "unimplemented loader import %s\n", names[i]); std::abort(); });
  elf_image main_image, unity_image;
  if (elf_load(LIBMAIN_IMAGE, kMainBase, resolve, &main_image) ||
      elf_load(SYNTHETIC_UNITY_IMAGE, kUnityBase, [](const char *) -> void * { return nullptr; }, &unity_image)) return 1;
  auto counts = reinterpret_cast<addr_t>(elf_symbol(&unity_image, "synthetic_counts"));
  auto version = reinterpret_cast<uint32_t *>(elf_symbol(&unity_image, "synthetic_version"));
  if (!counts || !version) return 1;
  if (scenario != "missing-module") {
    bunker::windows::Module module;
    module.name = "libunity.so"; module.aliases = {"/synthetic/libunity.so"};
    for (const char *name : {"JNI_OnLoad", "JNI_OnUnload", "synthetic_counts"})
      if (scenario != "missing-symbol" || std::strcmp(name, "JNI_OnLoad")) module.exports[name] = reinterpret_cast<addr_t>(elf_symbol(&unity_image, name));
    module.initializers.assign(kUnityInitializers, kUnityInitializers + sizeof(kUnityInitializers) / sizeof(kUnityInitializers[0]));
    module.finalizers.assign(kUnityFinalizers, kUnityFinalizers + sizeof(kUnityFinalizers) / sizeof(kUnityFinalizers[0]));
    auto snapshot = std::make_shared<std::vector<uint8_t>>(unity_image.base, unity_image.base + unity_image.span);
    module.reset_image = [snapshot, &unity_image, version, &scenario] {
      std::memcpy(unity_image.base, snapshot->data(), snapshot->size());
      if (scenario == "bad-version") *version = 0x10008;
    };
    modules.Add(std::move(module));
  }
  for (auto entry : kMainInitializers) run(entry, {});
  auto main_onload = reinterpret_cast<addr_t>(elf_symbol(&main_image, "JNI_OnLoad"));
  if (run(main_onload, {host.VmAddress(), 0}) != 0x10006) return 1;
  auto load = host.NativeEntry("com/unity3d/player/NativeLoader", "load", "(Ljava/lang/String;)Z");
  auto unload = host.NativeEntry("com/unity3d/player/NativeLoader", "unload", "()Z");
  auto path = host.NewString(u"/synthetic");
  if (run(load, {host.EnvAddress(), 0, path}) != 1) return 1;
  auto expected_loaded = scenario == "missing-symbol" ? 1ULL : 0x10001ULL;
  if (run(counts, {}) != expected_loaded || modules.ReferenceCount("libunity.so") != 1) return 1;
  if (scenario == "missing-symbol") {
    auto error = modules.Error();
    if (!error || !std::strstr(reinterpret_cast<const char *>(error), "JNI_OnLoad")) return 1;
  }
  if (run(load, {host.EnvAddress(), 0, path}) != 1 || run(counts, {}) != expected_loaded || modules.ReferenceCount("libunity.so") != 1) return 1;
  if (run(unload, {host.EnvAddress(), 0}) != 1 || modules.ReferenceCount("libunity.so") != 0) return 1;
  auto expected_unloaded = expected_loaded | (1ULL << 32) | (1ULL << 48);
  if (run(counts, {}) != expected_unloaded || run(unload, {host.EnvAddress(), 0}) != 1 || !host.PendingException().empty()) return 1;
  std::printf("Real libmain NativeLoader.load/unload passed with explicitly synthetic translated Unity fixture (%s): constructors, cached load, JNI_OnUnload/finalizers; JNI_OnLoad=%s.\n", scenario.c_str(), scenario == "missing-symbol" ? "optional and absent" : "called with working GetEnv");
}
