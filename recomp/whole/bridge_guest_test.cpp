#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <random>

#include "bridge.h"
#include "elfload.h"
#include "traces.h"

#ifndef BRIDGE_LIBRARY
#error BRIDGE_LIBRARY must name the original AArch64 caller fixture
#endif
namespace {
constexpr addr_t kBase = 0x40000000, kImport = 0xfeed0000, kReturn = 0xfeedffff;
const char *imports[] = {"host_mixed", "host_gp9_fp1", "host_fp9_gp1", "host_float",
    "host_double", "host_narrow", "host_write", "host_outer", "host_inner"};
size_t checks;
uint64_t seed;
double doubles[10];
float floats[10];
void check(bool condition, const char *name) {
  if (!condition) { std::fprintf(stderr, "guest ABI check failed: %s\n", name); std::exit(1); }
  ++checks;
}
template <typename T, typename U> T bits(U value) {
  static_assert(sizeof(T) == sizeof(U));
  T result;
  std::memcpy(&result, &value, sizeof(result));
  return result;
}
template <typename T> T fp(const State &state) {
  T value;
  std::memcpy(&value, &state.simd.v[0], sizeof(value));
  return value;
}
void *resolve(const char *name) {
  for (unsigned i = 0; i < sizeof(imports) / sizeof(imports[0]); ++i)
    if (!std::strcmp(name, imports[i])) return reinterpret_cast<void *>(kImport + i);
  return nullptr;
}
using Mixed = uint64_t(uint64_t, double, uint32_t, float, const float *, double,
    int8_t, float, uint16_t, double, int64_t, float, uint32_t, double, int16_t,
    float, uint64_t, double, uint64_t, float);
uint64_t mixed(uint64_t a, double b, uint32_t c, float d, const float *e, double f,
    int8_t g, float h, uint16_t i, double j, int64_t k, float l, uint32_t m, double n,
    int16_t o, float p, uint64_t q, double r, uint64_t s, float t) {
  check(a == seed && c == uint32_t(seed >> 1) && e == floats + 3 && g == int8_t(seed) &&
      i == uint16_t(seed >> 16) && uint64_t(k) == (seed ^ UINT64_C(0x123456789abcdef0)) &&
      m == uint32_t(seed >> 3) && o == int16_t(seed >> 9) && q == seed + 9 &&
      s == (seed ^ UINT64_C(0xdeadbeef12345678)), "compiler-generated mixed GP arguments/spills");
  check(bits<uint64_t>(b) == bits<uint64_t>(doubles[0]) && bits<uint32_t>(d) == bits<uint32_t>(floats[1]) &&
      bits<uint64_t>(f) == bits<uint64_t>(doubles[2]) && bits<uint32_t>(h) == bits<uint32_t>(floats[3]) &&
      bits<uint64_t>(j) == bits<uint64_t>(doubles[4]) && bits<uint32_t>(l) == bits<uint32_t>(floats[5]) &&
      bits<uint64_t>(n) == bits<uint64_t>(doubles[6]) && bits<uint32_t>(p) == bits<uint32_t>(floats[7]) &&
      bits<uint64_t>(r) == bits<uint64_t>(doubles[8]) && bits<uint32_t>(t) == bits<uint32_t>(floats[9]),
      "compiler-generated mixed FP arguments/spills preserve bits");
  return seed ^ UINT64_C(0x426269646765);
}
using GP9FP1 = uint64_t(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
    uint64_t, uint64_t, uint64_t, uint64_t, double);
using FP9GP1 = uint64_t(double, double, double, double, double, double, double,
    double, double, uint64_t);
}  // namespace

int main() {
  elf_image image;
  if (elf_load(BRIDGE_LIBRARY, kBase, resolve, &image)) return 1;
  recomp::Runtime outer, inner;
  for (auto *runtime : {&outer, &inner}) runtime->AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
  auto address = [&](const char *name) {
    auto result = reinterpret_cast<addr_t>(elf_symbol(&image, name));
    if (!result) std::abort();
    return result;
  };
  alignas(16) uint8_t outer_stack[1 << 18], inner_stack[1 << 18];
  auto call = [&](recomp::Runtime &runtime, const char *name, std::initializer_list<uint64_t> args, uint8_t *stack) {
    State state{};
    Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2};
    size_t index = 0;
    for (auto value : args) (state.gpr.*registers[index++]).qword = value;
    auto entry = address(name);
    state.gpr.sp.qword = reinterpret_cast<addr_t>(stack + (1 << 18));
    state.gpr.pc.qword = entry;
    state.gpr.x30.qword = kReturn;
    runtime.Run(state, entry);
    check(state.gpr.pc.qword == kReturn && state.gpr.sp.qword == reinterpret_cast<addr_t>(stack + (1 << 18)),
          "guest caller restores PC/SP");
    return state;
  };
  outer.AddImport(kImport, recomp::MakeBridge<Mixed>(&mixed));
  outer.AddImport(kImport + 1, recomp::MakeBridge<GP9FP1>([](uint64_t a, uint64_t b, uint64_t c,
      uint64_t d, uint64_t e, uint64_t f, uint64_t g, uint64_t h, uint64_t i, double j) {
    check(a == 1 && b == 2 && c == 3 && d == 4 && e == 5 && f == 6 && g == 7 && h == 8 &&
          i == seed && bits<uint64_t>(j) == bits<uint64_t>(doubles[0]), "GP spill followed by FP register");
    return seed + 17;
  }));
  outer.AddImport(kImport + 2, recomp::MakeBridge<FP9GP1>([](double a, double b, double c,
      double d, double e, double f, double g, double h, double i, uint64_t j) {
    const double values[] = {a, b, c, d, e, f, g, h, i};
    for (unsigned n = 0; n < 9; ++n)
      check(bits<uint64_t>(values[n]) == bits<uint64_t>(doubles[n]), "FP spill followed by GP register");
    check(j == seed, "GP register remains independent after FP spill");
    return seed + 29;
  }));
  outer.AddImport(kImport + 3, recomp::MakeBridge<float(uint32_t)>([](uint32_t v) { return bits<float>(v); }));
  outer.AddImport(kImport + 4, recomp::MakeBridge<double(uint64_t)>([](uint64_t v) { return bits<double>(v); }));
  outer.AddImport(kImport + 5, recomp::MakeBridge<int8_t(int8_t)>([](int8_t v) { return v; }));
  outer.AddImport(kImport + 6, recomp::MakeBridge<void(uint32_t *, int16_t)>([](uint32_t *p, int16_t v) { *p = uint32_t(v); }));
  outer.AddImport(kImport + 7, recomp::MakeBridge<uint64_t(uint64_t)>([&](uint64_t n) {
    return call(inner, "guest_inner", {n + 5}, inner_stack).gpr.x0.qword;
  }));
  outer.AddImport(kImport + 8, recomp::MakeBridge<uint64_t(uint64_t)>([](uint64_t n) { return n + 17; }));
  inner.AddImport(kImport + 8, recomp::MakeBridge<uint64_t(uint64_t)>([](uint64_t n) { return n + 29; }));

  std::mt19937_64 random(0x57494e414249);
  for (unsigned iteration = 0; iteration < 2000; ++iteration) {
    seed = random();
    for (unsigned i = 0; i < 10; ++i) {
      doubles[i] = bits<double>(uint64_t(random()));
      floats[i] = bits<float>(uint32_t(random()));
    }
    check(call(outer, "guest_mixed", {seed, reinterpret_cast<addr_t>(doubles), reinterpret_cast<addr_t>(floats)}, outer_stack).gpr.x0.qword ==
          (seed ^ UINT64_C(0x426269646765)) + 5, "mixed host result returns through ARM64 caller");
    check(call(outer, "guest_gp9_fp1", {seed, reinterpret_cast<addr_t>(doubles)}, outer_stack).gpr.x0.qword == seed + 17,
          "GP9/FP1 result");
    check(call(outer, "guest_fp9_gp1", {seed, reinterpret_cast<addr_t>(doubles)}, outer_stack).gpr.x0.qword == seed + 29,
          "FP9/GP1 result");
    auto f = call(outer, "guest_float", {uint32_t(seed)}, outer_stack);
    check(fp<uint32_t>(f) == uint32_t(seed), "float result crosses both ABIs bit-exactly");
    auto d = call(outer, "guest_double", {seed}, outer_stack);
    check(fp<uint64_t>(d) == seed, "double result crosses both ABIs bit-exactly");
    auto n = call(outer, "guest_narrow", {seed}, outer_stack);
    check(int8_t(n.gpr.x0.qword) == int8_t(seed), "signed narrow result crosses both ABIs");
    uint32_t target = 0;
    call(outer, "guest_write", {reinterpret_cast<addr_t>(&target), seed}, outer_stack);
    check(target == uint32_t(int16_t(seed)), "void pointer-writing host import");
    check(call(outer, "guest_nested", {seed}, outer_stack).gpr.x0.qword == seed * 2 + 55,
          "nested host-to-guest call restores active runtime");
  }
  std::printf("Compiler-generated ARM64/host ABI bridge: %zu checks passed.\n", checks);
}
