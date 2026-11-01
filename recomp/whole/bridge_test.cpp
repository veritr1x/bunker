#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <random>

#include "bridge.h"

namespace {
size_t checks;
void check(bool condition, const char *message) {
  if (!condition) { std::fprintf(stderr, "bridge check failed: %s\n", message); std::exit(1); }
  ++checks;
}
template <typename T, typename U> T bits(U value) {
  static_assert(sizeof(T) == sizeof(U));
  T out;
  std::memcpy(&out, &value, sizeof(out));
  return out;
}
template <typename T> void fp(State &s, unsigned reg, T value) {
  std::memcpy(&s.simd.v[reg], &value, sizeof(value));
}
template <typename T> T fp(const State &s, unsigned reg) {
  T value;
  std::memcpy(&value, &s.simd.v[reg], sizeof(value));
  return value;
}
enum class Small : int16_t { Negative = -32760 };
struct Aggregate { uint64_t x; };
static_assert(recomp::kBridgeSupported<void()>);
static_assert(recomp::kBridgeSupported<uint64_t(int32_t, float, double, void *)>);
static_assert(recomp::kBridgeSupported<Small(Small)>);
static_assert(!recomp::kBridgeSupported<void(int, ...)>);
static_assert(!recomp::kBridgeSupported<Aggregate()>);
static_assert(!recomp::kBridgeSupported<void(Aggregate)>);
static_assert(!recomp::kBridgeSupported<int &(int &)>);
static_assert(!recomp::kBridgeSupported<void(void (*)())>);
static_assert(!recomp::kBridgeSupported<long double(long double)>);

uint64_t plain(uint64_t a, uint64_t b) { return a ^ (b << 1); }

void unit_tests() {
  std::mt19937_64 random(0x41415043533634);
  for (unsigned i = 0; i < 10000; ++i) {
    State s{};
    uint64_t a = random(), b = random();
    uint32_t f = static_cast<uint32_t>(random());
    uint64_t d = random();
    s.gpr.x0.qword = a;
    s.gpr.x1.qword = 0xdeadbeef00000000 | static_cast<uint32_t>(b);
    s.gpr.x2.qword = 0x0123456789abcd80;
    s.gpr.x3.qword = 0x8877665544338001;
    fp(s, 0, bits<double>(d));
    fp(s, 1, bits<float>(f));
    auto bridge = recomp::MakeBridge<uint64_t(uint64_t, double, uint32_t, float, int8_t, int16_t)>(
        [&](uint64_t x, double y, uint32_t z, float w, int8_t n, int16_t m) {
          check(x == a && bits<uint64_t>(y) == d && z == static_cast<uint32_t>(b) &&
                bits<uint32_t>(w) == f && n == -128 && m == -32767,
                "independent GP/FP register positions and narrow integer bits");
          return a ^ b ^ f ^ d;
        });
    State expected = s;
    expected.gpr.x0.qword = a ^ b ^ f ^ d;
    bridge(s);
    check(!std::memcmp(&s, &expected, sizeof(s)), "integer return changes only X0");
  }

  {
    State s{};
    alignas(16) uint64_t stack[] = {0x0102030405060781, 0xdeadbeef1234fffe};
    s.gpr.sp.qword = reinterpret_cast<uintptr_t>(stack);
    s.gpr.x0.qword = 1; s.gpr.x1.qword = 2; s.gpr.x2.qword = 3; s.gpr.x3.qword = 4;
    s.gpr.x4.qword = 5; s.gpr.x5.qword = 6; s.gpr.x6.qword = 7; s.gpr.x7.qword = 8;
    auto bridge = recomp::MakeBridge<int64_t(uint64_t, uint64_t, uint64_t, uint64_t,
        uint64_t, uint64_t, uint64_t, uint64_t, int8_t, uint16_t)>(
        [&](uint64_t a, uint64_t b, uint64_t c, uint64_t d, uint64_t e, uint64_t f,
            uint64_t g, uint64_t h, int8_t n, uint16_t m) {
          check(a == 1 && b == 2 && c == 3 && d == 4 && e == 5 && f == 6 && g == 7 && h == 8,
                "first eight integral arguments");
          check(n == -127 && m == 65534, "narrow integral stack slots ignore padding");
          return INT64_MIN + 5;
        });
    bridge(s);
    check(s.gpr.x0.qword == uint64_t(INT64_MIN + 5), "64-bit signed return bits");
  }
  {
    State s{};
    alignas(16) uint64_t stack[] = {0x7ff80000deadbeef, 0xcafebabe80000001};
    s.gpr.sp.qword = reinterpret_cast<uintptr_t>(stack);
    for (unsigned i = 0; i < 8; ++i) fp(s, i, float(i) + 0.5f);
    auto bridge = recomp::MakeBridge<void(float, float, float, float, float, float,
        float, float, double, float)>(
        [&](float a, float b, float c, float d, float e, float f, float g, float h,
            double j, float k) {
          check(a == 0.5f && b == 1.5f && c == 2.5f && d == 3.5f && e == 4.5f &&
                f == 5.5f && g == 6.5f && h == 7.5f, "eight FP argument registers");
          check(bits<uint64_t>(j) == stack[0] && bits<uint32_t>(k) == 0x80000001,
                "FP stack slots use eight-byte stride and preserve NaN/subnormal bits");
        });
    State expected = s;
    bridge(s);
    check(!std::memcmp(&s, &expected, sizeof(s)), "void return preserves guest registers");
  }
  {
    State s{};
    alignas(16) uint64_t stack[] = {9, 0x4004000000000000, 11, 0x400c000000000000};
    s.gpr.sp.qword = reinterpret_cast<uintptr_t>(stack);
    s.gpr.x0.qword = 1; s.gpr.x1.qword = 2; s.gpr.x2.qword = 3; s.gpr.x3.qword = 4;
    s.gpr.x4.qword = 5; s.gpr.x5.qword = 6; s.gpr.x6.qword = 7; s.gpr.x7.qword = 8;
    for (unsigned i = 0; i < 8; ++i) fp(s, i, double(i) + 0.5);
    auto bridge = recomp::MakeBridge<uint64_t(uint64_t, double, uint64_t, double,
        uint64_t, double, uint64_t, double, uint64_t, double, uint64_t, double,
        uint64_t, double, uint64_t, double, uint64_t, double, uint64_t, double)>(
        [&](uint64_t a, double b, uint64_t c, double d, uint64_t e, double f, uint64_t g,
            double h, uint64_t i, double j, uint64_t k, double l, uint64_t m, double n,
            uint64_t o, double p, uint64_t q, double r, uint64_t t, double u) {
          check(a == 1 && b == 0.5 && c == 2 && d == 1.5 && e == 3 && f == 2.5 &&
              g == 4 && h == 3.5 && i == 5 && j == 4.5 && k == 6 && l == 5.5 &&
              m == 7 && n == 6.5 && o == 8 && p == 7.5 && q == 9 && r == 2.5 &&
              t == 11 && u == 3.5, "interleaved GP/FP spills share C argument order");
          return 123;
        });
    bridge(s);
    check(s.gpr.x0.qword == 123, "mixed-spill result");
  }
  {
    State s{};
    alignas(16) uint64_t stack[] = {9, 0xcccccccccccccccc};
    s.gpr.sp.qword = reinterpret_cast<uintptr_t>(stack);
    fp(s, 0, 12.5);
    recomp::MakeBridge<void(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
        uint64_t, uint64_t, uint64_t, double)>([&](auto, auto, auto, auto, auto, auto,
            auto, auto, uint64_t n, double d) {
          check(n == 9 && d == 12.5, "GP spill does not consume available FP registers");
        })(s);
    fp(s, 0, 1.0); fp(s, 1, 2.0); fp(s, 2, 3.0); fp(s, 3, 4.0);
    fp(s, 4, 5.0); fp(s, 5, 6.0); fp(s, 6, 7.0); fp(s, 7, 8.0);
    stack[0] = bits<uint64_t>(9.5);
    s.gpr.x0.qword = 77;
    recomp::MakeBridge<void(double, double, double, double, double, double, double,
        double, double, uint64_t)>([&](auto, auto, auto, auto, auto, auto, auto,
            auto, double d, uint64_t n) {
          check(d == 9.5 && n == 77, "FP spill does not consume available GP registers");
        })(s);
  }
  for (uint32_t pattern : {0U, 0x80000000U, 0x7f800000U, 0xff800000U, 0x7fc01234U, 0x7f801234U, 1U}) {
    State s{};
    s.gpr.x0.qword = pattern;
    std::memset(&s.simd.v[0], 0xab, sizeof(s.simd.v[0]));
    recomp::MakeBridge<float(uint32_t)>([](uint32_t x) { return bits<float>(x); })(s);
    check(fp<uint32_t>(s, 0) == pattern, "float return preserves IEEE bits");
    check(s.simd.v[0].qwords.elems[1] == 0 && s.simd.v[0].dwords.elems[1] == 0,
          "float return zeroes unused V0 bits");
  }
  for (uint64_t pattern : {0ULL, 0x8000000000000000ULL, 0x7ff0000000000000ULL,
      0xfff0000000000000ULL, 0x7ff8123456789abcULL, 0x7ff0123456789abcULL, 1ULL}) {
    State s{};
    s.gpr.x0.qword = pattern;
    std::memset(&s.simd.v[0], 0xab, sizeof(s.simd.v[0]));
    recomp::MakeBridge<double(uint64_t)>([](uint64_t x) { return bits<double>(x); })(s);
    check(fp<uint64_t>(s, 0) == pattern && s.simd.v[0].qwords.elems[1] == 0,
          "double return preserves IEEE bits and clears upper V0");
  }
  {
    uint32_t target = 0;
    State s{};
    s.gpr.x0.qword = reinterpret_cast<uintptr_t>(&target);
    s.gpr.x1.qword = 0x11223344556677fd;
    recomp::MakeBridge<void(uint32_t *, int8_t)>([](uint32_t *p, int8_t n) { *p = uint32_t(n); })(s);
    check(target == uint32_t(-3), "data pointer and signed narrow input");
    recomp::MakeBridge<int8_t()>([] { return int8_t(-127); })(s);
    check(s.gpr.x0.qword == 0xffffff81, "signed narrow return uses W0 representation");
    recomp::MakeBridge<uint8_t()>([] { return uint8_t(129); })(s);
    check(s.gpr.x0.qword == 129, "unsigned narrow return zero extends");
    recomp::MakeBridge<bool()>([] { return true; })(s);
    check(s.gpr.x0.qword == 1, "bool return");
    s.gpr.x0.qword = 0xfedcba9876548008;
    recomp::MakeBridge<Small(Small)>([](Small value) { return value; })(s);
    check(s.gpr.x0.qword == 0xffff8008, "enum input/output follows underlying width");
    recomp::MakeBridge<uint32_t *()>([&] { return &target; })(s);
    check(s.gpr.x0.qword == reinterpret_cast<uintptr_t>(&target), "pointer return");
    s.gpr.x0.qword = 3; s.gpr.x1.qword = 5;
    recomp::MakeBridge(&plain)(s);
    check(s.gpr.x0.qword == 9, "deduced typed function-pointer bridge");
    bool rejected = false;
    try { recomp::MakeBridge<uint64_t(uint64_t, uint64_t)>(static_cast<decltype(&plain)>(nullptr)); }
    catch (const std::invalid_argument &) { rejected = true; }
    check(rejected, "null host function rejected");
    recomp::MakeBridge<double()>([] { return 1.25f; })(s);
    check(fp<double>(s, 0) == 1.25, "declared result type controls return ABI after host conversion");
    recomp::MakeBridge<int8_t()>([] { return 255; })(s);
    check(s.gpr.x0.qword == 0xffffffff, "declared narrow result is converted before marshaling");
    alignas(16) uint64_t invalid_stack[3] = {};
    s.gpr.sp.qword = reinterpret_cast<uintptr_t>(invalid_stack + 1);
    rejected = false;
    try {
      recomp::MakeBridge<void(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
          uint64_t, uint64_t, uint64_t, uint64_t)>([](auto...) {})(s);
    } catch (const std::invalid_argument &) { rejected = true; }
    check(rejected, "first spill rejects non-16-byte-aligned SP");
  }
}
}  // namespace

int main() {
  unit_tests();
  std::printf("Scalar ABI bridge: %zu checks passed.\n", checks);
}
