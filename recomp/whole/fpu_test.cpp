#include <cfenv>
#include <cfloat>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "runtime.h"

static unsigned checks;
static void require(bool condition, const char *name) {
  ++checks;
  if (!condition) { std::fprintf(stderr, "FPU check failed: %s\n", name); std::exit(1); }
}
static uint64_t bits(double value) {
  uint64_t result;
  std::memcpy(&result, &value, sizeof(result));
  return result;
}
static void clear() { __remill_fpu_exception_clear(kFPUExceptionAll); }
static Memory *cleared_fpsr_then_import(State &state, addr_t, Memory *memory) {
  __remill_fpu_exception_raise(kFPUExceptionDivByZero);
  state.sr.dzc = 0;  // State after a guest MSR FPSR,#0.
  return __remill_function_call(state, 0x50000010, memory);
}

int main() {
  fenv_t original;
  std::fegetenv(&original);
  __remill_fpu_set_rounding(kFPURoundToNearestEven);
  volatile double zero = 0, one = 1, two = 2, three = 3, big = DBL_MAX, small = DBL_MIN;
  clear();
  volatile double result = one / zero;
  require(__remill_fpu_exception_test(kFPUExceptionAll) == kFPUExceptionDivByZero, "divide-by-zero mask");
  clear(); result = zero / zero;
  require(__remill_fpu_exception_test(kFPUExceptionAll) == kFPUExceptionInvalid, "invalid mask");
  clear(); result = big * two;
  require(__remill_fpu_exception_test(kFPUExceptionAll) == (kFPUExceptionOverflow | kFPUExceptionPrecision), "overflow+precision mask");
  clear(); result = small * small;
  require(__remill_fpu_exception_test(kFPUExceptionAll) == (kFPUExceptionUnderflow | kFPUExceptionPrecision), "underflow+precision mask");
  clear(); result = one / three;
  require(__remill_fpu_exception_test(kFPUExceptionAll) == kFPUExceptionPrecision, "precision mask");
  __remill_fpu_exception_raise(kFPUExceptionDenormal);
  require(__remill_fpu_exception_test(kFPUExceptionDenormal) == kFPUExceptionDenormal, "explicit ARM IDC");
  __remill_fpu_exception_clear(kFPUExceptionPrecision);
  require(__remill_fpu_exception_test(kFPUExceptionAll) == kFPUExceptionDenormal, "selective clearing");
  clear();
  require(__remill_fpu_exception_test(kFPUExceptionAll) == 0, "clear all");

  const int native_modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  for (int mode = 0; mode < 4; ++mode) {
    __remill_fpu_set_rounding(mode);
    require(__remill_fpu_get_rounding() == mode && std::fegetround() == native_modes[mode], "rounding mapping");
    volatile double half_ulp = 0x1p-53;
    result = one + half_ulp;
    require(bits(result) == (mode == kFPURoundUpInf ? UINT64_C(0x3ff0000000000001) : UINT64_C(0x3ff0000000000000)), "hardware rounding result");
  }

  recomp::Runtime runtime;
  runtime.AddImport(0x50000000, [&](State &state) {
    require(__remill_fpu_exception_test(kFPUExceptionAll) == 0, "clean guest FPU context");
    state.gpr.x0.qword = __remill_fpu_get_rounding();
    result = one / zero;
  });
  for (int mode = 0; mode < 4; ++mode) {
    std::fesetround(FE_DOWNWARD);
    clear();
    std::feraiseexcept(FE_INVALID);
    __remill_fpu_exception_raise(kFPUExceptionDenormal);
    State state{};
    state.fpcr.rmode = static_cast<FPURoundingMode>(mode);
    state.gpr.x30.qword = 0xfeedffff;
    runtime.Run(state, 0x50000000);
    require(state.gpr.x0.qword == static_cast<uint64_t>(mode), "guest FPCR rounding applied");
    require(state.sr.dzc && !state.sr.ioc, "host import exceptions captured in guest FPSR");
    require(state.gpr.pc.qword == 0xfeedffff, "import return address");
    require(std::fegetround() == FE_DOWNWARD, "host rounding restored");
    require(std::fetestexcept(FE_ALL_EXCEPT) == FE_INVALID, "host exception flags restored");
    require(__remill_fpu_exception_test(kFPUExceptionDenormal) == kFPUExceptionDenormal, "explicit IDC context restored");
  }
  runtime.AddImport(0x50000010, [](State &) {});
  const recomp::Trace regression = {0x50000020, cleared_fpsr_then_import};
  runtime.AddTraces(&regression, 1);
  State cleared{};
  cleared.gpr.x30.qword = 0xfeedffff;
  runtime.Run(cleared, regression.address);
  require(!cleared.sr.dzc, "cleared guest FPSR is not repopulated by stale host flags");
  clear();
  std::fesetenv(&original);
  std::printf("FPU runtime: %u checks passed (hardware flags, rounding, guest/host context isolation).\n", checks);
}
