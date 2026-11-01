#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>

#include "runtime.h"
#include "elfload.h"
#include "cases.h"
#include "traces.h"

namespace {
recomp::Runtime runtime;
elf_image image;
constexpr addr_t kImport = 0xfeed0000, kReturn = 0xfeedffff;
const char *names[] = {"memcpy", "memset", "__stack_chk_fail", "__cxa_atexit", "__cxa_finalize"};
alignas(16) uint8_t stack[1 << 20], tls[256];
void *resolve(const char *name) {
  for (unsigned i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
    if (!std::strcmp(name, names[i])) return reinterpret_cast<void *>(kImport + i);
  return nullptr;
}
uint32_t call(const char *name, std::initializer_list<uint64_t> args) {
  State state{};
  Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2, &GPR::x3, &GPR::x4, &GPR::x5, &GPR::x6, &GPR::x7};
  size_t i = 0;
  for (auto arg : args) (state.gpr.*registers[i++]).qword = arg;
  auto pc = reinterpret_cast<addr_t>(elf_symbol(&image, name));
  if (!pc) { std::fprintf(stderr, "missing AES export %s\n", name); std::exit(1); }
  state.gpr.pc.qword = pc;
  state.gpr.x30.qword = kReturn;
  state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + sizeof(stack));
  state.sr.tpidr_el0.qword = reinterpret_cast<addr_t>(tls);
  runtime.Run(state, pc);
  if (state.gpr.pc.qword != kReturn) { std::fprintf(stderr, "AES did not return\n"); std::exit(1); }
  return state.gpr.x0.dword;
}
uint32_t enc(uint8_t *out, void *unused, const uint8_t *in, uint32_t len,
             const uint8_t *key, uint32_t key_len, const uint8_t *iv, uint8_t padding) {
  return call("AES_CBC_encrypt", {reinterpret_cast<addr_t>(out), reinterpret_cast<addr_t>(unused),
      reinterpret_cast<addr_t>(in), len, reinterpret_cast<addr_t>(key), key_len, reinterpret_cast<addr_t>(iv), padding});
}
uint32_t dec(uint8_t *out, const uint8_t *in, uint32_t len, const uint8_t *key,
             uint32_t key_len, const uint8_t *iv, uint8_t padding) {
  return call("AES_CBC_decrypt", {reinterpret_cast<addr_t>(out), reinterpret_cast<addr_t>(in), len,
      reinterpret_cast<addr_t>(key), key_len, reinterpret_cast<addr_t>(iv), padding});
}
}  // namespace

int main(int argc, char **argv) {
  if (elf_load(argc > 1 ? argv[1] : LIB, BASE, resolve, &image)) return 1;
  runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
  for (unsigned i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
    runtime.AddImport(kImport + i, [i](State &s) {
      switch (i) {
        case 0: s.gpr.x0.qword = reinterpret_cast<addr_t>(std::memcpy(reinterpret_cast<void *>(s.gpr.x0.qword), reinterpret_cast<void *>(s.gpr.x1.qword), s.gpr.x2.qword)); break;
        case 1: s.gpr.x0.qword = reinterpret_cast<addr_t>(std::memset(reinterpret_cast<void *>(s.gpr.x0.qword), s.gpr.x1.dword, s.gpr.x2.qword)); break;
        case 2: std::abort();
        default: s.gpr.x0.qword = 0;
      }
    });
  }
  return run_cases(enc, dec);
}
