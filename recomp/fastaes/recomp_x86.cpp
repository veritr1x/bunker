// x86_64 side: runs the Remill-lifted libFastAES code natively.
//
// The original image is mapped at the same base as on ARM64, but only as data
// (S-boxes, GOT). Lifted code reads and writes host memory directly, so guest
// and host pointers are the same. Each export gets a wrapper that loads the
// arguments into an emulated AArch64 register file and calls the lifted entry.
// Imports resolve to marker addresses; reaching one through __remill_jump or
// __remill_function_call runs the host function on the guest's registers.
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>

#include "remill/Arch/AArch64/Runtime/State.h"
#include "remill/Arch/Runtime/Intrinsics.h"

#include "cases.h"
#include "elfload.h"

extern "C" {
Memory *enc_sub_1000066c(State &, addr_t, Memory *);
Memory *dec_sub_10001220(State &, addr_t, Memory *);
}

namespace {

constexpr addr_t kImportBase = 0xfeed0000, kReturnMarker = 0xfeedffff;
enum Import { kMemcpy, kMemset, kStackChkFail, kCxaAtexit, kCxaFinalize, kImportCount };
const char *const kImportNames[kImportCount] = {"memcpy", "memset", "__stack_chk_fail", "__cxa_atexit", "__cxa_finalize"};

alignas(16) uint8_t stack[1 << 20];
alignas(16) uint8_t tls[256];  // TPIDR_EL0 points here; the stack guard sits at +0x28.

void *resolve(const char *name) {
    for (int i = 0; i < kImportCount; i++)
        if (!strcmp(name, kImportNames[i])) return reinterpret_cast<void *>(kImportBase + i);
    return nullptr;
}

// Runs an import on the guest's argument registers (AAPCS64: x0-x7 in, x0 out).
bool host_call(State &state, addr_t target) {
    if (target < kImportBase || target >= kImportBase + kImportCount) return false;
    auto &r = state.gpr;
    switch (target - kImportBase) {
    case kMemcpy:
        r.x0.qword = reinterpret_cast<uint64_t>(memcpy(reinterpret_cast<void *>(r.x0.qword),
                                                       reinterpret_cast<void *>(r.x1.qword), r.x2.qword));
        break;
    case kMemset:
        r.x0.qword = reinterpret_cast<uint64_t>(memset(reinterpret_cast<void *>(r.x0.qword), r.x1.dword, r.x2.qword));
        break;
    case kStackChkFail:
        fprintf(stderr, "recomp: stack guard check failed\n");
        abort();
    default:
        r.x0.qword = 0;
    }
    state.gpr.pc.qword = r.x30.qword;
    return true;
}

[[noreturn]] void fail(const char *what, addr_t pc) {
    fprintf(stderr, "recomp: %s at %#lx\n", what, static_cast<unsigned long>(pc));
    abort();
}

uint64_t call(Memory *(*entry)(State &, addr_t, Memory *), addr_t pc, std::initializer_list<uint64_t> args) {
    static Reg GPR::*const kArgs[] = {&GPR::x0, &GPR::x1, &GPR::x2, &GPR::x3, &GPR::x4, &GPR::x5, &GPR::x6, &GPR::x7};
    State state{};
    int i = 0;
    for (auto arg : args) (state.gpr.*kArgs[i++]).qword = arg;
    state.gpr.sp.qword = reinterpret_cast<uint64_t>(stack + sizeof stack);
    state.gpr.x30.qword = kReturnMarker;
    state.gpr.pc.qword = pc;
    state.sr.tpidr_el0.qword = reinterpret_cast<uint64_t>(tls);
    entry(state, pc, nullptr);
    return state.gpr.x0.qword;
}

uint32_t enc(uint8_t *out, void *unused, const uint8_t *in, uint32_t len, const uint8_t *key, uint32_t key_len,
             const uint8_t *iv, uint8_t padding) {
    return call(enc_sub_1000066c, BASE + 0x66c,
                {(uint64_t)out, (uint64_t)unused, (uint64_t)in, len, (uint64_t)key, key_len, (uint64_t)iv, padding});
}

uint32_t dec(uint8_t *out, const uint8_t *in, uint32_t len, const uint8_t *key, uint32_t key_len, const uint8_t *iv,
             uint8_t padding) {
    return call(dec_sub_10001220, BASE + 0x1220,
                {(uint64_t)out, (uint64_t)in, len, (uint64_t)key, key_len, (uint64_t)iv, padding});
}

template <typename T> T load(addr_t addr) {
    T value;
    memcpy(&value, reinterpret_cast<void *>(addr), sizeof value);
    return value;
}

template <typename T> Memory *store(Memory *memory, addr_t addr, T value) {
    memcpy(reinterpret_cast<void *>(addr), &value, sizeof value);
    return memory;
}

}  // namespace

int main() {
    elf_image image;
    if (elf_load(LIB, BASE, resolve, &image)) return 1;
    return run_cases(enc, dec);
}

// Remill's runtime interface. Memory is the host's own, so reads and writes go straight through.
extern "C" {
uint8_t __remill_read_memory_8(Memory *, addr_t a) { return load<uint8_t>(a); }
uint16_t __remill_read_memory_16(Memory *, addr_t a) { return load<uint16_t>(a); }
uint32_t __remill_read_memory_32(Memory *, addr_t a) { return load<uint32_t>(a); }
uint64_t __remill_read_memory_64(Memory *, addr_t a) { return load<uint64_t>(a); }
float32_t __remill_read_memory_f32(Memory *, addr_t a) { return load<float32_t>(a); }
float64_t __remill_read_memory_f64(Memory *, addr_t a) { return load<float64_t>(a); }
float64_t __remill_read_memory_f80(Memory *, addr_t a) { fail("80-bit float read", a); }
float64_t __remill_read_memory_f128(Memory *, addr_t a) { fail("128-bit float read", a); }
Memory *__remill_write_memory_8(Memory *m, addr_t a, uint8_t v) { return store(m, a, v); }
Memory *__remill_write_memory_16(Memory *m, addr_t a, uint16_t v) { return store(m, a, v); }
Memory *__remill_write_memory_32(Memory *m, addr_t a, uint32_t v) { return store(m, a, v); }
Memory *__remill_write_memory_64(Memory *m, addr_t a, uint64_t v) { return store(m, a, v); }
Memory *__remill_write_memory_f32(Memory *m, addr_t a, float32_t v) { return store(m, a, v); }
Memory *__remill_write_memory_f64(Memory *m, addr_t a, float64_t v) { return store(m, a, v); }
Memory *__remill_write_memory_f80(Memory *, addr_t a, float64_t) { fail("80-bit float write", a); }
Memory *__remill_write_memory_f128(Memory *, addr_t a, float64_t) { fail("128-bit float write", a); }

uint8_t __remill_undefined_8(void) { return 0; }
uint16_t __remill_undefined_16(void) { return 0; }
uint32_t __remill_undefined_32(void) { return 0; }
uint64_t __remill_undefined_64(void) { return 0; }
float32_t __remill_undefined_f32(void) { return 0; }
float64_t __remill_undefined_f64(void) { return 0; }

Memory *__remill_error(State &, addr_t pc, Memory *) { fail("unliftable instruction", pc); }
Memory *__remill_missing_block(State &, addr_t pc, Memory *) { fail("missing block", pc); }
Memory *__remill_function_return(State &, addr_t, Memory *m) { return m; }
Memory *__remill_function_call(State &s, addr_t pc, Memory *m) {
    if (!host_call(s, pc)) fail("indirect call to unknown target", pc);
    return m;
}
Memory *__remill_jump(State &s, addr_t pc, Memory *m) {
    // A PLT stub ends in `br x17` to the GOT entry: that is how imports arrive here.
    if (!host_call(s, pc)) fail("indirect jump to unknown target", pc);
    return m;
}
Memory *__remill_async_hyper_call(State &, addr_t pc, Memory *) { fail("async hyper call", pc); }
Memory *__remill_sync_hyper_call(State &s, Memory *, SyncHyperCall::Name) { fail("sync hyper call", s.gpr.pc.qword); }

Memory *__remill_barrier_load_load(Memory *m) { return __atomic_thread_fence(__ATOMIC_SEQ_CST), m; }
Memory *__remill_barrier_load_store(Memory *m) { return __atomic_thread_fence(__ATOMIC_SEQ_CST), m; }
Memory *__remill_barrier_store_load(Memory *m) { return __atomic_thread_fence(__ATOMIC_SEQ_CST), m; }
Memory *__remill_barrier_store_store(Memory *m) { return __atomic_thread_fence(__ATOMIC_SEQ_CST), m; }
Memory *__remill_atomic_begin(Memory *m) { return m; }
Memory *__remill_atomic_end(Memory *m) { return m; }
Memory *__remill_delay_slot_begin(Memory *m) { return m; }
Memory *__remill_delay_slot_end(Memory *m) { return m; }

#define CMPXCHG(bits)                                                                                          \
    Memory *__remill_compare_exchange_memory_##bits(Memory *m, addr_t a, uint##bits##_t &expected,           \
                                                    uint##bits##_t desired) {                                  \
        __atomic_compare_exchange_n(reinterpret_cast<uint##bits##_t *>(a), &expected, desired, false,          \
                                    __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);                                       \
        return m;                                                                                              \
    }
CMPXCHG(8) CMPXCHG(16) CMPXCHG(32) CMPXCHG(64)
Memory *__remill_compare_exchange_memory_128(Memory *m, addr_t a, uint128_t &expected, uint128_t &desired) {
    __atomic_compare_exchange(reinterpret_cast<uint128_t *>(a), &expected, &desired, false, __ATOMIC_SEQ_CST,
                              __ATOMIC_SEQ_CST);
    return m;
}

// The fetch-and-op intrinsics return the old value through `value`.
#define FETCH(op, bits)                                                                                        \
    Memory *__remill_fetch_and_##op##_##bits(Memory *m, addr_t a, uint##bits##_t &value) {                   \
        value = __atomic_fetch_##op(reinterpret_cast<uint##bits##_t *>(a), value, __ATOMIC_SEQ_CST);          \
        return m;                                                                                              \
    }
#define FETCH_ALL(op) FETCH(op, 8) FETCH(op, 16) FETCH(op, 32) FETCH(op, 64)
FETCH_ALL(add) FETCH_ALL(sub) FETCH_ALL(and) FETCH_ALL(or) FETCH_ALL(xor) FETCH_ALL(nand)

int __remill_fpu_exception_test_and_clear(int read_mask, int clear_mask) {
    int flags = fetestexcept(read_mask);
    feclearexcept(clear_mask);
    return flags;
}

uint8_t __remill_read_io_port_8(Memory *, addr_t a) { fail("I/O port read", a); }
uint16_t __remill_read_io_port_16(Memory *, addr_t a) { fail("I/O port read", a); }
uint32_t __remill_read_io_port_32(Memory *, addr_t a) { fail("I/O port read", a); }
Memory *__remill_write_io_port_8(Memory *, addr_t a, uint8_t) { fail("I/O port write", a); }
Memory *__remill_write_io_port_16(Memory *, addr_t a, uint16_t) { fail("I/O port write", a); }
Memory *__remill_write_io_port_32(Memory *, addr_t a, uint32_t) { fail("I/O port write", a); }
}
