#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "format.h"

static unsigned checks;
static void require(bool value, const char *name) {
  ++checks;
  if (!value) { std::fprintf(stderr, "format check failed: %s\n", name); std::exit(1); }
}
static void fp(State &s, unsigned i, double value) { std::memcpy(&s.simd.v[i], &value, sizeof(value)); }
static std::string format(State &s, const char *text) {
  recomp::bridge_detail::Arguments args(s);
  return recomp::Format(text, args);
}
int main() {
  State state{};
  state.gpr.x0.qword = UINT64_C(0x100000000);
  require(format(state, "%ld|%d") == "4294967296|0", "Android LP64 long on Windows LLP64");
  state.gpr.x0.qword = UINT64_MAX;
  state.gpr.x1.qword = UINT64_MAX;
  state.gpr.x2.qword = UINT64_C(0x8000000000000000);
  state.gpr.x3.qword = UINT64_MAX;
  require(format(state, "%d|%u|%lld|%llu") == "-1|4294967295|-9223372036854775808|18446744073709551615", "signed/unsigned widths");
  require(format(state, "%hhd|%hhu|%hd|%hu") == "-1|255|0|65535", "promoted narrow conversions");
  state = State{};
  state.gpr.x0.qword = 8;
  state.gpr.x1.qword = 3;
  state.gpr.x2.qword = reinterpret_cast<uint64_t>("text");
  fp(state, 0, 1.25);
  require(format(state, "%*.*f|%.2s") == "   1.250|te", "independent FP bank and dynamic width/precision");
  state.gpr.x0.qword = static_cast<uint32_t>(-8);
  require(format(state, "%*.*f|%s") == "1.250   |text", "negative width");
  state = State{};
  require(format(state, "%s|%p") == "(null)|0x0", "Bionic null string/pointer");
  require(format(state, "%.0p") == "0x", "Bionic zero pointer explicit zero precision");
  state.gpr.x0.qword = 0x1234;
  require(format(state, "%p") == "0x1234", "Android-style pointer output");
  require(format(state, "%010p") == "0x00001234", "pointer zero padding follows prefix");
  require(format(state, "%10.6p") == "  0x001234", "pointer precision and width");
  state.gpr.x0.qword = 0;
  require(format(state, "%'.2s") == "(n", "Bionic grouping flag ignored and null precision");
  require(format(state, "literal %% done") == "literal % done", "percent escape");
  state.gpr.x0.qword = 0;
  auto nul = format(state, "%c");
  require(nul.size() == 1 && nul[0] == 0, "embedded NUL character");
  for (const char *unsupported : {"%n", "%2$d", "%Lf", "%ls", "%"}) {
    bool rejected = false;
    try { format(state, unsupported); } catch (const std::invalid_argument &) { rejected = true; }
    require(rejected, "unsupported format reports failure");
  }
  alignas(16) uint64_t stack[] = {9, 0};
  double ninth = 9.5;
  std::memcpy(&stack[1], &ninth, sizeof(ninth));
  state = State{};
  state.gpr.x0.qword = 1; state.gpr.x1.qword = 2; state.gpr.x2.qword = 3; state.gpr.x3.qword = 4;
  state.gpr.x4.qword = 5; state.gpr.x5.qword = 6; state.gpr.x6.qword = 7; state.gpr.x7.qword = 8;
  state.gpr.sp.qword = reinterpret_cast<uint64_t>(stack);
  for (unsigned i = 0; i < 8; ++i) fp(state, i, i + 1.5);
  const char *pattern = "%d%d%d%d%d%d%d%d|%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f|%d|%.1f";
  const std::string wanted = "12345678|1.5,2.5,3.5,4.5,5.5,6.5,7.5,8.5|9|9.5";
  require(format(state, pattern) == wanted, "shared GP/FP spill order");
  uint64_t gp[] = {1,2,3,4,5,6,7,8};
  alignas(16) uint8_t vectors[8][16]{};
  for (unsigned i = 0; i < 8; ++i) { double v = i + 1.5; std::memcpy(vectors[i], &v, sizeof(v)); }
  struct { uint64_t stack, gr, vr; int32_t go, vo; } list = {
    reinterpret_cast<uint64_t>(stack), reinterpret_cast<uint64_t>(gp + 8),
    reinterpret_cast<uint64_t>(vectors + 8), -64, -128};
  recomp::VaArguments va(&list);
  require(recomp::Format(pattern, va) == wanted, "AAPCS64 va_list save areas and shared stack");
  require(list.go == -64 && list.vo == -128, "formatting does not mutate caller va_list");
  std::printf("Variadic formatting: %u checks passed.\n", checks);
}
