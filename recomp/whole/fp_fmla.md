# Indexed FP32/FP64 fused multiply-add

Remill `79081a6` implements baseline scalar/vector indexed FMLA for S, D, 2S,
4S and 2D: all 16 legal shape/index combinations. FP16, FMLS, other fused
families, alternative FP modes and FP exception traps are outside this change.
The existing scalar FMADD helper is untouched.

The decoder reads the old destination explicitly, and semantics snapshot all
three register sources before writing. Scalar/Q0 results clear upper lanes.
An integer-only helper computes the exact product and addition with one final
rounding. A binary64 product needs at most 106 bits; normalization at bit 126
leaves at least 21 zero low bits. Close opposing terms therefore retain all
bits through cancellation. Exponent gaps large enough to discard bits prevent
deep cancellation, allowing a jammed bit to preserve rounding direction.
The helper handles signed zero, tininess before rounding, overflow, FZ/DN,
three-input NaN priorities and cumulative FPSR flags without host FP arithmetic.

The actual ARM64 QEMU reference includes the special invalid-product rule:
zero times infinity plus a quiet-NaN accumulator produces default NaN and IOC.
The independently written helper was checked against the reference output;
no QEMU implementation code was copied. Physical ARM64 validation remains
additional evidence rather than an asserted result.

Both lifted Linux x86_64 and native Windows pass **5,689,856 exact 64-byte
records each**, across 97 variants: all legal indices, six overlap/high-register
patterns and the exact original Unity opcode. Records compare full destination,
Rn/Rm bits, full FPSR and NZCV. Inputs cover representative 20-cubed edge
triples, deterministic raw triples, every finite normal exponent's cancellation/
tininess/overflow adversaries, all 16 rounding/FZ/DN combinations and both
zero/preset FPSR with NZCV A/5. PC and SP are checked separately.

The fixture uses CCMP/CSET for NZCV because MRS/MSR NZCV is unsupported. It
zero-extends the FPSR input before MSR: the preexisting SYSTEM helper retains
reserved high input bits, which is a separate remaining issue. Output FPSR is
compared in full without masking.

Seven decoding/original-code controls pass, including rejection of reserved
Q0D and D/L1 encodings. The original pinned Unity matrix at `0x7091bce0`,
containing indexed FMLA `4fa01234` at `0x7091bd08`, now lifts completely with
no error/missing blocks. This proves liftability, not execution of that matrix
or adoption of new semantics by the frozen whole-Unity cohort.

| Frozen artifact | SHA-256 |
| --- | --- |
| Lifter | `78e33b4cc37e8b2d34e7b6f2adf2a549ccc2590199f8c41a9758a039e09a5a54` |
| Semantics | `c6a6a752edfde4ccc6de252a52d58b87986f461b130869dac9a7241bc32e2b69` |
| ARM64/Linux/Windows output | `a444433a33f0c5485aefa66d84c0c7dab6ecda1b374d565ebdb148e2b7ef4596` |

```sh
python recomp/whole/test_fp_fmla.py --reference-root <ARM64-reference-root> --lift <remill-lift> --record-directory <native-WSL-output>
python recomp/whole/test_fp_fmla.py --reference-root <ARM64-reference-root> --lift <remill-lift> --windows --record-directory <native-WSL-output>
python recomp/whole/test_fp_fmla_decode.py --lift <remill-lift> --unity <original-libunity.so>
```

`--reference-file` permits sharing an oracle only after checking source/QEMU
provenance and its complete hash. Ignored evidence is under
`work/fp-fmla-{linux,windows}/` and `work/fp-fmla-decode/`.
