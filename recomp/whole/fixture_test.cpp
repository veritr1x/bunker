#include "runtime.h"
#include "elfload.h"
#include "traces.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <random>

#ifndef FIXTURE_LIB
#error FIXTURE_LIB must name the cross-compiled AArch64 fixture
#endif
static constexpr addr_t kBase = 0x20000000, kImport = 0xfeed0000, kReturn = 0xfeedffff;
static void *resolve(const char *name) {
  return std::strcmp(name, "fixture_host_add") ? nullptr : reinterpret_cast<void *>(kImport);
}
static uint64_t host_add(uint64_t a, uint64_t b) { return (a + b) ^ 0x5a5a5a5a; }

int main(int argc, char **) {
  elf_image image;
  if (elf_load(FIXTURE_LIB, kBase, resolve, &image)) return 1;
  recomp::Runtime runtime;
  runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
  runtime.AddImport(kImport, [](State &s) { s.gpr.x0.qword = host_add(s.gpr.x0.qword, s.gpr.x1.qword); });
  alignas(16) uint8_t stack[1 << 20];
  auto call_address = [&](addr_t entry, std::initializer_list<uint64_t> args) {
    State state{};
    Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2};
    size_t i = 0;
    for (auto arg : args) (state.gpr.*registers[i++]).qword = arg;
    state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + sizeof(stack));
    state.gpr.pc.qword = entry;
    state.gpr.x30.qword = kReturn;
    runtime.Run(state, entry);
    if (state.gpr.pc.qword != kReturn || state.gpr.sp.qword != reinterpret_cast<addr_t>(stack + sizeof(stack))) {
      std::fprintf(stderr, "guest call did not restore PC/SP\n");
      std::exit(1);
    }
    return state.gpr.x0.qword;
  };
  auto address = [&](const char *name) {
    auto *symbol = elf_symbol(&image, name);
    if (!symbol) { std::fprintf(stderr, "missing fixture export %s\n", name); std::exit(1); }
    return reinterpret_cast<addr_t>(symbol);
  };
  auto call = [&](const char *name, std::initializer_list<uint64_t> args) { return call_address(address(name), args); };
  for (addr_t initializer : kInitializers) call_address(initializer, {});
  if (argc > 1) {
    call_address(0xdeadbeef, {});  // Negative test: unknown target must fail loudly.
    return 1;
  }
  size_t checks = 0;
  auto check = [&](const char *name, uint64_t got, uint64_t expected) {
    if (got != expected) {
      std::fprintf(stderr, "%s: got %#llx expected %#llx\n", name,
                   static_cast<unsigned long long>(got), static_cast<unsigned long long>(expected));
      std::exit(1);
    }
    ++checks;
  };
  check("absolute symbol", reinterpret_cast<addr_t>(elf_symbol(&image, "fixture_absolute")), 0x12345678);
  check("absolute relocation", call("absolute_value", {0}), 0x12345678);
  check("absolute zero relocation", call("absolute_value", {1}), 0);
  check("absolute addend relocation", call("absolute_value", {2}), 0x12345681);
  check("undefined weak relocation", call("optional_value", {42}), 97);
  std::mt19937_64 random(0x57484f4c45);
  for (unsigned i = 0; i < 10000; ++i) {
    uint64_t x = random(), y = random();
    check("add_bias", call("add_bias", {x}), x + 11);
    check("direct", call("direct", {x}), (x + 11) + x * 2);
    check("via_pointer/add", call("via_pointer", {address("add_bias"), x}), x + 18);
    check("via_pointer/twice", call("via_pointer", {address("twice"), x}), x * 2 + 7);
    check("via_table/add", call("via_table", {0, x}), x + 14);
    check("via_table/twice", call("via_table", {1, x}), x * 2 + 3);
    check("tail_pointer", call("tail_pointer", {address("add_bias"), x}), x + 11);
    check("via_import", call("via_import", {x, y}), host_add(x, y) + 13);
    check("text relocation/load", call("text_byte", {0}), 'o');
    check("text relocation/signature", call("text_byte", {1}), 'J');
  }
  for (uint64_t n = 0, sum = 11; n < 100; ++n) {
    if (n) sum += n ^ 11;
    check("recursive", call("recursive", {n}), sum);
  }
  std::printf("Whole-library fixture: %zu checks passed (constructors, direct/indirect calls, relocated pointers, tail calls, recursion, imports).\n", checks);
}
