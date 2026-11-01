#include <atomic>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

#include "runtime.h"

namespace {
thread_local recomp::Runtime *active;
// ARM IDC is not x86's denormal-operand status bit. Instructions that flush
// an input explicitly raise IDC; ordinary subnormal inputs must not set it.
thread_local int explicit_denormal;
[[noreturn]] void fail(const char *reason, addr_t pc) {
  std::fprintf(stderr, "recomp: %s at %#llx\n", reason, static_cast<unsigned long long>(pc));
  std::abort();
}
template <typename T> T load(addr_t address) {
  T value;
  std::memcpy(&value, reinterpret_cast<const void *>(address), sizeof(value));
  return value;
}
template <typename T> Memory *store(Memory *memory, addr_t address, T value) {
  std::memcpy(reinterpret_cast<void *>(address), &value, sizeof(value));
  return memory;
}
Memory *dispatch(State &state, addr_t address, Memory *memory) {
  if (!active) fail("no active runtime for indirect target", address);
  return active->Dispatch(state, address, memory);
}
int host_exceptions(int mask) {
  int flags = 0;
  if (mask & kFPUExceptionInvalid) flags |= FE_INVALID;
  if (mask & kFPUExceptionDivByZero) flags |= FE_DIVBYZERO;
  if (mask & kFPUExceptionOverflow) flags |= FE_OVERFLOW;
  if (mask & kFPUExceptionUnderflow) flags |= FE_UNDERFLOW;
  if (mask & kFPUExceptionPrecision) flags |= FE_INEXACT;
  return flags;
}
int guest_exceptions(int flags) {
  int mask = 0;
  if (flags & FE_INVALID) mask |= kFPUExceptionInvalid;
  if (flags & FE_DIVBYZERO) mask |= kFPUExceptionDivByZero;
  if (flags & FE_OVERFLOW) mask |= kFPUExceptionOverflow;
  if (flags & FE_UNDERFLOW) mask |= kFPUExceptionUnderflow;
  if (flags & FE_INEXACT) mask |= kFPUExceptionPrecision;
  return mask;
}
int host_rounding(int mode) {
  switch (mode) {
    case kFPURoundToNearestEven: return FE_TONEAREST;
    case kFPURoundUpInf: return FE_UPWARD;
    case kFPURoundDownNegInf: return FE_DOWNWARD;
    case kFPURoundToZero: return FE_TOWARDZERO;
    default: fail("invalid guest floating-point rounding mode", mode);
  }
}
}  // namespace

void recomp::Runtime::AddTraces(const Trace *traces, size_t count) {
  for (size_t i = 0; i < count; ++i) {
    if (!traces[i].entry || imports_.count(traces[i].address) ||
        !traces_.emplace(traces[i].address, traces[i].entry).second)
      throw std::invalid_argument("duplicate or invalid guest trace");
  }
}
void recomp::Runtime::AddImport(addr_t address, std::function<void(State &)> bridge) {
  if (!bridge || traces_.count(address) || !imports_.emplace(address, std::move(bridge)).second)
    throw std::invalid_argument("duplicate or invalid guest import");
}
Memory *recomp::Runtime::Run(State &state, addr_t address, Memory *memory) {
  struct Scope {
    Runtime *previous;
    int denormal;
    fenv_t environment;
    Scope() : previous(active), denormal(explicit_denormal) { std::fegetenv(&environment); }
    ~Scope() { active = previous; explicit_denormal = denormal; std::fesetenv(&environment); }
  } scope;
  active = this;
  std::feclearexcept(FE_ALL_EXCEPT);
  explicit_denormal = 0;
  std::fesetround(host_rounding(state.fpcr.rmode));
  return Dispatch(state, address, memory);
}
Memory *recomp::Runtime::Dispatch(State &state, addr_t address, Memory *memory) {
  if (auto found = traces_.find(address); found != traces_.end())
    return found->second(state, address, memory);
  if (auto found = imports_.find(address); found != imports_.end()) {
    // Guest instructions have already accumulated their flags in State. A
    // guest MSR FPSR may have cleared those flags since the last host FP op.
    // Attribute only exceptions from this import to the guest call.
    std::feclearexcept(FE_ALL_EXCEPT);
    explicit_denormal = 0;
    found->second(state);
    const int mask = guest_exceptions(std::fetestexcept(FE_ALL_EXCEPT)) | explicit_denormal;
    state.sr.ioc |= (mask & kFPUExceptionInvalid) != 0;
    state.sr.dzc |= (mask & kFPUExceptionDivByZero) != 0;
    state.sr.ofc |= (mask & kFPUExceptionOverflow) != 0;
    state.sr.ufc |= (mask & kFPUExceptionUnderflow) != 0;
    state.sr.ixc |= (mask & kFPUExceptionPrecision) != 0;
    state.sr.idc |= (mask & kFPUExceptionDenormal) != 0;
    state.gpr.pc.qword = state.gpr.x30.qword;
    return memory;
  }
  fail("unresolved indirect target", address);
}

extern "C" {
int32_t __remill_fpu_exception_test(int32_t mask) {
  return (guest_exceptions(std::fetestexcept(FE_ALL_EXCEPT)) | explicit_denormal) & mask;
}
void __remill_fpu_exception_clear(int32_t mask) {
  std::feclearexcept(host_exceptions(mask));
  explicit_denormal &= ~mask;
}
void __remill_fpu_exception_raise(int32_t mask) {
  std::feraiseexcept(host_exceptions(mask));
  explicit_denormal |= mask & kFPUExceptionDenormal;
}
void __remill_fpu_set_rounding(int32_t mode) { std::fesetround(host_rounding(mode)); }
int32_t __remill_fpu_get_rounding() {
  switch (std::fegetround()) {
    case FE_TONEAREST: return kFPURoundToNearestEven;
    case FE_UPWARD: return kFPURoundUpInf;
    case FE_DOWNWARD: return kFPURoundDownNegInf;
    case FE_TOWARDZERO: return kFPURoundToZero;
    default: fail("invalid host floating-point rounding mode", 0);
  }
}
#define MEMORY(bits, type) \
type __remill_read_memory_##bits(Memory *, addr_t a) { return load<type>(a); } \
Memory *__remill_write_memory_##bits(Memory *m, addr_t a, type v) { return store(m, a, v); }
MEMORY(8, uint8_t)
MEMORY(16, uint16_t)
MEMORY(32, uint32_t)
MEMORY(64, uint64_t)
MEMORY(f32, float32_t)
MEMORY(f64, float64_t)
#undef MEMORY
Memory *__remill_read_memory_f80(Memory *m, addr_t a, float80_t &value) { value = load<float80_t>(a); return m; }
float128_t __remill_read_memory_f128(Memory *, addr_t a) { return load<float128_t>(a); }
Memory *__remill_write_memory_f80(Memory *m, addr_t a, const float80_t &v) { return store(m, a, v); }
Memory *__remill_write_memory_f128(Memory *m, addr_t a, float128_t v) { return store(m, a, v); }

uint8_t __remill_undefined_8() { return 0; }
uint16_t __remill_undefined_16() { return 0; }
uint32_t __remill_undefined_32() { return 0; }
uint64_t __remill_undefined_64() { return 0; }
float32_t __remill_undefined_f32() { return 0; }
float64_t __remill_undefined_f64() { return 0; }
bool __remill_flag_computation_zero(bool r, ...) { return r; }
bool __remill_flag_computation_sign(bool r, ...) { return r; }
bool __remill_flag_computation_overflow(bool r, ...) { return r; }
bool __remill_flag_computation_carry(bool r, ...) { return r; }
#define COMPARE(name) bool __remill_compare_##name(bool r) { return r; }
COMPARE(eq) COMPARE(neq) COMPARE(sle) COMPARE(slt) COMPARE(sge) COMPARE(sgt)
COMPARE(ule) COMPARE(ult) COMPARE(uge) COMPARE(ugt)
#undef COMPARE

Memory *__remill_error(State &, addr_t pc, Memory *) { fail("unliftable instruction", pc); }
Memory *__remill_missing_block(State &, addr_t pc, Memory *) { fail("missing block", pc); }
Memory *__remill_function_return(State &, addr_t, Memory *m) { return m; }
Memory *__remill_function_call(State &s, addr_t pc, Memory *m) { return dispatch(s, pc, m); }
Memory *__remill_jump(State &s, addr_t pc, Memory *m) { return dispatch(s, pc, m); }
Memory *__remill_async_hyper_call(State &, addr_t pc, Memory *) { fail("async hyper call", pc); }
Memory *__remill_sync_hyper_call(State &s, Memory *, SyncHyperCall::Name) { fail("sync hyper call", s.gpr.pc.qword); }

Memory *__remill_barrier_load_load(Memory *m) { std::atomic_thread_fence(std::memory_order_seq_cst); return m; }
Memory *__remill_barrier_load_store(Memory *m) { std::atomic_thread_fence(std::memory_order_seq_cst); return m; }
Memory *__remill_barrier_store_load(Memory *m) { std::atomic_thread_fence(std::memory_order_seq_cst); return m; }
Memory *__remill_barrier_store_store(Memory *m) { std::atomic_thread_fence(std::memory_order_seq_cst); return m; }
Memory *__remill_atomic_begin(Memory *m) { return m; }
Memory *__remill_atomic_end(Memory *m) { return m; }
Memory *__remill_delay_slot_begin(Memory *m) { return m; }
Memory *__remill_delay_slot_end(Memory *m) { return m; }

#define CMPXCHG(bits) \
Memory *__remill_compare_exchange_memory_##bits(Memory *m, addr_t a, uint##bits##_t &expected, uint##bits##_t desired) { \
  __atomic_compare_exchange_n(reinterpret_cast<uint##bits##_t *>(a), &expected, desired, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST); return m; }
CMPXCHG(8) CMPXCHG(16) CMPXCHG(32) CMPXCHG(64)
#undef CMPXCHG
Memory *__remill_compare_exchange_memory_128(Memory *m, addr_t a, uint128_t &expected, uint128_t &desired) {
  __atomic_compare_exchange(reinterpret_cast<uint128_t *>(a), &expected, &desired, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
  return m;
}
#define FETCH(op, bits) \
Memory *__remill_fetch_and_##op##_##bits(Memory *m, addr_t a, uint##bits##_t &value) { \
  value = __atomic_fetch_##op(reinterpret_cast<uint##bits##_t *>(a), value, __ATOMIC_SEQ_CST); return m; }
#define FETCH_ALL(op) FETCH(op, 8) FETCH(op, 16) FETCH(op, 32) FETCH(op, 64)
FETCH_ALL(add) FETCH_ALL(sub) FETCH_ALL(and) FETCH_ALL(or) FETCH_ALL(xor) FETCH_ALL(nand)
#undef FETCH_ALL
#undef FETCH
}
