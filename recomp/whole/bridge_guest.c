// Compiler-generated AAPCS64 callers: the host test never packs their import
// argument registers/stack itself, so these test the bridge against Clang's ABI.
#include <stdint.h>

extern uint64_t host_mixed(uint64_t, double, uint32_t, float, const float *, double,
    int8_t, float, uint16_t, double, int64_t, float, uint32_t, double, int16_t,
    float, uint64_t, double, uint64_t, float);
extern uint64_t host_gp9_fp1(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
    uint64_t, uint64_t, uint64_t, uint64_t, double);
extern uint64_t host_fp9_gp1(double, double, double, double, double, double,
    double, double, double, uint64_t);
extern float host_float(uint32_t);
extern double host_double(uint64_t);
extern int8_t host_narrow(int8_t);
extern void host_write(uint32_t *, int16_t);
extern uint64_t host_outer(uint64_t);
extern uint64_t host_inner(uint64_t);

uint64_t guest_mixed(uint64_t seed, const double *d, const float *f) {
    return host_mixed(seed, d[0], (uint32_t)(seed >> 1), f[1], f + 3, d[2],
        (int8_t)seed, f[3], (uint16_t)(seed >> 16), d[4],
        (int64_t)(seed ^ UINT64_C(0x123456789abcdef0)), f[5], (uint32_t)(seed >> 3),
        d[6], (int16_t)(seed >> 9), f[7], seed + 9, d[8],
        seed ^ UINT64_C(0xdeadbeef12345678), f[9]) + 5;
}
uint64_t guest_gp9_fp1(uint64_t seed, const double *d) {
    return host_gp9_fp1(1, 2, 3, 4, 5, 6, 7, 8, seed, d[0]);
}
uint64_t guest_fp9_gp1(uint64_t seed, const double *d) {
    return host_fp9_gp1(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], seed);
}
float guest_float(uint32_t bits) { return host_float(bits); }
double guest_double(uint64_t bits) { return host_double(bits); }
int8_t guest_narrow(int8_t value) { return host_narrow(value); }
void guest_write(uint32_t *target, int16_t value) { host_write(target, value); }
uint64_t guest_inner(uint64_t seed) { return host_inner(seed) + 3; }
uint64_t guest_nested(uint64_t seed) { return host_outer(seed) + host_inner(seed + 1); }
