#include <atomic>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
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

constexpr addr_t kReservationGranule = 64;
struct MemoryVersion {
  uint64_t epoch = 0;
  bool exhausted = false;
};
struct Reservation {
  addr_t address = 0;
  uint64_t size = 0;
  uint128_t value = 0;
  uint64_t epoch = 0;
  bool pair = false;
  std::shared_ptr<MemoryVersion> version;
};
struct ExecutionContext {
  State *state;
  Reservation reservation;
  ExecutionContext *previous;
};
thread_local ExecutionContext *execution;
struct MemoryTracking {
  std::mutex lock;
  // Only currently reserved granules have entries; ordinary game heap writes
  // do not allocate a permanent version record for every address they touch.
  std::map<addr_t, std::weak_ptr<MemoryVersion>> versions;
};
MemoryTracking &memory_tracking() {
  static MemoryTracking tracking;
  return tracking;
}
void check_range(addr_t address, size_t size) {
  if (size && size - 1 > std::numeric_limits<addr_t>::max() - address)
    throw std::invalid_argument("guest memory range overflows address space");
}
void invalidate_unlocked(addr_t address, size_t size) {
  if (!size) return;
  auto &versions = memory_tracking().versions;
  const addr_t first = address & ~(kReservationGranule - 1);
  const addr_t last = (address + size - 1) & ~(kReservationGranule - 1);
  for (auto it = versions.lower_bound(first); it != versions.end() && it->first <= last;) {
    auto version = it->second.lock();
    if (!version) {
      it = versions.erase(it);
    } else if (version->epoch == std::numeric_limits<uint64_t>::max()) {
      // Retire the object instead of wrapping and accidentally accepting ABA.
      version->exhausted = true;
      it = versions.erase(it);
    } else {
      ++version->epoch;
      ++it;
    }
  }
}
void clear_reservation_unlocked(Reservation &reservation) {
  if (reservation.version && reservation.version.use_count() == 1) {
    auto &versions = memory_tracking().versions;
    auto it = versions.find(reservation.address & ~(kReservationGranule - 1));
    if (it != versions.end() && it->second.lock() == reservation.version) versions.erase(it);
  }
  reservation = Reservation{};
}
void clear_current_reservation() {
  if (!execution) return;
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  clear_reservation_unlocked(execution->reservation);
}
ExecutionContext &exclusive_context(State &state, addr_t address, uint64_t size, bool pair = false) {
  if (!execution || execution->state != &state) fail("exclusive access outside active execution", address);
  if (pair ? (size != 8 && size != 16) : (size != 1 && size != 2 && size != 4 && size != 8))
    fail("unsupported exclusive access width", address);
  if (address % size) fail("unaligned exclusive access", address);
  return *execution;
}

template <typename T> uint64_t exclusive_load_unlocked(addr_t address) {
  return __atomic_load_n(reinterpret_cast<const T *>(address), __ATOMIC_SEQ_CST);
}
template <typename T> bool exclusive_store_unlocked(addr_t address, uint64_t expected, uint64_t desired) {
  T previous = static_cast<T>(expected);
  return __atomic_compare_exchange_n(reinterpret_cast<T *>(address), &previous, static_cast<T>(desired),
                                     false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}
void reserve_unlocked(ExecutionContext &context, addr_t address, uint64_t size, uint128_t value, bool pair) {
  auto &slot = memory_tracking().versions[address & ~(kReservationGranule - 1)];
  auto version = slot.lock();
  if (!version) slot = version = std::make_shared<MemoryVersion>();
  context.reservation = {address, size, value, version->epoch, pair, version};
}
template <typename T> T load(addr_t address) {
  T value;
  recomp::ReadGuestMemory(&value, address, sizeof(value));
  return value;
}
template <typename T> Memory *store(Memory *memory, addr_t address, T value) {
  recomp::WriteGuestMemory(address, &value, sizeof(value));
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

void recomp::ReadGuestMemory(void *destination, addr_t address, size_t size) {
  check_range(address, size);
  if (!size) return;
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  std::memmove(destination, reinterpret_cast<const void *>(address), size);
}
void recomp::WithGuestMemoryRead(const std::function<void()> &read) {
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  read();
}
void recomp::WriteGuestMemory(addr_t address, const void *source, size_t size) {
  check_range(address, size);
  if (!size) return;
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  invalidate_unlocked(address, size);
  std::memmove(reinterpret_cast<void *>(address), source, size);
}
void recomp::WithGuestMemoryWrite(addr_t address, size_t size, const std::function<void()> &write) {
  check_range(address, size);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  // Invalidate before invoking the write, including its partial effects if it
  // throws. The callback must not reenter this non-recursive memory protocol.
  invalidate_unlocked(address, size);
  write();
}
void recomp::InvalidateGuestMemory(addr_t address, size_t size) {
  check_range(address, size);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  invalidate_unlocked(address, size);
}

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
std::vector<State *> recomp::CurrentExecutionFrames(State &top) {
  if (!execution || execution->state != &top)
    throw std::invalid_argument("execution frames requested outside current target State");
  std::vector<State *> frames;
  for (auto *frame = execution; frame; frame = frame->previous) frames.push_back(frame->state);
  return frames;
}
State *recomp::CurrentExecutionState() noexcept { return execution ? execution->state : nullptr; }
Memory *recomp::Runtime::Run(State &state, addr_t address, Memory *memory) {
  clear_current_reservation();
  ExecutionContext context{&state, {}, execution};
  struct Scope {
    Runtime *previous;
    ExecutionContext *previous_execution;
    int denormal;
    fenv_t environment;
    Scope() : previous(active), previous_execution(execution), denormal(explicit_denormal) { std::fegetenv(&environment); }
    ~Scope() {
      clear_current_reservation();
      active = previous;
      execution = previous_execution;
      explicit_denormal = denormal;
      std::fesetenv(&environment);
    }
  } scope;
  active = this;
  execution = &context;
  std::feclearexcept(FE_ALL_EXCEPT);
  explicit_denormal = 0;
  std::fesetround(host_rounding(state.fpcr.rmode));
  return Dispatch(state, address, memory);
}
Memory *recomp::Runtime::Dispatch(State &state, addr_t address, Memory *memory) {
  if (auto found = traces_.find(address); found != traces_.end())
    return found->second(state, address, memory);
  if (auto found = imports_.find(address); found != imports_.end()) {
    clear_current_reservation();
    struct ImportReservationScope {
      ~ImportReservationScope() { clear_current_reservation(); }
    } import_reservation_scope;
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
  std::fprintf(stderr, "recomp: unresolved indirect context target=%#llx StatePC=%#llx LR=%#llx SP=%#llx\n", static_cast<unsigned long long>(address), static_cast<unsigned long long>(state.gpr.pc.qword), static_cast<unsigned long long>(state.gpr.x30.qword), static_cast<unsigned long long>(state.gpr.sp.qword));
  fail("unresolved indirect target", address);
}

extern "C" {
uint64_t __remill_aarch64_load_exclusive(State &state, addr_t address, uint64_t size, uint64_t) {
  auto &context = exclusive_context(state, address, size);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  clear_reservation_unlocked(context.reservation);
  uint64_t value = 0;
  switch (size) {
    case 1: value = exclusive_load_unlocked<uint8_t>(address); break;
    case 2: value = exclusive_load_unlocked<uint16_t>(address); break;
    case 4: value = exclusive_load_unlocked<uint32_t>(address); break;
    case 8: value = exclusive_load_unlocked<uint64_t>(address); break;
  }
  reserve_unlocked(context, address, size, value, false);
  return value;
}
uint32_t __remill_aarch64_store_exclusive(State &state, addr_t address, uint64_t value, uint64_t size, uint64_t) {
  auto &context = exclusive_context(state, address, size);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  const auto &reservation = context.reservation;
  bool success = reservation.version && !reservation.pair && reservation.address == address && reservation.size == size &&
                 !reservation.version->exhausted && reservation.version->epoch == reservation.epoch;
  if (success) {
    switch (size) {
      case 1: success = exclusive_store_unlocked<uint8_t>(address, static_cast<uint64_t>(reservation.value), value); break;
      case 2: success = exclusive_store_unlocked<uint16_t>(address, static_cast<uint64_t>(reservation.value), value); break;
      case 4: success = exclusive_store_unlocked<uint32_t>(address, static_cast<uint64_t>(reservation.value), value); break;
      case 8: success = exclusive_store_unlocked<uint64_t>(address, static_cast<uint64_t>(reservation.value), value); break;
    }
    if (success) invalidate_unlocked(address, size);
  }
  clear_reservation_unlocked(context.reservation);
  return success ? 0 : 1;
}
void __remill_aarch64_clear_exclusive(State &state) {
  if (!execution || execution->state != &state) fail("clear exclusive outside active execution", state.gpr.pc.qword);
  clear_current_reservation();
}
void __remill_aarch64_load_exclusive_pair(State &state, addr_t address, uint64_t element_size, uint64_t,
                                         uint64_t *first, uint64_t *second) {
  if (element_size != 4 && element_size != 8) fail("unsupported exclusive pair element width", address);
  if (!first || !second) fail("invalid exclusive pair output", address);
  auto &context = exclusive_context(state, address, element_size * 2, true);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  clear_reservation_unlocked(context.reservation);
  uint128_t value = 0;
  if (element_size == 4) value = exclusive_load_unlocked<uint64_t>(address);
  else __atomic_load(reinterpret_cast<const uint128_t *>(address), &value, __ATOMIC_SEQ_CST);
  reserve_unlocked(context, address, element_size * 2, value, true);
  const unsigned bits = element_size * 8;
  const uint64_t mask = element_size == 4 ? UINT64_C(0xffffffff) : ~UINT64_C(0);
  *first = static_cast<uint64_t>(value) & mask;
  *second = static_cast<uint64_t>(value >> bits) & mask;
}
uint32_t __remill_aarch64_store_exclusive_pair(State &state, addr_t address, uint64_t first, uint64_t second,
                                              uint64_t element_size, uint64_t) {
  if (element_size != 4 && element_size != 8) fail("unsupported exclusive pair element width", address);
  auto &context = exclusive_context(state, address, element_size * 2, true);
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  const auto &reservation = context.reservation;
  bool success = reservation.version && reservation.pair && reservation.address == address &&
                 reservation.size == element_size * 2 && !reservation.version->exhausted &&
                 reservation.version->epoch == reservation.epoch;
  if (success) {
    if (element_size == 4) {
      const uint64_t desired = uint64_t(static_cast<uint32_t>(first)) | (uint64_t(static_cast<uint32_t>(second)) << 32);
      success = exclusive_store_unlocked<uint64_t>(address, static_cast<uint64_t>(reservation.value), desired);
    } else {
      uint128_t expected = reservation.value;
      uint128_t desired = uint128_t(first) | (uint128_t(second) << 64);
      success = __atomic_compare_exchange(reinterpret_cast<uint128_t *>(address), &expected, &desired,
                                          false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
    }
    if (success) invalidate_unlocked(address, element_size * 2);
  }
  clear_reservation_unlocked(context.reservation);
  return success ? 0 : 1;
}
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
  std::lock_guard<std::mutex> lock(memory_tracking().lock); \
  if (__atomic_compare_exchange_n(reinterpret_cast<uint##bits##_t *>(a), &expected, desired, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) \
    invalidate_unlocked(a, sizeof(desired)); \
  return m; }
CMPXCHG(8) CMPXCHG(16) CMPXCHG(32) CMPXCHG(64)
#undef CMPXCHG
Memory *__remill_compare_exchange_memory_128(Memory *m, addr_t a, uint128_t &expected, uint128_t &desired) {
  std::lock_guard<std::mutex> lock(memory_tracking().lock);
  if (__atomic_compare_exchange(reinterpret_cast<uint128_t *>(a), &expected, &desired, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST))
    invalidate_unlocked(a, sizeof(desired));
  return m;
}
#define FETCH(op, bits) \
Memory *__remill_fetch_and_##op##_##bits(Memory *m, addr_t a, uint##bits##_t &value) { \
  std::lock_guard<std::mutex> lock(memory_tracking().lock); \
  value = __atomic_fetch_##op(reinterpret_cast<uint##bits##_t *>(a), value, __ATOMIC_SEQ_CST); \
  invalidate_unlocked(a, sizeof(value)); return m; }
#define FETCH_ALL(op) FETCH(op, 8) FETCH(op, 16) FETCH(op, 32) FETCH(op, 64)
FETCH_ALL(add) FETCH_ALL(sub) FETCH_ALL(and) FETCH_ALL(or) FETCH_ALL(xor) FETCH_ALL(nand)
#undef FETCH_ALL
#undef FETCH
}
