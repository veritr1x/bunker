// Cross-compiled integration fixture for the whole-library dispatcher.
#include <stdint.h>
#define NOINLINE __attribute__((noinline))
typedef uint64_t (*operation)(uint64_t);
extern uint64_t fixture_host_add(uint64_t, uint64_t);
static uint64_t bias;
__attribute__((constructor)) static void initialize(void) { bias = 11; }
NOINLINE uint64_t add_bias(uint64_t x) { return x + bias; }
NOINLINE uint64_t twice(uint64_t x) { return x * 2; }
operation operations[] = {add_bias, twice};
static const char message[] __attribute__((aligned(4))) = "load";
static const char signature[] __attribute__((aligned(4))) = "(J)Z";
const char *messages[] = {message, signature};
extern unsigned char fixture_absolute[], fixture_absolute_zero[];
extern uint64_t fixture_optional(uint64_t) __attribute__((weak));
__asm__(".global fixture_absolute\n.set fixture_absolute, 0x12345678\n"
        ".global fixture_absolute_zero\n.set fixture_absolute_zero, 0\n");
void *absolute_pointers[] = {fixture_absolute, fixture_absolute_zero, fixture_absolute + 9};
operation optional_pointer = fixture_optional;
NOINLINE uint64_t absolute_value(uint64_t i) { return (uintptr_t)absolute_pointers[i]; }
NOINLINE uint64_t optional_value(uint64_t x) { return optional_pointer ? optional_pointer(x) : 97; }
NOINLINE uint64_t direct(uint64_t x) { return add_bias(x) + twice(x); }
NOINLINE uint64_t via_pointer(operation op, uint64_t x) { return op(x) + 7; }
NOINLINE uint64_t via_table(uint64_t i, uint64_t x) { return operations[i & 1](x) + 3; }
NOINLINE uint64_t tail_pointer(operation op, uint64_t x) { return op(x); }
NOINLINE uint64_t recursive(uint64_t n) {
  if (n == 0) return bias;
  return recursive(n - 1) + (n ^ bias);
}
NOINLINE uint64_t via_import(uint64_t a, uint64_t b) { return fixture_host_add(a, b) + 13; }
NOINLINE uint64_t text_byte(uint64_t i) { return (uint8_t)messages[i & 1][1]; }
