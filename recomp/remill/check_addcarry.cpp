// Compare the actual Remill ADC/ADCS semantics with the x86 ADC instruction.
// This checks integer results and NZCV on an x86_64 host without ARM emulation.
// Decoder/register selection is covered separately by the AArch64 assembly tests.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>

#include "lib/Arch/AArch64/Runtime/Instructions.cpp"

extern "C" bool __remill_flag_computation_zero(bool result, ...) {
  return result;
}
extern "C" bool __remill_flag_computation_sign(bool result, ...) {
  return result;
}
extern "C" bool __remill_flag_computation_overflow(bool result, ...) {
  return result;
}

struct Oracle {
  uint64_t result;
  uint8_t n, z, c, v;
};

#ifdef CHECK_LIFTED_ADDCARRY
struct LiftedCase {
  Memory *(*entry)(State &, addr_t, Memory *);
  const char *name;
  unsigned bits, dst, lhs, rhs;
  bool set_flags;
};
#include "lifted-addcarry.h"
extern "C" Memory *__remill_function_return(State &, addr_t, Memory *memory) {
  return memory;
}
#endif

template <typename T>
Oracle NativeADC(T lhs, T rhs, uint64_t carry) {
  uint8_t n, z, c, v;
  if constexpr (sizeof(T) == 4) {
    asm volatile("btq $0, %[carry]; adcl %[rhs], %[result]; "
                 "sets %[n]; setz %[z]; setc %[c]; seto %[v]"
                 : [result] "+r"(lhs), [n] "=qm"(n), [z] "=qm"(z),
                   [c] "=qm"(c), [v] "=qm"(v)
                 : [rhs] "r"(rhs), [carry] "r"(carry)
                 : "cc");
  } else {
    asm volatile("btq $0, %[carry]; adcq %[rhs], %[result]; "
                 "sets %[n]; setz %[z]; setc %[c]; seto %[v]"
                 : [result] "+r"(lhs), [n] "=qm"(n), [z] "=qm"(z),
                   [c] "=qm"(c), [v] "=qm"(v)
                 : [rhs] "r"(rhs), [carry] "r"(carry)
                 : "cc");
  }
  return {lhs, n, z, c, v};
}

template <typename T>
size_t Check(T lhs, T rhs) {
  for (unsigned flags = 0; flags < 16; ++flags) {
    const auto want = NativeADC(lhs, rhs, (flags >> 1) & 1);
    for (bool set_flags : {false, true}) {
      State state{};
      state.gpr.x9.qword = UINT64_MAX;
      state.sr.n = (flags >> 3) & 1;
      state.sr.z = (flags >> 2) & 1;
      state.sr.c = (flags >> 1) & 1;
      state.sr.v = flags & 1;
      State expected = state;
      expected.gpr.x9.qword = want.result;
      if (set_flags) {
        expected.sr.n = want.n;
        expected.sr.z = want.z;
        expected.sr.c = want.c;
        expected.sr.v = want.v;
      }
      Memory *returned;
      if constexpr (sizeof(T) == 4) {
        auto sem = set_flags ? ISEL_ADCS_32_ADDSUB_CARRY : ISEL_ADC_32_ADDSUB_CARRY;
        returned = sem(nullptr, state, R32W{&state.gpr.x9.qword}, R32{lhs}, R32{rhs});
      } else {
        auto sem = set_flags ? ISEL_ADCS_64_ADDSUB_CARRY : ISEL_ADC_64_ADDSUB_CARRY;
        returned = sem(nullptr, state, R64W{&state.gpr.x9.qword}, R64{lhs}, R64{rhs});
      }
      if (returned != nullptr || std::memcmp(&state, &expected, sizeof(state))) {
        std::fprintf(stderr, "%s%zu lhs=%llx rhs=%llx NZCV=%x: result=%llx expected=%llx flags=%u%u%u%u expected=%u%u%u%u\n",
                     set_flags ? "ADCS" : "ADC", sizeof(T) * 8,
                     static_cast<unsigned long long>(lhs), static_cast<unsigned long long>(rhs), flags,
                     static_cast<unsigned long long>(state.gpr.x9.qword),
                     static_cast<unsigned long long>(want.result),
                     state.sr.n, state.sr.z, state.sr.c, state.sr.v,
                     expected.sr.n, expected.sr.z, expected.sr.c, expected.sr.v);
        std::exit(1);
      }
    }
  }
  return 32;
}

#ifdef CHECK_LIFTED_ADDCARRY
size_t CheckLifted(uint64_t lhs, uint64_t rhs) {
  size_t count = 0;
  for (const auto &test : kLiftedCases) {
    const uint64_t a = test.lhs == 31 ? 0 : lhs;
    const uint64_t b = test.rhs == 31 ? 0 : rhs;
    for (unsigned flags = 0; flags < 16; ++flags) {
      const auto carry = (flags >> 1) & 1;
      const auto want = test.bits == 32 ? NativeADC<uint32_t>(a, b, carry)
                                        : NativeADC<uint64_t>(a, b, carry);
      State state{};
      state.gpr.x0.qword = lhs;
      state.gpr.x1.qword = rhs;
      state.gpr.x9.qword = UINT64_MAX;
      state.gpr.sp.qword = 0x1122334455667788;  // Register 31 must mean ZR, not SP.
      state.gpr.x30.qword = 0xfeedffff;
      state.gpr.pc.qword = 0x10000000;
      state.sr.n = (flags >> 3) & 1;
      state.sr.z = (flags >> 2) & 1;
      state.sr.c = carry;
      state.sr.v = flags & 1;
      State expected = state;
      if (test.dst != 31) {
        auto &dest = test.dst == 0 ? expected.gpr.x0 :
                     test.dst == 1 ? expected.gpr.x1 : expected.gpr.x9;
        dest.qword = want.result;
      }
      expected.gpr.pc.qword = state.gpr.x30.qword;
      if (test.set_flags) {
        expected.sr.n = want.n;
        expected.sr.z = want.z;
        expected.sr.c = want.c;
        expected.sr.v = want.v;
      }
      auto *returned = test.entry(state, 0x10000000, nullptr);
      if (returned != nullptr || std::memcmp(&state, &expected, sizeof(state))) {
        std::fprintf(stderr, "Lifted %s failed: lhs=%llx rhs=%llx NZCV=%x\n", test.name,
                     static_cast<unsigned long long>(lhs),
                     static_cast<unsigned long long>(rhs), flags);
        std::exit(1);
      }
      ++count;
    }
  }
  return count;
}
#endif

int main() {
  const uint64_t edges[] = {0, 1, 2, 0x7ffffffe, 0x7fffffff, 0x80000000,
      0xfffffffe, 0xffffffff, 0x100000000, 0x7ffffffffffffffe,
      0x7fffffffffffffff, 0x8000000000000000, UINT64_MAX - 1, UINT64_MAX};
  size_t count = 0;
#ifdef CHECK_LIFTED_ADDCARRY
  size_t lifted_count = 0;
#endif
  for (auto lhs : edges) {
    for (auto rhs : edges) {
      count += Check<uint32_t>(lhs, rhs);
      count += Check<uint64_t>(lhs, rhs);
#ifdef CHECK_LIFTED_ADDCARRY
      lifted_count += CheckLifted(lhs, rhs);
#endif
    }
  }
  std::mt19937_64 random(0xaddca77);
  for (unsigned i = 0; i < 100000; ++i) {
    const auto lhs = random(), rhs = random();
    count += Check<uint32_t>(lhs, rhs);
    count += Check<uint64_t>(lhs, rhs);
#ifdef CHECK_LIFTED_ADDCARRY
    if (i < 10000) lifted_count += CheckLifted(lhs, rhs);
#endif
  }
  std::printf("ADC/ADCS: %zu cases match x86 hardware (32/64 bit, all NZCV inputs).\n", count);
#ifdef CHECK_LIFTED_ADDCARRY
  std::printf("Lifted ADC/ADCS: %zu cases match x86 hardware (24 instruction/register variants).\n", lifted_count);
#endif
}
