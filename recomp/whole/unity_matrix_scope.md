# Exact Unity matrix execution gate

This gate executes the original 104 bytes at Unity RVA `[0x91bce0,0x91bd48)`.
The pinned ELF SHA256 is
`3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f`;
the extracted function SHA256 is
`b48e85dc743d429026ca348a1c1becc34a52e21daa37807e462311f987dd6a7f`.

The extracted bytes are copied unchanged into a separate fixture. Its relocated
guest address is recorded in `extraction.json`. This is safe for this exact leaf:
its 26 instructions consist only of LD1, FMUL, FMLA, ST1 and the final RET. There
are no PC-relative operands, globals, stack accesses, calls or interior control
transfers. The extraction and linked fixture are both hash checked. The test
does not claim execution at the original ELF address or a complete Unity run.

## Proven ABI and order

X0 and X1 each address 64 readable bytes, and X2 addresses 64 writable bytes.
All three advance by 64. Every input load precedes the first output store.
For flat float32 arrays A, B and C, the routine computes each `C[4*k+r]` by:

1. Rounded multiply `A[r] * B[4*k]`.
2. Fused accumulate `A[4+r] * B[4*k+1]`.
3. Fused accumulate `A[8+r] * B[4*k+2]`.
4. Fused accumulate `A[12+r] * B[4*k+3]`.

This corresponds to column-major A×B. The test derives its independent bounded
integer formula from these accesses, rather than assuming a C++ matrix type.
An archived noncommuting example produces A×B element0=20 and B×A element0=-3.

The wrapper captures all 31 general registers, SP, all 32 full SIMD registers,
FPCR, FPSR and NZCV. Only pointer deltas, SP delta and the return-address delta
are normalized across fixture placements. Source/result bits and status outputs
remain unmasked. NZCV setup/capture uses CCMP/CSET; the FPSR input is explicitly
zero-extended before MSR. The original 104-byte function contains no wrapper code.

## Accepted finite profile

The baseline gate passes **36,928 records per host** on lifted Linux and native
Windows, matching actual ARM64 QEMU byte for byte:

- Identity and signed small-integer matrices, checked independently by integer
  multiplication and accumulation.
- Finite-normal random matrices with nonexact arithmetic.
- All 16 rounding/FZ/DN combinations and zero/preset cumulative FPSR, with NZCV
  patterns 0xA and 0x5.
- 18 disjoint, in-place, partial-overlap and unaligned pointer layouts.
- Entire memory arenas and record canaries, plus 64 page-guard records placing
  exactly64-byte ranges at the beginning or end of accessible pages.
- Unchanged unrelated general/SIMD registers, source snapshots, pointer
  increments, SP/LR, FPCR and NZCV. Integer cases preserve FPSR exactly;
  finite-normal cases may additionally accumulate IXC.

The finite ARM64/Linux/Windows output SHA256 is
`68387a0af7fff38a6754ff389ff9b913feb25ba5084a033c2f95e21a1df57432`.
The frozen baseline lifter/semantics hashes are respectively
`78e33b4cc37e8b2d34e7b6f2adf2a549ccc2590199f8c41a9758a039e09a5a54`
and `c6a6a752edfde4ccc6de252a52d58b87986f461b130869dac9a7241bc32e2b69`.

## Nonfinite/FZ baseline and indexed FMUL correction

The original baseline diagnostic had **5,368 of 18,432 records differ on each
host**. Its first difference was record2, FPCR.FZ=1:
result bits agree, but ARM64 FPSR=0x81 and lifted FPSR=0x99, adding UFC and IXC.
Those raw failures and the six-file source cohort from Bunker `fb2acfd` and
Remill `79081a6` are preserved under the native WSL work directory
`unity-matrix-fmul-baseline`, including `source/cohort.json` and both reports.
The earlier failure has not been reclassified as a passing baseline.

An isolated witness executes the original first FMUL opcode `0x4f809214` without
any FMLA. ARM64 and both lifted hosts show these baseline differences:

| Inputs / control | ARM64 result / FPSR | Lifted result / FPSR |
| --- | --- | --- |
| +0 × +infinity | 0x7fc00000 / 0x01 | 0xffc00000 / 0x01 |
| min-subnormal × 1, FZ=1 | 0x00000000 / 0x80 | 0x00000001 / 0x00 |
| min-normal × 0.5, FZ=1 | 0x00000000 / 0x08 | 0x00400000 / 0x00 |
| qNaN0x7fc12345 × 1, DN=1 | 0x7fc00000 / 0x00 | 0x7fc12345 / 0x00 |

The indexed-only FMUL correction now matches ARM64 on all seven isolated witness
rows on both hosts. The gate itself changes no semantics; the separate correction
routes only indexed FP32/FP64 FMUL through the validated integer fused helper with
a zero accumulator carrying the product sign. Ordinary scalar/vector FMUL and
scalar FMADD remain unchanged. Baseline witness artifacts are under ignored
`work/unity-matrix-fmul-witness`; corrected witnesses are under
`work/unity-matrix-fmul-fixed-witness`.

With corrected semantics SHA256
`098d2e4b3214af9b3e4a7a39053acf44bc04ab94527b549874fd7d69710bab1e`,
**both hosts pass all36,928 finite and all18,432 nonfinite/FZ diagnostic records,
with zero differences**. The finite output hash remains unchanged. The diagnostic
ARM64/Linux/Windows output SHA256 is
`07c6657562be0983f3c449217ad138ad8cefeaf37d605b939522eb358355030d`.
This remains bounded coverage of this exact routine and these input profiles.

## Reproduce

Run with the task Python environment containing pyelftools and capstone5:

```sh
python recomp/whole/test_unity_matrix.py \
  --unity /home/sattam/bunker-recomp/recomp/work/lib/libunity.so \
  --lift /home/sattam/bunker-recomp/recomp/work/remill-src/build-native/bin/lift/remill-lift-18 \
  --reference-root /home/sattam/bunker-recomp/recomp/work/reference-tools/root \
  --record-directory /home/sattam/bunker-recomp/recomp/work/unity-matrix-records
```

Add `--windows` for native Windows. Large binary streams stay on the native
Linux filesystem. Each platform writes a separate `acceptance.json` under
`recomp/work/unity-matrix-{linux,windows}`, retaining both profile outcomes,
source/toolchain hashes, extraction proof and diagnostic mismatch samples.
The runner now fails on any difference in either profile or any invariant
failure. For explicit observation of an archived baseline only,
`--allow-diagnostic-differences` permits a nonzero diagnostic mismatch count;
it remains printed as `DIFFERENT` and recorded as `passed:false`. That flag
cannot suppress a finite-profile difference.
