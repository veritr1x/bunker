/* Distinct callees keep Clang's switch as executable branches, not a value LUT. */
#include <stdint.h>
#define OP(n) __attribute__((noinline)) static uint64_t action##n(uint64_t value) { \
    __asm__ volatile("" : "+r"(value)); return (value ^ (UINT64_C(0x193ab7) * ((n) + 1))) + (n); }
OP(0) OP(1) OP(2) OP(3) OP(4) OP(5) OP(6) OP(7) OP(8) OP(9)
OP(10) OP(11) OP(12) OP(13) OP(14) OP(15) OP(16) OP(17) OP(18) OP(19)
#ifdef SWITCH_WIDE_CASES
static volatile uint64_t switch_padding;
#define V8(n) switch_padding+=(n)+1; switch_padding+=(n)+1; switch_padding+=(n)+1; switch_padding+=(n)+1; \
              switch_padding+=(n)+1; switch_padding+=(n)+1; switch_padding+=(n)+1; switch_padding+=(n)+1;
#define PAD(n) V8(n) V8(n) V8(n) V8(n) V8(n) V8(n) V8(n) V8(n)
#else
#define PAD(n)
#endif
#define CASE(n) case n: PAD(n) return action##n(value);
__attribute__((noinline)) uint64_t switch_dispatch(uint32_t selector, uint64_t value) {
    switch (selector) {
        CASE(0) CASE(1) CASE(2) CASE(3) CASE(4) CASE(5) CASE(6) CASE(7) CASE(8) CASE(9)
        CASE(10) CASE(11) CASE(12) CASE(13) CASE(14) CASE(15) CASE(16) CASE(17) CASE(18) CASE(19)
        default: return value ^ UINT64_C(0xfedcba9876543210);
    }
}
