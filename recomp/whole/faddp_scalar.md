# Scalar floating-point pair addition

`FADDP S<d>, V<n>.2S` and `FADDP D<d>, V<n>.2D` snapshot the source and add its first two lanes. The scalar result clears the remaining destination bits, including aliases. Exact original word `7e30d800` occurs at Unity `70ae33bc` in the existing `70ae31f0` helper.

The two new selectors use the existing integer fused helper for `lane0 + (1 × lane1)`. The positive unit product is exact; this reuses ARM NaN priority, signed-zero, rounding, FZ/DN, and cumulative FPSR handling without changing existing arithmetic handlers. Half precision, enabled FP traps, and AFP merging are outside this profile.

The actual first family gate passed at `work/faddp-scalar-qualification1/acceptance.json`, SHA256 `7a799a7745ba530a93444b453e37759ee186611bd0408600899e9c51d6f96b06`. Eight instruction cores cover both widths, destination/source aliases and high registers. Each of ARM64, Linux, and Windows produced 16,384 matching records: 64 edge pairs × 16 FPCR rounding/FZ/DN combinations × two sticky-flag seeds per core, with all 16 NZCV values distributed across cases. Explicit cases cover NaN argument priority and signaling payloads, signed zero, cancellation, subnormals, minimum normals, and overflow. Each record includes result bits and FNV64 digests of the normalized full 800-byte before/after architectural snapshots; normalization only removes native address roles. Both hosts also pass eight independent, unnormalized full 1,200-byte raw-State comparisons and opaque memory-token checks. Input/output canaries and a genuine scalar load/store control pass. The decoder gate passes 2,057 rows, including every Rd/Rn combination for both forms, the exact original word, unsupported half forms and supported neighbors.

The frozen matched pair is `work/faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4`: lifter SHA256 `bce34d408b57a2eaa085194599fe20a0fd34325d0d34327426b6c226fd04253d`, semantics SHA256 `5d2fc4bb5f4c8be48e82c5d291a8d0bda5c0e3300cda166b871b37e5650e970c`.

`compiled-semantic-proof2.json` in the same preparation directory (SHA256 `c252976336efdcdda4a6c90c568f9a097e630741f0a505adada0eaebfb6cefa6`) preserves all 1,262 previous function instructions, actual attributes and semantic metadata, all 1,422 previous selector globals, and State size/alignment 1200/16. Exactly two functions/selectors are added. Five diagnostic `!srcloc` cookies shift by the exact 927-byte source insertion; the proof lists their values and users. The private module debug-file path changes separately with its source checksum retained. No all-metadata byte-identity claim is made. LLVM documents `!srcloc` as backend-error location metadata: <https://llvm.org/docs/LangRef.html#inline-asm-metadata>.

The first isolated build failed because the decoder body was placed in `Decode.cpp`, where `Instruction` and operand helpers are unavailable. That attempt remains intact. The corrected decoder lives in `Arch.cpp`; only the old false stub is removed. Source inverse proof and the independent source peer bind the exact three changed files. The strict first metadata comparison also remains preserved; no rebuild was made to hide its diagnostic-cookie difference.

Run the existing same-object controller in WSL with a fresh output directory:

```sh
python recomp/whole/test_faddp.py --out recomp/work/faddp-scalar-qualification1 --reference-root /home/user/bunker-recomp/recomp/work/reference-tools/root --toolchain recomp/work/faddp-scalar-preparation2/toolchains/bce34d408b57a2ea-5d2fc4bb5f4c8be4 --support-commit c58d7a149e3e100d91bc513af37fa4f8db9d3208
```

This qualifies the instruction family and its transport only. It does not establish original helper completion, initialization, rendering, or a game frame.
