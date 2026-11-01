# ARMv8 reciprocal estimates

`FP_ESTIMATES.cpp` in the local Remill fork implements FP32/FP64 `FRECPE` and
`FRSQRTE`: scalar S/D and vector 2S/4S/2D, including in-place destinations.
Scalar and 64-bit vector destinations clear the unused upper Q-register bits.
The implementation computes the architecture's midpoint estimate tables with
integer arithmetic, independently of the host floating-point environment.
It handles NaN payload/sign propagation, signaling NaNs, signed zero,
infinities, gradual input/output underflow, reciprocal overflow rounding,
FZ/DN, and cumulative FPSR flags.

The table mathematics is described in Arm DDI 0406C.d, section A2.7's
reciprocal and reciprocal-square-root estimate definitions:
[Arm architecture reference](https://documentation-service.arm.com/static/5f8daeb7f86e16515cdb8c4e).
That older manual describes a different SIMD floating-point environment;
the FP32/FP64 AArch64 special cases and flags are checked separately through
actual AArch64 instructions under QEMU. No QEMU implementation code is copied.

`test_fp_estimate.py` builds an ARM64 shared-library fixture and reference
executable, translates the fixture, and compares full 128-bit register results
plus FPSR. On November 1, 2026, both native Windows x86_64 and Linux x86_64
matched **3,354,880 records each**, with 20 translated traces, zero unsupported
traces and zero unresolved direct targets. Coverage includes every estimate
bucket boundary at both exponent parities, normalized subnormal buckets,
all subnormal power boundaries, finite extremes, signed special values,
deterministic random inputs, 16 FPCR modes and two initial FPSR values.

The raw result streams share SHA-256
`23a9314231f783d13d105ebd40531841070e2ebc587f472af5da0be5c9e540d5`.
Ignored `work/fp-estimate-{linux,windows}/result.json` records frozen lifter,
semantics and compiler hashes. Run from WSL with LLVM 18 and the reference
cross-toolchain/sysroot:

```sh
python recomp/whole/test_fp_estimate.py \
  --reference-root /path/to/reference-tools/root \
  --remill /path/to/remill-src --lift /path/to/remill-lift-18 \
  --cc clang-18 --cxx clang++-18
# Add --windows for the native MinGW executable.
```

This is baseline ARMv8 estimate support. FP16 and newer alternative/enhanced
precision controls remain unsupported. Physical ARM64 verification remains
useful. Existing Unity/IL2CPP translation snapshots do not automatically gain
these semantics; they retain their own frozen toolchains until rebuilt.
