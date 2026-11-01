# Indexed FP32/FP64 FMUL correction

The validated Remill checkpoint is `dccbaa8`.

Only the already decoded indexed forms are changed:
`FMUL_ASIMDELEM_R_SD_{2S,4S,2D}` and `FMUL_ASISDELEM_R_SD_{S,D}`.
The implementation change is confined to `MAKE_FMUL_ELEM` in AArch64
`Semantics/BINARY.cpp`. Decoders, ordinary scalar/vector FMUL, scalar FMADD and
the validated `FP_FUSED_INDEXED.cpp` helper remain unchanged. FP16, FMULX,
alternative FP behavior and exception traps are outside this scope.

## Arithmetic

Each lane uses `IndexedFusedFPBits(state, (lhs ^ rhs) & sign, lhs, rhs)`.
The accumulator is a signed zero with the exact product sign. For a nonzero
product, adding zero changes no exact value or final rounding. For a zero
product, equal zero signs preserve the product sign in every rounding mode;
using an unconditional positive zero would incorrectly change negative zero.

The accumulator is never a NaN or infinity. Therefore the fused helper's
remaining NaN priority reduces to lhs then rhs, the invalid zero×infinity case
produces ARM's positive default NaN, and no accumulator-specific invalid case
can arise. The unchanged integer helper supplies input FZ/IDC, DN/default NaN,
signaling NaNs, exact significand multiplication, tininess before rounding,
output flushing, all four rounding modes and cumulative FPSR flags. No host FP
operation can canonicalize source NaNs or add host denormal behavior.

All sources are read before any destination write. Scalar and Q=0 destinations
clear unused bits; indexed sources retain all128 bits so high lanes remain
available for Q=0 operations and overlapping destinations.

## Validation

Actual ARM64 QEMU is compared with lifted Linux and native Windows:

- 97 variants: every legal shape/index combination, six overlap/high-register
  arrangements, and original Unity opcode `0x4f809214`.
- All38×38 raw edge pairs for every variant, including signed zeros,
  subnormals, normal boundaries, infinities and NaN signs/payloads.
- 1,024 deterministic random raw pairs per variant/control/status combination.
- Every finite normal exponent for representative FP32/FP64 forms, with
  halfway, underflow, overflow, extreme exponent and subnormal boundaries.
- All16 rounding/FZ/DN combinations, zero/preset cumulative FPSR, and NZCV
  patterns0xA/0x5.
- Full destination and source bits, full FPSR and full NZCV outputs.

**8,444,032 records pass on each host**, with97 strict lifted traces and zero
unsupported instructions or unresolved direct targets. The ARM64/Linux/Windows
record SHA256 is
`dc745379b99b98d1c243d39761d4e01d98e2938ded871686a9a22424155b54b3`.

The exact unchanged104-byte Unity matrix routine additionally passes36,928
finite and18,432 nonfinite/FZ records per host with zero differences. Its
previous5,368 diagnostic failures remain archived as a separate baseline;
see `unity_matrix_scope.md`. The seven readable original-opcode witness rows
also match on both hosts. A full Windows indexed FMLA regression passes all
5,689,856 records using the new frozen module, with its original golden hash
`a444433a33f0c5485aefa66d84c0c7dab6ecda1b374d565ebdb148e2b7ef4596`.

Validated lifter SHA256:
`78e33b4cc37e8b2d34e7b6f2adf2a549ccc2590199f8c41a9758a039e09a5a54`.
Validated semantics SHA256:
`098d2e4b3214af9b3e4a7a39053acf44bc04ab94527b549874fd7d69710bab1e`.

## Reproduce

Use the task Python environment and installed clang18/reference sysroot:

```sh
python recomp/whole/test_fp_fmul_indexed.py \
  --reference-root /home/user/bunker-recomp/recomp/work/reference-tools/root \
  --record-directory /home/user/bunker-recomp/recomp/work/fp-fmul-indexed-records \
  --lift /home/user/bunker-recomp/recomp/work/remill-src/build-native/bin/lift/remill-lift-18
```

Add `--windows` for native Windows. `--reference-only` generates just the ARM64
oracle; `--reference-file` reuses its full source/hash-verified binary stream.
Each platform writes a separate hash-backed `acceptance.json` under ignored
`work/fp-fmul-indexed-{linux,windows}`. Large records stay in the explicit native
Linux record directory. The existing full-output wrapper ABI is reused from
`fp_fmla_cases.py`; no FMLA fixture is modified.
